import readline from "node:readline";
import { chromium } from "playwright";
import { buildSelectorCandidates } from "./selector-generator.mjs";
import { locatorForCandidate, verifySelectorCandidate } from "./selector-validator.mjs";

const [, , startUrl = "about:blank", channel = "", storageStatePath = ""] = process.argv;

const navigationTimeout = Number(process.env.AI_TESTING_EXPLORATION_NAV_TIMEOUT_MS || "10000");
const browser = await chromium.launch({
  channel: channel || undefined,
  headless: true,
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  ignoreHTTPSErrors: true,
  ...(storageStatePath ? { storageState: storageStatePath } : {}),
});
const page = await context.newPage();
page.setDefaultTimeout(navigationTimeout);
page.setDefaultNavigationTimeout(navigationTimeout);

let lastElements = new Map();
let lastObservation = null;
let shuttingDown = false;

await gotoUrl(startUrl);
writeLine({ kind: "session_started", status: "started", url: page.url() });

const rl = readline.createInterface({
  input: process.stdin,
  crlfDelay: Infinity,
});

rl.on("line", async (line) => {
  const trimmed = line.trim();
  if (!trimmed) {
    return;
  }
  let command;
  try {
    command = JSON.parse(trimmed);
  } catch (error) {
    writeLine({ id: "", status: "error", error: `Invalid JSON command: ${String(error?.message || error)}` });
    return;
  }
  const id = String(command.id || "");
  try {
    const result = await handleCommand(command);
    writeLine({ id, status: "ok", result });
  } catch (error) {
    writeLine({ id, status: "error", error: String(error?.message || error).slice(0, 1000) });
  }
});

rl.on("close", async () => {
  await shutdown();
});

process.on("SIGTERM", async () => {
  await shutdown();
  process.exit(0);
});

process.on("SIGINT", async () => {
  await shutdown();
  process.exit(0);
});

async function handleCommand(command) {
  const type = String(command.type || "");
  if (type === "observe") {
    return observePage();
  }
  if (type === "click") {
    return clickElement(command.element_id || command.target_element_id);
  }
  if (type === "fill") {
    return fillField(command.element_id || command.target_element_id, String(command.value || ""));
  }
  if (type === "go_back") {
    return goBack();
  }
  if (type === "close_modal") {
    return closeModal();
  }
  if (type === "wait") {
    await page.waitForTimeout(Math.min(Math.max(Number(command.ms || 500), 100), 3000));
    return { status: "passed", url: page.url() };
  }
  if (type === "navigate") {
    await gotoUrl(String(command.url || startUrl));
    return { status: "passed", url: page.url() };
  }
  if (type === "finish") {
    await shutdown();
    return { status: "closed" };
  }
  throw new Error(`Unsupported browser-session command: ${type || "unknown"}`);
}

async function gotoUrl(url) {
  await page.goto(url || "about:blank", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: navigationTimeout }).catch(() => {});
}

async function observePage() {
  const facts = await collectDomFacts(page);
  const elements = [];
  for (const [index, fact] of facts.elements.entries()) {
    const selectors = await verifyBestElementSelectors(page, fact);
    const id = stableElementId(fact, index + 1);
    const element = {
      id,
      role: fact.role,
      name: fact.name,
      text: fact.text,
      action_type: fact.action_type,
      enabled: fact.enabled,
      visible: fact.visible,
      href: fact.href || "",
      risk_hint: riskHintFor(fact),
      primary_selector: selectors.primary_selector || null,
      fallback_selector: selectors.fallback_selector || null,
    };
    elements.push(element);
  }
  lastElements = new Map(elements.map((element) => [element.id, element]));
  const textSummary = summarizeObservation(facts, elements);
  const observation = {
    url: page.url(),
    normalized_url: normalizeUrl(page.url()),
    title: facts.title || page.url(),
    state_signature: signatureFor({
      url: normalizeUrl(page.url()),
      title: facts.title,
      text: facts.body_text,
      elements: elements.map((element) => `${element.role}:${element.name}:${element.action_type}`).join("|"),
    }),
    page_text_summary: textSummary,
    elements,
    forms: facts.forms,
    dialogs: facts.dialogs,
    tables: facts.tables,
    links: facts.links,
    breadcrumbs: facts.breadcrumbs,
    evidence: {},
  };
  lastObservation = observation;
  return observation;
}

async function clickElement(elementId) {
  const element = lastElements.get(String(elementId || ""));
  if (!element) {
    throw new Error(`Unknown element id: ${elementId || ""}`);
  }
  const before = await currentPageState();
  await cleanupTransientOverlays();
  const attempts = [];
  let coordinateFallback = null;
  for (const selector of selectorCandidatesFor(element)) {
    try {
      const locator = await actionableLocatorFor(page, locatorForCandidate(page, selector));
      const target = await firstVisibleLocator(locator);
      if (!target) {
        throw new Error("Locator did not resolve to a visible element.");
      }
      coordinateFallback = coordinateFallback || target;
      await Promise.all([
        page.waitForLoadState("domcontentloaded", { timeout: 3000 }).catch(() => {}),
        target.click({ timeout: 3000 }),
      ]);
      return passedActionResult(before, {
        element,
        actionType: "click",
        selector,
        attempts,
      });
    } catch (error) {
      attempts.push(actionErrorAttempt(selector, error));
      if (classifyActionError(error).error_type === "pointer_intercepted") {
        await cleanupTransientOverlays();
      }
    }
  }
  if (coordinateFallback) {
    try {
      const box = await coordinateFallback.boundingBox({ timeout: 1000 }).catch(() => null);
      if (box) {
        await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
        return passedActionResult(before, {
          element,
          actionType: "click",
          selector: { code: "coordinate_fallback", kind: "coordinate" },
          attempts,
        });
      }
    } catch (error) {
      attempts.push(actionErrorAttempt({ code: "coordinate_fallback", kind: "coordinate" }, error));
    }
  }
  return failedActionResult(before, element, "click", attempts);
}

async function fillField(elementId, value) {
  const element = lastElements.get(String(elementId || ""));
  if (!element) {
    throw new Error(`Unknown element id: ${elementId || ""}`);
  }
  const before = await currentPageState();
  await cleanupTransientOverlays();
  const attempts = [];
  for (const selector of selectorCandidatesFor(element)) {
    try {
      const locator = await actionableLocatorFor(page, locatorForCandidate(page, selector), { preserveInput: true });
      const target = await firstVisibleLocator(locator);
      if (!target) {
        throw new Error("Locator did not resolve to a visible element.");
      }
      await target.fill(value, { timeout: 3000 });
      await page.waitForTimeout(500).catch(() => {});
      const after = await currentPageState();
      return {
        status: "passed",
        element_id: element.id,
        element_name: element.name,
        action_type: "fill",
        selector: selector.code || "",
        selector_kind: selector.kind || "",
        before_url: before.url,
        after_url: after.url,
        value_applied: true,
        state_signature_changed: before.signature !== after.signature,
        result_count_changed: before.signature !== after.signature,
        attempts,
        error: "",
        error_type: "",
        error_summary: "",
      };
    } catch (error) {
      attempts.push(actionErrorAttempt(selector, error));
      if (classifyActionError(error).error_type === "pointer_intercepted") {
        await cleanupTransientOverlays();
      }
    }
  }
  return failedActionResult(before, element, "fill", attempts);
}

async function goBack() {
  const before = await currentPageState();
  await page.goBack({ waitUntil: "domcontentloaded", timeout: navigationTimeout }).catch(() => null);
  await page.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
  const after = await currentPageState();
  return {
    status: "passed",
    before_url: before.url,
    after_url: after.url,
    url_changed: normalizeUrl(before.url) !== normalizeUrl(after.url),
    state_signature_changed: before.signature !== after.signature,
    error: "",
  };
}

async function closeModal() {
  const before = await currentPageState();
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(250).catch(() => {});
  const after = await currentPageState();
  return {
    status: "passed",
    before_url: before.url,
    after_url: after.url,
    state_signature_changed: before.signature !== after.signature,
    error: "",
  };
}

function selectorCandidatesFor(element) {
  const candidates = [
    element.primary_selector,
    element.fallback_selector,
    ...buildSelectorCandidates(element),
  ].filter(Boolean);
  const seen = new Set();
  const unique = [];
  for (const candidate of candidates) {
    const key = candidate.code || JSON.stringify(candidate);
    if (!key || seen.has(key)) {
      continue;
    }
    seen.add(key);
    unique.push(candidate);
  }
  return unique;
}

async function actionableLocatorFor(browserPage, locator, options = {}) {
  if (options.preserveInput) {
    return locator;
  }
  const needsAncestor = await locator.first().evaluate((node) => {
    const element = node instanceof Element ? node : null;
    if (!element) return false;
    const tag = element.tagName.toLowerCase();
    const role = element.getAttribute("role") || "";
    const readonly = element.hasAttribute("readonly") || element.getAttribute("aria-readonly") === "true";
    return (tag === "input" && readonly) || role === "combobox";
  }).catch(() => false);
  if (!needsAncestor) {
    return locator;
  }
  return locator.locator(
    "xpath=ancestor-or-self::*[self::button or self::select or @role='button' or @role='combobox' or @tabindex or contains(concat(' ', normalize-space(@class), ' '), ' ant-select ') or contains(concat(' ', normalize-space(@class), ' '), ' el-select ') or contains(concat(' ', normalize-space(@class), ' '), ' uui-select ')][1]"
  );
}

async function firstVisibleLocator(locator) {
  const count = await locator.count().catch(() => 0);
  if (count === 0) {
    return null;
  }
  const limit = Math.min(count, 10);
  for (let index = 0; index < limit; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) {
      return candidate;
    }
  }
  return null;
}

async function cleanupTransientOverlays() {
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(120).catch(() => {});
}

async function passedActionResult(before, { element, actionType, selector, attempts }) {
  await page.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
  await page.waitForTimeout(250).catch(() => {});
  const after = await currentPageState();
  return {
    status: "passed",
    element_id: element.id,
    element_name: element.name,
    action_type: actionType,
    selector: selector.code || "",
    selector_kind: selector.kind || "",
    before_url: before.url,
    after_url: after.url,
    before_title: before.title,
    after_title: after.title,
    url_changed: normalizeUrl(before.url) !== normalizeUrl(after.url),
    title_changed: before.title !== after.title,
    state_signature_changed: before.signature !== after.signature,
    new_dialog_detected: await hasVisibleDialog(page),
    attempts,
    error: "",
    error_type: "",
    error_summary: "",
  };
}

function failedActionResult(before, element, actionType, attempts) {
  const last = attempts.at(-1) || {};
  return {
    status: "failed",
    element_id: element.id,
    element_name: element.name,
    action_type: actionType,
    before_url: before.url,
    after_url: page.url(),
    state_signature_changed: false,
    attempts,
    error: last.error || "No executable selector candidate succeeded.",
    error_type: last.error_type || "action_failed",
    error_summary: last.error_summary || "动作执行失败，所有 selector 候选均未成功。",
  };
}

function actionErrorAttempt(selector, error) {
  const classified = classifyActionError(error);
  return {
    selector: selector?.code || "",
    selector_kind: selector?.kind || "",
    ...classified,
  };
}

function classifyActionError(error) {
  const message = String(error?.message || error || "");
  const cleanMessage = message.replace(/\u001b\[[0-9;]*m/g, "");
  if (/intercepts pointer events/i.test(cleanMessage)) {
    return {
      error: cleanMessage,
      error_type: "pointer_intercepted",
      error_summary: compactErrorLine(cleanMessage, /intercepts pointer events/i) || "目标元素被浮层或其他元素遮挡。",
    };
  }
  if (/strict mode violation|resolved to \d+ elements/i.test(cleanMessage)) {
    return {
      error: cleanMessage,
      error_type: "locator_not_unique",
      error_summary: compactErrorLine(cleanMessage, /strict mode violation|resolved to \d+ elements/i) || "定位器匹配到多个元素。",
    };
  }
  if (/Timeout \d+ms exceeded|timed out/i.test(cleanMessage)) {
    return {
      error: cleanMessage,
      error_type: "locator_timeout",
      error_summary: compactErrorLine(cleanMessage, /waiting for|Timeout \d+ms exceeded/i) || "等待目标元素可执行超时。",
    };
  }
  if (/not visible|did not resolve to a visible element/i.test(cleanMessage)) {
    return {
      error: cleanMessage,
      error_type: "not_visible",
      error_summary: "定位器没有解析到可见元素。",
    };
  }
  return {
    error: cleanMessage,
    error_type: "action_failed",
    error_summary: compactErrorLine(cleanMessage) || "动作执行失败。",
  };
}

function compactErrorLine(message, pattern = null) {
  const lines = String(message || "").split(/\n/).map((line) => line.trim()).filter(Boolean);
  const selected = pattern ? lines.find((line) => pattern.test(line)) : lines[0];
  return String(selected || lines[0] || "").replace(/\s+/g, " ").slice(0, 220);
}

async function currentPageState() {
  const title = await page.title().catch(() => "");
  const bodyText = await page.locator("body").innerText({ timeout: 1500 }).catch(() => "");
  return {
    url: page.url(),
    title,
    signature: signatureFor({ url: normalizeUrl(page.url()), title, text: bodyText.slice(0, 2000) }),
  };
}

async function collectDomFacts(browserPage) {
  return browserPage.evaluate(() => {
    const clean = (value, limit = 160) => String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
    const interactiveSelector = [
      "a",
      "button",
      "input",
      "textarea",
      "select",
      "[role='button']",
      "[role='link']",
      "[role='tab']",
      "[role='menuitem']",
      "[role='option']",
      "[role='checkbox']",
      "[role='radio']",
      "[onclick]",
      "[tabindex]",
      "[class*='menu-item']",
      "[class*='menu-content']",
      "[class*='cursor-pointer']",
      "[class*='more-btn']",
    ].join(",");
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const firstMeaningful = (values) => {
      const cleaned = values.map((value) => clean(value)).filter(Boolean);
      return cleaned.find((value) => !/^(a|button|div|i|img|input|label|li|select|span|svg|textarea)$/i.test(value)) || cleaned[0] || "";
    };
    const textByIds = (ids) => ids
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent || "")
      .join(" ");
    const explicitLabelOf = (el) => {
      const id = el.getAttribute("id");
      if (id) {
        const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (label?.textContent?.trim()) return clean(label.textContent);
      }
      const wrappedLabel = el.closest("label");
      return wrappedLabel?.textContent?.trim() ? clean(wrappedLabel.textContent) : "";
    };
    const labelOf = (el) => firstMeaningful([
      textByIds(el.getAttribute("aria-labelledby") || ""),
      el.getAttribute("aria-label"),
      el.getAttribute("title"),
      el.getAttribute("placeholder"),
      explicitLabelOf(el),
      el.innerText || el.textContent,
      el.getAttribute("value"),
      el.getAttribute("name"),
      el.getAttribute("id"),
    ]);
    const hasClickableHint = (el) => {
      const className = String(el.getAttribute("class") || "");
      const tabIndex = Number(el.getAttribute("tabindex"));
      return Boolean(
        el.getAttribute("onclick")
          || el.getAttribute("role")
          || (!Number.isNaN(tabIndex) && tabIndex >= 0)
          || /\b(menu-item|menu-content|cursor-pointer|more-btn)\b/.test(className)
      );
    };
    const roleOf = (el) => {
      const tagName = el.tagName.toLowerCase();
      const explicitRole = el.getAttribute("role");
      if (explicitRole) return explicitRole;
      if (tagName === "a") return "link";
      if (tagName === "button") return "button";
      if (tagName === "textarea") return "textbox";
      if (tagName === "select") return "combobox";
      if (tagName === "input") {
        const inputType = (el.getAttribute("type") || "text").toLowerCase();
        if (inputType === "checkbox") return "checkbox";
        if (inputType === "radio") return "radio";
        if (inputType === "button" || inputType === "submit" || inputType === "reset") return "button";
        return "textbox";
      }
      if (hasClickableHint(el)) return "button";
      return tagName;
    };
    const uniqueCssPathOf = (el) => {
      const parts = [];
      let current = el;
      while (current?.nodeType === Node.ELEMENT_NODE && current !== document.documentElement) {
        const tag = current.tagName.toLowerCase();
        const parent = current.parentElement;
        if (!parent) break;
        const sameTagSiblings = Array.from(parent.children).filter((child) => child.tagName === current.tagName);
        const index = sameTagSiblings.indexOf(current) + 1;
        parts.unshift(sameTagSiblings.length > 1 ? `${tag}:nth-of-type(${index})` : tag);
        const selector = parts.join(" > ");
        if (document.querySelectorAll(selector).length === 1) return selector;
        current = parent;
      }
      return parts.join(" > ");
    };
    const cssSelectorOf = (el) => {
      const testId = el.getAttribute("data-testid") || el.getAttribute("data-test-id") || el.getAttribute("data-test");
      if (testId) return `[data-testid="${CSS.escape(testId)}"]`;
      const id = el.getAttribute("id");
      if (id) return `#${CSS.escape(id)}`;
      const name = el.getAttribute("name");
      if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
      return uniqueCssPathOf(el);
    };
    const elementFacts = Array.from(document.querySelectorAll(interactiveSelector))
      .filter(visible)
      .map((el, index) => {
        const role = roleOf(el);
        const tagName = el.tagName.toLowerCase();
        const name = labelOf(el);
        const actionType = ["input", "textarea", "select"].includes(tagName) && !["button", "checkbox", "radio"].includes(role) ? "fill" : "click";
        return {
          index,
          role,
          name,
          label: explicitLabelOf(el),
          testId: el.getAttribute("data-testid") || el.getAttribute("data-test-id") || el.getAttribute("data-test") || "",
          text: clean(el.innerText || el.textContent),
          css: cssSelectorOf(el),
          action_type: actionType,
          href: el.href || "",
          enabled: !el.disabled && el.getAttribute("aria-disabled") !== "true",
          visible: true,
        };
      })
      .filter((item) => {
        if (item.action_type === "fill") return true;
        const hasStableName = Boolean(item.name || item.text || item.testId || item.href);
        if (!hasStableName) return false;
        return item.name.length <= 120 || item.role !== "button";
      })
      .slice(0, 120);
    const links = elementFacts.filter((item) => item.href).map((item) => ({
      name: item.name,
      href: item.href,
      text: item.text,
    }));
    const dialogs = Array.from(document.querySelectorAll("[role='dialog'],dialog,.modal,.ant-modal,.el-dialog"))
      .filter(visible)
      .slice(0, 20)
      .map((dialog, index) => ({
        id: dialog.getAttribute("id") || `dialog-${String(index + 1).padStart(3, "0")}`,
        title: labelOf(dialog),
        role: dialog.getAttribute("role") || dialog.tagName.toLowerCase(),
      }));
    const forms = Array.from(document.querySelectorAll("form")).slice(0, 20).map((form, index) => ({
      id: `form-${String(index + 1).padStart(3, "0")}`,
      name: labelOf(form),
      fields: Array.from(form.querySelectorAll("input,textarea,select")).slice(0, 80).map((field) => ({
        name: labelOf(field),
        input_type: field.getAttribute("type") || field.tagName.toLowerCase(),
        required: Boolean(field.required || field.getAttribute("aria-required") === "true"),
      })),
    }));
    const tables = Array.from(document.querySelectorAll("table")).slice(0, 20).map((table, index) => ({
      id: `table-${String(index + 1).padStart(3, "0")}`,
      name: labelOf(table),
      columns: Array.from(table.querySelectorAll("th")).slice(0, 40).map((th) => labelOf(th)).filter(Boolean),
      row_count: table.querySelectorAll("tbody tr").length,
    }));
    const breadcrumbs = Array.from(document.querySelectorAll("[aria-label*='breadcrumb' i] a,.breadcrumb a,.breadcrumbs a"))
      .filter(visible)
      .slice(0, 20)
      .map((item) => clean(item.textContent));
    return {
      title: document.title || location.pathname || location.href,
      body_text: clean(document.body?.innerText || "", 3000),
      elements: elementFacts,
      links,
      forms,
      dialogs,
      tables,
      breadcrumbs,
    };
  });
}

async function verifyBestElementSelectors(browserPage, element) {
  const candidates = buildSelectorCandidates(element);
  if (!candidates.length) {
    return {};
  }
  const verified = [];
  for (const candidate of candidates) {
    verified.push(await verifySelectorCandidate(browserPage, candidate));
  }
  const usable = verified.filter(usableSelector);
  const primary = usable[0] || verified[0];
  const fallback = usable.find((candidate) => candidate.code !== primary?.code)
    || verified.find((candidate) => candidate.code !== primary?.code)
    || null;
  return {
    primary_selector: primary || null,
    fallback_selector: fallback,
  };
}

function usableSelector(selector) {
  return Boolean(selector?.verification?.checked && selector.verification.unique && selector.verification.visible);
}

async function hasVisibleDialog(browserPage) {
  return browserPage.evaluate(() => {
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    return Array.from(document.querySelectorAll("[role='dialog'],dialog,.modal,.ant-modal,.el-dialog")).some(visible);
  }).catch(() => false);
}

function riskHintFor(element) {
  const actionType = String(element.action_type || "").toLowerCase();
  const text = `${element.name || ""} ${element.text || ""} ${element.role || ""}`.toLowerCase();
  if (/删除|移除|发布|审批|支付|发送|权限|禁用|启用|清空|重置|覆盖|注销|退出登录|delete|remove|publish|approve|pay|send|permission|disable|enable|reset|clear|logout/i.test(text)) {
    return "destructive";
  }
  if (actionType === "fill" && /搜索|筛选|过滤|查询|search|filter|query/i.test(text)) {
    return "safe";
  }
  if (actionType === "fill") {
    return "guarded";
  }
  if (/新建|创建|编辑|修改|上传|导入|保存|草稿|提交|复制|导出|批量|授权|绑定|新增|create|new|edit|update|upload|import|save|submit|copy|export|batch/i.test(text)) {
    return "guarded";
  }
  return "safe";
}

function summarizeObservation(facts, elements) {
  const sampleNames = elements.map((element) => element.name).filter(Boolean).slice(0, 8).join("、");
  const textExcerpt = String(facts.body_text || "").slice(0, 180);
  return `标题：${facts.title || "-"}。可交互元素：${elements.length}。链接：${facts.links.length}。表单：${facts.forms.length}。表格：${facts.tables.length}。主要元素：${sampleNames || "-"}。正文：${textExcerpt || "-"}。`;
}

function stableElementId(element, index) {
  const base = slugify(`${element.role || element.action_type || "element"}-${element.name || element.text || index}`);
  return `${base || "element"}-${String(index).padStart(3, "0")}`;
}

function signatureFor(payload) {
  const value = JSON.stringify(payload);
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) + hash) ^ value.charCodeAt(index);
  }
  return `state-${(hash >>> 0).toString(16)}`;
}

function normalizeUrl(value) {
  try {
    const url = new URL(value);
    url.hash = "";
    if (url.pathname.endsWith("/") && url.pathname !== "/") {
      url.pathname = url.pathname.slice(0, -1);
    }
    return url.href;
  } catch {
    return String(value || "");
  }
}

function slugify(value) {
  return String(value || "element")
    .trim()
    .toLowerCase()
    .replace(/[^a-zA-Z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "element";
}

function writeLine(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

async function shutdown() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  rl.close();
  await browser.close().catch(() => {});
}
