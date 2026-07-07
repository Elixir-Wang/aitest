import { buildSelectorCandidates } from "./selector-generator.mjs";
import { verifySelectorCandidate } from "./selector-validator.mjs";

export async function verifyBestElementSelectors(browserPage, element) {
  const candidates = buildSelectorCandidates(element);
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

export function selectorUsable(selector) {
  return Boolean(selector?.verification?.checked && selector.verification.unique && selector.verification.visible);
}

export function stableElementId(element, index, { useTextFallback = true } = {}) {
  const label = element.name || (useTextFallback ? element.text : "") || index;
  const base = slugify(`${element.role || element.action_type || "element"}-${label}`);
  return `${base || "element"}-${String(index).padStart(3, "0")}`;
}

export function normalizeUrl(value, { invalidFallback = "string" } = {}) {
  try {
    const url = new URL(value);
    url.hash = "";
    if (url.pathname.endsWith("/") && url.pathname !== "/") {
      url.pathname = url.pathname.slice(0, -1);
    }
    return url.href;
  } catch {
    if (invalidFallback === "raw") {
      return value;
    }
    return String(value || "");
  }
}

export function slugify(value, fallback = "element") {
  return String(value || fallback)
    .trim()
    .toLowerCase()
    .replace(/[^a-zA-Z0-9\u4e00-\u9fff]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40) || fallback;
}
