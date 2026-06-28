#!/usr/bin/env node
/**
 * 简化测试：只测试填写表单和勾选协议
 */
import { chromium } from "playwright";
import {
  ensureAgreementWithPlan,
  normalizeLoginPlan,
  fillCredentialsWithPlan,
} from "./ai-letter-login.mjs";

async function simpleTest() {
  const username = process.env.AI_TESTING_LOGIN_USERNAME || 'hongbao.wang@brgroup.com';
  const password = process.env.AI_TESTING_LOGIN_PASSWORD || 'test';

  const browser = await chromium.launch({
    headless: false,
    slowMo: 1500,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });

  const page = await context.newPage();

  try {
    console.log("="*80);
    console.log("🧪 简化测试：填写表单 + 勾选协议");
    console.log("="*80);

    console.log("\n【步骤1】访问登录页");
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    console.log("✅ 页面加载完成");

    const plan = normalizeLoginPlan({
      strategy: "planned",
      username_locator: { type: "placeholder", value: "请输入邮箱/手机号" },
      password_locator: { type: "placeholder", value: "请输入密码" },
      agreement_locator: { type: "text", value: "我已阅读并同意" },
    });

    console.log("\n【步骤2】填写账号密码");
    await fillCredentialsWithPlan(page, plan, username, password);
    console.log(`✅ 账号: ${username}`);
    console.log(`✅ 密码: ${"*".repeat(password.length)}`);

    await page.waitForTimeout(1000);

    console.log("\n【步骤3】检查协议复选框状态（点击前）");
    const beforeClick = await page.evaluate(() => {
      const notChecked = document.querySelector('.not-checked');
      const checkBox = document.querySelector('.check-box');
      const svg = document.querySelector('.policy svg');

      return {
        notCheckedExists: Boolean(notChecked),
        notCheckedClass: notChecked?.className || '',
        checkBoxClass: checkBox?.className || '',
        hasSVG: Boolean(svg),
      };
    });

    console.log(`  not-checked 元素: ${beforeClick.notCheckedExists ? '存在' : '不存在'}`);
    console.log(`  not-checked class: "${beforeClick.notCheckedClass}"`);
    console.log(`  check-box class: "${beforeClick.checkBoxClass}"`);
    console.log(`  勾选图标(svg): ${beforeClick.hasSVG ? '存在' : '不存在'}`);

    if (beforeClick.notCheckedExists && beforeClick.notCheckedClass === 'not-checked') {
      console.log("  状态: ❌ 未勾选");
    } else if (beforeClick.hasSVG) {
      console.log("  状态: ✅ 已勾选");
    }

    // 高亮显示
    await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      const notChecked = document.querySelector('.not-checked');

      if (policy) {
        policy.style.border = '5px solid yellow';
        policy.style.padding = '5px';
      }

      if (notChecked) {
        notChecked.style.border = '5px solid red';
        notChecked.style.boxShadow = '0 0 30px red';
      }
    });

    console.log("\n⏸️  观察协议区域（黄色边框），复选框（红色边框）");
    console.log("等待5秒...");
    await page.waitForTimeout(5000);

    console.log("\n【步骤4】勾选协议");
    console.log("执行 ensureAgreementWithPlan...");

    const result = await ensureAgreementWithPlan(page, plan);
    console.log(`返回结果: ${result ? '✅ true' : '❌ false'}`);

    await page.waitForTimeout(2000);

    console.log("\n【步骤5】检查协议复选框状态（点击后）");
    const afterClick = await page.evaluate(() => {
      const notChecked = document.querySelector('.not-checked');
      const checkBox = document.querySelector('.check-box');
      const svg = document.querySelector('.policy svg');

      return {
        notCheckedExists: Boolean(notChecked),
        notCheckedClass: notChecked?.className || '',
        checkBoxClass: checkBox?.className || '',
        hasSVG: Boolean(svg),
        svgHref: svg?.querySelector('use')?.getAttribute('xlink:href') || '',
      };
    });

    console.log(`  not-checked 元素: ${afterClick.notCheckedExists ? '存在' : '不存在'}`);
    console.log(`  not-checked class: "${afterClick.notCheckedClass}"`);
    console.log(`  check-box class: "${afterClick.checkBoxClass}"`);
    console.log(`  勾选图标(svg): ${afterClick.hasSVG ? '存在' : '不存在'}`);
    if (afterClick.hasSVG) {
      console.log(`  SVG图标: ${afterClick.svgHref}`);
    }

    // 判断结果
    const isChecked = afterClick.hasSVG && afterClick.svgHref.includes('checked');
    const classChanged = beforeClick.notCheckedClass !== afterClick.notCheckedClass;

    console.log(`\n  class 改变: ${classChanged ? '✅ 是' : '❌ 否'}`);
    console.log(`  状态: ${isChecked ? '✅ 已勾选' : '❌ 未勾选'}`);

    if (!isChecked) {
      console.log("\n❌ 复选框仍未勾选！");
      console.log("\n可能原因：");
      console.log("  1. 代码找到了错误的元素");
      console.log("  2. 点击事件被阻止");
      console.log("  3. 需要特定的点击顺序");
    } else {
      console.log("\n✅ 复选框成功勾选！");
    }

    // 截图
    await page.screenshot({ path: '/tmp/agreement-test-result.png', fullPage: true });
    console.log("\n📸 截图已保存: /tmp/agreement-test-result.png");

    console.log("\n⏸️  浏览器保持打开 60 秒，请仔细观察复选框状态...");
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("\n❌ 错误:", error.message);
    console.error(error.stack);
    await page.waitForTimeout(10000);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

simpleTest().catch(console.error);
