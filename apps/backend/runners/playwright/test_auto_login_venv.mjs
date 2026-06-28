#!/usr/bin/env node
/**
 * 自动化登录测试 - 使用虚拟环境中的 Python
 */
import { chromium } from "playwright";
import { execSync } from "child_process";
import {
  collectLoginFormElements,
  ensureAgreementWithPlan,
  normalizeLoginPlan,
  fillCredentialsWithPlan,
  locateCaptchaWithPlan,
  fillCaptchaWithPlan,
  submitLoginWithPlan,
} from "./ai-letter-login.mjs";

// 使用虚拟环境中的 Python 识别验证码
function recognizeCaptcha(imagePath) {
  try {
    const pythonScript = `
import sys
sys.path.insert(0, '.')
import ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)
with open("${imagePath}", "rb") as f:
    result = ocr.classification(f.read())
print(result, end="")
`;

    // 使用虚拟环境中的 Python
    const result = execSync(
      `cd ../../ && source .venv/bin/activate && python3 -c '${pythonScript}'`,
      { encoding: 'utf8', shell: '/bin/bash' }
    );
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
    console.log("\n❌ 请设置环境变量");
    return;
  }

  const browser = await chromium.launch({
    headless: true,
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
      await page.screenshot({ path: "/tmp/no-captcha.png", fullPage: true });
      return;
    }

    const captchaPath = "/tmp/auto-captcha.png";
    await captchaTarget.screenshot({ path: captchaPath });
    console.log(`✅ 验证码已保存: ${captchaPath}`);

    console.log("🔍 正在识别验证码...");
    const captchaAnswer = recognizeCaptcha(captchaPath);
    if (!captchaAnswer) {
      console.log("❌ 验证码识别失败");
      return;
    }
    console.log(`✅ 验证码识别结果: ${captchaAnswer}`);

    console.log("\n5️⃣ 填写验证码...");
    await fillCaptchaWithPlan(page, plan, captchaAnswer);
    console.log("✅ 验证码已填写");

    console.log("\n6️⃣ 勾选用户协议（使用修复后的逻辑）...");
    console.log("-".repeat(80));

    const agreementResult = await ensureAgreementWithPlan(page, plan);
    console.log(`协议处理函数返回: ${agreementResult}`);

    await page.waitForTimeout(1000);

    // 详细检查协议状态
    const agreementStatus = await page.evaluate(() => {
      const checkBox = document.querySelector('.check-box, .checked-box, [class*="check"]');
      const allCheckElements = document.querySelectorAll('[class*="check"]');
      const hasMarker = Boolean(document.querySelector('[data-ai-testing-agreement-clicked="1"]'));

      return {
        checkBoxFound: Boolean(checkBox),
        checkBoxClass: checkBox ? checkBox.className : '未找到',
        checkBoxTag: checkBox ? checkBox.tagName.toLowerCase() : '',
        allCheckElementsCount: allCheckElements.length,
        hasMarker,
        markerElement: hasMarker ? document.querySelector('[data-ai-testing-agreement-clicked="1"]').className : '',
      };
    });

    console.log("\n【协议状态详细检查】");
    console.log(`  找到复选框元素: ${agreementStatus.checkBoxFound ? '✅' : '❌'}`);
    if (agreementStatus.checkBoxFound) {
      console.log(`  复选框标签: <${agreementStatus.checkBoxTag}>`);
      console.log(`  复选框class: "${agreementStatus.checkBoxClass}"`);

      if (agreementStatus.checkBoxClass.includes('checked')) {
        console.log(`  状态: ✅ 已勾选`);
      } else if (agreementStatus.checkBoxClass.includes('not-checked')) {
        console.log(`  状态: ❌ 未勾选`);
      } else {
        console.log(`  状态: ⚠️  无法判断`);
      }
    }
    console.log(`  页面中check相关元素数: ${agreementStatus.allCheckElementsCount}`);
    console.log(`  点击标记已设置: ${agreementStatus.hasMarker ? '✅' : '❌'}`);
    if (agreementStatus.hasMarker) {
      console.log(`  标记元素class: "${agreementStatus.markerElement}"`);
    }
    console.log("-".repeat(80));

    console.log("\n7️⃣ 提交登录...");
    await page.waitForTimeout(1500);

    // 提交前截图
    await page.screenshot({ path: "/tmp/before-submit.png", fullPage: true });
    console.log("📸 提交前截图: /tmp/before-submit.png");

    const submitResult = await submitLoginWithPlan(page, plan);
    console.log(`登录按钮点击结果: ${submitResult}`);

    console.log("\n8️⃣ 检查登录结果...");
    await page.waitForTimeout(3000);

    // 提交后截图
    await page.screenshot({ path: "/tmp/after-submit.png", fullPage: true });
    console.log("📸 提交后截图: /tmp/after-submit.png");

    const pageStatus = await page.evaluate(() => {
      return {
        url: window.location.href,
        title: document.title,
        bodyText: document.body.innerText.substring(0, 500),
      };
    });

    console.log("\n【登录结果】");
    console.log(`URL: ${pageStatus.url}`);
    console.log(`标题: ${pageStatus.title}`);

    if (pageStatus.url.includes('/login')) {
      console.log("\n❌ 仍在登录页面，登录失败\n");

      // 查找错误消息
      const errorMessages = await page.evaluate(() => {
        const messages = [];
        const selectors = ['.error', '.message', '.toast', '.tip', '[role="alert"]', '[class*="message"]'];
        selectors.forEach(sel => {
          document.querySelectorAll(sel).forEach(el => {
            const text = el.textContent?.trim();
            if (text && text.length > 0 && text.length < 200) {
              messages.push(text);
            }
          });
        });
        return [...new Set(messages)];
      });

      if (errorMessages.length > 0) {
        console.log("⚠️  页面错误消息:");
        errorMessages.forEach(msg => console.log(`   • ${msg}`));
      }

      console.log("\n页面内容片段:");
      console.log(pageStatus.bodyText);
    } else {
      console.log("\n✅ 已离开登录页面");
      console.log("🎉 登录成功！");
    }

  } catch (error) {
    console.error("\n❌ 测试出错:", error.message);
    console.error(error.stack);
  } finally {
    await browser.close();
    console.log("\n" + "=".repeat(80));
    console.log("✅ 测试完成");
    console.log("=".repeat(80));
    console.log("\n📸 截图文件:");
    console.log("   • /tmp/auto-captcha.png - 验证码图片");
    console.log("   • /tmp/before-submit.png - 提交前页面");
    console.log("   • /tmp/after-submit.png - 提交后页面");
  }
}

autoLogin().catch(console.error);
