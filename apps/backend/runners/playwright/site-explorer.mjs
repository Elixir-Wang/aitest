import { chromium } from "playwright";

const [, , startUrl, artifactRoot, channel = "", forbiddenInput = ""] = process.argv;

if (!startUrl || !artifactRoot) {
  console.error("Usage: node site-explorer.mjs <startUrl> <artifactRoot> [channel]");
  process.exit(2);
}

const maxPages = Number(process.env.AI_TESTING_EXPLORATION_MAX_PAGES || "50");
const maxActions = Number(process.env.AI_TESTING_EXPLORATION_MAX_ACTIONS || "1000");
const navigationTimeout = Number(process.env.AI_TESTING_EXPLORATION_NAV_TIMEOUT_MS || "10000");

const browser = await chromium.launch({
  channel: channel || undefined,
  headless: true,
});

const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  ignoreHTTPSErrors: true,
});
const page = await context.newPage();
page.setDefaultTimeout(navigationTimeout);
page.setDefaultNavigationTimeout(navigationTimeout);

const start = new URL(startUrl);
const visited = new Set();
const queued = [start.href];
const pages = [];
const blockers = [];
const graphNodes = [];
const graphEdges = [];
const logLines = [];
const forbiddenTerms = forbiddenInput
  .split(/[\n,，;；]+/)
  .map((item) => item.trim().toLowerCase())
  .filter(Boolean);
let actionCount = 0;

try {
  while (queued.length > 0 && pages.length < maxPages && actionCount < maxActions) {
    const targetUrl = queued.shift();
    if (!targetUrl || visited.has(normalizeUrl(targetUrl))) {
      continue;
    }
    visited.add(normalizeUrl(targetUrl));

    try {
      await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: navigationTimeout }).catch(() => {});
    } catch (error) {
      blockers.push({
        id: makeId("blocker", blockers.length + 1),
        type: "navigation_failed",
        page: targetUrl,
        reason: String(error?.message || error),
        severity: "blocking",
        suggested_action: "检查页面路由、网络连通性、登录状态或证书配置后重试。",
      });
      logLines.push(`BLOCKED navigation_failed ${targetUrl}`);
      continue;
    }

    const facts = await collectAccessibilityFacts(page);
    const pageId = makeId("page", pages.length + 1);
    const pageDoc = buildPageDoc(pageId, facts, targetUrl, blockers);
    pages.push(pageDoc);
    graphNodes.push({
      id: pageId,
      title: pageDoc.page.title,
      url: pageDoc.page.url,
      type: pageDoc.page.page_type,
      module: pageDoc.page.module,
    });
    logLines.push(`PAGE ${pageId} ${pageDoc.page.url}`);

    for (const link of facts.links) {
      const href = sameOriginHref(link.href, start);
      if (!href) {
        graphEdges.push({
          id: makeId("edge", graphEdges.length + 1),
          from: pageId,
          to: link.href,
          type: "external_link",
          action: `发现外链 ${link.name || link.href}`,
          element: link,
          result: { url_changed: false, visited: false, skipped: true },
        });
        continue;
      }
      if (visited.has(normalizeUrl(href)) || queued.some((item) => normalizeUrl(item) === normalizeUrl(href))) {
        continue;
      }
      if (isForbidden(`${link.name} ${href}`)) {
        blockers.push({
          id: makeId("blocker", blockers.length + 1),
          type: "forbidden_path",
          page: pageDoc.page.url,
          action: link.name || href,
          reason: `命中禁止路径，已跳过：${link.name || href}`,
          severity: "warning",
          suggested_action: "如需覆盖该功能，请在安全测试环境中调整禁止路径后重新探索。",
        });
        logLines.push(`SKIPPED forbidden_path ${link.name || href}`);
        continue;
      }
      queued.push(href);
      graphEdges.push({
        id: makeId("edge", graphEdges.length + 1),
        from: pageId,
        to: href,
        type: "navigation",
        action: `访问 ${link.name || href}`,
        element: link,
        result: { url_changed: true, target_page_detected: true },
      });
      actionCount += 1;
    }

    for (const action of facts.actions) {
      if (actionCount >= maxActions) {
        break;
      }
      if (!canInteract(action)) {
        continue;
      }
      if (isForbidden(`${action.name} ${action.locator_hint || ""}`)) {
        blockers.push({
          id: makeId("blocker", blockers.length + 1),
          type: "forbidden_path",
          page: pageDoc.page.url,
          action: action.name || action.locator_hint,
          reason: `命中禁止路径，已跳过：${action.name || action.locator_hint}`,
          severity: "warning",
          suggested_action: "如需覆盖该功能，请在安全测试环境中调整禁止路径后重新探索。",
        });
        logLines.push(`SKIPPED forbidden_path ${action.name || action.locator_hint}`);
        continue;
      }
      graphEdges.push({
        id: makeId("edge", graphEdges.length + 1),
        from: pageId,
        to: pageId,
        type: action.action_type === "fill" ? "submit" : "state_change",
        action: action.name || action.locator_hint || "action",
        element: action,
        result: { url_changed: false, target_page_detected: false },
      });
      actionCount += 1;
    }
  }

  const summary = `已探索 ${pages.length} 个页面，识别 ${factsCount(pages)} 个可交互元素，记录 ${blockers.length} 个阻塞项。`;
  console.log(
    JSON.stringify({
      status: pages.length > 0 ? (blockers.length > 0 ? "partial" : "completed") : "blocked",
      summary,
      pages,
      graph: {
        nodes: graphNodes,
        edges: graphEdges,
        paths: [],
      },
      blockers,
      log_lines: logLines.length > 0 ? logLines : ["INFO run_completed"],
      action_count: actionCount,
      field_count: pages.reduce((count, item) => count + (item.actions || []).filter((action) => action.action_type === "fill").length, 0),
      state_transition_count: Math.max(0, pages.length - 1),
      discovery: {
        queued_count: queued.length + visited.size,
        visited_count: visited.size,
        discovered_link_count: graphEdges.filter((edge) => edge.type === "navigation").length,
        skipped_link_count: blockers.filter((item) => item.type === "forbidden_path").length,
        clickable_count: pages.reduce((count, item) => count + item.actions.length, 0),
        input_count: pages.reduce((count, item) => count + item.actions.filter((action) => action.action_type === "fill").length, 0),
        same_origin_link_count: graphEdges.filter((edge) => edge.type === "navigation").length,
        reason_if_stopped: queued.length === 0 ? "已处理发现的入口，探索队列为空。" : "",
      },
    }),
  );
} finally {
  await browser.close();
}

async function collectAccessibilityFacts(browserPage) {
  const snapshot = await browserPage.accessibility.snapshot({ interestingOnly: false }).catch(() => null);
  const accessibilityNodes = flattenAccessibility(snapshot).slice(0, 300);
  const domFacts = await collectDomFacts(browserPage);
  const actions = accessibilityNodes
    .filter((node) => ["button", "link", "textbox", "combobox", "checkbox", "radio", "tab", "menuitem"].includes(node.role))
    .map((node, index) => ({
      id: makeId("action", index + 1),
      role: node.role,
      name: node.name || "",
      locator_hint: locatorHint(node.role, node.name),
      action_type: node.role === "textbox" ? "fill" : "click",
      enabled: !node.disabled,
      visible: true,
    }));

  return {
    title: documentTitleFromNodes(accessibilityNodes) || domFacts.title,
    url: browserPage.url(),
    accessibility_tree: accessibilityNodes.map((node) => ({
      role: node.role,
      name: node.name || "",
      locator_hint: locatorHint(node.role, node.name),
      enabled: !node.disabled,
      visible: true,
      source: node.source || "accessibility",
    })),
    actions: actions.length > 0 ? actions : domFacts.actions,
    links: domFacts.links,
  };
}

async function collectDomFacts(browserPage) {
  return browserPage.evaluate(() => {
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const labelOf = (el) => {
      const aria = el.getAttribute("aria-label");
      const title = el.getAttribute("title");
      const placeholder = el.getAttribute("placeholder");
      const text = el.innerText || el.textContent;
      const value = el.getAttribute("value");
      return (aria || title || placeholder || text || value || el.name || el.id || el.tagName).trim().replace(/\s+/g, " ").slice(0, 120);
    };
    const elements = Array.from(document.querySelectorAll("a,button,input,textarea,select,[role='button'],[role='link'],[role='tab'],[role='menuitem']"))
      .filter(visible)
      .slice(0, 120)
      .map((el, index) => {
        const role = el.tagName.toLowerCase() === "a" ? "link" : (el.getAttribute("role") || el.tagName.toLowerCase());
        const name = labelOf(el);
        return {
          index,
          role,
          name,
          action_type: ["input", "textarea"].includes(el.tagName.toLowerCase()) ? "fill" : "click",
          locator_hint: role && name ? `getByRole('${role}', { name: ${JSON.stringify(name)} })` : "",
          href: el.href || "",
          source: "dom_fallback",
        };
      });
    return {
      title: document.title || location.pathname || location.href,
      actions: elements.filter((item) => item.role !== "link" || !item.href),
      links: elements.filter((item) => item.href),
    };
  });
}

function flattenAccessibility(node, output = []) {
  if (!node) return output;
  output.push({
    role: node.role || "generic",
    name: node.name || "",
    disabled: Boolean(node.disabled),
    source: "accessibility",
  });
  for (const child of node.children || []) {
    flattenAccessibility(child, output);
  }
  return output;
}

function locatorHint(role, name) {
  if (!role || !name) return "";
  return `getByRole('${role}', { name: ${JSON.stringify(name)} })`;
}

function documentTitleFromNodes(nodes) {
  const heading = nodes.find((node) => node.role === "heading" && node.name);
  return heading?.name || "";
}

function buildPageDoc(pageId, facts, entryPath, blockers) {
  const moduleName = "未分组模块";
  const pageType = detectPageType(facts.title, facts.url, facts.accessibility_tree);
  const blocker = blockers.find((item) => item.page === facts.url || item.page === entryPath);
  return {
    page: {
      id: pageId,
      title: facts.title || facts.url || "未命名页面",
      url: facts.url,
      normalized_url: normalizeUrl(facts.url),
      module: moduleName,
      page_type: pageType,
      depth: 0,
      status: blocker ? "blocked" : "explored",
    },
    accessibility_tree: facts.accessibility_tree,
    actions: facts.actions.map((action, index) => ({
      id: makeId("action", index + 1),
      role: action.role,
      name: action.name,
      locator_hint: action.locator_hint,
      action_type: action.action_type,
      enabled: action.enabled,
      visible: action.visible,
    })),
    relations: {
      incoming_edges: [],
      outgoing_edges: [],
    },
    quality: {
      confidence: "observed",
      needs_confirmation: false,
      blockers: blocker ? [blocker.reason] : [],
    },
  };
}

function factsCount(pages) {
  return pages.reduce((count, pageDoc) => count + (pageDoc.actions?.length || 0), 0);
}

function canInteract(action) {
  return ["button", "textbox", "combobox", "checkbox", "radio", "menuitem", "tab"].includes(action.role || action.action_type);
}

function detectPageType(title, url, tree) {
  const titleText = `${title || ""} ${url || ""} ${JSON.stringify(tree || [])}`;
  if (/(列表|list)/i.test(titleText)) return "list";
  if (/(详情|detail)/i.test(titleText)) return "detail";
  if (/(编辑|新建|create|edit|form)/i.test(titleText)) return "form";
  if (/(设置|setting)/i.test(titleText)) return "settings";
  if (/(首页|dashboard|home)/i.test(titleText)) return "dashboard";
  return "unknown";
}

function sameOriginHref(href, start) {
  try {
    const target = new URL(href, start);
    if (target.origin !== start.origin) {
      return "";
    }
    return target.href;
  } catch {
    return "";
  }
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
    return value;
  }
}

function isForbidden(value) {
  const lower = String(value || "").toLowerCase();
  return forbiddenTerms.some((term) => lower.includes(term));
}

function makeId(prefix, index) {
  return `${prefix}-${String(index).padStart(3, "0")}`;
}
