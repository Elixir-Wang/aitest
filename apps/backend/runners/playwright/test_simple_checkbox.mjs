#!/usr/bin/env node
/**
 * 测试简化版的协议勾选函数
 */
import { chromium } from "playwright";
import { clickAgreementCheckbox } from "./ai-letter-login.mjs";

async function testSimpleCheckbox() {
  const browser = await chromium.launch({ headless: false, slowMo: 1500 });
  const page = await (await browser.newContext()).newPage();

  try {
    console.log("🧪 测试简化版协议勾选函数\n");

    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("✅ 页面加载完成\n");

    // 检查点击前状态
    const before = await page.evaluate(() => {
      const hasSVG = Boolean(document.querySelector('.policy svg'));
      const notChecked = document.querySelector('.not-checked');
      return {
        hasSVG,
        notCheckedExists: Boolean(notChecked),
      };
    });

    console.log("【点击前】");
    console.log(`  复选框勾选: ${before.hasSVG ? '✅' : '❌'}`);
    console.log(`  not-checked元素存在: ${before.notCheckedExists ? '✅' : '❌'}\n`);

    // 调用简化函数
    console.log("【执行勾选】调用 clickAgreementCheckbox(page)...\n");
    const result = await clickAgreementCheckbox(page);

    console.log(`函数返回: ${result ? '✅ true' : '❌ false'}\n`);

    await page.waitForTimeout(1000);

    // 检查点击后状态
    const after = await page.evaluate(() => {
      const hasSVG = Boolean(document.querySelector('.policy svg'));
      const notChecked = document.querySelector('.not-checked');
      const svg = document.querySelector('.policy svg use');
      return {
        hasSVG,
        notCheckedExists: Boolean(notChecked),
        svgIcon: svg?.getAttribute('xlink:href') || '',
      };
    });

    console.log("【点击后】");
    console.log(`  复选框勾选: ${after.hasSVG ? '✅' : '❌'}`);
    console.log(`  not-checked元素存在: ${after.notCheckedExists ? '✅' : '❌'}`);
    if (after.hasSVG) {
      console.log(`  SVG图标: ${after.svgIcon}`);
    }

    const success = after.hasSVG && !before.hasSVG;
    console.log(`\n【最终结果】: ${success ? '✅ 成功勾选' : '❌ 未勾选'}\n`);

    // 截图
    await page.screenshot({ path: '/tmp/simple-checkbox-test.png', fullPage: true });
    console.log("📸 截图: /tmp/simple-checkbox-test.png\n");

    console.log("⏸️  浏览器保持打开30秒...");
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error("错误:", error);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

testSimpleCheckbox().catch(console.error);
