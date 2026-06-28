#!/usr/bin/env node
/**
 * 完整的登录流程测试 - 有头模式
 * 使用修复后的协议点击逻辑 + 验证码识别
 */
import { chromium } from "playwright";
import { readFileSync, existsSync } from "fs";
import {
  collectLoginFormElements,
  ensureAgreementWithPlan,
  normalizeLoginPlan,
  fillCredentialsWithPlan,
  locateCaptchaWithPlan,
  fillCaptchaWithPlan,
  submitLoginWithPlan,
  waitForLoginSuccess,
} from "./ai-letter-login.mjs";

async function testFullLoginFlow() {
  console.log("="*80);
  console.log("🚀 完整登录流程测试 - 有头模式");
  console.log("="*80);

  // 从环境变量获取凭据
  const username = process.env.AI_TESTING_LOGIN_USERNAME;
  const password = process.env.AI_TESTING_LOGIN_PASSWORD;

  if (!username || !password) {
    console.log("\n❌ 请设置环境变量:");
    console.log("   export AI_TESTING_LOGIN_USERNAME='your_username'");
    console.log("   export AI_TESTING_LOGIN_PASSWORD='your_password'");
    return;
  }

  const browser = await chromium.launch({
    headless: false,  // 有头模式
    slowMo: 800,      // 放慢速度
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });

  const page = await context.newPage();

  try {
    // ==================== 第1步：访问登录页 ====================
    console.log("\n📍 第1步：访问登录页");
    console.log("-".repeat(80));
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    console.log("✅ 页面加载完成");

    // ==================== 第2步：收集页面元素 ====================
    console.log("\n📍 第2步：分析登录表单");
    console.log("-".repeat(80));
    const elements = await collectLoginFormElements(page);
    console.log(`✅ 找到 ${elements.length} 个交互元素`);

    // 加载登录计划
    const plan = normalizeLoginPlan({
      strategy: "planned",
      username_locator: { type: "placeholder", value: "请输入邮箱/手机号" },
      password_locator: { type: "placeholder", value: "请输入密码" },
      captcha_image_locator: { type: "css", value: "img.verify-code" },
      captcha_input_locator: { type: "placeholder", value: "请输入图形验证码" },
      agreement_locator: { type: "text", value: "我已阅读并同意" },
      login_button_locator: { type: "role", role: "button", name: "登录" },
    });

    // ==================== 第3步：填写账号密码 ====================
    console.log("\n📍 第3步：填写账号密码");
    console.log("-".repeat(80));
    const fillResult = await fillCredentialsWithPlan(page, plan, username, password);
    if (fillResult) {
      console.log(`✅ 账号: ${username}`);
      console.log(`✅ 密码: ${"*".repeat(password.length)}`);
    } else {
      console.log("❌ 填写账号密码失败");
    }
    await page.waitForTimeout(1000);

    // ==================== 第4步：定位验证码 ====================
    console.log("\n📍 第4步：定位验证码图片");
    console.log("-".repeat(80));
    const captchaTarget = await locateCaptchaWithPlan(page, plan);
    if (!captchaTarget) {
      console.log("❌ 未找到验证码图片");
      await page.waitForTimeout(10000);
      return;
    }
    console.log("✅ 验证码图片已定位");

    // 截取验证码
    const captchaImagePath = "/tmp/captcha-test.png";
    await captchaTarget.screenshot({ path: captchaImagePath });
    console.log(`✅ 验证码已保存: ${captchaImagePath}`);

    // ==================== 第5步：识别验证码 ====================
    console.log("\n📍 第5步：识别验证码（需要手动输入）");
    console.log("-".repeat(80));
    console.log("⚠️  请查看浏览器中的验证码图片");
    console.log("⚠️  本次测试需要您手动输入验证码");
    console.log("");
    console.log("请在终端输入验证码，然后按回车:");

    // 等待用户输入
    const { createInterface } = await import("readline");
    const rl = createInterface({
      input: process.stdin,
      output: process.stdout
    });

    const captchaAnswer = await new Promise((resolve) => {
      rl.question("> ", (answer) => {
        rl.close();
        resolve(answer.trim());
      });
    });

    if (!captchaAnswer) {
      console.log("❌ 未输入验证码");
      await page.waitForTimeout(10000);
      return;
    }

    console.log(`✅ 验证码: ${captchaAnswer}`);

    // ==================== 第6步：填写验证码 ====================
    console.log("\n📍 第6步：填写验证码");
    console.log("-".repeat(80));
    const fillCaptchaResult = await fillCaptchaWithPlan(page, plan, captchaAnswer);
    if (fillCaptchaResult) {
      console.log("✅ 验证码已填写");
    } else {
      console.log("❌ 验证码填写失败");
    }
    await page.waitForTimeout(1000);

    // ==================== 第7步：勾选协议（使用修复后的逻辑）====================
    console.log("\n📍 第7步：勾选用户协议");
    console.log("-".repeat(80));

    // 高亮协议区域
    await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      if (policy) {
        policy.style.border = '3px solid yellow';
        policy.style.boxShadow = '0 0 10px yellow';
      }
    });

    const agreementResult = await ensureAgreementWithPlan(page, plan);
    console.log(`协议处理结果: ${agreementResult}`);

    await page.waitForTimeout(1500);

    // 检查协议状态
    const agreementStatus = await page.evaluate(() => {
      const checkBox = document.querySelector('.check-box, .checked-box, [class*="check"]');
      const hasMarker = Boolean(document.querySelector('[data-ai-testing-agreement-clicked="1"]'));
      return {
        checkBoxClass: checkBox ? checkBox.className : '未找到',
        hasMarker,
        checkBoxHTML: checkBox ? checkBox.outerHTML : '未找到',
      };
    });

    console.log(`✅ 协议复选框class: ${agreementStatus.checkBoxClass}`);
    console.log(`✅ 点击标记已设置: ${agreementStatus.hasMarker}`);
    if (agreementStatus.checkBoxClass.includes('checked')) {
      console.log("✅ 复选框显示为已勾选状态");
    } else {
      console.log("⚠️  复选框可能未勾选");
    }

    // ==================== 第8步：提交登录 ====================
    console.log("\n📍 第8步：提交登录表单");
    console.log("-".repeat(80));
    console.log("⏸️  请确认信息无误，3秒后将提交...");
    await page.waitForTimeout(3000);

    const submitResult = await submitLoginWithPlan(page, plan);
    if (submitResult) {
      console.log("✅ 登录按钮已点击");
    } else {
      console.log("❌ 登录按钮点击失败");
    }

    // ==================== 第9步：等待登录结果 ====================
    console.log("\n📍 第9步：等待登录结果");
    console.log("-".repeat(80));
    await page.waitForTimeout(2000);

    // 截取提交后的页面
    await page.screenshot({ path: "/tmp/after-submit.png", fullPage: true });
    console.log("✅ 提交后截图: /tmp/after-submit.png");

    // 检查页面状态
    const pageStatus = await page.evaluate(() => {
      return {
        url: window.location.href,
        title: document.title,
        bodyText: document.body.innerText.substring(0, 500),
      };
    });

    console.log(`\n当前URL: ${pageStatus.url}`);
    console.log(`页面标题: ${pageStatus.title}`);

    if (pageStatus.url.includes('/login')) {
      console.log("\n❌ 仍在登录页面，登录可能失败");
      console.log("\n页面内容摘要:");
      console.log(pageStatus.bodyText.substring(0, 300));

      // 查找错误消息
      const errorMessages = await page.evaluate(() => {
        const selectors = [
          '.error', '.message', '.ant-message', '.el-message',
          '[role="alert"]', '[class*="error"]', '[class*="tip"]'
        ];
        const messages = [];
        for (const sel of selectors) {
          const elements = document.querySelectorAll(sel);
          elements.forEach(el => {
            const text = el.textContent?.trim();
            if (text && text.length > 0 && text.length < 200) {
              messages.push(text);
            }
          });
        }
        return [...new Set(messages)];
      });

      if (errorMessages.length > 0) {
        console.log("\n⚠️  页面错误消息:");
        errorMessages.forEach(msg => {
          console.log(`  • ${msg}`);
        });
      }
    } else {
      console.log("\n✅ 已离开登录页面");

      // 等待并检查登录成功信号
      console.log("检查登录成功信号...");
      const loginResult = await waitForLoginSuccess(context, "https://www.cybotstar.cn/agentStore", 5000);

      if (loginResult.success) {
        console.log("\n🎉 登录成功！");
        console.log(`成功信号: ${loginResult.reasons?.join(", ")}`);
      } else {
        console.log("\n⚠️  无法确认登录成功");
        console.log(`失败原因: ${loginResult.reasons?.join(", ")}`);
      }
    }

    // ==================== 保持浏览器打开 ====================
    console.log("\n" + "=".repeat(80));
    console.log("⏸️  浏览器将保持打开60秒，请查看最终状态");
    console.log("=".repeat(80));
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("\n❌ 测试过程出错:", error.message);
    console.error(error.stack);
    await page.waitForTimeout(15000);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

testFullLoginFlow().catch(console.error);
