/**
 * parsePlaywrightLocatorString
 *
 * 把 LLM 传进来的 Playwright Locator 字符串解析成真实的 Locator 对象。
 *
 * 设计目的：
 * - click / fill 工具的 locator 参数既支持 snap ref（element.id），
 *   也支持直接传 Playwright Locator 字符串。
 * - 后者（getByRole / getByLabel / getByTestId / getByText / getByPlaceholder）
 *   在 LLM 上下文中跨调用稳定，因为它们是"按需查询表达式"，
 *   每次执行都在 page 内实时查找，不会因 DOM 抖动失效。
 *
 * 与 selector-validator.mjs 的关系：
 * - selector-validator.mjs:locatorForCandidate(page, candidate) 接收结构化对象
 *   {kind: "role", role: "X", name: "Y"}；
 * - 本函数接收字符串 "getByRole('X', { name: 'Y' })"，
 *   解析成相同语义，最后调用 page.getByRole(...) 直接拿 Locator。
 *
 * 与 selector-generator.mjs 的关系：
 * - snap 时 selector-generator 已把元素的 primary_selector 渲染成同样的字符串。
 *   这里只是反向解析，所以两种字符串形式完全可逆。
 */

const ROLE_PATTERN = /^getByRole\(\s*['"]([^'"]+)['"]\s*(?:,\s*\{([^)]*)\})?\s*\)$/;
const LABEL_PATTERN = /^getByLabel\(\s*['"]([^'"]*)['"]\s*(?:,\s*\{([^)]*)\})?\s*\)$/;
const TEST_ID_PATTERN = /^getByTestId\(\s*['"]([^'"]*)['"]\s*\)$/;
const TEXT_PATTERN = /^getByText\(\s*['"]([^'"]*)['"]\s*(?:,\s*\{([^)]*)\})?\s*\)$/;
const PLACEHOLDER_PATTERN = /^getByPlaceholder\(\s*['"]([^'"]*)['"]\s*(?:,\s*\{([^)]*)\})?\s*\)$/;

export function parsePlaywrightLocatorString(page, expr) {
  const trimmed = String(expr || "").trim();
  if (!trimmed || !trimmed.startsWith("getBy")) {
    return null;
  }

  const roleMatch = trimmed.match(ROLE_PATTERN);
  if (roleMatch) {
    return page.getByRole(roleMatch[1], parseOptions(roleMatch[2] || ""));
  }

  const labelMatch = trimmed.match(LABEL_PATTERN);
  if (labelMatch) {
    return page.getByLabel(labelMatch[1], parseOptions(labelMatch[2] || ""));
  }

  const testIdMatch = trimmed.match(TEST_ID_PATTERN);
  if (testIdMatch) {
    return page.getByTestId(testIdMatch[1]);
  }

  const textMatch = trimmed.match(TEXT_PATTERN);
  if (textMatch) {
    return page.getByText(textMatch[1], parseOptions(textMatch[2] || ""));
  }

  const placeholderMatch = trimmed.match(PLACEHOLDER_PATTERN);
  if (placeholderMatch) {
    return page.getByPlaceholder(placeholderMatch[1], parseOptions(placeholderMatch[2] || ""));
  }

  return null;
}

/**
 * 解析 Locator 字符串内的选项对象：
 *   { name: 'X', exact: true, level: 1 }
 *
 * 只支持 LLM 在探索场景下常用的几个选项，更复杂的请直接传 ref 形式。
 */
function parseOptions(body) {
  const opts = {};
  if (!body) return opts;

  const nameMatch = body.match(/name:\s*['"]([^'"]*)['"]/);
  if (nameMatch) opts.name = nameMatch[1];

  const exactMatch = body.match(/exact:\s*(true|false)/);
  if (exactMatch) opts.exact = exactMatch[1] === "true";

  const levelMatch = body.match(/level:\s*(\d+)/);
  if (levelMatch) opts.level = Number(levelMatch[1]);

  return opts;
}

/**
 * 判断 locator 字符串是否能被本解析器处理。
 * 用于 click / fill 工具快速判断是否走 live-locator 分支。
 */
export function isParseableLocatorString(expr) {
  const trimmed = String(expr || "").trim();
  return (
    /^getByRole\(/.test(trimmed) ||
    /^getByLabel\(/.test(trimmed) ||
    /^getByTestId\(/.test(trimmed) ||
    /^getByText\(/.test(trimmed) ||
    /^getByPlaceholder\(/.test(trimmed)
  );
}
