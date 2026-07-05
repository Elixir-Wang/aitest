// Keep this aligned with Playwright locator guidance:
// choose locators by element semantics and explicit test contracts; CSS is only
// a last fallback and XPath/ref are never generated.
const CANDIDATE_TIE_BREAKER = ["label", "role", "contextual", "text", "placeholder", "testid", "css"];
const PLAYWRIGHT_ROLE_LOCATOR_ROLES = new Set([
  "button",
  "link",
  "textbox",
  "combobox",
  "checkbox",
  "radio",
  "tab",
  "menuitem",
  "option",
  "treeitem",
  "heading",
]);
const FORM_CONTROL_ROLES = new Set(["textbox", "combobox", "checkbox", "radio", "option"]);
const COMMAND_ROLES = new Set(["button", "link", "tab", "menuitem", "treeitem"]);

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
  const hasRealRole = role && name && PLAYWRIGHT_ROLE_LOCATOR_ROLES.has(role) && roleSource !== "inferred";
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
  // Do not turn DOM clickability hints into fake role locators.
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
  if (placeholder && isFormControl) {
    candidates.push({
      kind: "placeholder",
      suitability: "form_placeholder",
      placeholder,
      code: `page.getByPlaceholder('${escapeSingle(placeholder)}')`,
    });
  }

  if (text && (!hasRealRole || text !== name)) {
    candidates.push({
      kind: "text",
      suitability: isCommand ? "visible_command_text" : "visible_text",
      text,
      code: `page.getByText('${escapeSingle(text)}')`,
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

  if (contextText && hasRealRole && contextText !== name && (containerTestId || containerRole === "listitem" || containerRole === "article")) {
    const container = containerTestId
      ? {
          kind: "testid",
          testId: containerTestId,
          hasText: contextText,
        }
      : {
          kind: "role",
          role: containerRole,
          hasText: contextText,
        };
    candidates.push({
      kind: "contextual",
      suitability: "semantic_context",
      container,
      target: {
        kind: "role",
        role,
        name,
      },
      code: containerTestId
        ? `page.getByTestId('${escapeSingle(containerTestId)}').filter({ hasText: '${escapeSingle(contextText)}' }).getByRole('${escapeSingle(role)}', { name: '${escapeSingle(name)}' })`
        : `page.getByRole('${escapeSingle(containerRole)}').filter({ hasText: '${escapeSingle(contextText)}' }).getByRole('${escapeSingle(role)}', { name: '${escapeSingle(name)}' })`,
    });
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
    .filter((candidate) => CANDIDATE_TIE_BREAKER.includes(candidate.kind))
    .sort(compareCandidateSuitability);
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
  if (candidate.kind === "contextual") return 1;
  if (candidate.kind === "role" && candidate.suitability === "form_accessible_role") return 1;
  if (candidate.kind === "text") return 2;
  if (candidate.kind === "placeholder") return 3;
  if (candidate.kind === "testid") return 4;
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
