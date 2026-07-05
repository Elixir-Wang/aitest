import { chromium } from "playwright";
import { buildSelectorCandidates } from "./selector-generator.mjs";
import { locatorForCandidate, verifySelectorCandidate } from "./selector-validator.mjs";

const [, , startUrl, artifactRoot, channel = "", forbiddenInput = "", storageStatePath = ""] = process.argv;

if (!startUrl || !artifactRoot) {
  console.error("Usage: node site-explorer.mjs <startUrl> <artifactRoot> [channel]");
  process.exit(2);
}

const maxPages = Number(process.env.AI_TESTING_EXPLORATION_MAX_PAGES || "50");
const maxActions = Number(process.env.AI_TESTING_EXPLORATION_MAX_ACTIONS || "1000");
const navigationTimeout = Number(process.env.AI_TESTING_EXPLORATION_NAV_TIMEOUT_MS || "20000");
const runTimeout = Number(process.env.AI_TESTING_EXPLORATION_TIMEOUT_MS || "7200000");

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
const startedAt = Date.now();

try {
  logEvent("run_started", { url: start.href, max_pages: maxPages, max_actions: maxActions, timeout_ms: runTimeout });
  emitProgress("run_progress", { recent_event: "Playwright 探索已启动。", url: start.href });
  while (queued.length > 0 && pages.length < maxPages && actionCount < maxActions) {
    if (Date.now() - startedAt > runTimeout) {
      blockers.push({
        id: makeId("blocker", blockers.length + 1),
        type: "run_timeout",
        page: queued[0] || start.href,
        reason: `探索超过超时时间 ${runTimeout}ms，已停止继续访问。`,
        severity: "blocking",
        suggested_action: "缩小探索范围或提高超时时间后重新探索。",
      });
      logEvent("blocked", { type: "run_timeout", page: queued[0] || start.href });
      break;
    }
    const targetUrl = queued.shift();
    if (!targetUrl || visited.has(normalizeUrl(targetUrl))) {
      continue;
    }
    visited.add(normalizeUrl(targetUrl));
    const nextPageId = makeId("page", pages.length + 1);
    emitProgress("page_discovered", {
      module_key: "site-entry",
      page_id: nextPageId,
      title: targetUrl,
      url: targetUrl,
      entry_path: targetUrl,
      status: "running",
      recent_event: `准备访问 ${targetUrl}`,
    });

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
      logEvent("blocked", { type: "navigation_failed", page: targetUrl, reason: String(error?.message || error) });
      emitProgress("page_blocked", {
        module_key: "site-entry",
        page_id: nextPageId,
        title: targetUrl,
        url: targetUrl,
        entry_path: targetUrl,
        status: "blocked",
        blocker_reason: String(error?.message || error),
        recent_event: "页面访问失败",
        steps: [
          makeStep("step-001", "visit", "进入页面", `访问 ${targetUrl}`, "failed"),
          makeStep("step-002", "blocked", "页面阻塞", String(error?.message || error), "blocked"),
        ],
      });
      continue;
    }

    const facts = await collectAccessibilityFacts(page);
    const pageId = nextPageId;
    const pageDoc = await buildPageDoc(page, pageId, facts, targetUrl, blockers);
    addPageStep(pageDoc, "visit", "进入页面", `访问 ${targetUrl}`);
    emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
    addPageStep(pageDoc, "snapshot", "采集页面结构", `采集 ${facts.accessibility_tree.length} 个无障碍节点、${facts.links.length} 个链接。`);
    emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
    if (facts.actions.length > 0) {
      addPageStep(pageDoc, "element_discovered", "识别可操作元素", `识别 ${facts.actions.length} 个可操作元素。`);
      emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
    }
    emitProgress("page_updated", {
      module_key: "site-entry",
      page_id: pageId,
      title: pageDoc.page.title,
      url: pageDoc.page.url,
      entry_path: pageDoc.page.normalized_url,
      structure_summary: pageDoc.page.structure_summary,
      status: "running",
      recent_event: "页面结构采集完成",
      steps: pageDoc.steps,
    });
    pages.push(pageDoc);
    graphNodes.push({
      id: pageId,
      title: pageDoc.page.title,
      url: pageDoc.page.url,
      module: pageDoc.page.module,
    });
    logEvent("page_captured", {
      page_id: pageId,
      url: pageDoc.page.url,
      title: pageDoc.page.title,
      artifact_path: `pages/${pageId}-${slugify(pageDoc.page.title || pageDoc.page.url)}.yaml`,
    });

    for (const link of facts.links) {
      const href = sameOriginHref(link.href, start);
      if (!href) {
        graphEdges.push({
          id: makeId("edge", graphEdges.length + 1),
          source: pageId,
          target: link.href,
          type: "external_link",
          action: `发现外链 ${link.name || link.href}`,
          element: link,
          result: { url_changed: false, visited: false, skipped: true },
        });
        logEvent("edge_created", { edge_id: graphEdges.at(-1).id, source: pageId, target: link.href, type: "external_link" });
        addPageStep(pageDoc, "skipped", "记录外链", `发现外链 ${link.name || link.href}，已记录但不访问。`);
        emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
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
        logEvent("skipped", { type: "forbidden_path", page_id: pageId, action: link.name || href });
        addPageStep(pageDoc, "skipped", "跳过禁止路径", `命中禁止路径，已跳过：${link.name || href}`);
        emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
        continue;
      }
      queued.push(href);
      graphEdges.push({
        id: makeId("edge", graphEdges.length + 1),
        source: pageId,
        target: normalizeUrl(href),
        type: "navigation",
        action: `访问 ${link.name || href}`,
        element: link,
        result: { url_changed: true, target_page_detected: true },
      });
      logEvent("edge_created", { edge_id: graphEdges.at(-1).id, source: pageId, target: normalizeUrl(href), type: "navigation" });
      addPageStep(pageDoc, "edge_created", "记录页面关系", `发现同域链接 ${link.name || href}`);
      emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
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
        logEvent("skipped", { type: "forbidden_path", page_id: pageId, action: action.name || action.locator_hint });
        addPageStep(pageDoc, "skipped", "跳过禁止动作", `命中禁止动作，已跳过：${action.name || action.locator_hint}`);
        emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
        continue;
      }
      let clickValidation = null;
      if (action.action_type === "click" && action.role === "button") {
        const storedAction = pageDoc.actions.find((item) => item.id === action.id || (item.name === action.name && item.locator_hint === action.locator_hint));
        const capturedState = await captureStateAfterSafeOpenAction(page, pageDoc, action, storedAction);
        if (capturedState) {
          pageDoc.states.push(capturedState);
          addPageStep(
            pageDoc,
            "state_captured",
            "采集页面内状态",
            `${action.name || action.locator_hint || "按钮"} 打开后识别 ${capturedState.elements.length} 个状态内元素。`,
          );
          emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
        }
        clickValidation = await validateSafeButtonClick(page, action, pageDoc.page.url, storedAction);
        if (storedAction) {
          storedAction.validation = clickValidation;
        }
        if (clickValidation.status === "passed" || clickValidation.status === "failed") {
          addPageStep(
            pageDoc,
            "goal_validation",
            "验证按钮跳转",
            `${action.name || action.locator_hint || "按钮"}：${clickValidation.reason}`,
            clickValidation.status === "failed" ? "failed" : "completed",
          );
          emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
        }
      }
      const edge = {
        id: makeId("edge", graphEdges.length + 1),
        source: pageId,
        target: pageId,
        type: edgeTypeForAction(action),
        action: action.name || action.locator_hint || "action",
        element: action,
        result: clickValidation || { url_changed: false, target_page_detected: false },
      };
      const clickedUrl = sameOriginHref(clickValidation?.after_url || "", start);
      if (clickValidation?.status === "passed" && clickValidation.url_changed && clickedUrl) {
        const normalizedClickedUrl = normalizeUrl(clickedUrl);
        if (isForbidden(`${action.name} ${normalizedClickedUrl}`)) {
          blockers.push({
            id: makeId("blocker", blockers.length + 1),
            type: "forbidden_path",
            page: pageDoc.page.url,
            action: action.name || normalizedClickedUrl,
            reason: `按钮跳转命中禁止路径，已跳过：${action.name || normalizedClickedUrl}`,
            severity: "warning",
            suggested_action: "如需覆盖该功能，请在安全测试环境中调整禁止路径后重新探索。",
          });
          logEvent("skipped", { type: "forbidden_path", page_id: pageId, action: action.name || normalizedClickedUrl });
          addPageStep(pageDoc, "skipped", "跳过禁止跳转", `按钮跳转命中禁止路径，已跳过：${action.name || normalizedClickedUrl}`);
          emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
        } else {
          edge.target = normalizedClickedUrl;
          edge.type = "navigation";
          edge.result = {
            ...clickValidation,
            target_page_detected: true,
          };
          if (!visited.has(normalizedClickedUrl) && !queued.some((item) => normalizeUrl(item) === normalizedClickedUrl)) {
            queued.push(clickedUrl);
            addPageStep(pageDoc, "edge_created", "记录按钮跳转", `按钮 ${action.name || action.locator_hint || "action"} 跳转到 ${normalizedClickedUrl}`);
            emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
          }
        }
      }
      graphEdges.push(edge);
      logEvent("edge_created", { edge_id: graphEdges.at(-1).id, source: pageId, target: edge.target, type: graphEdges.at(-1).type });
      addPageStep(pageDoc, "action_observed", "识别动作", `发现 ${action.name || action.locator_hint || "action"}`);
      emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
      actionCount += 1;
    }
    addPageStep(pageDoc, "artifact_written", "写入页面事实", `写入 pages/${pageId}-${slugify(pageDoc.page.title || pageDoc.page.url)}.yaml`);
    emitProgress("step_recorded", { module_key: "site-entry", page_id: pageId, step: pageDoc.steps.at(-1) });
    addPageStep(pageDoc, pageDoc.page.status === "blocked" ? "blocked" : "completed", pageDoc.page.status === "blocked" ? "页面阻塞" : "页面探索完成", pageDoc.page.status === "blocked" ? pageDoc.quality.blockers.join("；") : pageDoc.page.structure_summary);
    emitProgress(pageDoc.page.status === "blocked" ? "page_blocked" : "page_completed", {
      module_key: "site-entry",
      page_id: pageId,
      title: pageDoc.page.title,
      url: pageDoc.page.url,
      entry_path: pageDoc.page.normalized_url,
      structure_summary: pageDoc.page.structure_summary,
      status: pageDoc.page.status === "blocked" ? "blocked" : "completed",
      recent_event: pageDoc.steps.at(-1)?.detail || pageDoc.steps.at(-1)?.title || "",
      steps: pageDoc.steps,
    });
  }

  const summary = `已探索 ${pages.length} 个页面，识别 ${factsCount(pages)} 个可交互元素，记录 ${blockers.length} 个阻塞项。`;
  const finalStatus = pages.length > 0 ? (blockers.length > 0 ? "partial" : "completed") : "blocked";
  logEvent("run_completed", { status: finalStatus, page_count: pages.length, action_count: actionCount });
  emitResult({
      status: finalStatus,
      summary,
      structured_pages: pages,
      graph: {
        nodes: graphNodes,
        edges: graphEdges,
        paths: [],
      },
      blockers,
      log_lines: logLines.length > 0 ? logLines : [JSON.stringify({ event: "run_completed" })],
      log: `${logLines.join("\n")}\n`,
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
    });
} finally {
  await browser.close();
}

async function collectAccessibilityFacts(browserPage) {
  const snapshot = await browserPage.accessibility?.snapshot?.({ interestingOnly: false }).catch(() => null) || null;
  const accessibilityNodes = flattenAccessibility(snapshot).slice(0, 300);
  const domFacts = await collectDomFacts(browserPage);
  const domAccessibilityNodes = domFacts.actions.map((action, index) => ({
    id: makeId("node", index + 1),
    role: action.role || action.action_type || "generic",
    name: action.name || "",
    disabled: action.enabled === false,
    locator_hint: action.locator_hint || "",
    enabled: action.enabled !== false,
    visible: action.visible !== false,
    source: action.source || "dom_fallback",
  }));
  const pageNodes = mergePageNodes(accessibilityNodes, domAccessibilityNodes);
  const accessibilityActions = accessibilityNodes
    .filter((node) => ["button", "link", "textbox", "combobox", "checkbox", "radio", "tab", "menuitem"].includes(node.role))
    .map(actionFromAccessibilityNode);
  const actions = mergeActionFacts(domFacts.actions, accessibilityActions);

  return {
    title: documentTitleFromNodes(pageNodes) || domFacts.title,
    url: browserPage.url(),
    accessibility_tree: pageNodes.map((node) => ({
      id: node.id,
      role: node.role,
      name: node.name || "",
      locator_hint: node.locator_hint || locatorHint(node.role, node.name),
      enabled: node.enabled ?? !node.disabled,
      visible: node.visible ?? true,
      source: node.source || "accessibility",
    })),
    actions: actions.length > 0 ? actions : domFacts.actions,
    links: domFacts.links,
    forms: domFacts.forms,
    tables: domFacts.tables,
    states: domFacts.states || [],
  };
}

async function collectDomFacts(browserPage) {
  return browserPage.evaluate(() => {
    const clean = (value) => String(value || "").trim().replace(/\s+/g, " ").slice(0, 120);
    const isGenericLabel = (value) => /^(a|button|div|i|img|input|label|li|select|span|svg|textarea)$/i.test(clean(value));
    const firstMeaningful = (values) => {
      const cleaned = values.map(clean).filter(Boolean);
      return cleaned.find((value) => !isGenericLabel(value)) || cleaned[0] || "";
    };
    const textByIds = (ids) => ids
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent || "")
      .join(" ");
    const visible = (el) => {
      const style = window.getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const explicitLabelOf = (el) => {
      const id = el.getAttribute("id");
      if (id) {
        const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (label?.textContent?.trim()) {
          return clean(label.textContent);
        }
      }
      const wrappedLabel = el.closest("label");
      if (wrappedLabel?.textContent?.trim()) {
        return clean(wrappedLabel.textContent);
      }
      return "";
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
      el.tagName,
    ]);
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
      return { role: tagName, roleSource: "native" };
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
        if (document.querySelectorAll(selector).length === 1) {
          return selector;
        }
        current = parent;
      }
      return parts.join(" > ");
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
        .map((node) => (node.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80))
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
    const elementFacts = (root) => Array.from(root.querySelectorAll("a,button,input,textarea,select,[role='button'],[role='link'],[role='tab'],[role='menuitem'],[role='option'],[role='checkbox'],[role='radio']"))
      .filter(visible)
      .slice(0, 120)
      .map((el, index) => {
        const { role, roleSource } = roleOf(el);
        const name = labelOf(el);
        const tagName = el.tagName.toLowerCase();
        return {
          index,
          role,
          role_source: roleSource,
          name,
          label: explicitLabelOf(el),
          testId: el.getAttribute("data-testid") || el.getAttribute("data-test-id") || el.getAttribute("data-test") || "",
          text: (el.innerText || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 120),
          css: cssSelectorOf(el),
          context: contextOf(el, name),
          action_type: ["input", "textarea", "select"].includes(tagName) && !["button", "checkbox", "radio"].includes(role) ? "fill" : "click",
          locator_hint: role && name ? `getByRole('${role}', { name: ${JSON.stringify(name)} })` : "",
          href: el.href || "",
          enabled: !el.disabled && el.getAttribute("aria-disabled") !== "true",
          visible: true,
          source: "dom_fallback",
        };
      });
    const elements = elementFacts(document);
    const states = Array.from(document.querySelectorAll("[role='dialog'],[role='menu'],[role='listbox'],dialog,.modal,.ant-modal,.el-dialog"))
      .filter(visible)
      .slice(0, 20)
      .map((state, index) => ({
        id: state.getAttribute("id") || state.getAttribute("role") || `state-${String(index + 1).padStart(3, "0")}`,
        role: state.getAttribute("role") || state.tagName.toLowerCase(),
        title: labelOf(state),
        css: cssSelectorOf(state),
        elements: elementFacts(state).slice(0, 80),
      }));
    const forms = Array.from(document.querySelectorAll("form")).slice(0, 20).map((form, index) => ({
      id: `form-${String(index + 1).padStart(3, "0")}`,
      name: labelOf(form),
      fields: Array.from(form.querySelectorAll("input,textarea,select")).slice(0, 80).map((field) => ({
        name: labelOf(field),
        input_type: field.getAttribute("type") || field.tagName.toLowerCase(),
        required: Boolean(field.required || field.getAttribute("aria-required") === "true"),
        locator_hint: field.id ? `locator('#${field.id}')` : "",
      })),
    }));
    const tables = Array.from(document.querySelectorAll("table")).slice(0, 20).map((table, index) => ({
      id: `table-${String(index + 1).padStart(3, "0")}`,
      name: labelOf(table),
      columns: Array.from(table.querySelectorAll("th")).slice(0, 40).map((th) => labelOf(th)).filter(Boolean),
      row_count: table.querySelectorAll("tbody tr").length,
    }));
    return {
      title: document.title || location.pathname || location.href,
      actions: elements.filter((item) => item.role !== "link" || !item.href),
      links: elements.filter((item) => item.href),
      forms,
      tables,
      states,
    };
  });
}

function flattenAccessibility(node, output = []) {
  if (!node) return output;
  output.push({
    id: makeId("node", output.length + 1),
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

async function buildPageDoc(browserPage, pageId, facts, entryPath, blockers) {
  const moduleName = inferModuleName(facts.title, facts.url);
  const blocker = blockers.find((item) => item.page === facts.url || item.page === entryPath);
  const actions = [];
  const stateElements = [];
  for (const [index, action] of facts.actions.entries()) {
    const selectors = await verifyBestElementSelectors(browserPage, action);
    const elementId = stableElementId(action, index + 1);
    actions.push({
      id: makeId("action", index + 1),
      role: action.role,
      name: action.name,
      locator_hint: selectors.primary_selector?.code || "",
      action_type: action.action_type,
      enabled: action.enabled,
      visible: action.visible,
      locator_confidence: selectorConfidence(selectors.primary_selector),
      primary_selector: selectors.primary_selector || null,
      fallback_selector: selectors.fallback_selector || null,
    });
    stateElements.push({
      id: elementId,
      name: action.name || "",
      role: action.role || "",
      action: action.action_type || "inspect",
      enabled: action.enabled !== false,
      visible: action.visible !== false,
      source: action.source || "accessibility",
      primary_selector: selectors.primary_selector || null,
      fallback_selector: selectors.fallback_selector || null,
      needs_confirmation: !selectorUsable(selectors.primary_selector),
    });
  }
  const rootSelector = await verifySelectorCandidate(browserPage, {
    kind: "css",
    css: "body",
    code: "page.locator('body')",
  });
  return {
    artifact_schema_version: 2,
    page: {
      id: pageId,
      title: facts.title || facts.url || "未命名页面",
      url: facts.url,
      normalized_url: normalizeUrl(facts.url),
      module: moduleName,
      depth: 0,
      status: blocker ? "blocked" : "explored",
      structure_summary: summarizeFacts(facts),
    },
    states: [
      {
        id: "default",
        type: "page",
        title: facts.title || facts.url || "默认状态",
        root_selector: rootSelector,
        elements: stateElements,
      },
    ],
    accessibility_tree: treeFromFlatNodes(facts.accessibility_tree),
    steps: [],
    actions,
    forms: facts.forms,
    tables: facts.tables,
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

function actionFromAccessibilityNode(node, index) {
  return {
    id: makeId("action", index + 1),
    role: node.role,
    name: node.name || "",
    locator_hint: locatorHint(node.role, node.name),
    action_type: ["textbox", "combobox"].includes(node.role) ? "fill" : "click",
    enabled: !node.disabled,
    visible: true,
    source: node.source || "accessibility",
  };
}

function mergePageNodes(accessibilityNodes, domAccessibilityNodes) {
  if (!accessibilityNodes.length) {
    return domAccessibilityNodes;
  }
  const merged = [...accessibilityNodes];
  const seen = new Set(accessibilityNodes.map((node) => nodeDedupeKey(node)).filter(Boolean));
  for (const node of domAccessibilityNodes) {
    const key = nodeDedupeKey(node);
    if (key && seen.has(key)) {
      continue;
    }
    if (key) {
      seen.add(key);
    }
    merged.push(node);
  }
  return merged.slice(0, 300);
}

function mergeActionFacts(domActions, accessibilityActions) {
  const merged = [];
  const seen = new Set();
  for (const action of domActions || []) {
    addMergedAction(merged, seen, action, { keepGeneric: true });
  }
  for (const action of accessibilityActions || []) {
    addMergedAction(merged, seen, action, { keepGeneric: !merged.length });
  }
  return merged.map((action, index) => ({
    ...action,
    id: action.id || makeId("action", index + 1),
  }));
}

function addMergedAction(merged, seen, action, { keepGeneric }) {
  const key = actionDedupeKey(action);
  const generic = isGenericElementName(action?.name);
  if (generic && !keepGeneric) {
    return;
  }
  if (key && seen.has(key)) {
    return;
  }
  if (key) {
    seen.add(key);
  }
  merged.push(action);
}

function actionDedupeKey(action = {}) {
  const role = String(action.role || action.action_type || "").toLowerCase();
  const testId = String(action.testId || action.testid || action.test_id || "").trim();
  const css = String(action.css || "").trim();
  const href = String(action.href || "").trim();
  const name = normalizedElementName(action.name);
  if (testId) return `testid:${testId}`;
  if (css) return `css:${css}`;
  if (href) return `href:${href}`;
  if (role && name && !isGenericElementName(name)) return `role:${role}:name:${name}`;
  return "";
}

function nodeDedupeKey(node = {}) {
  const role = String(node.role || "").toLowerCase();
  const name = normalizedElementName(node.name);
  if (role && name && !isGenericElementName(name)) return `role:${role}:name:${name}`;
  return "";
}

function isGenericElementName(value) {
  return /^(a|button|div|i|img|input|label|li|select|span|svg|textarea)$/i.test(normalizedElementName(value));
}

function normalizedElementName(value) {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

async function verifyBestElementSelectors(browserPage, action) {
  const candidates = buildSelectorCandidates(action);
  if (!candidates.length) {
    return {};
  }
  const verified = [];
  for (const candidate of candidates) {
    verified.push(await verifySelectorCandidate(browserPage, candidate));
  }
  const usable = verified.filter(selectorUsable);
  const semanticUsable = usable.filter((candidate) => candidate.kind !== "css");
  const cssUsable = usable.filter((candidate) => candidate.kind === "css");
  const primary = semanticUsable[0] || cssUsable[0] || null;
  if (primary?.kind === "css") {
    primary.locator_confidence = "low";
    primary.needs_confirmation = true;
    primary.degraded_reason = "semantic_locators_unavailable";
  }
  const fallback = primary
    ? (semanticUsable.find((candidate) => candidate.code !== primary.code)
      || cssUsable.find((candidate) => candidate.code !== primary.code)
      || null)
    : null;
  return {
    primary_selector: primary || null,
    fallback_selector: fallback,
  };
}

function addPageStep(pageDoc, type, title, detail = "", status = "completed") {
  pageDoc.steps.push(makeStep(makeId("step", pageDoc.steps.length + 1), type, title, detail, status));
}

function makeStep(id, type, title, detail = "", status = "completed") {
  return {
    id,
    type,
    title,
    detail,
    status,
    occurred_at: new Date().toISOString(),
    source: "runner",
  };
}

function logEvent(event, payload = {}) {
  logLines.push(JSON.stringify({ ts: new Date().toISOString(), event, ...payload }));
}

function emitProgress(type, payload = {}) {
  console.log(JSON.stringify({ kind: "progress", type, payload }));
}

function emitResult(payload) {
  console.log(JSON.stringify({ kind: "result", payload }));
}

function edgeTypeForAction(action) {
  if (action.role === "tab") return "tab_switch";
  if (action.role === "textbox" || action.action_type === "fill") return "filter";
  if (/弹窗|新增|新建|详情|编辑|设置|modal|dialog|add|create|edit|detail/i.test(action.name || "")) return "open_modal";
  return "state_change";
}

function treeFromFlatNodes(nodes) {
  return (nodes || []).slice(0, 300).map((node, index) => ({
    id: node.id || makeId("node", index + 1),
    role: node.role,
    name: node.name || "",
    locator_hint: node.locator_hint || locatorHint(node.role, node.name),
    fallback_locator: node.fallback_locator || "",
    locator_confidence: node.name ? "medium" : "low",
    enabled: node.enabled,
    visible: node.visible,
    source: node.source || "accessibility",
    children: [],
  }));
}

function summarizeFacts(facts) {
  return `标题：${facts.title || "-"}。可交互元素：${facts.actions.length}。链接：${facts.links.length}。表单：${facts.forms.length}。表格：${facts.tables.length}。`;
}

function factsCount(pages) {
  return pages.reduce((count, pageDoc) => count + (pageDoc.actions?.length || 0), 0);
}

function selectorConfidence(selector) {
  if (!selector?.verification?.checked) return "unverified";
  if (selector.verification.unique && selector.verification.visible) return "high";
  return "low";
}

function selectorUsable(selector) {
  return Boolean(selector?.verification?.checked && selector.verification.unique && selector.verification.visible);
}

function stableElementId(action, index) {
  const base = slugify(`${action.role || action.action_type || "element"}-${action.name || index}`);
  return `${base || "element"}-${String(index).padStart(3, "0")}`;
}

async function captureStateAfterSafeOpenAction(browserPage, pageDoc, action, storedAction) {
  if (!shouldCapturePostClickState(action, storedAction)) {
    return null;
  }
  const beforeUrl = normalizeUrl(browserPage.url());
  try {
    const selector = storedAction?.primary_selector;
    await locatorForCandidate(browserPage, selector).click({ timeout: 2500 });
    await browserPage.waitForTimeout(500);
    await browserPage.waitForLoadState("networkidle", { timeout: 1500 }).catch(() => {});
    if (normalizeUrl(browserPage.url()) !== beforeUrl) {
      await browserPage.goto(beforeUrl, { waitUntil: "domcontentloaded" }).catch(() => {});
      await browserPage.waitForLoadState("networkidle", { timeout: 1500 }).catch(() => {});
      return null;
    }
    const stateFacts = await collectDomFacts(browserPage);
    const visibleState = (stateFacts.states || []).find((state) => Array.isArray(state.elements) && state.elements.length > 0);
    if (!visibleState) {
      return null;
    }
    const elements = [];
    for (const [index, element] of visibleState.elements.entries()) {
      const selectors = await verifyBestElementSelectors(browserPage, element);
      elements.push({
        id: stableElementId(element, index + 1),
        name: element.name || "",
        role: element.role || "",
        action: element.action_type || "inspect",
        enabled: element.enabled !== false,
        visible: element.visible !== false,
        source: "post_click_state",
        primary_selector: selectors.primary_selector || null,
        fallback_selector: selectors.fallback_selector || null,
        needs_confirmation: !selectorUsable(selectors.primary_selector),
      });
    }
    const rootSelector = await rootSelectorForState(browserPage, visibleState);
    return {
      id: `${slugify(action.name || action.locator_hint || "state")}-${String(pageDoc.states.length + 1).padStart(3, "0")}`,
      type: stateTypeFromRole(visibleState.role),
      title: visibleState.title || action.name || "页面内状态",
      parent_state: "default",
      trigger: {
        element_id: stableElementId(action, actionIndex(action)),
        action: "click",
      },
      root_selector: rootSelector,
      elements,
    };
  } catch {
    return null;
  } finally {
    await closeTransientState(browserPage);
  }
}

function shouldCapturePostClickState(action, storedAction) {
  const name = String(action.name || "").trim();
  if (!name || !selectorUsable(storedAction?.primary_selector)) {
    return false;
  }
  if (isUnsafeStateOpenName(name)) {
    return false;
  }
  return /新增|新建|添加|详情|查看|编辑|设置|筛选|搜索|展开|更多|选择|add|create|new|detail|view|edit|setting|filter|search|more|select/i.test(name);
}

function isUnsafeStateOpenName(name) {
  return /删除|移除|提交|支付|付款|确认|确定|发布|保存|上传|发送|delete|remove|submit|pay|confirm|save|upload|send/i.test(name || "");
}

async function rootSelectorForState(browserPage, state) {
  if (state.role && state.title) {
    return verifySelectorCandidate(browserPage, {
      kind: "role",
      role: state.role,
      name: state.title,
      code: `page.getByRole('${escapeSingle(state.role)}', { name: '${escapeSingle(state.title)}' })`,
    });
  }
  if (state.css) {
    return verifySelectorCandidate(browserPage, {
      kind: "css",
      css: state.css,
      code: `page.locator('${escapeSingle(state.css)}')`,
    });
  }
  return {
    kind: "unknown",
    code: "",
    verification: {
      checked: false,
      unique: false,
      visible: false,
      match_count: 0,
    },
  };
}

function stateTypeFromRole(role) {
  const normalized = String(role || "").toLowerCase();
  if (normalized.includes("dialog") || normalized.includes("modal")) return "dialog";
  if (normalized.includes("menu")) return "menu";
  if (normalized.includes("listbox")) return "listbox";
  return "panel";
}

async function closeTransientState(browserPage) {
  await browserPage.keyboard.press("Escape").catch(() => {});
  await browserPage.waitForTimeout(200).catch(() => {});
}

function actionIndex(action) {
  const parsed = Number.parseInt(String(action.id || "").split("-").at(-1) || "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function escapeSingle(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}

function canInteract(action) {
  return ["button", "textbox", "combobox", "checkbox", "radio", "menuitem", "tab"].includes(action.role || action.action_type);
}

async function validateSafeButtonClick(browserPage, action, beforeUrl, storedAction) {
  const name = String(action.name || "").trim();
  if (!name || name.toUpperCase() === "BUTTON") {
    return {
      status: "unverified",
      result: "unverified",
      reason: "按钮名称不可识别，未执行点击验证。",
      before_url: beforeUrl,
      after_url: "",
    };
  }
  if (isUnsafeButtonName(name)) {
    return {
      status: "skipped",
      result: "skipped",
      reason: "按钮疑似会修改业务数据，跳过真实点击验证。",
      before_url: beforeUrl,
      after_url: "",
    };
  }
  const beforeTitle = await browserPage.title().catch(() => "");
  const beforePageUrl = browserPage.url();
  try {
    const selector = storedAction?.primary_selector;
    if (!selectorUsable(selector)) {
      return {
        status: "unverified",
        result: "unverified",
        reason: "按钮 selector 未通过唯一性和可见性校验，未执行点击验证。",
        before_url: beforePageUrl,
        after_url: "",
        before_title: beforeTitle,
        selector: selector?.code || "",
      };
    }
    const locator = locatorForCandidate(browserPage, selector);
    const count = await locator.count().catch(() => 0);
    if (count !== 1) {
      return {
        status: "unverified",
        result: "unverified",
        reason: "按钮 selector 未能唯一定位元素。",
        before_url: beforePageUrl,
        after_url: "",
        before_title: beforeTitle,
        selector: selector.code || "",
        match_count: count,
      };
    }
    await Promise.all([
      browserPage.waitForLoadState("domcontentloaded", { timeout: 3000 }).catch(() => {}),
      locator.click({ timeout: 3000 }),
    ]);
    await browserPage.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
    const afterUrl = browserPage.url();
    const afterTitle = await browserPage.title().catch(() => "");
    const bodyText = await browserPage.locator("body").innerText({ timeout: 2000 }).catch(() => "");
    const loginDetected = looksLikeLogin(`${afterUrl} ${afterTitle} ${bodyText.slice(0, 1000)}`);
    const validation = {
      status: loginDetected ? "failed" : "passed",
      result: loginDetected ? "failed" : "passed",
      reason: loginDetected ? "点击后页面命中登录/鉴权特征。" : "点击后页面未命中登录页特征。",
      before_url: beforePageUrl,
      after_url: afterUrl,
      before_title: beforeTitle,
      after_title: afterTitle,
      url_changed: normalizeUrl(beforePageUrl) !== normalizeUrl(afterUrl),
      login_detected: loginDetected,
    };
    if (normalizeUrl(browserPage.url()) !== normalizeUrl(beforePageUrl)) {
      await browserPage.goto(beforePageUrl, { waitUntil: "domcontentloaded" }).catch(() => {});
      await browserPage.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
    }
    return validation;
  } catch (error) {
    await browserPage.goto(beforePageUrl, { waitUntil: "domcontentloaded" }).catch(() => {});
    await browserPage.waitForLoadState("networkidle", { timeout: 3000 }).catch(() => {});
    return {
      status: "unverified",
      result: "unverified",
      reason: `按钮点击验证失败：${String(error?.message || error).slice(0, 200)}`,
      before_url: beforePageUrl,
      after_url: browserPage.url(),
      before_title: beforeTitle,
    };
  }
}

function isUnsafeButtonName(name) {
  return /删除|移除|提交|支付|付款|确认|确定|发布|保存|创建|新增|修改|编辑|上传|发送|delete|remove|submit|pay|confirm|save|create|add|edit|upload|send/i.test(name || "");
}

function looksLikeLogin(value) {
  return /login|signin|sign-in|auth|passport|account\/login|user\/login|登录|登陆|验证码|401|403/i.test(value || "");
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

function inferModuleName(title, url) {
  const text = String(title || "").trim();
  if (text && text.length <= 40) return text;
  try {
    const parsed = new URL(url);
    const first = parsed.pathname.split("/").filter(Boolean)[0];
    return first || "入口页";
  } catch {
    return "未分组模块";
  }
}

function slugify(value) {
  return String(value || "page")
    .trim()
    .toLowerCase()
    .replace(/[^a-zA-Z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || "page";
}
