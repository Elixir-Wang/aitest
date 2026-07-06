/**
 * Parse the small Playwright locator expression subset accepted by page
 * exploration tools.
 *
 * The accepted grammar intentionally mirrors the locators we ask the agent to
 * use: page/getBy* bases, page.locator CSS fallback, chained filter(), child
 * getBy* calls, and explicit and/or composition. We do not eval arbitrary JS.
 */

const BASE_METHODS = new Set([
  "getByRole",
  "getByLabel",
  "getByTestId",
  "getByText",
  "getByPlaceholder",
  "getByAltText",
  "getByTitle",
  "locator",
]);

const CHAIN_METHODS = new Set([
  ...BASE_METHODS,
  "filter",
  "and",
  "or",
]);

export function parsePlaywrightLocatorString(page, expr) {
  const trimmed = String(expr || "").trim();
  if (!trimmed || !isParseableLocatorString(trimmed)) {
    return null;
  }
  try {
    return parseLocatorChain(page, page, trimmed);
  } catch {
    return null;
  }
}

export function isParseableLocatorString(expr) {
  const trimmed = String(expr || "").trim();
  if (!trimmed) {
    return false;
  }
  if (/^(?:page\.)?(?:getByRole|getByLabel|getByTestId|getByText|getByPlaceholder|getByAltText|getByTitle|locator)\(/.test(trimmed)) {
    return true;
  }
  if (/^(?:page\.)?(?:getByRole|getByLabel|getByTestId|getByText|getByPlaceholder|getByAltText|getByTitle|locator)\([^)]*\)\./.test(trimmed)) {
    return true;
  }
  return false;
}

function parseLocatorChain(page, scope, expr) {
  const segments = splitChain(expr);
  if (segments[0] === "page") {
    segments.shift();
  }
  if (!segments.length) {
    return null;
  }

  let locator = null;
  for (const segment of segments) {
    const call = parseMethodCall(segment);
    if (!call || !CHAIN_METHODS.has(call.method)) {
      return null;
    }

    if (!locator) {
      if (!BASE_METHODS.has(call.method)) {
        return null;
      }
      locator = applyLocatorMethod(scope, call);
      continue;
    }

    if (call.method === "filter") {
      locator = locator.filter(parseFilterOptions(page, call.args));
    } else if (call.method === "and") {
      locator = locator.and(parseLocatorChain(page, page, call.args));
    } else if (call.method === "or") {
      locator = locator.or(parseLocatorChain(page, page, call.args));
    } else {
      locator = applyLocatorMethod(locator, call);
    }
  }
  return locator;
}

function applyLocatorMethod(scope, call) {
  if (!scope || typeof scope[call.method] !== "function") {
    throw new Error(`Unsupported locator method: ${call.method}`);
  }
  if (call.method === "getByRole") {
    const [role, rest] = parseFirstString(call.args);
    return scope.getByRole(role, parseOptions(rest));
  }
  if (call.method === "getByLabel") {
    const [label, rest] = parseFirstString(call.args);
    return scope.getByLabel(label, parseOptions(rest));
  }
  if (call.method === "getByTestId") {
    const [testId] = parseFirstString(call.args);
    return scope.getByTestId(testId);
  }
  if (call.method === "getByText") {
    const [text, rest] = parseFirstString(call.args);
    return scope.getByText(text, parseOptions(rest));
  }
  if (call.method === "getByPlaceholder") {
    const [placeholder, rest] = parseFirstString(call.args);
    return scope.getByPlaceholder(placeholder, parseOptions(rest));
  }
  if (call.method === "getByAltText") {
    const [alt, rest] = parseFirstString(call.args);
    return scope.getByAltText(alt, parseOptions(rest));
  }
  if (call.method === "getByTitle") {
    const [title, rest] = parseFirstString(call.args);
    return scope.getByTitle(title, parseOptions(rest));
  }
  if (call.method === "locator") {
    const [selector] = parseFirstString(call.args);
    return scope.locator(selector);
  }
  throw new Error(`Unsupported locator method: ${call.method}`);
}

function splitChain(expr) {
  const segments = [];
  let current = "";
  let quote = "";
  let escaped = false;
  let parens = 0;
  let braces = 0;
  for (const char of String(expr)) {
    if (quote) {
      current += char;
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        quote = "";
      }
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      current += char;
      continue;
    }
    if (char === "(") parens += 1;
    if (char === ")") parens -= 1;
    if (char === "{") braces += 1;
    if (char === "}") braces -= 1;
    if (char === "." && parens === 0 && braces === 0) {
      if (current.trim()) {
        segments.push(current.trim());
      }
      current = "";
      continue;
    }
    current += char;
  }
  if (current.trim()) {
    segments.push(current.trim());
  }
  return segments;
}

function parseMethodCall(segment) {
  const match = String(segment || "").trim().match(/^([A-Za-z_][A-Za-z0-9_]*)\(([\s\S]*)\)$/);
  if (!match) {
    return null;
  }
  return { method: match[1], args: match[2].trim() };
}

function parseFirstString(args) {
  const source = String(args || "").trim();
  const quote = source[0];
  if (quote !== "'" && quote !== '"') {
    throw new Error("Locator argument must start with a string literal.");
  }
  let value = "";
  let escaped = false;
  for (let index = 1; index < source.length; index += 1) {
    const char = source[index];
    if (escaped) {
      value += char;
      escaped = false;
      continue;
    }
    if (char === "\\") {
      escaped = true;
      continue;
    }
    if (char === quote) {
      return [value, source.slice(index + 1).trim().replace(/^,/, "").trim()];
    }
    value += char;
  }
  throw new Error("Unterminated string literal.");
}

function parseOptions(body) {
  const opts = {};
  const normalized = stripOuterObject(String(body || "").trim());
  if (!normalized) return opts;

  const name = extractStringProperty(normalized, "name");
  if (name !== null) opts.name = name;

  const exact = extractBooleanProperty(normalized, "exact");
  if (exact !== null) opts.exact = exact;

  const level = extractNumberProperty(normalized, "level");
  if (level !== null) opts.level = level;

  return opts;
}

function parseFilterOptions(page, args) {
  const body = stripOuterObject(String(args || "").trim());
  if (!body) {
    return {};
  }
  const options = {};
  const hasText = extractStringProperty(body, "hasText");
  if (hasText !== null) {
    options.hasText = hasText;
  }
  const hasLocatorExpr = extractLocatorProperty(body, "has");
  if (hasLocatorExpr) {
    options.has = parseLocatorChain(page, page, hasLocatorExpr);
  }
  const visible = extractBooleanProperty(body, "visible");
  if (visible !== null) {
    options.visible = visible;
  }
  return options;
}

function stripOuterObject(value) {
  const trimmed = value.trim();
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    return trimmed.slice(1, -1).trim();
  }
  return trimmed;
}

function extractStringProperty(body, key) {
  const match = body.match(new RegExp(`${key}\\s*:\\s*(['"])((?:\\\\.|(?!\\1).)*)\\1`));
  return match ? match[2].replace(/\\(['"\\])/g, "$1") : null;
}

function extractBooleanProperty(body, key) {
  const match = body.match(new RegExp(`${key}\\s*:\\s*(true|false)`));
  return match ? match[1] === "true" : null;
}

function extractNumberProperty(body, key) {
  const match = body.match(new RegExp(`${key}\\s*:\\s*(\\d+)`));
  return match ? Number(match[1]) : null;
}

function extractLocatorProperty(body, key) {
  const prefix = body.match(new RegExp(`${key}\\s*:\\s*`));
  if (!prefix) {
    return "";
  }
  const start = prefix.index + prefix[0].length;
  return readExpressionUntilTopLevelComma(body.slice(start)).trim();
}

function readExpressionUntilTopLevelComma(source) {
  let quote = "";
  let escaped = false;
  let parens = 0;
  let braces = 0;
  let result = "";
  for (const char of source) {
    if (quote) {
      result += char;
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        quote = "";
      }
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      result += char;
      continue;
    }
    if (char === "(") parens += 1;
    if (char === ")") parens -= 1;
    if (char === "{") braces += 1;
    if (char === "}") braces -= 1;
    if (char === "," && parens === 0 && braces === 0) {
      break;
    }
    result += char;
  }
  return result;
}
