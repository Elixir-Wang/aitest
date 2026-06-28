#!/usr/bin/env node
/**
 * 验证修复后的协议点击逻辑
 */
import { chromium } from "playwright";
import { ensureAgreementWithPlan, normalizeLoginPlan, collectLoginFormElements } from "./ai-letter-login.mjs";

async function testFixedAgreementClick() {
  console.log("="*80);
  console.log("🔧 测试修复后的协议点击逻辑");
  console.log("="*80);

  const browser = await chromium.launch({
    headless: false,
    slowMo: 1000,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });

  const page = await context.newPage();

  try {
    console.log("\n✓ 访问登录页...");
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("✓ 收集页面元素...");
    const elements = await collectLoginFormElements(page);

    const agreementElements = elements.filter(el => el.kind === 'agreement');
    console.log(`\n找到 ${agreementElements.length} 个协议元素:`);
    agreementElements.forEach(el => {
      console.log(`  - ${el.tag}.${el.class_name}: "${el.text}"`);
    });

    // 点击前截图
    console.log("\n📸 点击前状态:");
    await page.screenshot({ path: '/tmp/before-click.png' });

    const beforeHTML = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      return policy ? policy.outerHTML : '';
    });
    console.log("协议区域HTML长度:", beforeHTML.length, "字节");

    // 使用修复后的逻辑点击
    console.log("\n🖱️  执行协议点击（使用修复后的逻辑）...");
    const plan = normalizeLoginPlan({
      strategy: "planned",
      agreement_locator: {
        type: "text",
        value: "我已阅读并同意"
      }
    });

    const result = await ensureAgreementWithPlan(page, plan);
    console.log(`✅ 点击返回结果: ${result}`);

    await page.waitForTimeout(2000);

    // 点击后截图
    console.log("\n📸 点击后状态:");
    await page.screenshot({ path: '/tmp/after-click.png' });

    const afterHTML = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      return policy ? policy.outerHTML : '';
    });
    console.log("协议区域HTML长度:", afterHTML.length, "字节");

    // 详细检查
    console.log("\n🔍 详细状态检查:");
    const status = await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      if (!policy) return { error: '未找到.policy元素' };

      // 查找所有可能的复选框元素
      const allElements = policy.querySelectorAll('*');
      const elements = Array.from(allElements).map(el => ({
        tag: el.tagName.toLowerCase(),
        class: el.className,
        clicked: el.getAttribute('data-ai-testing-agreement-clicked'),
        checked: el.checked,
        ariaChecked: el.getAttribute('aria-checked'),
        text: el.textContent?.substring(0, 20),
      }));

      // 查找带有特定class的元素
      const checkElements = Array.from(policy.querySelectorAll('[class*="check"], [class*="icon"]')).map(el => ({
        tag: el.tagName.toLowerCase(),
        class: el.className,
        width: el.getBoundingClientRect().width,
        height: el.getBoundingClientRect().height,
        clicked: el.getAttribute('data-ai-testing-agreement-clicked'),
      }));

      return {
        totalElements: elements.length,
        elements: elements.slice(0, 10),
        checkElements,
        hasClickedMarker: Boolean(document.querySelector('[data-ai-testing-agreement-clicked="1"]')),
      };
    });

    console.log(`  总元素数: ${status.totalElements}`);
    console.log(`  带check/icon class的元素: ${status.checkElements.length}`);
    console.log(`  点击标记已设置: ${status.hasClickedMarker ? '✅' : '❌'}`);

    if (status.checkElements.length > 0) {
      console.log("\n  可能的复选框元素:");
      status.checkElements.forEach((el, i) => {
        console.log(`    #${i}: <${el.tag}> class="${el.class}"`);
        console.log(`        尺寸: ${el.width}x${el.height}`);
        console.log(`        点击标记: ${el.clicked || '无'}`);
      });
    }

    console.log("\n  前10个子元素:");
    status.elements.forEach((el, i) => {
      if (el.class) {
        console.log(`    #${i}: <${el.tag}> class="${el.class}" ${el.clicked ? '✅已标记' : ''}`);
      }
    });

    // 高亮显示
    await page.evaluate(() => {
      const policy = document.querySelector('.policy');
      if (policy) {
        policy.style.border = '5px solid cyan';
        policy.style.boxShadow = '0 0 20px cyan';
      }

      const clicked = document.querySelector('[data-ai-testing-agreement-clicked="1"]');
      if (clicked) {
        clicked.style.border = '5px solid magenta';
        clicked.style.boxShadow = '0 0 30px magenta';
      }

      // 高亮所有check相关元素
      document.querySelectorAll('[class*="check"], [class*="icon"]').forEach(el => {
        el.style.outline = '3px solid orange';
      });
    });

    console.log("\n✨ 页面已高亮:");
    console.log("   🟦 青色 = .policy 容器");
    console.log("   🟣 紫色 = 被点击的元素");
    console.log("   🟠 橙色 = check/icon 元素");

    console.log("\n📁 截图保存:");
    console.log("   点击前: /tmp/before-click.png");
    console.log("   点击后: /tmp/after-click.png");

    console.log("\n⏸️  浏览器保持打开 60 秒...");
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("\n❌ 错误:", error.message);
    await page.waitForTimeout(10000);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

testFixedAgreementClick().catch(console.error);
