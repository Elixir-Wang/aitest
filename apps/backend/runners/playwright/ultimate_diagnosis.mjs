#!/usr/bin/env node
/**
 * 终极诊断：找出为什么复选框没有被勾选
 */
import { chromium } from "playwright";

async function ultimateDiagnosis() {
  const browser = await chromium.launch({ headless: false, slowMo: 2000 });
  const page = await (await browser.newContext()).newPage();

  try {
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("="*80);
    console.log("🔬 终极诊断：复选框点击问题");
    console.log("="*80);

    // 获取完整DOM结构
    const domInfo = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      if (!policy) return { error: 'policy not found' };

      // 获取所有可能的点击目标
      const allElements = Array.from(policy.querySelectorAll('*')).map(el => ({
        tag: el.tagName.toLowerCase(),
        class: el.className,
        id: el.id,
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height,
        visible: el.offsetParent !== null,
        text: el.textContent?.substring(0, 20),
      }));

      return {
        policyHTML: policy.outerHTML,
        allElements,
      };
    });

    console.log("\n【协议区域完整HTML】");
    console.log(domInfo.policyHTML);

    console.log("\n【所有子元素】");
    domInfo.allElements.forEach((el, i) => {
      if (el.visible && el.width > 0) {
        console.log(`${i+1}. <${el.tag}> class="${el.class}" ${el.width}x${el.height}`);
      }
    });

    // 尝试所有可能的点击方式
    console.log("\n【测试不同的点击方式】");
    console.log("="*80);

    // 方式1: 点击 .not-checked
    console.log("\n方式1: 点击 <span class='not-checked'>");
    let result1 = await page.evaluate(() => {
      const el = document.querySelector('.not-checked');
      if (!el) return { success: false, reason: '元素不存在' };

      const before = el.className;
      el.click();

      setTimeout(() => {}, 500); // 等待DOM更新

      const after = document.querySelector('.not-checked')?.className || '';
      const hasSVG = Boolean(document.querySelector('.policy svg'));

      return {
        success: true,
        before,
        after,
        changed: before !== after,
        hasSVG,
      };
    });

    await page.waitForTimeout(1000);

    console.log(`  点击前class: "${result1.before}"`);
    console.log(`  点击后class: "${result1.after}"`);
    console.log(`  class改变: ${result1.changed ? '✅' : '❌'}`);
    console.log(`  出现SVG图标: ${result1.hasSVG ? '✅' : '❌'}`);
    console.log(`  结论: ${result1.hasSVG ? '✅ 成功勾选' : '❌ 未勾选'}`);

    if (result1.hasSVG) {
      console.log("\n🎉 方式1有效！问题是 ensureAgreementWithPlan 没有正确调用这个逻辑。");
    }

    await page.waitForTimeout(2000);

    // 刷新页面，重新测试
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // 方式2: 点击 .check-box 容器
    console.log("\n方式2: 点击 <p class='check-box'>");
    let result2 = await page.evaluate(() => {
      const el = document.querySelector('.check-box');
      if (!el) return { success: false, reason: '元素不存在' };

      el.click();

      setTimeout(() => {}, 500);

      const hasSVG = Boolean(document.querySelector('.policy svg'));

      return {
        success: true,
        hasSVG,
      };
    });

    await page.waitForTimeout(1000);
    console.log(`  出现SVG图标: ${result2.hasSVG ? '✅' : '❌'}`);
    console.log(`  结论: ${result2.hasSVG ? '✅ 成功勾选' : '❌ 未勾选'}`);

    await page.waitForTimeout(2000);

    // 刷新页面
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // 方式3: 点击协议文字
    console.log("\n方式3: 点击协议文字");
    let result3 = await page.evaluate(() => {
      const el = document.querySelector('.policy-content');
      if (!el) return { success: false, reason: '元素不存在' };

      el.click();

      setTimeout(() => {}, 500);

      const hasSVG = Boolean(document.querySelector('.policy svg'));

      return {
        success: true,
        hasSVG,
      };
    });

    await page.waitForTimeout(1000);
    console.log(`  出现SVG图标: ${result3.hasSVG ? '✅' : '❌'}`);
    console.log(`  结论: ${result3.hasSVG ? '✅ 成功勾选' : '❌ 未勾选'}`);

    console.log("\n" + "="*80);
    console.log("📊 诊断总结");
    console.log("="*80);

    if (result1.hasSVG) {
      console.log("\n✅ 方式1（点击 .not-checked）有效");
      console.log("\n问题根源：ensureAgreementWithPlan 没有正确定位和点击 .not-checked 元素");
      console.log("\n需要确认：");
      console.log("  1. clickVisualAgreementControl 是否被调用");
      console.log("  2. querySelector('.not-checked') 是否找到元素");
      console.log("  3. 点击事件是否被执行");
    } else if (result2.hasSVG) {
      console.log("\n✅ 方式2（点击 .check-box）有效");
    } else if (result3.hasSVG) {
      console.log("\n✅ 方式3（点击协议文字）有效");
    } else {
      console.log("\n❌ 所有方式都无效！这不可能...");
    }

    console.log("\n⏸️  浏览器保持打开30秒...");
    await page.waitForTimeout(30000);

  } catch (error) {
    console.error("错误:", error);
  } finally {
    await browser.close();
  }
}

ultimateDiagnosis().catch(console.error);
