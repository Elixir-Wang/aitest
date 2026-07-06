export async function verifyElementSelectors(page, selectors = {}) {
  const verified = {};
  if (selectors.primary_selector) {
    verified.primary_selector = await verifySelectorCandidate(page, selectors.primary_selector);
  }
  if (selectors.fallback_selector) {
    verified.fallback_selector = await verifySelectorCandidate(page, selectors.fallback_selector);
  }
  return verified;
}

export async function verifySelectorCandidate(page, candidate = {}) {
  const result = { ...candidate };
  try {
    const locator = locatorForCandidate(page, candidate);
    const matchCount = await locator.count().catch(() => 0);
    const unique = matchCount === 1;
    const visible = unique ? await locator.first().isVisible().catch(() => false) : false;
    result.verification = {
      checked: true,
      unique,
      visible,
      match_count: matchCount,
    };
  } catch (error) {
    result.verification = {
      checked: true,
      unique: false,
      visible: false,
      match_count: 0,
      error: String(error?.message || error).slice(0, 200),
    };
  }
  return result;
}

/**
 * 把 candidate 反向成 Playwright Locator。
 *
 * candidate.kind 涵盖 selector-generator 产出的所有形式：
 *   - role / label / placeholder / testid / text / css
 *   - contextual：container 接受 testid/role/label 三种锚点
 *     · container.kind = "testid"：page.getByTestId(...).filter({ hasText }).getByRole(...)
 *     · container.kind = "role"   ：page.getByRole(...).filter({ hasText }).getByRole(...)
 *     · container.kind = "label"  ：page.getByLabel(...).getByRole(...)
 *
 * target 仅支持 role / testid / text 三类子元素定位；其它类型请改用 page.locator。
 */
export function locatorForCandidate(page, candidate = {}) {
  const kind = String(candidate.kind || "");
  if (kind === "role") {
    return page.getByRole(String(candidate.role || ""), {
      name: String(candidate.name || ""),
      ...(candidate.exact === false ? { exact: false } : { exact: true }),
    });
  }
  if (kind === "label") {
    return page.getByLabel(String(candidate.label || ""));
  }
  if (kind === "placeholder") {
    // generator 总是给 exact=true；解析端也透传
    return page.getByPlaceholder(String(candidate.placeholder || ""), { exact: true });
  }
  if (kind === "testid") {
    return page.getByTestId(String(candidate.testId || candidate.test_id || ""));
  }
  if (kind === "text") {
    return page.getByText(String(candidate.text || ""), { exact: true });
  }
  if (kind === "alt") {
    return page.getByAltText(String(candidate.text || candidate.alt || ""));
  }
  if (kind === "title") {
    return page.getByTitle(String(candidate.text || candidate.title || ""));
  }
  if (kind === "contextual") {
    const container = contextualContainerLocator(page, candidate.container || {});
    const target = candidate.target || {};
    if (target.kind === "role") {
      return container.getByRole(String(target.role || ""), {
        name: String(target.name || ""),
        exact: target.exact === false ? false : true,
      });
    }
    if (target.kind === "testid") {
      return container.getByTestId(String(target.testId || target.test_id || ""));
    }
    if (target.kind === "text") {
      return container.getByText(String(target.text || ""), { exact: true });
    }
    throw new Error(`Unsupported contextual target kind: ${target.kind || "unknown"}`);
  }
  if (kind === "css") {
    return page.locator(String(candidate.css || ""));
  }
  throw new Error(`Unsupported selector kind: ${kind || "unknown"}`);
}

function contextualContainerLocator(page, container = {}) {
  const kind = String(container.kind || "");
  if (kind === "testid") {
    const locator = page.getByTestId(String(container.testId || container.test_id || ""));
    const hasText = String(container.hasText || container.text || "");
    return hasText ? locator.filter({ hasText }) : locator;
  }
  if (kind === "role") {
    const role = String(container.role || "");
    if (!role) {
      throw new Error("Contextual selector is missing container role.");
    }
    const locator = page.getByRole(role);
    const hasText = String(container.hasText || container.text || "");
    return hasText ? locator.filter({ hasText }) : locator;
  }
  if (kind === "label") {
    // label 锚点没有 filter
    return page.getByLabel(String(container.label || ""));
  }
  throw new Error(`Unsupported contextual container kind: ${kind || "unknown"}`);
}
