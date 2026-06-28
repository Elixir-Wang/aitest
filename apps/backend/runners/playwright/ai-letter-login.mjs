import readline from "node:readline";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

import {
  autofillCredentials,
  collectAuthDetectionState,
  evaluateLoginSuccessSignals,
  startCredentialAutofill,
} from "./manual-auth-session.mjs";

const LOGIN_FAILURE_PATTERN =
  /账号或密码错误|密码错误|验证码错误|登录失败|登陆失败|认证失败|invalid password|incorrect password|invalid credentials|login failed|sign in failed/i;

const SMS_CAPTCHA_PATTERN = /短信|sms|phone|mobile|动态码|otp/i;
const AGREEMENT_TEXT_PATTERN = /用户协议|隐私政策|服务协议|我已阅读|terms of service|privacy policy|user agreement/i;
const MODAL_DISMISS_PATTERN = /同意并继续|我知道了|关闭|取消|确定/i;

export function captchaInputSelector() {
  return [
    'input[name*="captcha" i]',
    'input[id*="captcha" i]',
    'input[name*="verify" i]',
    'input[id*="verify" i]',
    'input[name*="code" i]',
    'input[id*="code" i]',
    'input[placeholder*="图形验证码" i]',
    'input[placeholder*="图片验证码" i]',
    'input[placeholder*="验证码" i]',
    'input[aria-label*="图形验证码" i]',
    'input[aria-label*="验证码" i]',
    'input[placeholder*="校验码" i]',
    'input[aria-label*="校验码" i]',
  ].join(", ");
}

export function captchaImageSelector() {
  return [
    "img.verify-code",
    'img[class*="verify-code" i]',
    'img[class*="verify_code" i]',
    'img[class*="verifycode" i]',
    'img[class*="captcha" i]',
    'img[class*="vcode" i]',
    'img[class*="validcode" i]',
    'img[src*="captcha" i]',
    'img[src*="verify" i]',
    'img[src*="kaptcha" i]',
    'img[src*="validcode" i]',
    'img[src^="data:image" i]',
    'img[alt*="验证码" i]',
    'img[title*="验证码" i]',
    "canvas",
  ].join(", ");
}

function credentialScopes(page) {
  const frames = typeof page.frames === "function" ? page.frames() : [];
  return [page, ...frames.filter((frame) => frame !== page.mainFrame())];
}

export async function collectLoginFormElements(page) {
  return page.evaluate(() => {
    const clean = (value, limit = 120) => String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
    const cssEscape = (value) => {
      if (window.CSS?.escape) {
        return window.CSS.escape(value);
      }
      return String(value).replace(/["\\]/g, "\\$&");
    };
    const attrSelector = (element, attr) => {
      const value = element.getAttribute(attr);
      if (!value) {
        return "";
      }
      return `${element.tagName.toLowerCase()}[${attr}="${cssEscape(value)}"]`;
    };
    const locatorFor = (element, kind, text) => {
      const tag = element.tagName.toLowerCase();
      const role = element.getAttribute("role") || "";
      const placeholder = clean(element.getAttribute("placeholder"));
      const ariaLabel = clean(element.getAttribute("aria-label"));
      const title = clean(element.getAttribute("title"));
      const testId = clean(element.getAttribute("data-testid") || element.getAttribute("data-test"));
      const labelText = clean(
        element.getAttribute("aria-label") ||
          element.getAttribute("title") ||
          element.getAttribute("placeholder") ||
          element.innerText ||
          element.textContent,
      );

      if (kind === "agreement") {
        return {
          type: "text",
          value: "我已阅读并同意",
        };
      }
      if (testId) {
        return { type: "testid", value: testId };
      }
      if (role && labelText) {
        return { type: "role", role, name: labelText };
      }
      if (ariaLabel) {
        return { type: "label", value: ariaLabel };
      }
      if (placeholder) {
        return { type: "placeholder", value: placeholder };
      }
      if (title) {
        return { type: "text", value: title };
      }
      if (tag === "button" && text) {
        return { type: "role", role: "button", name: clean(text, 80) };
      }
      return { type: "css", value: stableSelectorFor(element) };
    };
    const stableSelectorFor = (element) => {
      const tag = element.tagName.toLowerCase();
      if (element.id) {
        return `#${cssEscape(element.id)}`;
      }
      for (const attr of ["data-testid", "data-test", "name", "aria-label", "placeholder", "alt", "title"]) {
        const selector = attrSelector(element, attr);
        if (selector && element.ownerDocument.querySelectorAll(selector).length === 1) {
          return selector;
        }
      }
      const classNames = Array.from(element.classList || []).filter(Boolean).slice(0, 3);
      if (classNames.length) {
        const selector = `${tag}.${classNames.map(cssEscape).join(".")}`;
        if (element.ownerDocument.querySelectorAll(selector).length === 1) {
          return selector;
        }
      }
      const parent = element.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter((item) => item.tagName === element.tagName);
        const index = siblings.indexOf(element) + 1;
        const parentSelector = parent.id ? `#${cssEscape(parent.id)}` : parent.tagName.toLowerCase();
        return `${parentSelector} > ${tag}:nth-of-type(${index})`;
      }
      return tag;
    };
    const visible = (element) => {
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.visibility !== "hidden" && style.display !== "none" && rect.width > 0 && rect.height > 0;
    };
    const isNarrowAgreementText = (text) => {
      if (!/我已阅读|read and agree|accept.*terms/i.test(text)) {
        return false;
      }
      if (text.length > 120) {
        return false;
      }
      if (/账号|密码|验证码|登录|注册|短信验证/.test(text)) {
        return false;
      }
      return true;
    };
    const elements = [];
    const seen = new Set();
    let sequence = 0;
    const addElement = (element) => {
      if (!element || seen.has(element) || !visible(element)) {
        return;
      }
      seen.add(element);
      sequence += 1;
      const elementId = `login-el-${sequence}`;
      element.setAttribute("data-ai-testing-login-el", elementId);
      const tag = element.tagName.toLowerCase();
      const className = clean(element.className, 80);
      const text = clean(element.innerText || element.textContent, 80);
      let kind = tag;
      if (tag === "input" && (element.getAttribute("type") || "").toLowerCase() === "checkbox") {
        kind = "checkbox";
      } else if (/checkbox/i.test(className) || element.getAttribute("role") === "checkbox") {
        kind = "checkbox";
      } else if (isNarrowAgreementText(text) && tag !== "a") {
        kind = "agreement";
      }
      const stableSelector = stableSelectorFor(element);
      elements.push({
        element_id: elementId,
        tag,
        kind,
        role: element.getAttribute("role") || tag,
        type: element.getAttribute("type") || "",
        class_name: className,
        name: clean(element.getAttribute("name")),
        placeholder: clean(element.getAttribute("placeholder")),
        aria_label: clean(element.getAttribute("aria-label")),
        aria_checked: element.getAttribute("aria-checked") || "",
        text,
        src: tag === "img" ? clean(element.getAttribute("src"), 120) : "",
        selector: `[data-ai-testing-login-el="${elementId}"]`,
        stable_selector: stableSelector,
        locator: locatorFor(element, kind, text),
      });
    };

    const interactiveSelector = [
      "input",
      "button",
      "img",
      "label",
      "a",
      "[role='button']",
      "[role='checkbox']",
      "[class*='checkbox' i]",
      "[aria-checked]",
    ].join(", ");
    document.querySelectorAll(interactiveSelector).forEach((element) => addElement(element));

    document.querySelectorAll("label, div, span, p").forEach((element) => {
      const text = clean(element.innerText || element.textContent, 200);
      if (!isNarrowAgreementText(text)) {
        return;
      }
      if (/^《.+》$/.test(text)) {
        return;
      }
      addElement(element);
    });

    return elements;
  });
}

export async function observeLoginPage(page, storageDir) {
  mkdirSync(storageDir, { recursive: true });
  await dismissBlockingDialogs(page);
  await waitForCaptchaSurface(page);
  const pageImagePath = `${storageDir}/login-page.png`;
  await page.screenshot({ path: pageImagePath, fullPage: true }).catch(() => {});
  const elements = await collectLoginFormElements(page);
  const elementsPath = `${storageDir}/login-elements.json`;
  writeFileSync(elementsPath, `${JSON.stringify(elements, null, 2)}\n`, "utf8");
  return { pageImagePath, elementsPath, elements };
}

export async function loginPageReadiness(page, elements) {
  if (Array.isArray(elements) && elements.length > 0) {
    return { ready: true };
  }
  const state = await page
    .evaluate(() => ({
      body_text: String(document.body?.innerText || "").trim().slice(0, 500),
      title: document.title,
      url: window.location.href,
    }))
    .catch(() => ({ body_text: "", title: "", url: "" }));
  return {
    ready: false,
    reason: "login_page_not_ready",
    ...state,
  };
}

export function isPlannedLoginForm(plan) {
  return Boolean(
    plan &&
      plan.strategy === "planned" &&
      (plan.captcha_image_locator || plan.captcha_image_selector) &&
      (plan.captcha_input_locator || plan.captcha_input_selector),
  );
}

function normalizeLocatorDescriptor(value, fallbackSelector = "") {
  if (value && typeof value === "object" && value.type) {
    return {
      ...value,
      type: String(value.type || "").toLowerCase(),
    };
  }
  if (fallbackSelector) {
    return { type: "css", value: String(fallbackSelector) };
  }
  return null;
}

export function normalizeLoginPlan(plan) {
  if (!plan || plan.strategy !== "planned") {
    return { strategy: "heuristic" };
  }
  const usernameLocator = normalizeLocatorDescriptor(plan.username_locator, plan.username_selector);
  const passwordLocator = normalizeLocatorDescriptor(plan.password_locator, plan.password_selector);
  const captchaImageLocator = normalizeLocatorDescriptor(plan.captcha_image_locator, plan.captcha_image_selector);
  const captchaInputLocator = normalizeLocatorDescriptor(plan.captcha_input_locator, plan.captcha_input_selector);
  const agreementLocator = normalizeLocatorDescriptor(plan.agreement_locator, plan.agreement_selector);
  const loginButtonLocator = normalizeLocatorDescriptor(plan.login_button_locator, plan.login_button_selector);
  return {
    version: Number(plan.version || 1),
    strategy: "planned",
    site_url: String(plan.site_url || ""),
    username_locator: usernameLocator,
    password_locator: passwordLocator,
    captcha_image_locator: captchaImageLocator,
    captcha_input_locator: captchaInputLocator,
    agreement_locator: agreementLocator,
    login_button_locator: loginButtonLocator,
    username_selector: String(plan.username_selector || usernameLocator?.value || ""),
    password_selector: String(plan.password_selector || passwordLocator?.value || ""),
    captcha_image_selector: String(plan.captcha_image_selector || captchaImageLocator?.value || ""),
    captcha_input_selector: String(plan.captcha_input_selector || captchaInputLocator?.value || ""),
    agreement_selector: String(plan.agreement_selector || agreementLocator?.value || ""),
    login_button_selector: String(plan.login_button_selector || loginButtonLocator?.value || ""),
    has_agreement_checkbox: Boolean(plan.has_agreement_checkbox || agreementLocator || plan.agreement_selector),
    created_from: String(plan.created_from || "successful_login"),
    created_at: String(plan.created_at || new Date().toISOString()),
    dom_fingerprint: plan.dom_fingerprint || {},
  };
}

export function locatorFromDescriptor(scope, descriptor, fallbackSelector = "") {
  const normalized = normalizeLocatorDescriptor(descriptor, fallbackSelector);
  if (!normalized) {
    return null;
  }
  const value = String(normalized.value || "");
  const name = normalized.name === undefined ? value : normalized.name;
  switch (normalized.type) {
    case "role":
      if (!normalized.role) return null;
      return scope.getByRole(String(normalized.role), name ? { name } : undefined);
    case "label":
      return value ? scope.getByLabel(value) : null;
    case "placeholder":
      return value ? scope.getByPlaceholder(value) : null;
    case "text":
      return value ? scope.getByText(value) : null;
    case "testid":
    case "test-id":
      return value ? scope.getByTestId(value) : null;
    case "title":
      return value ? scope.getByTitle(value) : null;
    case "css":
      return value ? scope.locator(value) : null;
    default:
      return fallbackSelector ? scope.locator(fallbackSelector) : null;
  }
}

export function loadLoginPlan(loginPlanPath) {
  if (!loginPlanPath || !existsSync(loginPlanPath)) {
    return null;
  }
  try {
    return normalizeLoginPlan(JSON.parse(readFileSync(loginPlanPath, "utf8")));
  } catch {
    return null;
  }
}

export async function saveLoginPlan(page, loginPlanPath, plan, startUrl) {
  if (!loginPlanPath || !isPlannedLoginForm(plan)) {
    return false;
  }
  const fingerprint = await page
    .evaluate(() => ({
      host: window.location.host,
      title: document.title,
      element_count: document.querySelectorAll("input, button, img, canvas, [role='button'], [role='checkbox']").length,
    }))
    .catch(() => ({}));
  const payload = normalizeLoginPlan({
    ...plan,
    site_url: startUrl,
    created_from: "successful_login",
    created_at: new Date().toISOString(),
    dom_fingerprint: fingerprint,
  });
  mkdirSync(dirname(loginPlanPath), { recursive: true });
  writeFileSync(loginPlanPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return true;
}

export async function validateLoginPlan(page, plan) {
  if (!isPlannedLoginForm(plan)) {
    return { valid: false, reason: "not_planned" };
  }
  const checks = [
    ["username_locator", "username_selector", "editable"],
    ["password_locator", "password_selector", "editable"],
    ["captcha_image_locator", "captcha_image_selector", "visible"],
    ["captcha_input_locator", "captcha_input_selector", "editable"],
    ["login_button_locator", "login_button_selector", "visible"],
  ];
  for (const [locatorField, selectorField, expectation] of checks) {
    const locator = locatorFromDescriptor(page, plan[locatorField], plan[selectorField])?.first();
    if (!locator) {
      return { valid: false, reason: `${selectorField}_missing` };
    }
    // 🔧 修复：验证码图片可能是异步加载的，增加等待时间到5秒
    const timeout = selectorField === "captcha_image_selector" ? 5000 : 300;
    const ok =
      expectation === "editable"
        ? await locator.isEditable({ timeout }).catch(() => false)
        : await locator.isVisible({ timeout }).catch(() => false);
    if (!ok) {
      return { valid: false, reason: `${selectorField}_not_${expectation}` };
    }
  }
  return { valid: true };
}

export async function fillCredentialsWithPlan(page, plan, username, password) {
  if (!isPlannedLoginForm(plan)) {
    return false;
  }
  const usernameInput = locatorFromDescriptor(page, plan.username_locator, plan.username_selector)?.first();
  const passwordInput = locatorFromDescriptor(page, plan.password_locator, plan.password_selector)?.first();
  if (!usernameInput || !passwordInput) {
    return false;
  }
  if (!(await usernameInput.isEditable({ timeout: 300 }).catch(() => false))) {
    return false;
  }
  if (!(await passwordInput.isEditable({ timeout: 300 }).catch(() => false))) {
    return false;
  }
  await usernameInput.fill(username, { timeout: 1000 }).catch(() => {});
  await passwordInput.fill(password, { timeout: 1000 }).catch(() => {});
  return true;
}

export async function locateCaptchaWithPlan(page, plan) {
  if (isPlannedLoginForm(plan)) {
    const candidate = locatorFromDescriptor(page, plan.captcha_image_locator, plan.captcha_image_selector)?.first();
    if (candidate && (await candidate.isVisible({ timeout: 300 }).catch(() => false)) && (await isValidCaptchaElement(candidate))) {
      return candidate;
    }
  }
  return locateCaptchaTarget(page);
}

export async function fillCaptchaWithPlan(page, plan, value) {
  if (isPlannedLoginForm(plan)) {
    const input = locatorFromDescriptor(page, plan.captcha_input_locator, plan.captcha_input_selector)?.first();
    if (input && (await input.isVisible({ timeout: 300 }).catch(() => false))) {
      await input.fill(value, { timeout: 1000 }).catch(() => {});
      return (await input.inputValue({ timeout: 300 }).catch(() => "")) === value;
    }
  }
  return fillCaptchaValue(page, value);
}

export async function expectedCaptchaLengthWithPlan(page, plan) {
  if (isPlannedLoginForm(plan)) {
    const input = locatorFromDescriptor(page, plan.captcha_input_locator, plan.captcha_input_selector)?.first();
    const expectedLength = await expectedCaptchaLengthForInput(input);
    if (expectedLength) {
      return expectedLength;
    }
  }
  for (const scope of credentialScopes(page)) {
    const input = await locateGraphicCaptchaInput(scope);
    const expectedLength = await expectedCaptchaLengthForInput(input);
    if (expectedLength) {
      return expectedLength;
    }
  }
  return null;
}

async function expectedCaptchaLengthForInput(input) {
  if (!input) {
    return null;
  }
  const maxLength = Number(await input.getAttribute("maxlength").catch(() => ""));
  if (Number.isInteger(maxLength) && maxLength > 0 && maxLength <= 12) {
    return maxLength;
  }
  const pattern = String(await input.getAttribute("pattern").catch(() => "") || "");
  const exactRepeat = pattern.match(/\{(\d+)\}/);
  if (exactRepeat) {
    const length = Number(exactRepeat[1]);
    if (Number.isInteger(length) && length > 0 && length <= 12) {
      return length;
    }
  }
  return null;
}

/**
 * 简单直接地勾选协议复选框
 * @param {Page} page - Playwright page 对象
 * @returns {Promise<boolean>} 是否成功勾选
 */
export async function clickAgreementCheckbox(page) {
  try {
    // 方法1: 直接点击 .not-checked 元素（最有效）
    const notCheckedLocator = page.locator('.not-checked').first();
    const isVisible = await notCheckedLocator.isVisible({ timeout: 1000 }).catch(() => false);

    if (isVisible) {
      await notCheckedLocator.click();
      await page.waitForTimeout(300); // 🚀 从500ms降到300ms

      // 验证是否成功（检查是否出现SVG图标）
      const hasSVG = await page.evaluate(() => {
        return Boolean(document.querySelector('.policy svg'));
      });

      if (hasSVG) {
        return true;
      }
    }

    // 方法2: 点击 .check-box 容器
    const checkBoxLocator = page.locator('.check-box').first();
    const isCheckBoxVisible = await checkBoxLocator.isVisible({ timeout: 1000 }).catch(() => false);

    if (isCheckBoxVisible) {
      await checkBoxLocator.click();
      await page.waitForTimeout(300); // 🚀 从500ms降到300ms

      const hasSVG = await page.evaluate(() => {
        return Boolean(document.querySelector('.policy svg'));
      });

      if (hasSVG) {
        return true;
      }
    }

    // 方法3: 点击整个 .policy 区域
    const policyLocator = page.locator('.policy').first();
    const isPolicyVisible = await policyLocator.isVisible({ timeout: 1000 }).catch(() => false);

    if (isPolicyVisible) {
      await policyLocator.click();
      await page.waitForTimeout(300); // 🚀 从500ms降到300ms

      const hasSVG = await page.evaluate(() => {
        return Boolean(document.querySelector('.policy svg'));
      });

      return hasSVG;
    }

    return false;
  } catch (error) {
    console.error('勾选协议失败:', error.message);
    return false;
  }
}

export async function ensureAgreementWithPlan(page, plan) {
  // 🚀 优化：增加重试机制，确保协议勾选成功
  for (let attempt = 0; attempt < 3; attempt++) {
    const success = await clickAgreementCheckbox(page);

    // 双重验证：检查SVG和实际状态
    const isChecked = await page.evaluate(() => {
      const hasSVG = Boolean(document.querySelector('.policy svg'));
      const hasCheckedClass = !Boolean(document.querySelector('.not-checked'));
      return hasSVG || hasCheckedClass;
    }).catch(() => false);

    if (success || isChecked) {
      return true;
    }

    // 如果第一次失败，等待后重试
    if (attempt < 2) {
      await page.waitForTimeout(200);
    }
  }

  return false;
}

async function clickAgreementTarget(target) {
  const tag = await target.evaluate((element) => element.tagName.toLowerCase()).catch(() => "");
  if (tag === "input") {
    if (!(await target.isChecked({ timeout: 100 }).catch(() => false))) {
      await target.check({ force: true, timeout: 1000 }).catch(() => {});
    }
    return await target.isChecked({ timeout: 100 }).catch(() => false);
  }
  const ariaChecked = await target.getAttribute("aria-checked").catch(() => null);
  if (ariaChecked === "true") {
    return true;
  }
  await target.click({ force: true, timeout: 1000 }).catch(() => {});
  return await isAgreementSelected(target);
}

async function isAgreementSelected(target) {
  return target
    .evaluate((element) => {
      const hasSelectedControl = (candidate) => {
        if (!candidate) return false;
        if (candidate instanceof HTMLInputElement && candidate.type === "checkbox") {
          return candidate.checked;
        }
        if (candidate.getAttribute("aria-checked") === "true") {
          return true;
        }
        if (candidate.getAttribute("data-ai-testing-agreement-clicked") === "1") {
          return true;
        }
        return false;
      };

      if (hasSelectedControl(element)) {
        return true;
      }

      const roots = [
        element.closest("label"),
        element.closest("[role='checkbox']"),
        element.closest(".policy"),
        element.closest("div"),
        element.parentElement,
      ].filter(Boolean);

      for (const root of roots) {
        if (hasSelectedControl(root)) {
          return true;
        }
        const controls = root.querySelectorAll("input[type='checkbox'], [role='checkbox'], [aria-checked]");
        for (const control of controls) {
          if (hasSelectedControl(control)) {
            return true;
          }
        }
      }

      return false;
    })
    .catch(() => false);
}

async function clickVisualAgreementControl(container) {
  return container
    .evaluate((element) => {
      const root = element.closest(".policy, label, div") || element.parentElement || element;

      // 🔥 策略1: 查找真正的复选框输入框
      const realCheckbox = root.querySelector('input[type="checkbox"]');
      if (realCheckbox) {
        if (!realCheckbox.checked) {
          realCheckbox.click();
        }
        realCheckbox.setAttribute("data-ai-testing-agreement-clicked", "1");
        return true;
      }

      // 🔥 策略2: 查找 "not-checked" 元素（这才是真正的复选框！）
      const notCheckedEl = root.querySelector('.not-checked, [class*="not-checked"]');
      if (notCheckedEl) {
        const rect = notCheckedEl.getBoundingClientRect();
        // 验证是小尺寸元素
        if (rect.width >= 10 && rect.width <= 30 && rect.height >= 10 && rect.height <= 30) {
          notCheckedEl.click();
          notCheckedEl.setAttribute("data-ai-testing-agreement-clicked", "1");
          return true;
        }
      }

      // 🔥 策略3: 查找 check-box 容器内的第一个小元素
      const checkBoxContainer = root.querySelector('.check-box, .checkbox, [class*="check-box"]');
      if (checkBoxContainer) {
        // 查找容器内的小尺寸子元素（通常是复选框的视觉部分）
        const children = checkBoxContainer.querySelectorAll('span, div, i, svg');
        for (const child of children) {
          const rect = child.getBoundingClientRect();
          if (rect.width >= 10 && rect.width <= 30 && rect.height >= 10 && rect.height <= 30) {
            child.click();
            child.setAttribute("data-ai-testing-agreement-clicked", "1");
            return true;
          }
        }

        // 如果子元素没找到，点击容器本身
        checkBoxContainer.click();
        checkBoxContainer.setAttribute("data-ai-testing-agreement-clicked", "1");
        return true;
      }

      // 🔥 策略4: 查找 ARIA checkbox
      const ariaCheckbox = root.querySelector('[role="checkbox"]');
      if (ariaCheckbox) {
        ariaCheckbox.click();
        ariaCheckbox.setAttribute("data-ai-testing-agreement-clicked", "1");
        return true;
      }

      // 🔥 策略5: 通过位置和尺寸查找最左边的小方形元素
      const allSmallElements = root.querySelectorAll('div, span, i, p, svg');
      let leftmostCheckbox = null;
      let minLeft = Infinity;

      for (const el of allSmallElements) {
        const rect = el.getBoundingClientRect();

        // 必须是小方形（10-30px，接近正方形）
        if (rect.width >= 10 && rect.width <= 30 &&
            rect.height >= 10 && rect.height <= 30 &&
            Math.abs(rect.width - rect.height) < 10) {

          // 找到最左边的元素
          if (rect.left < minLeft) {
            minLeft = rect.left;
            leftmostCheckbox = el;
          }
        }
      }

      if (leftmostCheckbox) {
        leftmostCheckbox.click();
        leftmostCheckbox.setAttribute("data-ai-testing-agreement-clicked", "1");
        return true;
      }

      // 🔥 策略6: 最后兜底 - 点击整个容器
      element.click();
      element.setAttribute("data-ai-testing-agreement-clicked", "1");
      return true;
    })
    .catch(() => false);
}

export async function ensureUserAgreementChecked(page) {
  let checkedAny = false;

  for (const scope of credentialScopes(page)) {
    const customCheckboxes = scope.locator(
      '[class*="checkbox"][aria-checked="false"], [role="checkbox"][aria-checked="false"]',
    );
    const customCount = Math.min(await customCheckboxes.count().catch(() => 0), 10);
    for (let index = 0; index < customCount; index += 1) {
      const candidate = customCheckboxes.nth(index);
      const text = await candidate
        .evaluate((element) => {
          const root = element.closest("div, label, form") || element.parentElement;
          return (root?.textContent || element.textContent || "").slice(0, 200);
        })
        .catch(() => "");
      if (!AGREEMENT_TEXT_PATTERN.test(text)) {
        continue;
      }
      await candidate.click({ force: true, timeout: 1000 }).catch(() => {});
      await candidate
        .evaluate((element) => {
          if (element.getAttribute("aria-checked") !== "true") {
            element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
          }
        })
        .catch(() => {});
      if ((await candidate.getAttribute("aria-checked").catch(() => null)) === "true") {
        return true;
      }
      checkedAny = true;
    }
    if (checkedAny) {
      continue;
    }

    const containers = scope.locator("label, div, span, p").filter({
      hasText: /我已阅读|I have read and agree|accept the/i,
    });
    const containerCount = Math.min(await containers.count().catch(() => 0), 20);
    for (let index = 0; index < containerCount; index += 1) {
      const container = containers.nth(index);
      const text = (await container.innerText({ timeout: 100 }).catch(() => "")).trim();
      if (!AGREEMENT_TEXT_PATTERN.test(text)) {
        continue;
      }
      if (/^《.+》$/.test(text)) {
        continue;
      }
      if (await clickVisualAgreementControl(container)) {
        checkedAny = true;
        continue;
      }
      const checkbox = container.locator('input[type="checkbox"]').first();
      if ((await checkbox.count().catch(() => 0)) > 0) {
        if (!(await checkbox.isChecked({ timeout: 100 }).catch(() => false))) {
          await checkbox.check({ force: true, timeout: 1000 }).catch(() => container.click({ force: true }));
          checkedAny = true;
        }
        continue;
      }
      await container.click({ force: true, timeout: 1000 }).catch(() => {});
      checkedAny = true;
    }

    const labels = scope.locator("label");
    const labelCount = Math.min(await labels.count().catch(() => 0), 30);
    for (let index = 0; index < labelCount; index += 1) {
      const label = labels.nth(index);
      const text = (await label.innerText({ timeout: 100 }).catch(() => "")).trim();
      if (!AGREEMENT_TEXT_PATTERN.test(text)) {
        continue;
      }
      if (await clickAgreementTarget(label)) {
        checkedAny = true;
      }
    }

    const checkboxes = scope.locator('input[type="checkbox"]');
    const checkboxCount = Math.min(await checkboxes.count().catch(() => 0), 20);
    for (let index = 0; index < checkboxCount; index += 1) {
      const checkbox = checkboxes.nth(index);
      const meta = await checkbox
        .evaluate((element) => {
          const label = element.closest("label");
          const container = element.parentElement;
          const text = `${label?.innerText || ""} ${container?.innerText || ""}`.slice(0, 300);
          return {
            checked: element.checked,
            text,
          };
        })
        .catch(() => null);
      if (!meta || !AGREEMENT_TEXT_PATTERN.test(meta.text)) {
        continue;
      }
      if (!meta.checked) {
        await checkbox.check({ force: true, timeout: 1000 }).catch(() => {});
        checkedAny = true;
      }
    }
  }

  return checkedAny;
}

export async function submitLoginWithPlan(page, plan) {
  if (isPlannedLoginForm(plan) && (plan.login_button_locator || plan.login_button_selector)) {
    const button = locatorFromDescriptor(page, plan.login_button_locator, plan.login_button_selector)?.first();
    if (button && (await button.isVisible({ timeout: 300 }).catch(() => false))) {
      const text = (await button.innerText({ timeout: 100 }).catch(() => "")).trim();
      if (!/同意并继续|企业登录/.test(text)) {
        await button.click({ timeout: 2000 }).catch(() => {});
        return true;
      }
    }
  }
  return submitLoginForm(page);
}

export function isSmsCaptchaText(value) {
  return SMS_CAPTCHA_PATTERN.test(String(value || ""));
}

export function isLikelyCaptchaImageBox(box, viewport = { width: 1440, height: 1000 }) {
  if (!box) {
    return false;
  }
  if (box.width < 40 || box.height < 16) {
    return false;
  }
  if (box.width > 320 || box.height > 120) {
    return false;
  }
  if (box.width > viewport.width * 0.45 || box.height > viewport.height * 0.25) {
    return false;
  }
  const aspectRatio = box.width / box.height;
  if (aspectRatio < 1.2 || aspectRatio > 8) {
    return false;
  }
  return true;
}

export async function isValidCaptchaElement(candidate) {
  return candidate
    .evaluate((element) => {
      const tag = element.tagName.toLowerCase();
      if (tag !== "img" && tag !== "canvas") {
        return false;
      }
      if (element.closest("button, a, [role='button']")) {
        return false;
      }
      const dialog = element.closest("[role='dialog'], .el-dialog, .modal, .ant-modal");
      if (dialog) {
        const dialogText = (dialog.textContent || "").slice(0, 300);
        if (/同意并继续|隐私政策更新|用户协议更新|温馨提示/.test(dialogText) && !element.classList.contains("verify-code")) {
          return false;
        }
      }
      const rect = element.getBoundingClientRect();
      if (!rect.width || !rect.height) {
        return false;
      }
      const aspectRatio = rect.width / rect.height;
      if (aspectRatio < 1.2 || aspectRatio > 8) {
        return false;
      }
      if (tag === "canvas") {
        return true;
      }
      const className = String(element.className || "");
      const src = String(element.getAttribute("src") || "");
      if (/verify-code|captcha|vcode|validcode/i.test(className)) {
        return true;
      }
      if (/data:image|captcha|verify|kaptcha|validcode/i.test(src)) {
        return true;
      }
      const alt = String(element.getAttribute("alt") || "");
      const title = String(element.getAttribute("title") || "");
      if (/验证码|校验码|captcha/i.test(`${alt} ${title}`)) {
        return true;
      }
      return false;
    })
    .catch(() => false);
}

function captchaFieldText(candidate) {
  return [candidate.placeholder, candidate.name, candidate.id, candidate.ariaLabel].filter(Boolean).join(" ");
}

export async function locateGraphicCaptchaInput(scope) {
  const locator = scope.locator(captchaInputSelector());
  const count = Math.min(await locator.count().catch(() => 0), 20);
  let fallback = null;

  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (!(await candidate.isVisible({ timeout: 100 }).catch(() => false))) {
      continue;
    }
    if (!(await candidate.isEditable({ timeout: 100 }).catch(() => false))) {
      continue;
    }
    const meta = await candidate
      .evaluate((element) => ({
        ariaLabel: element.getAttribute("aria-label") || "",
        id: element.id || "",
        name: element.getAttribute("name") || "",
        placeholder: element.getAttribute("placeholder") || "",
      }))
      .catch(() => null);
    if (!meta) {
      continue;
    }
    const text = captchaFieldText(meta);
    if (isSmsCaptchaText(text)) {
      continue;
    }
    if (/图形|图片|graphic/i.test(text)) {
      return candidate;
    }
    fallback ||= candidate;
  }

  return fallback;
}

async function firstVisibleCaptchaImage(scope, selector) {
  const imageLocator = scope.locator(selector);
  const imageCount = Math.min(await imageLocator.count().catch(() => 0), 30);
  for (let index = 0; index < imageCount; index += 1) {
    const candidate = imageLocator.nth(index);
    if (!(await candidate.isVisible({ timeout: 100 }).catch(() => false))) {
      continue;
    }
    if (!(await isValidCaptchaElement(candidate))) {
      continue;
    }
    const box = await candidate.boundingBox().catch(() => null);
    if (!isLikelyCaptchaImageBox(box)) {
      continue;
    }
    return candidate;
  }
  return null;
}

export async function locateCaptchaImageNearInput(scope, input) {
  const marked = await input
    .evaluate((inputEl) => {
      const rect = inputEl.getBoundingClientRect();
      let best = null;
      let bestScore = Number.POSITIVE_INFINITY;

      for (const element of inputEl.ownerDocument.querySelectorAll("[data-ai-testing-captcha-img]")) {
        element.removeAttribute("data-ai-testing-captcha-img");
      }

      for (const img of inputEl.ownerDocument.querySelectorAll("img, canvas")) {
        if (img.closest("button, a, [role='button']")) {
          continue;
        }
        const dialog = img.closest("[role='dialog'], .el-dialog, .modal, .ant-modal");
        if (dialog) {
          const dialogText = (dialog.textContent || "").slice(0, 300);
          if (/同意并继续|隐私政策更新|用户协议更新|温馨提示/.test(dialogText) && !img.classList.contains("verify-code")) {
            continue;
          }
        }

        const imageRect = img.getBoundingClientRect();
        if (imageRect.width < 40 || imageRect.height < 16 || imageRect.width > 320 || imageRect.height > 120) {
          continue;
        }
        const aspectRatio = imageRect.width / imageRect.height;
        if (aspectRatio < 1.2 || aspectRatio > 8) {
          continue;
        }
        if (img.tagName.toLowerCase() === "img") {
          const className = String(img.className || "");
          const src = String(img.getAttribute("src") || "");
          const alt = String(img.getAttribute("alt") || "");
          const title = String(img.getAttribute("title") || "");
          const looksLikeCaptcha =
            /verify-code|captcha|vcode|validcode/i.test(className) ||
            /data:image|captcha|verify|kaptcha|validcode/i.test(src) ||
            /验证码|校验码|captcha/i.test(`${alt} ${title}`);
          if (!looksLikeCaptcha) {
            continue;
          }
        }

        const verticalDistance = Math.abs(imageRect.y + imageRect.height / 2 - (rect.y + rect.height / 2));
        if (verticalDistance > Math.max(rect.height, imageRect.height) * 2) {
          continue;
        }

        const horizontalDistance =
          imageRect.x >= rect.x
            ? imageRect.x - (rect.x + rect.width)
            : rect.x - (imageRect.x + imageRect.width);
        if (horizontalDistance > 280) {
          continue;
        }

        const distance = Math.hypot(imageRect.x - rect.x, imageRect.y - rect.y);
        const score = distance + (horizontalDistance < 0 ? 80 : 0);
        if (distance > 360 || score >= bestScore) {
          continue;
        }
        best = img;
        bestScore = score;
      }

      if (!best) {
        return false;
      }
      best.setAttribute("data-ai-testing-captcha-img", "1");
      return true;
    })
    .catch(() => false);

  if (!marked) {
    return null;
  }
  return scope.locator('[data-ai-testing-captcha-img="1"]').first();
}

export async function locateCaptchaTarget(page) {
  for (const scope of credentialScopes(page)) {
    const classBased = await firstVisibleCaptchaImage(
      scope,
      [
        "img.verify-code",
        'img[class*="verify-code" i]',
        'img[class*="verify_code" i]',
        'img[class*="captcha" i]',
      ].join(", "),
    );
    if (classBased) {
      return classBased;
    }

    const input = await locateGraphicCaptchaInput(scope);
    if (input) {
      const nearInput = await locateCaptchaImageNearInput(scope, input);
      if (nearInput && (await isValidCaptchaElement(nearInput))) {
        return nearInput;
      }
    }

    const semantic = await firstVisibleCaptchaImage(scope, captchaImageSelector());
    if (semantic) {
      return semantic;
    }
  }
  return null;
}

export async function fillCaptchaValue(page, value) {
  for (const scope of credentialScopes(page)) {
    const input = await locateGraphicCaptchaInput(scope);
    if (!input) {
      continue;
    }
    await input.fill(value, { timeout: 1000 }).catch(() => {});
    return (await input.inputValue({ timeout: 300 }).catch(() => "")) === value;
  }
  return false;
}

export async function dismissBlockingDialogs(page) {
  let clickedAny = false;
  for (const scope of credentialScopes(page)) {
    const dismissButtons = scope.locator("button, [role='button'], a").filter({
      hasText: MODAL_DISMISS_PATTERN,
    });
    const count = Math.min(await dismissButtons.count().catch(() => 0), 10);
    for (let index = 0; index < count; index += 1) {
      const button = dismissButtons.nth(index);
      const text = (await button.innerText({ timeout: 100 }).catch(() => "")).trim();
      if (!MODAL_DISMISS_PATTERN.test(text)) {
        continue;
      }
      if (/登录|login/i.test(text)) {
        continue;
      }
      if (await button.isVisible({ timeout: 100 }).catch(() => false)) {
        await button.click({ timeout: 1000 }).catch(() => {});
        clickedAny = true;
        await page.waitForTimeout(300);
      }
    }
  }
  await page.keyboard.press("Escape").catch(() => {});
  return clickedAny;
}

export async function refreshCaptchaImage(page) {
  for (const scope of credentialScopes(page)) {
    const captchaImage = scope
      .locator('img.verify-code, img[class*="verify-code" i], img[class*="captcha" i]')
      .first();
    if (!(await captchaImage.isVisible({ timeout: 200 }).catch(() => false))) {
      continue;
    }
    const previousSrc = await captchaImage.getAttribute("src").catch(() => "");
    await captchaImage.click({ timeout: 1000 }).catch(() => {});
    const startedAt = Date.now();
    // 🚀 优化：从2000ms降到1000ms
    while (Date.now() - startedAt < 1000) {
      const currentSrc = await captchaImage.getAttribute("src").catch(() => "");
      if (currentSrc && currentSrc !== previousSrc) {
        break;
      }
      await page.waitForTimeout(100); // 从150ms降到100ms，检查更频繁
    }
    await page.waitForTimeout(200); // 从300ms降到200ms
    return true;
  }
  return false;
}

export async function prepareNextCaptchaAttempt(page, plan = null) {
  await dismissBlockingDialogs(page);
  const input = isPlannedLoginForm(plan)
    ? locatorFromDescriptor(page, plan.captcha_input_locator, plan.captcha_input_selector)?.first()
    : await locateGraphicCaptchaInput(page);
  if (input) {
    await input.fill("", { timeout: 1000 }).catch(() => {});
  }
  await refreshCaptchaImage(page);
  await waitForCaptchaSurface(page);
}

export async function submitLoginForm(page) {
  const selectors = [
    'form button[type="submit"]:has-text("登录")',
    'form button[type="submit"]:has-text("登陆")',
    'form button:has-text("登录")',
    'form button:has-text("登陆")',
    'button[type="submit"]:has-text("登录")',
    'button[type="submit"]:has-text("登陆")',
    'button:has-text("登录"):not(:has-text("同意"))',
    'button:has-text("登陆"):not(:has-text("同意"))',
    'button:has-text("Sign in")',
    'button:has-text("Login")',
    'input[type="submit"]',
    '[role="button"]:has-text("登录")',
    '[role="button"]:has-text("登陆")',
  ];
  for (const selector of selectors) {
    const button = page.locator(selector).first();
    if (await button.isVisible({ timeout: 200 }).catch(() => false)) {
      const text = (await button.innerText({ timeout: 100 }).catch(() => "")).trim();
      if (/同意并继续|企业登录/.test(text)) {
        continue;
      }
      await button.click({ timeout: 2000 }).catch(() => {});
      return true;
    }
  }
  return false;
}

export async function detectLoginFailure(page) {
  const bodyText = await page.locator("body").innerText({ timeout: 500 }).catch(() => "");
  return LOGIN_FAILURE_PATTERN.test(bodyText);
}

async function collectAttemptDiagnostics(page, plan, answer) {
  const captchaInput = isPlannedLoginForm(plan)
    ? locatorFromDescriptor(page, plan.captcha_input_locator, plan.captcha_input_selector)?.first()
    : null;
  const agreement = isPlannedLoginForm(plan)
    ? locatorFromDescriptor(page, plan.agreement_locator, plan.agreement_selector)?.first()
    : null;
  const captchaInputValue = captchaInput ? await captchaInput.inputValue({ timeout: 200 }).catch(() => "") : "";
  const agreementText = agreement ? await agreement.innerText({ timeout: 200 }).catch(() => "") : "";
  return page
    .evaluate(
      ({ answerValue, captchaValue, agreementTextValue, agreementLocator }) => {
        const clean = (value, limit = 500) => String(value || "").trim().replace(/\s+/g, " ").slice(0, limit);
        const bodyText = clean(document.body?.innerText || "", 1200);
        const likelyMessages = Array.from(document.querySelectorAll("[class*='error' i], [class*='message' i], [class*='toast' i], [class*='tip' i], [role='alert']"))
          .map((element) => clean(element.innerText || element.textContent, 200))
          .filter(Boolean)
          .slice(0, 8);
        const clickedAgreement = document.querySelector('[data-ai-testing-agreement-clicked="1"]');
        const agreementChecked = Boolean(
          document.querySelector(
            [
              "input[type='checkbox']:checked",
              "[role='checkbox'][aria-checked='true']",
              "[data-ai-testing-agreement-clicked='1']",
            ].join(", "),
          ),
        );
        return {
          url: window.location.href,
          title: document.title,
          answer_length: String(answerValue || "").length,
          captcha_input_value: captchaValue,
          captcha_input_matches_answer: captchaValue === answerValue,
          agreement_locator: agreementLocator,
          agreement_text: clean(agreementTextValue, 200),
          agreement_clicked_marker: Boolean(clickedAgreement),
          agreement_aria_checked: clickedAgreement?.getAttribute("aria-checked") || "",
          agreement_checked: agreementChecked,
          likely_messages: likelyMessages,
          body_excerpt: bodyText,
        };
      },
      {
        answerValue: answer,
        captchaValue: captchaInputValue,
        agreementTextValue: agreementText,
        agreementLocator: isPlannedLoginForm(plan) ? plan.agreement_locator || null : null,
      },
    )
    .catch((error) => ({ error: String(error?.message || error || "diagnostics_failed") }));
}

export async function waitForLoginSuccess(context, startUrl, timeoutMs = 3000) {
  // 🚀 优化：从8秒降到3秒，失败时快速重试
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const state = await collectAuthDetectionState(context, startUrl).catch(() => null);
    if (state && evaluateLoginSuccessSignals(state).success) {
      return evaluateLoginSuccessSignals(state);
    }
    await new Promise((resolve) => setTimeout(resolve, 300)); // 从500ms降到300ms，更快响应
  }
  const state = await collectAuthDetectionState(context, startUrl).catch(() => null);
  return state ? evaluateLoginSuccessSignals(state) : { success: false, reasons: ["timeout"], score: -5 };
}

async function waitForCaptchaSurface(page) {
  // 🚀 优化：主动触发验证码加载
  // 通过聚焦输入框来触发懒加载的验证码
  try {
    const usernameInput = page.locator('input[type="text"], input[name*="user" i], input[name*="account" i]').first();
    if (await usernameInput.isVisible({ timeout: 500 }).catch(() => false)) {
      await usernameInput.focus({ timeout: 500 }).catch(() => {});
      await page.waitForTimeout(200); // 给懒加载一点时间
    }
  } catch {}

  // 🚀 优化：缩短超时从10秒到5秒
  await page
    .locator(
      [
        "img.verify-code",
        'img[class*="verify-code" i]',
        'input[placeholder*="图形验证码" i]',
        'input[placeholder*="验证码" i]',
        captchaImageSelector(),
      ].join(", "),
    )
    .first()
    .waitFor({ state: "visible", timeout: 5_000 })
    .catch(() => {});
  await page.waitForTimeout(300); // 从800ms降到300ms
}

function writeEvent(payload) {
  process.stdout.write(`${JSON.stringify(payload)}\n`);
}

function isDirectRun() {
  return process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
}

function createCommandReader() {
  const rl = readline.createInterface({
    input: process.stdin,
    crlfDelay: Infinity,
  });
  const answerWaiters = [];
  let planResolver = null;

  rl.on("line", (line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    let command;
    try {
      command = JSON.parse(trimmed);
    } catch {
      return;
    }
    if (command.type === "login_form_plan" && planResolver) {
      const resolve = planResolver;
      planResolver = null;
      resolve(command);
      return;
    }
    const waiter = answerWaiters.shift();
    if (waiter) {
      waiter(command);
    }
  });

  return {
    close() {
      rl.close();
    },
    waitForLoginFormPlan(timeoutMs = 120_000) {
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          planResolver = null;
          resolve({ type: "login_form_plan", strategy: "heuristic" });
        }, timeoutMs);
        planResolver = (command) => {
          clearTimeout(timeout);
          resolve(command);
        };
      });
    },
    waitForAnswer(expectedAttempt, _expectedLength = null, timeoutMs = 120_000) {
      return new Promise((resolve) => {
        const timeout = setTimeout(() => resolve(""), timeoutMs);
        answerWaiters.push((command) => {
          clearTimeout(timeout);
          if (command.type === "abort") {
            resolve("");
            return;
          }
          if (command.type !== "captcha_answer") {
            resolve("");
            return;
          }
          if (Number(command.attempt || 0) !== expectedAttempt) {
            resolve("");
            return;
          }
          resolve(String(command.value || "").trim());
        });
      });
    },
  };
}

export async function runAiLetterLogin({
  startUrl,
  storageStatePath,
  channel = "",
  username = "",
  password = "",
  maxAttempts = 3,
  onEvent = () => {},
  waitForLoginFormPlan = async () => ({ type: "login_form_plan", strategy: "heuristic" }),
  waitForAnswer = async () => "",
  loginPlanPath = "",
}) {
  mkdirSync(dirname(storageStatePath), { recursive: true });
  const authDir = dirname(storageStatePath);

  const browser = await chromium.launch({
    channel: channel || undefined,
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  const stopAutofill = startCredentialAutofill(context, { username, password });

  try {
    await page.goto(startUrl, { waitUntil: "domcontentloaded" }).catch(() => {});
    onEvent({ kind: "session_started", url: page.url() });
    let plan = loadLoginPlan(loginPlanPath);
    if (plan) {
      onEvent({ kind: "login_plan_loaded", path: loginPlanPath });
      const planValidation = await validateLoginPlan(page, plan);
      if (!planValidation.valid) {
        onEvent({ kind: "login_plan_invalid", reason: planValidation.reason });
        plan = null;
      }
    }

    if (!plan) {
      const observation = await observeLoginPage(page, authDir);
      onEvent({
        kind: "login_page_observed",
        url: page.url(),
        page_image_path: observation.pageImagePath,
        elements_path: observation.elementsPath,
        element_count: observation.elements.length,
      });
      const readiness = await loginPageReadiness(page, observation.elements);
      if (!readiness.ready) {
        onEvent({
          kind: "login_failed",
          reason: readiness.reason,
          page_image_path: observation.pageImagePath,
          elements_path: observation.elementsPath,
          readiness,
        });
        return { success: false, reason: readiness.reason };
      }
      plan = normalizeLoginPlan(await waitForLoginFormPlan());
    }

    if (!(await fillCredentialsWithPlan(page, plan, username, password))) {
      await autofillCredentials(page, username, password).catch(() => {});
    }

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      if (attempt > 1) {
        await prepareNextCaptchaAttempt(page, plan);
        if (!(await fillCredentialsWithPlan(page, plan, username, password))) {
          await autofillCredentials(page, username, password).catch(() => {});
        }
      } else {
        // 🚀 优化：第一次尝试时主动触发验证码加载
        await waitForCaptchaSurface(page);
      }

      const captchaTarget = await locateCaptchaWithPlan(page, plan);
      if (!captchaTarget) {
        const debugPath = `${authDir}/captcha-not-found-${attempt}.png`;
        await page.screenshot({ path: debugPath, fullPage: true }).catch(() => {});
        onEvent({ kind: "login_failed", reason: "captcha_not_found", attempt, debug_image_path: debugPath });
        return { success: false, reason: "captcha_not_found" };
      }

      const imagePath = `${authDir}/captcha-attempt-${attempt}.png`;
      mkdirSync(dirname(imagePath), { recursive: true });
      await captchaTarget.screenshot({ path: imagePath }).catch(() => {});
      const expectedLength = await expectedCaptchaLengthWithPlan(page, plan);
      onEvent({ kind: "captcha_challenge", attempt, image_path: imagePath, expected_length: expectedLength });

      const answer = await waitForAnswer(attempt, expectedLength);
      if (!answer) {
        onEvent({ kind: "login_failed", reason: "captcha_answer_missing", attempt });
        return { success: false, reason: "captcha_answer_missing" };
      }

      const filled = await fillCaptchaWithPlan(page, plan, answer);
      if (!filled) {
        onEvent({ kind: "login_attempt", attempt, result: "captcha_fill_failed" });
        continue;
      }

      const agreementHandled = await ensureAgreementWithPlan(page, plan);
      const submitted = await submitLoginWithPlan(page, plan);
      await page.waitForTimeout(1200);
      const postSubmitDialogHandled = await dismissBlockingDialogs(page);
      if (postSubmitDialogHandled) {
        await page.waitForTimeout(1200);
      }
      const afterSubmitImagePath = `${authDir}/login-attempt-${attempt}-after-submit.png`;
      await page.screenshot({ path: afterSubmitImagePath, fullPage: true }).catch(() => {});
      const diagnostics = await collectAttemptDiagnostics(page, plan, answer);
      onEvent({
        kind: "login_attempt_diagnostics",
        attempt,
        agreement_handled: agreementHandled,
        post_submit_dialog_handled: postSubmitDialogHandled,
        submitted,
        after_submit_image_path: afterSubmitImagePath,
        diagnostics,
      });

      if (await detectLoginFailure(page)) {
        onEvent({ kind: "login_attempt", attempt, result: "captcha_rejected" });
        continue;
      }

      const loginResult = await waitForLoginSuccess(context, startUrl);
      if (loginResult.success) {
        await context.storageState({ path: storageStatePath, indexedDB: true });
        if (await saveLoginPlan(page, loginPlanPath, plan, startUrl)) {
          onEvent({ kind: "login_plan_saved", path: loginPlanPath });
        }
        onEvent({ kind: "login_succeeded", attempt, reasons: loginResult.reasons || [] });
        return { success: true, attempt };
      }

      onEvent({ kind: "login_attempt", attempt, result: "login_not_confirmed" });
    }

    onEvent({ kind: "login_failed", reason: "captcha_exhausted" });
    return { success: false, reason: "captcha_exhausted" };
  } finally {
    stopAutofill();
    await browser.close().catch(() => {});
  }
}

if (isDirectRun()) {
  const [, , startUrl, storageStatePath, channel = "", loginPlanArg = ""] = process.argv;
  const maxAttempts = Number(process.env.AI_TESTING_CAPTCHA_MAX_ATTEMPTS || "3");
  const username = process.env.AI_TESTING_LOGIN_USERNAME || "";
  const password = process.env.AI_TESTING_LOGIN_PASSWORD || "";
  const loginPlanPath = loginPlanArg || process.env.AI_TESTING_LOGIN_PLAN_PATH || "";

  if (!startUrl || !storageStatePath) {
    console.error("Usage: node ai-letter-login.mjs <startUrl> <storageStatePath> [channel]");
    process.exit(2);
  }

  const commandReader = createCommandReader();
  const result = await runAiLetterLogin({
    startUrl,
    storageStatePath,
    channel,
    username,
    password,
    maxAttempts,
    loginPlanPath,
    onEvent: writeEvent,
    waitForLoginFormPlan: () => commandReader.waitForLoginFormPlan(),
    waitForAnswer: (attempt, expectedLength) => commandReader.waitForAnswer(attempt, expectedLength),
  });
  commandReader.close();
  process.exit(result.success ? 0 : 1);
}
