import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { chromium } from "playwright";

import { autofillCredentials, evaluateLoginSuccessSignals, startCredentialAutofill } from "./manual-auth-session.mjs";

describe("manual auth credential autofill", () => {
  it("fills phone-style username and password inputs", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <input type="tel" placeholder="请输入手机号" />
        <input type="password" placeholder="请输入密码" />
      `);

      await autofillCredentials(page, "13800000000", "secret123");

      assert.equal(await page.locator('input[type="tel"]').inputValue(), "13800000000");
      assert.equal(await page.locator('input[type="password"]').inputValue(), "secret123");
    } finally {
      await browser.close();
    }
  });

  it("skips hidden candidate inputs and fills the visible login form", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <input type="text" placeholder="账号" style="display: none" />
        <input type="password" placeholder="密码" style="display: none" />
        <input type="text" placeholder="请输入邮箱/手机号" />
        <input type="password" placeholder="请输入密码" />
      `);

      await autofillCredentials(page, "admin@example.com", "secret123");

      assert.equal(await page.locator('input[placeholder="请输入邮箱/手机号"]').inputValue(), "admin@example.com");
      assert.equal(await page.locator('input[placeholder="请输入密码"]').inputValue(), "secret123");
      assert.equal(await page.locator('input[placeholder="账号"]').inputValue(), "");
    } finally {
      await browser.close();
    }
  });

  it("fills credentials inside iframe login forms", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const page = await browser.newPage();
      await page.setContent(`
        <iframe srcdoc='
          <input type="text" placeholder="请输入邮箱/手机号" />
          <input type="password" placeholder="请输入密码" />
        '></iframe>
      `);

      await autofillCredentials(page, "admin@example.com", "secret123");

      const frame = page.frameLocator("iframe");
      assert.equal(await frame.locator('input[placeholder="请输入邮箱/手机号"]').inputValue(), "admin@example.com");
      assert.equal(await frame.locator('input[placeholder="请输入密码"]').inputValue(), "secret123");
    } finally {
      await browser.close();
    }
  });

  it("fills credentials on login pages opened after the initial page", async () => {
    const browser = await chromium.launch({ channel: "chrome", headless: true });
    try {
      const context = await browser.newContext();
      const stopAutofill = startCredentialAutofill(context, {
        password: "secret123",
        username: "admin",
      });
      try {
        const page = await context.newPage();
        await page.setContent(`
          <button onclick="window.open('about:blank', '_blank')">登录</button>
        `);
        const [loginPage] = await Promise.all([
          context.waitForEvent("page"),
          page.getByRole("button", { name: "登录" }).click(),
        ]);
        await loginPage.setContent(`
          <input placeholder="账号" />
          <input type="password" placeholder="密码" />
        `);

        await expectInputValue(loginPage.locator('input[placeholder="账号"]'), "admin");
        await expectInputValue(loginPage.locator('input[type="password"]'), "secret123");
      } finally {
        stopAutofill();
      }
    } finally {
      await browser.close();
    }
  });
});

describe("manual auth login success detection", () => {
  it("accepts a high-confidence post-login page", () => {
    const result = evaluateLoginSuccessSignals({
      bodyText: "控制台 我的 退出登录",
      cookieCount: 2,
      navigationChanged: true,
      storageItemCount: 1,
      title: "工作台",
      url: "https://example.test/dashboard",
      visibleLoginButtons: 0,
      visiblePasswordInputs: 0,
    });

    assert.equal(result.success, true);
    assert.ok(result.score >= 5);
  });

  it("rejects pages that still show password inputs", () => {
    const result = evaluateLoginSuccessSignals({
      bodyText: "登录",
      cookieCount: 2,
      navigationChanged: false,
      storageItemCount: 0,
      title: "登录",
      url: "https://example.test/login",
      visibleLoginButtons: 1,
      visiblePasswordInputs: 1,
    });

    assert.equal(result.success, false);
  });

  it("rejects failure and pending-human states", () => {
    assert.equal(
      evaluateLoginSuccessSignals({
        bodyText: "账号或密码错误",
        cookieCount: 0,
        navigationChanged: false,
        storageItemCount: 0,
        title: "登录",
        url: "https://example.test/login",
        visibleLoginButtons: 1,
        visiblePasswordInputs: 1,
      }).success,
      false,
    );
    assert.equal(
      evaluateLoginSuccessSignals({
        bodyText: "请输入短信验证码",
        cookieCount: 1,
        navigationChanged: true,
        storageItemCount: 0,
        title: "安全验证",
        url: "https://example.test/verify",
        visibleLoginButtons: 0,
        visiblePasswordInputs: 0,
      }).success,
      false,
    );
  });
});

async function expectInputValue(locator, expected) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if ((await locator.inputValue().catch(() => "")) === expected) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  assert.equal(await locator.inputValue(), expected);
}
