import readline from "node:readline";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const [, , startUrl, storageStatePath, channel = ""] = process.argv;
const AUTO_SAVE_TIMEOUT_MS = 120_000;
const AUTO_SAVE_STABLE_MS = 2_500;
const AUTO_SAVE_POLL_MS = 1_000;
const LOGIN_FAILURE_PATTERN = /账号或密码错误|密码错误|验证码错误|登录失败|登陆失败|认证失败|invalid password|incorrect password|invalid credentials|login failed|sign in failed/i;
const LOGIN_PENDING_PATTERN = /验证码|动态码|短信码|二次验证|安全验证|选择租户|选择企业|mfa|otp|captcha|verification code|two-factor|2fa/i;
const LOGGED_IN_PATTERN = /退出登录|注销|个人中心|用户中心|用户菜单|我的|控制台|工作台|管理后台|dashboard|logout|sign out|profile|account center/i;
const LOGIN_URL_PATTERN = /login|signin|sign-in|auth|passport|account\/login|user\/login|登录|登陆/i;

if (isDirectRun()) {
  if (!startUrl || !storageStatePath) {
    console.error("Usage: node manual-auth-session.mjs <startUrl> <storageStatePath> [channel]");
    process.exit(2);
  }

  const browser = await chromium.launch({
    channel: channel || undefined,
    headless: false,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    ignoreHTTPSErrors: true,
  });
  let browserClosed = false;
  browser.on("disconnected", () => {
    browserClosed = true;
  });
  let completed = false;

  const stopAutofillCredentials = startCredentialAutofill(context, {
    password: process.env.AI_TESTING_LOGIN_PASSWORD || "",
    username: process.env.AI_TESTING_LOGIN_USERNAME || "",
  });
  const stopAutoSaveOnLoginSuccess = startAutoSaveOnLoginSuccess(context, {
    onSaved: () => {
      completed = true;
      rl.close();
    },
    startUrl,
    storageStatePath,
  });
  context.on("page", (page) => trackPageLifecycle({ browser, browserClosed: () => browserClosed, context, page }));

  const page = await context.newPage();
  await page.goto(startUrl, { waitUntil: "domcontentloaded" }).catch(() => {});

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });
  browser.on("disconnected", () => rl.close());

  for await (const line of rl) {
    const command = line.trim().toLowerCase();
    if (command === "save") {
      await context.storageState({ path: storageStatePath });
      completed = true;
      break;
    }
    if (command === "cancel") {
      completed = true;
      break;
    }
  }

  stopAutoSaveOnLoginSuccess();
  stopAutofillCredentials();
  await browser.close().catch(() => {});
  process.exit(completed ? 0 : 1);
}

export function startAutoSaveOnLoginSuccess(context, options) {
  const storageStatePath = options?.storageStatePath;
  if (!storageStatePath) {
    return () => {};
  }

  const startUrl = options?.startUrl || "";
  const timeoutMs = options?.timeoutMs ?? AUTO_SAVE_TIMEOUT_MS;
  const stableMs = options?.stableMs ?? AUTO_SAVE_STABLE_MS;
  const pollMs = options?.pollMs ?? AUTO_SAVE_POLL_MS;
  const onSaved = typeof options?.onSaved === "function" ? options.onSaved : () => {};
  const startedAt = Date.now();
  let stableSince = 0;
  let saving = false;

  const timer = setInterval(async () => {
    if (saving) {
      return;
    }
    if (Date.now() - startedAt > timeoutMs) {
      clearInterval(timer);
      return;
    }

    const state = await collectAuthDetectionState(context, startUrl).catch(() => null);
    if (!state) {
      return;
    }
    const result = evaluateLoginSuccessSignals(state);
    if (!result.success) {
      stableSince = 0;
      return;
    }
    stableSince ||= Date.now();
    if (Date.now() - stableSince < stableMs) {
      return;
    }

    saving = true;
    clearInterval(timer);
    await context.storageState({ path: storageStatePath });
    onSaved(result);
  }, pollMs);

  return () => clearInterval(timer);
}

export function evaluateLoginSuccessSignals(state) {
  const url = state?.url || "";
  const title = state?.title || "";
  const bodyText = state?.bodyText || "";
  const storageItemCount = Number(state?.storageItemCount || 0);
  const cookieCount = Number(state?.cookieCount || 0);
  const visiblePasswordInputs = Number(state?.visiblePasswordInputs || 0);
  const visibleLoginButtons = Number(state?.visibleLoginButtons || 0);
  const navigationChanged = Boolean(state?.navigationChanged);
  const haystack = `${url}\n${title}\n${bodyText}`;
  const stillLooksLikeLogin = LOGIN_URL_PATTERN.test(url) || /登录|登陆|sign in|login/i.test(title);
  const hasFailureSignal = LOGIN_FAILURE_PATTERN.test(haystack);
  const hasPendingHumanSignal = LOGIN_PENDING_PATTERN.test(haystack);
  const hasLoggedInSignal = LOGGED_IN_PATTERN.test(bodyText);
  const hasStoredAuth = cookieCount > 0 || storageItemCount > 0;

  let score = 0;
  const reasons = [];
  if (hasFailureSignal) {
    return { reasons: ["failure_signal"], score: -5, success: false };
  }
  if (hasPendingHumanSignal && visiblePasswordInputs === 0 && !hasLoggedInSignal) {
    return { reasons: ["pending_human_signal"], score: -5, success: false };
  }
  if (!stillLooksLikeLogin && visiblePasswordInputs === 0) {
    score += 3;
    reasons.push("left_login_page_without_password_input");
  }
  if (hasLoggedInSignal) {
    score += 3;
    reasons.push("logged_in_ui_signal");
  }
  if (hasStoredAuth && visiblePasswordInputs === 0 && !stillLooksLikeLogin) {
    score += 3;
    reasons.push("stored_auth_off_login_page");
  }
  if (navigationChanged) {
    score += 1;
    reasons.push("navigation_changed");
  }
  if (visibleLoginButtons === 0 && visiblePasswordInputs === 0) {
    score += 1;
    reasons.push("login_controls_absent");
  }
  if (visiblePasswordInputs > 0) {
    score -= 5;
    reasons.push("password_input_visible");
  }
  if (stillLooksLikeLogin && !hasLoggedInSignal) {
    score -= 2;
    reasons.push("still_looks_like_login");
  }

  return { reasons, score, success: score >= 5 };
}

async function collectAuthDetectionState(context, startUrl) {
  const pages = context.pages().filter((page) => !page.isClosed());
  const page = pages.at(-1);
  if (!page) {
    return null;
  }
  const storageState = await context.storageState().catch(() => ({ cookies: [], origins: [] }));
  const storageItemCount = (storageState.origins || []).reduce(
    (total, origin) => total + (origin.localStorage || []).length,
    0,
  );
  const bodyText = await page.locator("body").innerText({ timeout: 300 }).catch(() => "");
  const visiblePasswordInputs = await countVisible(page, passwordSelector());
  const visibleLoginButtons = await countVisible(page, loginButtonSelector());
  const url = page.url();
  return {
    bodyText: bodyText.slice(0, 4000),
    cookieCount: (storageState.cookies || []).length,
    navigationChanged: normalizeComparableUrl(url) !== normalizeComparableUrl(startUrl),
    storageItemCount,
    title: await page.title().catch(() => ""),
    url,
    visibleLoginButtons,
    visiblePasswordInputs,
  };
}

export function startCredentialAutofill(context, credentials) {
  const username = credentials?.username || "";
  const password = credentials?.password || "";
  if (!username || !password) {
    return () => {};
  }

  const timers = new Set();
  const startPageAutofill = (page) => {
    if (page.isClosed()) {
      return;
    }
    let attempts = 0;
    void autofillCredentials(page, username, password).catch(() => {});
    const timer = setInterval(() => {
      attempts += 1;
      if (attempts > 120 || page.isClosed()) {
        clearInterval(timer);
        timers.delete(timer);
        return;
      }
      void autofillCredentials(page, username, password).catch(() => {});
    }, 1000);
    timers.add(timer);
  };

  for (const page of context.pages()) {
    startPageAutofill(page);
  }
  context.on("page", startPageAutofill);

  return () => {
    for (const timer of timers) {
      clearInterval(timer);
    }
    timers.clear();
  };
}

export async function autofillCredentials(page, username, password) {
  for (const scope of credentialScopes(page)) {
    await fillFirstBlank(scope, usernameSelector(), username);
    await fillFirstBlank(scope, passwordSelector(), password);
  }
}

async function fillFirstBlank(scope, selector, value) {
  const locator = scope.locator(selector);
  const count = Math.min(await locator.count().catch(() => 0), 25);
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    const visible = await candidate.isVisible({ timeout: 100 }).catch(() => false);
    const editable = await candidate.isEditable({ timeout: 100 }).catch(() => false);
    if (!visible || !editable) {
      continue;
    }
    const currentValue = await candidate.inputValue({ timeout: 100 }).catch(() => null);
    if (currentValue === value) {
      return true;
    }
    if (currentValue === "") {
      await candidate.fill(value, { timeout: 500 }).catch(() => {});
      return true;
    }
  }
  return false;
}

function credentialScopes(page) {
  const frames = typeof page.frames === "function" ? page.frames() : [];
  return [page, ...frames];
}

function usernameSelector() {
  return [
    'input[type="email"]',
    'input[type="tel"]',
    'input[autocomplete="username"]',
    'input[autocomplete="email"]',
    'input[autocomplete="tel"]',
    'input[name*="user" i]',
    'input[id*="user" i]',
    'input[name*="account" i]',
    'input[id*="account" i]',
    'input[name*="email" i]',
    'input[id*="email" i]',
    'input[name*="phone" i]',
    'input[id*="phone" i]',
    'input[name*="mobile" i]',
    'input[id*="mobile" i]',
    'input[aria-label*="账号" i]',
    'input[aria-label*="用户" i]',
    'input[aria-label*="邮箱" i]',
    'input[aria-label*="手机" i]',
    'input[placeholder*="账号" i]',
    'input[placeholder*="用户" i]',
    'input[placeholder*="邮箱" i]',
    'input[placeholder*="手机" i]',
    'input[type="text"]',
    "textarea",
  ].join(", ");
}

function passwordSelector() {
  return [
    'input[type="password"]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="password"]',
    'input[name*="password" i]',
    'input[id*="password" i]',
    'input[aria-label*="密码" i]',
    'input[placeholder*="密码" i]',
  ].join(", ");
}

function loginButtonSelector() {
  return [
    'button:has-text("登录")',
    'button:has-text("登陆")',
    'button:has-text("Sign in")',
    'button:has-text("Login")',
    'input[type="submit"]',
    '[role="button"]:has-text("登录")',
    '[role="button"]:has-text("登陆")',
    '[role="button"]:has-text("Sign in")',
    '[role="button"]:has-text("Login")',
  ].join(", ");
}

async function countVisible(page, selector) {
  const scopes = credentialScopes(page);
  let total = 0;
  for (const scope of scopes) {
    const locator = scope.locator(selector);
    const count = Math.min(await locator.count().catch(() => 0), 50);
    for (let index = 0; index < count; index += 1) {
      if (await locator.nth(index).isVisible({ timeout: 50 }).catch(() => false)) {
        total += 1;
      }
    }
  }
  return total;
}

function normalizeComparableUrl(value) {
  try {
    const url = new URL(value);
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  } catch {
    return String(value || "").replace(/#.*$/, "").replace(/\/$/, "");
  }
}

function trackPageLifecycle({ browser, browserClosed, context, page }) {
  page.on("close", async () => {
    if (!browserClosed() && context.pages().every((candidate) => candidate.isClosed())) {
      await browser.close().catch(() => {});
    }
  });
}

function isDirectRun() {
  return process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
}
