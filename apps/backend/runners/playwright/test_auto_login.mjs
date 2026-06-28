#!/usr/bin/env node
/**
 * 无头模式自动化登录测试
 * 自动识别验证码，无需手动输入
 */
import { chromium } from "playwright";
import { execSync } from "child_process";
import { existsSync } from "fs";
import {
  collectLoginFormElements,
  ensureAgreementWithPlan,
  normalizeLoginPlan,
  fillCredentialsWithPlan,
  locateCaptchaWithPlan,
  fillCaptchaWithPlan,
  submitLoginWithPlan,
} from "./ai-letter-login.mjs";

// 使用 ddddocr 识别验证码
function recognizeCaptcha(imagePath) {
  try {
    const pythonScript = `
import sys
import ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)
with open("${imagePath}", "rb") as f:
    result = ocr.classification(f.read())
print(result, end="")
`;
    const result = execSync(`python3 -c '${pythonScript}'`, { encoding: 'utf8' });
    return result.trim();
  } catch (error) {
    console.error("验证码识别失败:", error.message);
    return null;
  }
}

async function autoLogin() {
  console.log("="*80);
  console.log("🤖 自动化登录测试 - 无头模式");
  console.log("="*80);

  const username = process.env.AI_TESTING_LOGIN_USERNAME;
  const password = process.env.AI_TESTING_LOGIN_PASSWORD;

  if (!username || !password) {
    console.log("\n❌ 请设置环境变量:");
    console.log("   export AI_TESTING_LOGIN_USERNAME='your_username'");
    console.log("   export AI_TESTING_LOGIN_PASSWORD='your_password'");
    return;
  }

  const browser = await chromium.launch({
    headless: true,  // 无头模式
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });

  const page = await context.newPage();

  try {
    console.log("\n1️⃣ 访问登录页...");
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    console.log("✅ 页面加载完成");

    console.log("\n2️⃣ 分析页面元素...");
    const elements = await collectLoginFormElements(page);
    console.log(`✅ 找到 ${elements.length} 个元素`);

    const plan = normalizeLoginPlan({
      strategy: "planned",
      username_locator: { type: "placeholder", value: "请输入邮箱/手机号" },
      password_locator: { type: "placeholder", value: "请输入密码" },
      captcha_image_locator: { type: "css", value: "img.verify-code" },
      captcha_input_locator: { type: "placeholder", value: "请输入图形验证码" },
      agreement_locator: { type: "text", value: "我已阅读并同意" },
      login_button_locator: { type: "role", role: "button", name: "登录" },
    });

    console.log("\n3️⃣ 填写账号密码...");
    await fillCredentialsWithPlan(page, plan, username, password);
    console.log(`✅ 账号: ${username}`);
    console.log(`✅ 密码: ${"*".repeat(8)}`);

    console.log("\n4️⃣ 定位并识别验证码...");
    const captchaTarget = await locateCaptchaWithPlan(page, plan);
    if (!captchaTarget) {
      console.log("❌ 未找到验证码");
      return;
    }

    const captchaPath = "/tmp/auto-captcha.png";
    await captchaTarget.screenshot({ path: captchaPath });
    console.log(`✅ 验证码已保存: ${captchaPath}`);

    const captchaAnswer = recognizeCaptcha(captchaPath);
    if (!captchaAnswer) {
      console.log("❌ 验证码识别失败");
      return;
    }
    console.log(`✅ 验证码识别: ${captchaAnswer}`);

    console.log("\n5️⃣ 填写验证码...");
    await fillCaptchaWithPlan(page, plan, captchaAnswer);
    console.log("✅ 验证码已填写");

    console.log("\n6️⃣ 勾选用户协议（使用修复后的逻辑）...");
    const agreementResult = await ensureAgreementWithPlan(page, plan);
    console.log(`协议处理结果: ${agreementResult}`);

    // 检查协议状态
    const agreementStatus = await page.evaluate(() => {
      const checkBox = document.querySelector('.check-box, .checked-box');
      const hasMarker = Boolean(document.querySelector('[data-ai-testing-agreement-clicked="1"]'));
      return {
        checkBoxClass: checkBox ? checkBox.className : '未找到',
        hasMarker,
      };
    });

    console.log(`   复选框class: ${agreementStatus.checkBoxClass}`);
    console.log(`   点击标记: ${agreementStatus.hasMarker ? '✅' : '❌'}`);

    if (agreementStatus.checkBoxClass.includes('checked')) {
      console.log("   ✅ 协议已勾选");
    } else {
      console.log("   ⚠️  协议可能未勾选");
    }

    console.log("\n7️⃣ 提交登录...");
    await page.waitForTimeout(1000);
    await submitLoginWithPlan(page, plan);
    console.log("✅ 登录表单已提交");

    console.log("\n8️⃣ 检查登录结果...");
    await page.waitForTimeout(3000);

    const pageStatus = await page.evaluate(() => {
      return {
        url: window.location.href,
        title: document.title,
        bodyText: document.body.innerText.substring(0, 300),
      };
    });

    console.log(`\n当前URL: ${pageStatus.url}`);
    console.log(`页面标题: ${pageStatus.title}`);

    if (pageStatus.url.includes('/login')) {
      console.log("\n❌ 仍在登录页面，登录失败");

      // 查找错误消息
      const errorMessages = await page.evaluate(() => {
        const messages = [];
        document.querySelectorAll('.error, .message, [role="alert"]').forEach(el => {
          const text = el.textContent?.trim();
          if (text && text.length > 0) messages.push(text);
        });
        return messages;
      });

      if (errorMessages.length > 0) {
        console.log("\n错误消息:");
        errorMessages.forEach(msg => console.log(`  • ${msg}`));
      }

      console.log("\n页面内容:");
      console.log(pageStatus.bodyText);
    } else {
      console.log("\n✅ 已离开登录页面");
      console.log("🎉 登录可能成功！");
    }

    // 截图
    await page.screenshot({ path: "/tmp/auto-login-result.png", fullPage: true });
    console.log("\n📸 结果截图: /tmp/auto-login-result.png");

  } catch (error) {
    console.error("\n❌ 测试出错:", error.message);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

autoLogin().catch(console.error);
