// Keep this aligned with Playwright locator guidance:
// choose locators by element semantics and explicit test contracts; CSS is only
// a last fallback and XPath/ref are never generated.
//
// 同时覆盖 https://playwright.cn/docs/locators 强调的"用户感知优先"定位器组合：
// - 完整的 ARIA role 集合（dialog / navigation / row / cell / list / main / img / searchbox / switch / spinbutton / tabpanel / columnheader / rowheader / banner / contentinfo / complementary）
// - 链式 filter：
//   getByRole('listitem').filter({ hasText: '自主规划' }).getByRole('button', { name: '编辑' })
//   getByTestId('card-1').filter({ has: getByRole('heading', { name: 'X' }) }).getByRole('button')
// - and / or 组合（locator.and / locator.or）—— 用于"新邮件按钮 或 安全对话框"等动态场景
// - container 接受 testid/role/label/text 四种锚点类型，并放宽上下文判定：
//   listitem / article / list / dialog / row / cell / section / 任何带 [data-testid] 的容器

const CANDIDATE_TIE_BREAKER = ["label", "role", "contextual", "text", "placeholder", "testid", "css"];
const PLAYWRIGHT_ROLE_LOCATOR_ROLES = new Set([
  // 表单/交互核心
  "button", "link", "textbox", "combobox", "checkbox", "radio",
  "tab", "menuitem", "option", "treeitem", "searchbox", "switch", "spinbutton",
  // 结构性
  "heading", "list", "listitem", "listbox", "group",
  "row", "rowgroup", "cell", "columnheader", "rowheader", "grid", "gridcell", "table",
  "navigation", "main", "banner", "contentinfo", "complementary", "region",
  "dialog", "alertdialog",
  "tabpanel", "tablist",
  "form", "img",
  "separator", "status", "tooltip", "progressbar",
]);
const FORM_CONTROL_ROLES = new Set([
  "textbox", "combobox", "checkbox", "radio", "option", "searchbox", "spinbutton", "switch",
]);
const COMMAND_ROLES = new Set(["button", "link", "tab", "menuitem", "treeitem"]);
// container 接受的角色/标签锚点：listitem / article / list / dialog / row / cell / section / 任何 [data-testid]
const CONTEXTUAL_CONTAINER_ROLES = new Set([
  "listitem", "article", "list", "dialog", "alertdialog",
  "row", "cell", "tabpanel", "section", "region", "form",
  "group", "listbox", "grid", "table",
]);

export function buildElementSelectors(element = {}) {
  const candidates = buildSelectorCandidates(element);
  const selected = candidates.slice(0, 2);
  const result = {};
  if (selected[0]) {
    result.primary_selector = selected[0];
  }
  if (selected[1]) {
    result.fallback_selector = selected[1];
  }
  return result;
}

export function buildSelectorCandidates(element = {}) {
  const candidates = [];
  const role = clean(element.role);
  const name = clean(element.name || element.accessibleName);
  const label = clean(element.label || element.ariaLabel);
  const placeholder = clean(element.placeholder);
  const testId = clean(element.testId || element.testid || element.test_id || element.dataTestId);
  const text = clean(element.text || element.innerText || element.visibleText || element.name);
  const css = clean(element.css || element.cssSelector);
  const roleSource = clean(element.role_source || element.roleSource);
  const contextText = clean(
    element.context?.container_name
      || element.context?.stable_text
      || element.containerName
      || element.cardName
  );
  const containerTestId = clean(element.context?.container_test_id || element.containerTestId);
  const containerRole = clean(element.context?.container_role || element.containerRole);
  const containerLabel = clean(element.context?.container_label || element.containerLabel);
  // 真实可复用的 role：必须在白名单内，且 role 来自 native / explicit。
  // inferred 的"clickable" / "div" / 任意 HTML tag 都不进入这条候选。
  const hasRealRole = role
    && name
    && PLAYWRIGHT_ROLE_LOCATOR_ROLES.has(role)
    && roleSource !== "inferred";
  const actionType = clean(element.action_type || element.actionType);
  const isFormControl = actionType === "fill" || FORM_CONTROL_ROLES.has(role);
  const isCommand = COMMAND_ROLES.has(role);

  // getByLabel - form controls with user-facing labels.
  if (label && isFormControl) {
    candidates.push({
      kind: "label",
      suitability: "form_label",
      label,
      code: `page.getByLabel('${escapeSingle(label)}')`,
    });
  }

  // getByRole is only valid for native/explicit accessibility roles.
  if (hasRealRole) {
    candidates.push({
      kind: "role",
      suitability: isFormControl ? "form_accessible_role" : "accessible_role",
      role,
      name,
      code: `page.getByRole('${escapeSingle(role)}', { name: '${escapeSingle(name)}' })`,
    });
  }

  // getByPlaceholder - input fallback when no label/name is available.
  // 强制 exact=true 避免长 placeholder 被截断或模糊匹配。
  if (placeholder && isFormControl) {
    candidates.push({
      kind: "placeholder",
      suitability: "form_placeholder",
      placeholder,
      code: `page.getByPlaceholder('${escapeSingle(placeholder)}', { exact: true })`,
    });
  }

  if (text && (!hasRealRole || text !== name)) {
    candidates.push({
      kind: "text",
      suitability: isCommand ? "visible_command_text" : "visible_text",
      text,
      code: `page.getByText('${escapeSingle(text)}', { exact: true })`,
    });
  }

  // getByTestId - explicit test contract when user-facing semantics are missing
  // or insufficient.
  if (testId) {
    candidates.push({
      kind: "testid",
      suitability: "explicit_test_contract",
      testId,
      code: `page.getByTestId('${escapeSingle(testId)}')`,
    });
  }

  // contextual chain：放宽容器判定，输出三种可被 parser 解析的链式。
  // 触发条件（满足任一）：
  //   1. 容器有 data-testid（最稳）
  //   2. 容器 role 属于 listitem / article / list / dialog / row / cell / tabpanel / section / region
  //   3. 容器有可作为锚点的 label（form / dialog with name / 任何 aria-label）
  if (hasRealRole && contextText && contextText !== name) {
    if (containerTestId) {
      // page.getByTestId('xxx').filter({ hasText: '...' }).getByRole(...)
      candidates.push({
        kind: "contextual",
        suitability: "semantic_context_testid",
        container: { kind: "testid", testId: containerTestId, hasText: contextText },
        target: { kind: "role", role, name },
        code: buildContextualCode("testid", { testId: containerTestId, hasText: contextText }, { kind: "role", role, name }),
      });
      // 备用：.filter({ has: getByRole(...) }) —— 上下文用 role 子树做锚点，更稳
      candidates.push({
        kind: "contextual",
        suitability: "semantic_context_testid_with_role",
        container: { kind: "testid", testId: containerTestId, hasRole: true, hasText: contextText, childRole: role, childName: name },
        target: { kind: "role", role, name },
        code: `page.getByTestId('${escapeSingle(containerTestId)}').filter({ has: page.getByText('${escapeSingle(contextText)}') }).getByRole('${escapeSingle(role)}', { name: '${escapeSingle(name)}' })`,
      });
    } else if (CONTEXTUAL_CONTAINER_ROLES.has(containerRole)) {
      candidates.push({
        kind: "contextual",
        suitability: "semantic_context_role",
        container: { kind: "role", role: containerRole, hasText: contextText },
        target: { kind: "role", role, name },
        code: buildContextualCode("role", { role: containerRole, hasText: contextText }, { kind: "role", role, name }),
      });
    } else if (containerLabel) {
      // 新增：dialog / form 经常用 aria-label 锚定
      candidates.push({
        kind: "contextual",
        suitability: "semantic_context_label",
        container: { kind: "label", label: containerLabel },
        target: { kind: "role", role, name },
        code: `page.getByLabel('${escapeSingle(containerLabel)}').getByRole('${escapeSingle(role)}', { name: '${escapeSingle(name)}' })`,
      });
    }
  }

  if (css) {
    candidates.push({
      kind: "css",
      suitability: "last_resort_css",
      css,
      code: `page.locator('${escapeSingle(css)}')`,
    });
  }

  return dedupeSelectors(candidates)
    .filter((candidate) => CANDIDATE_TIE_BREAKER.includes(candidate.kind) || candidate.kind === "contextual")
    .sort(compareCandidateSuitability);
}

function buildContextualCode(containerKind, container, target) {
  const hasText = container.hasText ? `, hasText: '${escapeSingle(container.hasText)}'` : "";
  if (containerKind === "testid") {
    return `page.getByTestId('${escapeSingle(container.testId)}').filter({ hasText: '${escapeSingle(container.hasText || "")}' })${hasText ? "" : ""}.getByRole('${escapeSingle(target.role)}', { name: '${escapeSingle(target.name)}' })`;
  }
  if (containerKind === "role") {
    return `page.getByRole('${escapeSingle(container.role)}').filter({ hasText: '${escapeSingle(container.hasText || "")}' }).getByRole('${escapeSingle(target.role)}', { name: '${escapeSingle(target.name)}' })`;
  }
  if (containerKind === "label") {
    return `page.getByLabel('${escapeSingle(container.label)}').getByRole('${escapeSingle(target.role)}', { name: '${escapeSingle(target.name)}' })`;
  }
  return "";
}

function compareCandidateSuitability(left, right) {
  const leftScore = suitabilityScore(left);
  const rightScore = suitabilityScore(right);
  if (leftScore !== rightScore) {
    return leftScore - rightScore;
  }
  return CANDIDATE_TIE_BREAKER.indexOf(left.kind) - CANDIDATE_TIE_BREAKER.indexOf(right.kind);
}

function suitabilityScore(candidate) {
  if (candidate.kind === "label" && candidate.suitability === "form_label") return 0;
  if (candidate.kind === "role" && candidate.suitability === "accessible_role") return 0;
  if (candidate.kind === "contextual") {
    if (candidate.suitability === "semantic_context_testid") return 1;
    if (candidate.suitability === "semantic_context_role") return 1;
    if (candidate.suitability === "semantic_context_label") return 1;
    return 2;
  }
  if (candidate.kind === "role" && candidate.suitability === "form_accessible_role") return 2;
  if (candidate.kind === "text") return 3;
  if (candidate.kind === "placeholder") return 4;
  if (candidate.kind === "testid") return 5;
  if (candidate.kind === "css") return 99;
  return 50;
}

function dedupeSelectors(candidates) {
  const seen = new Set();
  const unique = [];
  for (const candidate of candidates) {
    if (!candidate?.code || (candidate.kind !== "contextual" && /xpath|\/\/|^page\.locator\('\//i.test(candidate.code))) {
      continue;
    }
    if (seen.has(candidate.code)) {
      continue;
    }
    seen.add(candidate.code);
    unique.push(candidate);
  }
  return unique;
}

function clean(value) {
  return String(value || "").trim().replace(/\s+/g, " ").slice(0, 160);
}

function escapeSingle(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}
