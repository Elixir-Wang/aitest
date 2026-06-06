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

export function locatorForCandidate(page, candidate = {}) {
  const kind = String(candidate.kind || "");
  if (kind === "role") {
    return page.getByRole(String(candidate.role || ""), { name: String(candidate.name || "") });
  }
  if (kind === "label") {
    return page.getByLabel(String(candidate.label || ""));
  }
  if (kind === "testid") {
    return page.getByTestId(String(candidate.testId || candidate.test_id || ""));
  }
  if (kind === "text") {
    return page.getByText(String(candidate.text || ""));
  }
  if (kind === "css") {
    return page.locator(String(candidate.css || ""));
  }
  throw new Error(`Unsupported selector kind: ${kind || "unknown"}`);
}
