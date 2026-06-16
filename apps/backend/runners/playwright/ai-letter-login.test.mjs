import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { tmpdir } from "node:os";

import { chromium } from "playwright";

import {
  collectLoginFormElements,
  ensureAgreementWithPlan,
  ensureUserAgreementChecked,
  fillCaptchaWithPlan,
  fillCaptchaValue,
  fillCredentialsWithPlan,
  isLikelyCaptchaImageBox,
  isSmsCaptchaText,
  isValidCaptchaElement,
  loadLoginPlan,
  loginPageReadiness,
  locateCaptchaTarget,
  locateGraphicCaptchaInput,
  normalizeLoginPlan,
  saveLoginPlan,
  runAiLetterLogin,
  submitLoginForm,
  validateLoginPlan,
} from "./ai-letter-login.mjs";

describe("ai letter login helpers", () => {
  it("locates captcha image near login form", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <img src="https://example.test/captcha.png" alt="验证码" width="120" height="40" />
        <input placeholder="请输入验证码" />
      `);

      const target = await locateCaptchaTarget(page);
      assert.ok(target);
    } finally {
      await browser.close();
    }
  });

  it("locates verify-code base64 captcha near graphic captcha input", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <input type="text" placeholder="账号" />
          <input type="password" placeholder="密码" />
          <div style="display:flex;gap:8px;align-items:center;">
            <input type="text" placeholder="请输入图形验证码" />
            <img class="verify-code" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" width="133" height="40" alt="" />
          </div>
          <input type="text" placeholder="请输入短信验证码" />
          <button type="button">登录</button>
        </form>
      `);

      const target = await locateCaptchaTarget(page);
      assert.ok(target);
      assert.equal(await target.evaluate((element) => element.className), "verify-code");
      const graphicInput = await locateGraphicCaptchaInput(page);
      assert.ok(graphicInput);
      const filled = await fillCaptchaValue(page, "AB12");
      assert.equal(filled, true);
      assert.equal(await page.locator('input[placeholder="请输入图形验证码"]').inputValue(), "AB12");
      assert.equal(await page.locator('input[placeholder="请输入短信验证码"]').inputValue(), "");
    } finally {
      await browser.close();
    }
  });

  it("ignores dialog buttons and prefers verify-code captcha", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <input type="text" placeholder="请输入图形验证码" />
          <img class="verify-code" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==" width="120" height="40" alt="" />
          <button type="button">登录</button>
        </form>
        <div role="dialog">
          <button style="width:120px;height:40px;">同意并继续</button>
          <button style="width:120px;height:40px;">取消</button>
        </div>
      `);

      const target = await locateCaptchaTarget(page);
      assert.ok(target);
      assert.equal(await target.evaluate((element) => element.tagName.toLowerCase()), "img");
      assert.equal(await isValidCaptchaElement(target), true);
    } finally {
      await browser.close();
    }
  });

  it("checks user agreement before login click", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <label><input type="checkbox" id="agreement" /> 我已阅读并同意《用户协议》和《隐私政策》</label>
          <button type="button">登录</button>
        </form>
      `);

      assert.equal(await page.locator("#agreement").isChecked(), false);
      assert.equal(await ensureUserAgreementChecked(page), true);
      assert.equal(await page.locator("#agreement").isChecked(), true);

      let clicked = false;
      await page.locator("button").evaluate((button) => {
        button.addEventListener("click", () => {
          button.dataset.clicked = "1";
        });
      });
      assert.equal(await submitLoginForm(page), true);
      clicked = await page.locator("button").evaluate((button) => button.dataset.clicked === "1");
      assert.equal(clicked, true);
    } finally {
      await browser.close();
    }
  });

  it("checks custom aria checkbox agreement container", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <div style="display:flex;align-items:center;gap:8px;">
            <span id="agreement-box" class="uui-checkbox" role="checkbox" aria-checked="false" tabindex="0"></span>
            <span>我已阅读并同意《用户协议》和《隐私政策》</span>
          </div>
          <button type="button">登录</button>
        </form>
        <script>
          document.getElementById("agreement-box").addEventListener("click", (event) => {
            const target = event.currentTarget;
            target.setAttribute("aria-checked", target.getAttribute("aria-checked") === "true" ? "false" : "true");
          });
        </script>
      `);

      assert.equal(await page.locator('[role="checkbox"]').getAttribute("aria-checked"), "false");
      assert.equal(await ensureUserAgreementChecked(page), true);
      assert.equal(await page.locator('[role="checkbox"]').getAttribute("aria-checked"), "true");
    } finally {
      await browser.close();
    }
  });

  it("clicks visual checkbox next to policy text", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <div id="app">
            <div class="login-wrap">
              <input placeholder="请输入邮箱/手机号" />
              <input placeholder="请输入密码" type="password" />
              <input placeholder="请输入图形验证码" />
              <button type="button">登录</button>
              <div class="policy">
                <img id="policy-check" src="data:image/svg+xml,%3csvg%20width='40'%20height='40'%20xmlns='http://www.w3.org/2000/svg'%3e%3c/svg%3e" />
                <span class="mr4">我已阅读并同意</span>
                <a>《用户协议》</a>
                <span>和</span>
                <a>《隐私政策》</a>
              </div>
            </div>
          </div>
          <script>
            document.getElementById("policy-check").addEventListener("click", (event) => {
              event.currentTarget.dataset.checked = "1";
            });
          </script>
        </form>
      `);

      assert.equal(await ensureUserAgreementChecked(page), true);
      assert.equal(await page.locator("#policy-check").getAttribute("data-checked"), "1");
    } finally {
      await browser.close();
    }
  });

  it("does not toggle visual policy checkbox back off", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <div class="policy">
            <img id="policy-check" src="data:image/svg+xml,%3csvg%20width='40'%20height='40'%20xmlns='http://www.w3.org/2000/svg'%3e%3c/svg%3e" />
            <span class="mr4">我已阅读并同意</span>
            <a>《用户协议》</a>
            <span>和</span>
            <a>《隐私政策》</a>
          </div>
          <script>
            document.getElementById("policy-check").addEventListener("click", (event) => {
              event.currentTarget.dataset.checked = event.currentTarget.dataset.checked === "1" ? "0" : "1";
            });
          </script>
        </form>
      `);

      assert.equal(await ensureUserAgreementChecked(page), true);
      assert.equal(await page.locator("#policy-check").getAttribute("data-checked"), "1");
      assert.equal(await ensureUserAgreementChecked(page), true);
      assert.equal(await page.locator("#policy-check").getAttribute("data-checked"), "1");
    } finally {
      await browser.close();
    }
  });

  it("does not collect broad login containers as agreement candidates", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <div id="app">
          <div class="login-wrap">
            账号密码 | 短信验证 账号 密码 验证码 忘记密码? 登录
            <div class="policy">
              <img src="data:image/svg+xml,%3csvg%3e%3c/svg%3e" />
              <span>我已阅读并同意</span>
              <a>《用户协议》</a>
              <span>和</span>
              <a>《隐私政策》</a>
            </div>
          </div>
        </div>
      `);

      const elements = await collectLoginFormElements(page);
      const agreementTexts = elements.filter((item) => item.kind === "agreement").map((item) => item.text);

      assert.ok(agreementTexts.some((text) => text.includes("我已阅读并同意")));
      assert.ok(!agreementTexts.some((text) => text.includes("账号密码")));
    } finally {
      await browser.close();
    }
  });

  it("uses text descriptor agreement locators instead of brittle div indexes", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <div class="login-wrap">
          <div>|</div>
          <div class="policy">
            <img src="data:image/svg+xml,%3csvg%3e%3c/svg%3e" />
            <span>我已阅读并同意</span>
            <a>《用户协议》</a>
            <span>和</span>
            <a>《隐私政策》</a>
          </div>
        </div>
      `);

      const elements = await collectLoginFormElements(page);
      const policy = elements.find((item) => item.kind === "agreement" && item.class_name === "policy");

      assert.ok(policy);
      assert.equal(policy.stable_selector, "div.policy");
      assert.deepEqual(policy.locator, { type: "text", value: "我已阅读并同意" });
    } finally {
      await browser.close();
    }
  });

  it("falls back when planned agreement selector points at non-agreement text", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <div id="wrong-target">|</div>
          <label><input id="agreement" type="checkbox" /> 我已阅读并同意《用户协议》和《隐私政策》</label>
        </form>
      `);

      const checked = await ensureAgreementWithPlan(page, {
        strategy: "planned",
        captcha_image_selector: "img.verify-code",
        captcha_input_selector: "#captcha",
        agreement_selector: "#wrong-target",
      });

      assert.equal(checked, true);
      assert.equal(await page.locator("#agreement").isChecked(), true);
    } finally {
      await browser.close();
    }
  });

  it("does not treat agreement text click as checked unless a control changes", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <div class="policy">
            <img id="policy-check" src="data:image/svg+xml,%3csvg%20width='40'%20height='40'%20xmlns='http://www.w3.org/2000/svg'%3e%3c/svg%3e" />
            <span class="mr4">我已阅读并同意</span>
            <a>《用户协议》</a>
            <span>和</span>
            <a>《隐私政策》</a>
          </div>
          <script>
            document.querySelector(".mr4").addEventListener("click", (event) => {
              event.currentTarget.dataset.textClicked = "1";
            });
            document.getElementById("policy-check").addEventListener("click", (event) => {
              event.currentTarget.dataset.checked = "1";
            });
          </script>
        </form>
      `);

      const checked = await ensureAgreementWithPlan(page, {
        strategy: "planned",
        captcha_image_selector: "img.verify-code",
        captcha_input_selector: "#captcha",
        agreement_locator: { type: "text", value: "我已阅读并同意" },
      });

      assert.equal(checked, true);
      assert.equal(await page.locator(".mr4").getAttribute("data-text-clicked"), "1");
      assert.equal(await page.locator("#policy-check").getAttribute("data-checked"), "1");
    } finally {
      await browser.close();
    }
  });

  it("collects login form elements with stable selectors", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <input type="text" placeholder="请输入图形验证码" />
          <img class="verify-code" src="data:image/png;base64,abc" width="120" height="40" />
          <label><input type="checkbox" /> 我已阅读并同意《用户协议》</label>
          <button type="button">登录</button>
        </form>
      `);

      const elements = await collectLoginFormElements(page);
      assert.ok(elements.length >= 4);
      assert.ok(elements.some((item) => item.placeholder.includes("图形验证码")));
      assert.ok(elements.some((item) => item.class_name === "verify-code"));
      assert.ok(elements.every((item) => item.selector.includes("data-ai-testing-login-el")));
      assert.ok(elements.every((item) => item.stable_selector));
      assert.ok(elements.some((item) => item.stable_selector === 'input[placeholder="请输入图形验证码"]'));
      assert.ok(
        elements.some(
          (item) =>
            item.placeholder === "请输入图形验证码" &&
            item.locator?.type === "placeholder" &&
            item.locator?.value === "请输入图形验证码",
        ),
      );
      assert.ok(
        elements.some(
          (item) =>
            item.text.includes("我已阅读并同意") &&
            item.locator?.type === "text" &&
            item.locator?.value === "我已阅读并同意",
        ),
      );
    } finally {
      await browser.close();
    }
  });

  it("normalizes and reloads saved login plan without sensitive values", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <input name="username" />
          <input name="password" type="password" />
          <input name="captcha" />
          <img class="verify-code" src="data:image/png;base64,abc" width="120" height="40" />
          <label><input type="checkbox" /> 我已阅读并同意《用户协议》</label>
          <button type="button">登录</button>
        </form>
      `);
      const dir = mkdtempSync(join(tmpdir(), "ai-letter-login-"));
      const planPath = join(dir, "login-plan.json");
      const saved = await saveLoginPlan(
        page,
        planPath,
        normalizeLoginPlan({
          strategy: "planned",
          username_selector: 'input[name="username"]',
          password_selector: 'input[name="password"]',
          captcha_image_selector: "img.verify-code",
          captcha_input_selector: 'input[name="captcha"]',
          agreement_selector: "label",
          login_button_selector: "button",
        }),
        "https://example.test/login",
      );

      assert.equal(saved, true);
      const raw = readFileSync(planPath, "utf8");
      assert.doesNotMatch(raw, /secret|ABCD|token/i);
      const plan = loadLoginPlan(planPath);
      assert.equal(plan.strategy, "planned");
      assert.equal(plan.username_selector, 'input[name="username"]');
      assert.equal(plan.password_selector, 'input[name="password"]');
      assert.equal(plan.site_url, "https://example.test/login");
      assert.equal(plan.dom_fingerprint.element_count > 0, true);
    } finally {
      await browser.close();
    }
  });

  it("marks saved plans invalid when a critical selector is missing", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <input name="username" />
        <input name="password" type="password" />
        <input name="captcha" />
        <button type="button">登录</button>
      `);

      const result = await validateLoginPlan(
        page,
        normalizeLoginPlan({
          strategy: "planned",
          username_locator: { type: "css", value: 'input[name="username"]' },
          password_locator: { type: "css", value: 'input[name="password"]' },
          captcha_image_locator: { type: "css", value: "img.verify-code" },
          captcha_input_locator: { type: "css", value: 'input[name="captcha"]' },
          login_button_locator: { type: "role", role: "button", name: "登录" },
        }),
      );

      assert.equal(result.valid, false);
      assert.equal(result.reason, "captcha_image_selector_not_visible");
    } finally {
      await browser.close();
    }
  });

  it("uses descriptor locators in saved login plans", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <form>
          <input placeholder="请输入邮箱/手机号" />
          <input placeholder="请输入密码" type="password" />
          <input placeholder="请输入图形验证码" />
          <img class="verify-code" src="data:image/png;base64,abc" width="120" height="40" />
          <label><input type="checkbox" /> 我已阅读并同意《用户协议》</label>
          <button type="button">登录</button>
        </form>
      `);

      const plan = normalizeLoginPlan({
        strategy: "planned",
        username_locator: { type: "placeholder", value: "请输入邮箱/手机号" },
        password_locator: { type: "placeholder", value: "请输入密码" },
        captcha_image_locator: { type: "css", value: "img.verify-code" },
        captcha_input_locator: { type: "placeholder", value: "请输入图形验证码" },
        agreement_locator: { type: "label", value: "我已阅读并同意" },
        login_button_locator: { type: "role", role: "button", name: "登录" },
      });

      assert.equal((await validateLoginPlan(page, plan)).valid, true);
      assert.equal(await fillCredentialsWithPlan(page, plan, "tester@example.com", "secret123"), true);
      assert.equal(await fillCaptchaWithPlan(page, plan, "AB12"), true);
      assert.equal(await ensureAgreementWithPlan(page, plan), true);
      assert.equal(await page.getByPlaceholder("请输入图形验证码").inputValue(), "AB12");
    } finally {
      await browser.close();
    }
  });

  it("reports login page not ready when observation has no elements", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`<body></body>`);

      const readiness = await loginPageReadiness(page, []);

      assert.equal(readiness.ready, false);
      assert.equal(readiness.reason, "login_page_not_ready");
    } finally {
      await browser.close();
    }
  });

  it("filters sms captcha fields", () => {
    assert.equal(isSmsCaptchaText("请输入短信验证码"), true);
    assert.equal(isSmsCaptchaText("请输入图形验证码"), false);
  });

  it("accepts typical captcha image dimensions", () => {
    assert.equal(isLikelyCaptchaImageBox({ width: 133, height: 40, x: 0, y: 0 }), true);
    assert.equal(isLikelyCaptchaImageBox({ width: 1280, height: 720, x: 0, y: 0 }), false);
    assert.equal(isLikelyCaptchaImageBox({ width: 120, height: 40, x: 0, y: 0 }), true);
    assert.equal(isLikelyCaptchaImageBox({ width: 40, height: 40, x: 0, y: 0 }), false);
  });

  it("fills captcha input with provided value", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`<input placeholder="请输入验证码" />`);

      const filled = await fillCaptchaValue(page, "AB12");
      assert.equal(filled, true);
      assert.equal(await page.locator('input[placeholder="请输入验证码"]').inputValue(), "AB12");
    } finally {
      await browser.close();
    }
  });

  it("continues past post-submit agreement modal", async () => {
    const html = `
      <form>
        <input id="username" placeholder="请输入邮箱/手机号" />
        <input id="password" type="password" placeholder="请输入密码" />
        <input id="captcha" placeholder="请输入图形验证码" />
        <img id="captcha-img" class="verify-code" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAHgAAAAkCAIAAADNSmkJAAABKUlEQVR4nO3YwQ2AMAwDQQv7/5e3gWg2dFjJ2lFv1h1wqf5kQAAAAAAAAAAAAAAAAAAAAAAAPwB6W7c7hG0T6o0J8f2r1rQ0k6jXx2b1K4tGQ1m6s0x2W4Yf6pS5j2mQm9v3x0l6t5Wq8wQAAAAAAAAAAAAAAAAAAAAAAAPgkV2o2zvYv8m8MZ0mK8tq7w1Pp8vW1mQm6w5sN6h3o1XwWmYv8s2cNQAAAAAAAAAAAAAAAAAAAAAAAB4b7n9mY0T8h0qY8pQvQd0QAAAAAAAAAAAAAAAAAAAAAAAD4A6k5j2c3m5mY8wAAAABJRU5ErkJggg==" width="120" height="40" />
        <label id="agreement-label"><input id="agreement" type="checkbox" /> 我已阅读并同意《用户协议》和《隐私政策》</label>
        <button id="login-btn" type="button">登录</button>
      </form>
      <div id="modal" role="dialog" hidden>
        <p>友情提示 我已阅读并同意《用户协议》和《隐私政策》</p>
        <button id="confirm-btn">同意并继续</button>
        <button id="cancel-btn">取消</button>
      </div>
      <script>
        document.getElementById("login-btn").addEventListener("click", () => {
          const agreement = document.getElementById("agreement");
          const captcha = document.getElementById("captcha");
          if (agreement.checked && captcha.value === "AB12") {
            document.getElementById("modal").hidden = false;
          }
        });
        document.getElementById("confirm-btn").addEventListener("click", () => {
          document.body.innerHTML = "<div>退出登录</div>";
          history.pushState({}, "", "/home");
        });
        document.getElementById("cancel-btn").addEventListener("click", () => {
          document.getElementById("modal").hidden = true;
        });
      </script>
    `;
    const server = createServer((_request, response) => {
      response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      response.end(html);
    });
    try {
      await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
      const { port } = server.address();

      const dir = mkdtempSync(join(tmpdir(), "ai-letter-login-"));
      const storageStatePath = join(dir, "storage-state.json");
      const result = await runAiLetterLogin({
        startUrl: `http://127.0.0.1:${port}/login`,
        storageStatePath,
        channel: "chrome",
        username: "tester",
        password: "secret123",
        maxAttempts: 1,
        waitForLoginFormPlan: async () => ({
          type: "login_form_plan",
          strategy: "planned",
          username_locator: { type: "placeholder", value: "请输入邮箱/手机号" },
          password_locator: { type: "placeholder", value: "请输入密码" },
          captcha_image_locator: { type: "css", value: "#captcha-img" },
          captcha_input_locator: { type: "placeholder", value: "请输入图形验证码" },
          agreement_locator: { type: "label", value: "我已阅读并同意" },
          login_button_locator: { type: "role", role: "button", name: "登录" },
        }),
        waitForAnswer: async () => "AB12",
      });

      assert.equal(result.success, true);
    } finally {
      await new Promise((resolve) => server.close(resolve));
    }
  });
});
