#!/usr/bin/env node
/**
 * 使用 Playwright 原生方法点击
 */
import { chromium } from "playwright";

async function testPlaywrightClick() {
  const browser = await chromium.launch({ headless: false, slowMo: 2000 });
  const page = await (await browser.newContext()).newPage();

  try {
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("="*80);
    console.log("🎯 使用 Playwright 原生点击方法");
    console.log("="*80);

    // 高亮显示
    await page.evaluate(() => {
      const notChecked = document.querySelector('.not-checked');
      const checkBox = document.querySelector('.check-box');
      const policy = document.querySelector('.policy');

      if (notChecked) {
        notChecked.style.border = '5px solid red';
        notChecked.style.boxShadow = '0 0 30px red';
      }
      if (checkBox) checkBox.style.border = '3px solid yellow';
      if (policy) policy.style.border = '3px solid cyan';
    });

    console.log("\n⏸️  观察高亮的元素（红色=复选框，黄色=容器，青色=协议区域）");
    console.log("等待5秒...\n");
    await page.waitForTimeout(5000);

    // 检查点击前状态
    const before = await page.evaluate(() => {
      const hasSVG = Boolean(document.querySelector('.policy svg'));
      const notChecked = document.querySelector('.not-checked');
      return {
        hasSVG,
        notCheckedClass: notChecked?.className || '',
      };
    });

    console.log("【点击前】");
    console.log(`  SVG图标: ${before.hasSVG ? '存在' : '不存在'}`);
    console.log(`  not-checked class: "${before.notCheckedClass}"`);

    // 使用 Playwright 定位器点击
    console.log("\n【执行点击】使用 Playwright locator.click()");

    const notCheckedLocator = page.locator('.not-checked').first();
    await notCheckedLocator.click();

    console.log("✅ 点击完成");

    await page.waitForTimeout(2000);

    // 检查点击后状态
    const after = await page.evaluate(() => {
      const hasSVG = Boolean(document.querySelector('.policy svg'));
      const notChecked = document.querySelector('.not-checked');
      const svg = document.querySelector('.policy svg');
      return {
        hasSVG,
        notCheckedExists: Boolean(notChecked),
        notCheckedClass: notChecked?.className || '',
        svgIcon: svg?.querySelector('use')?.getAttribute('xlink:href') || '',
      };
    });

    console.log("\n【点击后】");
    console.log(`  SVG图标: ${after.hasSVG ? '存在 ✅' : '不存在 ❌'}`);
    console.log(`  not-checked元素: ${after.notCheckedExists ? '存在' : '不存在'}`);
    console.log(`  not-checked class: "${after.notCheckedClass}"`);
    if (after.hasSVG) {
      console.log(`  SVG图标类型: ${after.svgIcon}`);
    }

    const success = after.hasSVG && after.svgIcon.includes('checked');
    console.log(`\n【结果】: ${success ? '✅ 复选框已勾选' : '❌ 复选框未勾选'}`);

    if (!success) {
      console.log("\n❌ Playwright 原生点击也无效！");
      console.log("\n可能原因：");
      console.log("  1. 页面需要特定的事件序列（mousedown + mouseup + click）");
      console.log("  2. 需要点击特定的坐标位置");
      console.log("  3. 有JavaScript阻止了点击事件");
      console.log("  4. 需要等待页面某个状态");
    }

    console.log("\n⏸️  浏览器保持打开60秒，请手动点击复选框测试...");
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("错误:", error);
  } finally {
    await browser.close();
  }
}

testPlaywrightClick().catch(console.error);
