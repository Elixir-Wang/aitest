import readline from "node:readline";
import { chromium } from "playwright";
import { parsePlaywrightLocatorString, isParseableLocatorString } from "./locator-parser.mjs";
import {
  normalizeUrl,
  stableElementId,
  verifyBestElementSelectors,
} from "./page-facts.mjs";
const [, , startUrl = "about:blank", channel = "", storageStatePath = ""] = process.argv;

const navigationTimeout = Number(process.env.AI_TESTING_EXPLORATION_NAV_TIMEOUT_MS || "20000");
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

let lastObservation = null;
let shuttingDown = false;

try {
  await gotoUrl(startUrl);
  writeLine({ kind: "session_started", status: "started", url: page.url() });
} catch (error) {
  const classified = classifyActionError(error);
  writeLine({
    kind: "session_failed",
    status: "error",
    url: startUrl,
    current_url: page.url(),
    error: classified.error,
    error_type: classified.error_type,
    error_summary: classified.error_summary,
  });
  await shutdown();
  process.exit(1);
}

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
  const accessibilityTree = await collectAccessibilityTree(page);
  const visibleTextBlocks = await collectVisibleTextBlocks(page);
  const elements = [];
  for (const [index, fact] of facts.elements.entries()) {
    const selectors = await verifyBestElementSelectors(page, fact);
    const id = stableElementId(fact, index + 1);
    const element = {
      id,
      role: fact.role,
      role_source: fact.role_source || "",
      name: fact.name,
      text: fact.text,
      context: fact.context || {},
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
    accessibility_tree: accessibilityTree,
    visible_text_blocks: visibleTextBlocks,
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

async function collectAccessibilityTree(browserPage) {
  const snapshot = await browserPage.accessibility?.snapshot?.({ interestingOnly: false }).catch(() => null) || null;
  const nativeTree = flattenAccessibility(snapshot).slice(0, 300);
  if (nativeTree.length) {
    return nativeTree;
  }
  return collectAccessibilityFallback(browserPage);
}

function flattenAccessibility(node, path = "ax", output = []) {
  if (!node || typeof node !== "object") {
    return output;
  }
  const name = cleanText(node.name, 100);
  const role = cleanText(node.role, 40);
  const children = Array.isArray(node.children) ? node.children : [];
  if (name || role) {
    output.push({
      id: path,
      role,
      name,
      level: Number.isFinite(node.level) ? node.level : null,
      checked: typeof node.checked === "boolean" ? node.checked : null,
      disabled: typeof node.disabled === "boolean" ? node.disabled : null,
      expanded: typeof node.expanded === "boolean" ? node.expanded : null,
    });
  }
  for (const [index, child] of children.entries()) {
    if (output.length >= 500) {
      break;
    }
    flattenAccessibility(child, `${path}-${index + 1}`, output);
  }
  return output;
}

async function collectVisibleTextBlocks(browserPage) {
  return browserPage.evaluate(() => {
    const clean = (value, limit = 120) => String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const seen = new Set();
    const blocks = [];
    const addBlock = (value) => {
      const text = clean(value);
      if (!text || seen.has(text)) {
        return;
      }
      seen.add(text);
      blocks.push(text);
    };
    for (const line of String(document.body?.innerText || "").split(/\n+/)) {
      addBlock(line);
      if (blocks.length >= 200) {
        return blocks;
      }
    }
    const selector = "h1,h2,h3,h4,h5,h6,button,label,input,textarea,select,[role],p,span,strong,b,li,[class*='popover'],[class*='popover'] div,[class*='dropdown'],[class*='dropdown'] div";
    for (const el of Array.from(document.body?.querySelectorAll(selector) || [])) {
      if (!visible(el)) {
        continue;
      }
      addBlock(el.innerText || el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.textContent);
      if (blocks.length >= 200) {
        break;
      }
    }
    return blocks;
  }).catch(() => []);
}

async function collectAccessibilityFallback(browserPage) {
  return browserPage.evaluate(() => {
    const clean = (value, limit = 100) => String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const roleOf = (el) => {
      const explicitRole = clean(el.getAttribute("role"), 40);
      if (explicitRole) return explicitRole;
      const tag = el.tagName.toLowerCase();
      if (/^h[1-6]$/.test(tag)) return "heading";
      if (tag === "button") return "button";
      if (tag === "a") return "link";
      if (["input", "textarea"].includes(tag)) return "textbox";
      if (tag === "select") return "combobox";
      return "text";
    };
    const nameOf = (el) => clean(
      el.getAttribute("aria-label")
        || el.getAttribute("placeholder")
        || el.innerText
        || el.textContent
    );
    const selector = "h1,h2,h3,h4,h5,h6,button,a,input,textarea,select,[role],p,span,strong,b,li";
    const seen = new Set();
    const nodes = [];
    for (const el of Array.from(document.body?.querySelectorAll(selector) || [])) {
      if (!visible(el)) continue;
      const role = roleOf(el);
      const name = nameOf(el);
      if (!name) continue;
      const key = `${role}:${name}`;
      if (seen.has(key)) continue;
      seen.add(key);
      nodes.push({
        id: `ax-fallback-${String(nodes.length + 1).padStart(3, "0")}`,
        role,
        name,
        level: role === "heading" ? Number(el.tagName.slice(1)) : null,
        checked: null,
        disabled: el.hasAttribute("disabled") || el.getAttribute("aria-disabled") === "true" || null,
        expanded: null,
      });
      if (nodes.length >= 500) break;
    }
    return nodes;
  }).catch(() => []);
}

async function clickElement(elementIdOrLocator) {
  const raw = String(elementIdOrLocator || "").trim();

  if (isParseableLocatorString(raw)) {
    const liveLocator = parsePlaywrightLocatorString(page, raw);
    if (liveLocator) {
      return clickViaLiveLocator(liveLocator, raw);
    }
  }

  // 不支持的 locator 形式也走结构化错误，避免 Python 侧只能拿到裸字符串
  const before = await currentPageState();
  return await buildActionResult({
    success: false,
    action: "click",
    raw,
    before,
    failure: {
      error_type: "action_failed",
      error: `Unsupported locator: ${raw || ""}`,
      error_summary: `不支持的 locator 写法：${raw || ""}。只支持 getByRole / getByLabel / getByTestId / getByText / getByPlaceholder / getByAltText / getByTitle / page.locator，以及 filter({ hasText })、filter({ has })、容器内 getBy*、and/or 受控链式；不支持 first/nth/evaluate 等任意 JS 链式。`,
    },
    effectiveLocator: null,
  });
}

async function clickViaLiveLocator(liveLocator, rawExpr) {
  const before = await currentPageState();
  const matchCount = await liveLocator.count().catch(() => 0);
  if (matchCount > 1) {
    const visibleMatches = await visibleLocators(liveLocator);
    if (visibleMatches.length !== 1) {
      return await buildActionResult({
        success: false,
        action: "click",
        raw: rawExpr,
        before,
        failure: ambiguousLocatorFailure(rawExpr, matchCount),
        effectiveLocator: null,
      });
    }
    liveLocator = visibleMatches[0];
  }
  const initialVisible = await firstVisibleLocator(liveLocator);
  if (!initialVisible) {
    const failure = classifyActionError(new Error(`Locator did not resolve to a visible element: ${rawExpr}`));
    return await buildActionResult({
      success: false,
      action: "click",
      raw: rawExpr,
      before,
      failure,
      effectiveLocator: null,
    });
  }
  const target = await actionableClickTargetFor(initialVisible);
  if (!target) {
    const failure = classifyActionError(new Error(`Locator did not resolve to a clickable target: ${rawExpr}`));
    return await buildActionResult({
      success: false,
      action: "click",
      raw: rawExpr,
      before,
      failure,
      effectiveLocator: null,
    });
  }
  let clickError = null;
  try {
    await Promise.all([
      page.waitForLoadState("domcontentloaded", { timeout: 3000 }).catch(() => {}),
      target.click({ timeout: 3000 }),
    ]);
  } catch (error) {
    clickError = error;
  }
  if (!clickError) {
    await page.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
    await page.waitForTimeout(250).catch(() => {});
    const after = await currentPageState();
    return await buildActionResult({
      success: true,
      action: "click",
      raw: rawExpr,
      before,
      after,
      effectiveLocator: rawExpr,
    });
  }
  const classified = classifyActionError(clickError);
  if (classified.error_type === "pointer_intercepted") {
    await cleanupTransientOverlays();
    const retryCount = await liveLocator.count().catch(() => 0);
    if (retryCount > 1) {
      return await buildActionResult({
        success: false,
        action: "click",
        raw: rawExpr,
        before,
        failure: ambiguousLocatorFailure(rawExpr, retryCount),
        effectiveLocator: null,
      });
    }
    const retryVisible = await firstVisibleLocator(liveLocator);
    if (retryVisible) {
      const retryTarget = await actionableClickTargetFor(retryVisible);
      let retryError = null;
      try {
        await Promise.all([
          page.waitForLoadState("domcontentloaded", { timeout: 3000 }).catch(() => {}),
          retryTarget.click({ timeout: 3000 }),
        ]);
      } catch (error) {
        retryError = error;
      }
      if (!retryError) {
        await page.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
        await page.waitForTimeout(250).catch(() => {});
        const after = await currentPageState();
        return await buildActionResult({
          success: true,
          action: "click",
          raw: rawExpr,
          before,
          after,
          effectiveLocator: rawExpr,
        });
      }
      return await buildActionResult({
        success: false,
        action: "click",
        raw: rawExpr,
        before,
        failure: classifyActionError(retryError),
        effectiveLocator: null,
      });
    }
  }
  if (classified.error_type === "locator_not_unique" || /resolved to \d+ elements/i.test(classified.error)) {
    return await buildActionResult({
      success: false,
      action: "click",
      raw: rawExpr,
      before,
      failure: classified,
      effectiveLocator: null,
    });
  }
  return await buildActionResult({
    success: false,
    action: "click",
    raw: rawExpr,
    before,
    failure: classified,
    effectiveLocator: null,
  });
}

async function fillField(elementIdOrLocator, value) {
  const raw = String(elementIdOrLocator || "").trim();

  if (isParseableLocatorString(raw)) {
    const liveLocator = parsePlaywrightLocatorString(page, raw);
    if (liveLocator) {
      return fillViaLiveLocator(liveLocator, value, raw);
    }
  }

  const before = await currentPageState();
  return await buildActionResult({
    success: false,
    action: "fill",
    raw,
    before,
    failure: {
      error_type: "action_failed",
      error: `Unsupported locator: ${raw || ""}`,
      error_summary: `不支持的 locator 写法：${raw || ""}。只支持 getByRole / getByLabel / getByTestId / getByText / getByPlaceholder / getByAltText / getByTitle / page.locator，以及 filter({ hasText })、filter({ has })、容器内 getBy*、and/or 受控链式；不支持 first/nth/evaluate 等任意 JS 链式。`,
    },
    effectiveLocator: null,
  });
}

async function fillViaLiveLocator(liveLocator, value, rawExpr) {
  const before = await currentPageState();
  const matchCount = await liveLocator.count().catch(() => 0);
  if (matchCount > 1) {
    const visibleMatches = await visibleLocators(liveLocator);
    if (visibleMatches.length !== 1) {
      return await buildActionResult({
        success: false,
        action: "fill",
        raw: rawExpr,
        before,
        failure: ambiguousLocatorFailure(rawExpr, matchCount),
        effectiveLocator: null,
      });
    }
    liveLocator = visibleMatches[0];
  }
  const target = await firstVisibleLocator(liveLocator);
  if (!target) {
    const failure = classifyActionError(new Error(`Locator did not resolve to a visible element: ${rawExpr}`));
    return await buildActionResult({
      success: false,
      action: "fill",
      raw: rawExpr,
      before,
      failure,
      effectiveLocator: null,
    });
  }
  let fillError = null;
  try {
    await target.fill(value, { timeout: 3000 });
    await page.waitForTimeout(500).catch(() => {});
  } catch (error) {
    fillError = error;
  }
  if (!fillError) {
    const after = await currentPageState();
    return await buildActionResult({
      success: true,
      action: "fill",
      raw: rawExpr,
      before,
      after,
      effectiveLocator: rawExpr,
      valueApplied: true,
    });
  }
  const classified = classifyActionError(fillError);
  if (classified.error_type === "pointer_intercepted") {
    await cleanupTransientOverlays();
    const retryCount = await liveLocator.count().catch(() => 0);
    if (retryCount > 1) {
      return await buildActionResult({
        success: false,
        action: "fill",
        raw: rawExpr,
        before,
        failure: ambiguousLocatorFailure(rawExpr, retryCount),
        effectiveLocator: null,
      });
    }
    const retryTarget = await firstVisibleLocator(liveLocator);
    if (retryTarget) {
      let retryError = null;
      try {
        await retryTarget.fill(value, { timeout: 3000 });
        await page.waitForTimeout(500).catch(() => {});
      } catch (error) {
        retryError = error;
      }
      if (!retryError) {
        const after = await currentPageState();
        return await buildActionResult({
          success: true,
          action: "fill",
          raw: rawExpr,
          before,
          after,
          effectiveLocator: rawExpr,
          valueApplied: true,
        });
      }
      return await buildActionResult({
        success: false,
        action: "fill",
        raw: rawExpr,
        before,
        failure: classifyActionError(retryError),
        effectiveLocator: null,
      });
    }
  }
  if (classified.error_type === "locator_not_unique" || /resolved to \d+ elements/i.test(classified.error)) {
    return await buildActionResult({
      success: false,
      action: "fill",
      raw: rawExpr,
      before,
      failure: classified,
      effectiveLocator: null,
    });
  }
  return await buildActionResult({
    success: false,
    action: "fill",
    raw: rawExpr,
    before,
    failure: classified,
    effectiveLocator: null,
  });
}

/**
 * 统一构造 action_result 协议。
 * 成功：{ success: true, action, raw, before, after, effective_locator, ... }
 * 失败：{ success: false, action, raw, before, failure: { error_type, summary, raw, recovered, recovery_warning }, effective_locator: null }
 */
async function buildActionResult({
  success,
  action,
  raw,
  before,
  after,
  failure = null,
  effectiveLocator = null,
  recovered = false,
  recoveryWarning = "",
  originalFailure = null,
  valueApplied = false,
}) {
  const result = {
    success,
    status: success ? "passed" : "failed",
    action,
    raw,
    effective_locator: effectiveLocator,
    error_type: "",
    error_summary: "",
    error: "",
  };
  if (after) {
    result.before_url = before.url;
    result.after_url = after.url;
    result.before_title = before.title;
    result.after_title = after.title;
    result.url_changed = normalizeUrl(before.url) !== normalizeUrl(after.url);
    result.title_changed = before.title !== after.title;
    result.state_signature_changed = before.signature !== after.signature;
    if (action === "click") {
      result.new_dialog_detected = await hasVisibleDialog(page);
    }
  }
  if (action === "fill") {
    result.value_applied = valueApplied;
  }
  if (!success) {
    result.failure = {
      error_type: failure.error_type || "action_failed",
      summary: failure.error_summary || failure.error || "动作执行失败。",
      raw: failure.error || "动作执行失败。",
      recovered: false,
      recovery_warning: "",
    };
    result.error_type = result.failure.error_type;
    result.error_summary = result.failure.summary;
    result.error = result.failure.raw;
  } else if (recovered) {
    result.failure = {
      error_type: originalFailure?.error_type || "locator_not_unique",
      summary: originalFailure?.error_summary || "严格模式违规。",
      raw: originalFailure?.error || "",
      recovered: true,
      recovery_warning: recoveryWarning,
    };
    result.error_type = result.failure.error_type;
    result.error_summary = result.failure.summary;
  }
  return result;
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

async function actionableClickTargetFor(locator) {
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
  const handle = await locator.first().evaluateHandle((node) => {
    let current = node instanceof Element ? node : null;
    while (current) {
      const role = current.getAttribute("role") || "";
      const className = String(current.getAttribute("class") || "");
      const tag = current.tagName.toLowerCase();
      if (
        tag === "button"
        || tag === "select"
        || role === "button"
        || role === "combobox"
        || current.hasAttribute("tabindex")
        || /\b(ant-select|el-select|uui-select)\b/.test(className)
      ) {
        return current;
      }
      current = current.parentElement;
    }
    return node;
  }).catch(() => null);
  const element = handle?.asElement?.();
  if (!element) {
    await handle?.dispose?.().catch(() => {});
    return locator;
  }
  return element;
}

async function firstVisibleLocator(locator) {
  const visible = await visibleLocators(locator);
  return visible[0] || null;
}

async function visibleLocators(locator) {
  const count = await locator.count().catch(() => 0);
  if (count === 0) return [];
  const limit = Math.min(count, 10);
  const visible = [];
  for (let index = 0; index < limit; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) {
      visible.push(candidate);
    }
  }
  return visible;
}

async function cleanupTransientOverlays() {
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(120).catch(() => {});
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

function ambiguousLocatorFailure(rawExpr, count) {
  return {
    error: `Locator matched ${count} elements: ${rawExpr}`,
    error_type: "locator_not_unique",
    error_summary: `定位器匹配到 ${count} 个元素。请使用 getByRole/getByLabel/getByText 与 filter({ hasText }) 或父级容器链式定位，把范围缩小到唯一元素。`,
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
    signature: signatureFor({ url: normalizeUrl(page.url()), title, text: bodyText.slice(0, 800) }),
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
      "[class*='option' i]",
      "[class*='item' i]",
      "[class*='card' i]",
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
      const cursor = window.getComputedStyle(el).cursor;
      return Boolean(
        el.getAttribute("onclick")
          || el.getAttribute("role")
          || (!Number.isNaN(tabIndex) && tabIndex >= 0)
          || cursor === "pointer"
          || /\b(menu-item|menu-content|cursor-pointer|more-btn)\b/.test(className)
          || /(?:^|[-_\s])(option|item|card)(?:$|[-_\s])/i.test(className)
      );
    };
    const roleOf = (el) => {
      const tagName = el.tagName.toLowerCase();
      const explicitRole = el.getAttribute("role");
      if (explicitRole) return { role: explicitRole, roleSource: "explicit" };
      if (tagName === "a") return { role: "link", roleSource: "native" };
      if (tagName === "button") return { role: "button", roleSource: "native" };
      if (tagName === "textarea") return { role: "textbox", roleSource: "native" };
      if (tagName === "select") return { role: "combobox", roleSource: "native" };
      if (tagName === "input") {
        const inputType = (el.getAttribute("type") || "text").toLowerCase();
        if (inputType === "checkbox") return { role: "checkbox", roleSource: "native" };
        if (inputType === "radio") return { role: "radio", roleSource: "native" };
        if (inputType === "button" || inputType === "submit" || inputType === "reset") return { role: "button", roleSource: "native" };
        return { role: "textbox", roleSource: "native" };
      }
      if (hasClickableHint(el)) return { role: "clickable", roleSource: "inferred" };
      return { role: tagName, roleSource: "native" };
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
    const contextOf = (el, ownName = "") => {
      const container = el.closest('article,[role="listitem"],[data-testid*="card" i],[data-test-id*="card" i],[data-test*="card" i],[class*="card" i]');
      if (!container || container === el) return {};
      const heading = container.querySelector('h1,h2,h3,h4,h5,h6,[role="heading"]');
      const titleCandidates = [
        heading?.textContent,
        ...Array.from(container.querySelectorAll("h1,h2,h3,h4,h5,h6,[role='heading'],strong,b"))
          .map((node) => node.textContent),
      ];
      const texts = Array.from(container.querySelectorAll("*"))
        .filter(visible)
        .map((node) => clean(node.textContent, 80))
        .filter((text) => text && text !== ownName && text.length <= 80 && !/^(已发布|未发布|分析|使用|对话历史|更多|编辑|删除|\.\.\.)$/.test(text));
      const containerName = firstMeaningful([...titleCandidates, ...texts]);
      if (!containerName || containerName === ownName) return {};
      return {
        container_role: container.getAttribute("role") || container.tagName.toLowerCase(),
        container_name: containerName,
        container_test_id: container.getAttribute("data-testid") || container.getAttribute("data-test-id") || container.getAttribute("data-test") || "",
        stable_text: containerName,
      };
    };
    const pointerCandidateSelector = "div,span,li,article,section";
    const explicitCandidates = Array.from(document.querySelectorAll(interactiveSelector));
    const explicitSet = new Set(explicitCandidates);
    const pointerCandidates = Array.from(document.querySelectorAll(pointerCandidateSelector))
      .filter((el) => !explicitSet.has(el))
      .filter(visible)
      .filter((el) => hasClickableHint(el))
      .filter((el) => clean(el.innerText || el.textContent, 160))
      .slice(0, 40);
  // 祖先链：截取 element → body 路径中最有结构意义的中间层（最多 5 层）
  // 用于让 LLM 直接从 DOM 结构判断元素所在上下文，不再依赖 JS 枚举 dialog 容器列表
  // 始终收集（role 或 tagName 作为标识），让 LLM 看到完整的 DOM 路径来消歧
  const ancestorChainOf = (el) => {
    const chain = [];
    let current = el.parentElement;
    while (current && current !== document.documentElement) {
      const tagName = current.tagName ? current.tagName.toLowerCase() : "";
      const role = current.getAttribute("role") || "";
      const name = labelOf(current);
      // role 属性优先，否则用 tagName；name 可能为空（div 等容器）
      chain.unshift({
        role: role || tagName,
        name: name || "",
      });
      if (chain.length >= 5) break;
      current = current.parentElement;
    }
    console.log(`[DEBUG ancestorChainOf] tag=${el.tagName} parentEl=${!!el.parentElement} chainLen=${chain.length} body=${!!document.body} docElem=${!!document.documentElement}`);
    return chain;
  };

  const elementFacts = [...explicitCandidates, ...pointerCandidates]
    .filter(visible)
    .map((el, index) => {
      const { role, roleSource } = roleOf(el);
      const tagName = el.tagName.toLowerCase();
      const name = labelOf(el);
      const actionType = ["input", "textarea", "select"].includes(tagName) && !["button", "checkbox", "radio"].includes(role) ? "fill" : "click";
      const nativeInteractive = ["a", "button", "input", "textarea", "select"].includes(tagName);
      const clickHint = hasClickableHint(el);
      const ancestor_chain = ancestorChainOf(el);
      return {
        index,
        role,
        role_source: roleSource,
        name,
        label: explicitLabelOf(el),
        testId: el.getAttribute("data-testid") || el.getAttribute("data-test-id") || el.getAttribute("data-test") || "",
        text: clean(el.innerText || el.textContent),
        css: cssSelectorOf(el),
        context: contextOf(el, name),
        action_type: actionType,
        href: el.href || "",
        enabled: !el.disabled && el.getAttribute("aria-disabled") !== "true",
        interactive_hint: nativeInteractive || clickHint,
        visible: true,
        ancestor_chain: ancestor_chain,
      };
    })
    .filter((item) => {
      if (item.action_type === "fill") return true;
      if (!item.interactive_hint) return false;
      const hasStableName = Boolean(item.name || item.text || item.testId || item.href);
      if (!hasStableName) return false;
      return item.name.length <= 120 || item.role !== "button";
    })
    .slice(0, 80);
    const links = elementFacts.filter((item) => item.href).map((item) => ({
      name: item.name,
      href: item.href,
      text: item.text,
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
      body_text: clean(document.body?.innerText || "", 800),
      elements: elementFacts,
      links,
      forms,
      tables,
      breadcrumbs,
    };
  });
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

function signatureFor(payload) {
  const value = JSON.stringify(payload);
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) + hash) ^ value.charCodeAt(index);
  }
  return `state-${(hash >>> 0).toString(16)}`;
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
