#!/usr/bin/env node
/**
 * 精确测试协议复选框点击
 */
import { chromium } from "playwright";

async function testPreciseCheckboxClick() {
  console.log("="*80);
  console.log("🎯 精确测试协议复选框点击");
  console.log("="*80);

  const browser = await chromium.launch({
    headless: false,
    slowMo: 1500,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });

  const page = await context.newPage();

  try {
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("\n✅ 页面加载完成\n");

    // 分析协议区域
    console.log("【步骤1】分析协议区域结构");
    console.log("-".repeat(80));

    const structure = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      const notChecked = policy?.querySelector('.not-checked');
      const checkBox = policy?.querySelector('.check-box');

      return {
        policyExists: Boolean(policy),
        notCheckedExists: Boolean(notChecked),
        checkBoxExists: Boolean(checkBox),
        notCheckedClass: notChecked?.className || '',
        notCheckedRect: notChecked ? {
          x: notChecked.getBoundingClientRect().x,
          y: notChecked.getBoundingClientRect().y,
          width: notChecked.getBoundingClientRect().width,
          height: notChecked.getBoundingClientRect().height,
        } : null,
      };
    });

    console.log(`协议容器存在: ${structure.policyExists ? '✅' : '❌'}`);
    console.log(`not-checked元素存在: ${structure.notCheckedExists ? '✅' : '❌'}`);
    console.log(`check-box容器存在: ${structure.checkBoxExists ? '✅' : '❌'}`);

    if (structure.notCheckedExists) {
      console.log(`\nnot-checked元素信息:`);
      console.log(`  class: "${structure.notCheckedClass}"`);
      console.log(`  位置: (${structure.notCheckedRect.x}, ${structure.notCheckedRect.y})`);
      console.log(`  尺寸: ${structure.notCheckedRect.width}x${structure.notCheckedRect.height}`);
    }

    // 高亮元素
    await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      const notChecked = policy?.querySelector('.not-checked');
      const checkBox = policy?.querySelector('.check-box');

      if (policy) policy.style.border = '3px solid cyan';
      if (checkBox) checkBox.style.border = '3px solid yellow';
      if (notChecked) {
        notChecked.style.border = '5px solid red';
        notChecked.style.boxShadow = '0 0 20px red';
      }
    });

    console.log("\n【步骤2】点击前状态");
    console.log("-".repeat(80));

    const beforeClick = await page.evaluate(() => {
      const notChecked = document.querySelector('.not-checked');
      const checkBox = document.querySelector('.check-box');
      return {
        notCheckedClass: notChecked?.className || '',
        checkBoxClass: checkBox?.className || '',
      };
    });

    console.log(`not-checked class: "${beforeClick.notCheckedClass}"`);
    console.log(`check-box class: "${beforeClick.checkBoxClass}"`);

    console.log("\n⏸️  等待3秒，请观察高亮的元素...");
    console.log("   🟦 青色边框 = 协议容器");
    console.log("   🟡 黄色边框 = check-box 容器");
    console.log("   🔴 红色边框 = not-checked 元素（将要点击）");
    await page.waitForTimeout(3000);

    // 精确点击 not-checked 元素
    console.log("\n【步骤3】点击 not-checked 元素");
    console.log("-".repeat(80));

    const clickResult = await page.evaluate(() => {
      const notChecked = document.querySelector('.not-checked');
      if (!notChecked) return { success: false, reason: '未找到元素' };

      // 尝试多种点击方式
      notChecked.click();
      notChecked.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      notChecked.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
      notChecked.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));

      return { success: true };
    });

    console.log(`点击结果: ${clickResult.success ? '✅ 成功' : '❌ 失败'}`);
    if (!clickResult.success) {
      console.log(`失败原因: ${clickResult.reason}`);
    }

    await page.waitForTimeout(2000);

    // 检查点击后状态
    console.log("\n【步骤4】点击后状态");
    console.log("-".repeat(80));

    const afterClick = await page.evaluate(() => {
      const notChecked = document.querySelector('.not-checked');
      const checkBox = document.querySelector('.check-box');
      const policy = document.querySelector('.policy');

      return {
        notCheckedClass: notChecked?.className || '',
        checkBoxClass: checkBox?.className || '',
        policyHTML: policy?.outerHTML.substring(0, 500) || '',
      };
    });

    console.log(`not-checked class: "${afterClick.notCheckedClass}"`);
    console.log(`check-box class: "${afterClick.checkBoxClass}"`);

    // 判断是否勾选
    const isChecked = !afterClick.notCheckedClass.includes('not-checked') ||
                     afterClick.checkBoxClass.includes('checked');

    console.log(`\n复选框状态: ${isChecked ? '✅ 已勾选' : '❌ 未勾选'}`);

    if (!isChecked) {
      console.log("\n⚠️  复选框仍未勾选！");
      console.log("\n可能原因:");
      console.log("  1. 需要点击父容器而不是 not-checked 元素");
      console.log("  2. 需要特定的事件顺序");
      console.log("  3. 有 JavaScript 事件监听器在父元素上");
      console.log("\n协议区域 HTML:");
      console.log(afterClick.policyHTML);
    }

    console.log("\n⏸️  浏览器保持打开 60 秒，请手动尝试点击复选框...");
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("\n❌ 错误:", error.message);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

testPreciseCheckboxClick().catch(console.error);
