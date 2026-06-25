// Playwright 推荐的选择器优先级顺序
// 参考: https://playwright.dev/docs/locators#locate-by-role
const SELECTOR_PRIORITY = ["role", "label", "placeholder", "text", "testid", "css"];

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

  // 1. getByRole - 首选，匹配无障碍树
  if (role && name) {
    candidates.push({
      kind: "role",
      role,
      name,
      code: `page.getByRole('${escapeSingle(role)}', { name: '${escapeSingle(name)}' })`,
    });
  }

  // 2. getByLabel - 用于表单输入关联的标签
  if (label) {
    candidates.push({
      kind: "label",
      label,
      code: `page.getByLabel('${escapeSingle(label)}')`,
    });
  }

  // 3. getByPlaceholder - 当没有标签时
  if (placeholder) {
    candidates.push({
      kind: "placeholder",
      placeholder,
      code: `page.getByPlaceholder('${escapeSingle(placeholder)}')`,
    });
  }

  // 4. getByText - 用于非交互元素的可见文本
  if (text) {
    candidates.push({
      kind: "text",
      text,
      code: `page.getByText('${escapeSingle(text)}')`,
    });
  }

  // 5. getByTestId - 当语义选择器不可行时
  if (testId) {
    candidates.push({
      kind: "testid",
      testId,
      code: `page.getByTestId('${escapeSingle(testId)}')`,
    });
  }

  // 6. CSS selector - 最后的手段
  if (css) {
    candidates.push({
      kind: "css",
      css,
      code: `page.locator('${escapeSingle(css)}')`,
    });
  }

  return dedupeSelectors(candidates)
    .filter((candidate) => SELECTOR_PRIORITY.includes(candidate.kind))
    .sort((left, right) => SELECTOR_PRIORITY.indexOf(left.kind) - SELECTOR_PRIORITY.indexOf(right.kind));
}

function dedupeSelectors(candidates) {
  const seen = new Set();
  const unique = [];
  for (const candidate of candidates) {
    if (!candidate?.code || /xpath|\/\/|^page\.locator\('\//i.test(candidate.code)) {
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
