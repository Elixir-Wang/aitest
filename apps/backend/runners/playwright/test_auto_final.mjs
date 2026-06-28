#!/usr/bin/env node
/**
 * 自动化登录测试 - 修复版
 */
import { chromium } from "playwright";
import { execSync } from "child_process";
import { writeFileSync } from "fs";
import {
  collectLoginFormElements,
  ensureAgreementWithPlan,
  normalizeLoginPlan,
  fillCredentialsWithPlan,
  locateCaptchaWithPlan,
  fillCaptchaWithPlan,
  submitLoginWithPlan,
} from "./ai-letter-login.mjs";

// 使用临时 Python 文件识别验证码
function recognizeCaptcha(imagePath) {
  try {
    const pythonScript = `
import ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)
with open("${imagePath}", "rb") as f:
    result = ocr.classification(f.read())
print(result, end="")
`;

    // 写入临时文件
    const scriptPath = "/tmp/recognize_captcha.py";
    writeFileSync(scriptPath, pythonScript);

    // 使用虚拟环境中的 Python 执行
    const result = execSync(
      `cd ../../ && source .venv/bin/activate && python3 ${scriptPath}`,
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
  console.log("🤖 自动化登录测试 - 完整流程");
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
    console.log("\n【第1步】访问登录页");
    console.log("-".repeat(80));
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    console.log("✅ 页面加载完成");

    console.log("\n【第2步】分析页面元素");
    console.log("-".repeat(80));
    const elements = await collectLoginFormElements(page);
    console.log(`✅ 找到 ${elements.length} 个交互元素`);

    const plan = normalizeLoginPlan({
      strategy: "planned",
      username_locator: { type: "placeholder", value: "请输入邮箱/手机号" },
      password_locator: { type: "placeholder", value: "请输入密码" },
      captcha_image_locator: { type: "css", value: "img.verify-code" },
      captcha_input_locator: { type: "placeholder", value: "请输入图形验证码" },
      agreement_locator: { type: "text", value: "我已阅读并同意" },
      login_button_locator: { type: "role", role: "button", name: "登录" },
    });

    console.log("\n【第3步】填写账号密码");
    console.log("-".repeat(80));
    await fillCredentialsWithPlan(page, plan, username, password);
    console.log(`✅ 账号: ${username}`);
    console.log(`✅ 密码: ${"*".repeat(password.length)}`);

    console.log("\n【第4步】定位并识别验证码");
    console.log("-".repeat(80));
    const captchaTarget = await locateCaptchaWithPlan(page, plan);
    if (!captchaTarget) {
      console.log("❌ 未找到验证码");
      await page.screenshot({ path: "/tmp/no-captcha.png", fullPage: true });
      return;
    }

    const captchaPath = "/tmp/auto-captcha.png";
    await captchaTarget.screenshot({ path: captchaPath });
    console.log(`✅ 验证码图片已保存: ${captchaPath}`);

    console.log("🔍 正在识别验证码...");
    const captchaAnswer = recognizeCaptcha(captchaPath);
    if (!captchaAnswer) {
      console.log("❌ 验证码识别失败");
      return;
    }
    console.log(`✅ 验证码识别结果: "${captchaAnswer}" (长度: ${captchaAnswer.length})`);

    console.log("\n【第5步】填写验证码");
    console.log("-".repeat(80));
    const fillCaptchaResult = await fillCaptchaWithPlan(page, plan, captchaAnswer);
    console.log(`✅ 验证码填写${fillCaptchaResult ? '成功' : '失败'}`);

    console.log("\n【第6步】勾选用户协议 ⭐ 重点观察");
    console.log("=".repeat(80));

    const agreementResult = await ensureAgreementWithPlan(page, plan);
    console.log(`协议处理函数返回: ${agreementResult ? '✅ true' : '❌ false'}`);

    await page.waitForTimeout(1000);

    // 详细检查协议状态
    const agreementStatus = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      const checkBox = document.querySelector('.check-box, .checked-box, [class*="check"]');
      const hasMarker = Boolean(document.querySelector('[data-ai-testing-agreement-clicked="1"]'));
      const markerElements = document.querySelectorAll('[data-ai-testing-agreement-clicked="1"]');

      return {
        policyFound: Boolean(policy),
        checkBoxFound: Boolean(checkBox),
        checkBoxClass: checkBox ? checkBox.className : '未找到',
        checkBoxTag: checkBox ? checkBox.tagName.toLowerCase() : '',
        hasMarker,
        markerCount: markerElements.length,
        markerElements: Array.from(markerElements).map(el => ({
          tag: el.tagName.toLowerCase(),
          class: el.className,
        })),
      };
    });

    console.log("\n✨ 协议状态检查:");
    console.log(`   协议容器(.policy): ${agreementStatus.policyFound ? '✅ 找到' : '❌ 未找到'}`);
    console.log(`   复选框元素: ${agreementStatus.checkBoxFound ? '✅ 找到' : '❌ 未找到'}`);

    if (agreementStatus.checkBoxFound) {
      console.log(`   复选框标签: <${agreementStatus.checkBoxTag}>`);
      console.log(`   复选框class: "${agreementStatus.checkBoxClass}"`);

      if (agreementStatus.checkBoxClass.includes('checked-box') ||
          agreementStatus.checkBoxClass.includes('checked')) {
        console.log(`   复选框状态: ✅ 已勾选`);
      } else if (agreementStatus.checkBoxClass.includes('not-checked')) {
        console.log(`   复选框状态: ❌ 未勾选`);
      } else {
        console.log(`   复选框状态: ⚠️  无法判断`);
      }
    }

    console.log(`   点击标记数量: ${agreementStatus.markerCount}`);
    if (agreementStatus.markerCount > 0) {
      console.log(`   被标记的元素:`);
      agreementStatus.markerElements.forEach((el, i) => {
        console.log(`     ${i+1}. <${el.tag}> class="${el.class}"`);
      });
    }
    console.log("=".repeat(80));

    console.log("\n【第7步】提交登录");
    console.log("-".repeat(80));
    await page.waitForTimeout(1000);

    // 提交前截图
    await page.screenshot({ path: "/tmp/before-submit.png", fullPage: true });
    console.log("📸 提交前截图: /tmp/before-submit.png");

    const submitResult = await submitLoginWithPlan(page, plan);
    console.log(`✅ 登录按钮${submitResult ? '已点击' : '点击失败'}`);

    console.log("\n【第8步】等待并检查登录结果");
    console.log("-".repeat(80));
    await page.waitForTimeout(4000);

    // 提交后截图
    await page.screenshot({ path: "/tmp/after-submit.png", fullPage: true });
    console.log("📸 提交后截图: /tmp/after-submit.png");

    const pageStatus = await page.evaluate(() => {
      return {
        url: window.location.href,
        title: document.title,
        bodyText: document.body.innerText.substring(0, 600),
      };
    });

    console.log("\n" + "=".repeat(80));
    console.log("🎯 登录结果");
    console.log("=".repeat(80));
    console.log(`当前URL: ${pageStatus.url}`);
    console.log(`页面标题: ${pageStatus.title}`);

    if (pageStatus.url.includes('/login')) {
      console.log("\n❌ 仍在登录页面 - 登录失败\n");

      // 查找错误消息
      const errorMessages = await page.evaluate(() => {
        const messages = [];
        const selectors = [
          '.error', '.message', '.toast', '.tip', '[role="alert"]',
          '[class*="error"]', '[class*="message"]', '[class*="tip"]'
        ];
        selectors.forEach(sel => {
          document.querySelectorAll(sel).forEach(el => {
            const text = el.textContent?.trim();
            if (text && text.length > 0 && text.length < 200 && !text.includes('账号密码')) {
              messages.push(text);
            }
          });
        });
        return [...new Set(messages)];
      });

      if (errorMessages.length > 0) {
        console.log("⚠️  页面中的错误/提示消息:");
        errorMessages.forEach(msg => console.log(`   • ${msg}`));
      } else {
        console.log("   (未找到明显的错误消息)");
      }

      console.log("\n📄 页面内容片段:");
      const lines = pageStatus.bodyText.split('\n').filter(l => l.trim());
      lines.slice(0, 15).forEach(line => {
        console.log(`   ${line.substring(0, 80)}`);
      });
    } else {
      console.log("\n✅ 已离开登录页面");
      console.log("🎉 登录成功！");
    }

  } catch (error) {
    console.error("\n❌ 测试过程出错:", error.message);
    console.error(error.stack);
  } finally {
    await browser.close();
    console.log("\n" + "=".repeat(80));
    console.log("✅ 测试执行完成");
    console.log("=".repeat(80));
    console.log("\n📁 生成的文件:");
    console.log("   • /tmp/auto-captcha.png - 验证码图片");
    console.log("   • /tmp/before-submit.png - 提交前的完整页面");
    console.log("   • /tmp/after-submit.png - 提交后的完整页面");
    console.log("\n💡 如果登录失败，请查看截图文件分析原因");
  }
}

autoLogin().catch(console.error);
