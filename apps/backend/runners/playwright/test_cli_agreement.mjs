#!/usr/bin/env node
/**
 * 使用 ai-letter-login.mjs 的函数来测试协议点击
 */
import { chromium } from "playwright";
import {
  collectLoginFormElements,
  ensureAgreementWithPlan,
  normalizeLoginPlan,
  locatorFromDescriptor
} from "./ai-letter-login.mjs";

async function testAgreementWithCLI() {
  console.log("="*80);
  console.log("🔍 使用 Playwright CLI 函数验证协议点击");
  console.log("="*80);

  const browser = await chromium.launch({
    headless: false,  // 有头模式
    slowMo: 1000,     // 慢速播放
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

    console.log("\n2️⃣ 收集登录表单元素...");
    const elements = await collectLoginFormElements(page);
    console.log(`✅ 找到 ${elements.length} 个元素`);

    // 查找协议相关元素
    const agreementElements = elements.filter(el =>
      el.kind === 'agreement' ||
      el.text.includes('我已阅读') ||
      el.text.includes('协议')
    );

    console.log(`\n3️⃣ 协议相关元素 (${agreementElements.length} 个):`);
    agreementElements.forEach(el => {
      console.log(`  - ${el.element_id}: ${el.tag}.${el.kind}`);
      console.log(`    text: "${el.text}"`);
      console.log(`    locator: ${JSON.stringify(el.locator)}`);
    });

    // 查找复选框
    const checkboxElements = elements.filter(el =>
      el.kind === 'checkbox' ||
      el.type === 'checkbox' ||
      el.role === 'checkbox'
    );

    console.log(`\n4️⃣ 复选框元素 (${checkboxElements.length} 个):`);
    checkboxElements.forEach(el => {
      console.log(`  - ${el.element_id}: ${el.tag}`);
      console.log(`    type: ${el.type}, role: ${el.role}`);
      console.log(`    aria-checked: "${el.aria_checked}"`);
      console.log(`    class: "${el.class_name}"`);
    });

    // 使用 login-plan.json 中的配置
    console.log("\n5️⃣ 加载登录计划...");
    const plan = normalizeLoginPlan({
      strategy: "planned",
      agreement_locator: {
        type: "text",
        value: "我已阅读并同意"
      }
    });
    console.log(`✅ 协议定位器: ${JSON.stringify(plan.agreement_locator)}`);

    // 点击前检查
    console.log("\n6️⃣ 点击前状态检查...");
    const beforeState = await page.evaluate(() => {
      return {
        checkboxes: Array.from(document.querySelectorAll("input[type='checkbox']")).map(cb => ({
          checked: cb.checked,
          class: cb.className,
        })),
        ariaCheckboxes: Array.from(document.querySelectorAll("[role='checkbox']")).map(cb => ({
          ariaChecked: cb.getAttribute("aria-checked"),
          class: cb.className,
        })),
      };
    });

    console.log(`  普通复选框: ${beforeState.checkboxes.length} 个`);
    beforeState.checkboxes.forEach((cb, i) => {
      console.log(`    #${i}: checked=${cb.checked}`);
    });

    console.log(`  ARIA复选框: ${beforeState.ariaCheckboxes.length} 个`);
    beforeState.ariaCheckboxes.forEach((cb, i) => {
      console.log(`    #${i}: aria-checked="${cb.ariaChecked}"`);
    });

    // 执行协议点击（使用真实的登录逻辑）
    console.log("\n7️⃣ 执行协议点击（使用 ensureAgreementWithPlan）...");
    const result = await ensureAgreementWithPlan(page, plan);
    console.log(`✅ 点击结果: ${result}`);

    await page.waitForTimeout(1500);

    // 点击后检查
    console.log("\n8️⃣ 点击后状态检查...");
    const afterState = await page.evaluate(() => {
      const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox']"));
      const ariaCheckboxes = Array.from(document.querySelectorAll("[role='checkbox']"));
      const clickedMarker = document.querySelector("[data-ai-testing-agreement-clicked='1']");

      const anyChecked = Boolean(
        document.querySelector(
          "input[type='checkbox']:checked, [role='checkbox'][aria-checked='true'], [data-ai-testing-agreement-clicked='1']"
        )
      );

      return {
        checkboxes: checkboxes.map(cb => ({
          checked: cb.checked,
          class: cb.className,
        })),
        ariaCheckboxes: ariaCheckboxes.map(cb => ({
          ariaChecked: cb.getAttribute("aria-checked"),
          class: cb.className,
        })),
        hasClickedMarker: Boolean(clickedMarker),
        clickedMarkerClass: clickedMarker?.className || "",
        clickedMarkerTag: clickedMarker?.tagName || "",
        anyChecked,
      };
    });

    console.log(`  普通复选框:`);
    afterState.checkboxes.forEach((cb, i) => {
      const changed = cb.checked !== beforeState.checkboxes[i]?.checked;
      const status = cb.checked ? "✅ 已勾选" : "❌ 未勾选";
      const changeMarker = changed ? " 🔄 (状态变化)" : "";
      console.log(`    #${i}: ${status}${changeMarker} - ${cb.class}`);
    });

    console.log(`\n  ARIA复选框:`);
    afterState.ariaCheckboxes.forEach((cb, i) => {
      const changed = cb.ariaChecked !== beforeState.ariaCheckboxes[i]?.ariaChecked;
      const status = cb.ariaChecked === "true" ? "✅ 已勾选" : "❌ 未勾选";
      const changeMarker = changed ? " 🔄 (状态变化)" : "";
      console.log(`    #${i}: ${status} (aria-checked="${cb.ariaChecked}")${changeMarker} - ${cb.class}`);
    });

    console.log(`\n  自定义点击标记: ${afterState.hasClickedMarker ? "✅ 已设置" : "❌ 未设置"}`);
    if (afterState.hasClickedMarker) {
      console.log(`    标记元素: <${afterState.clickedMarkerTag.toLowerCase()}> class="${afterState.clickedMarkerClass}"`);
    }

    console.log(`\n  【验证结果】任意控件被勾选: ${afterState.anyChecked ? "✅ 是" : "❌ 否"}`);

    // 高亮显示
    await page.evaluate(() => {
      document.querySelectorAll("input[type='checkbox']").forEach(cb => {
        cb.style.outline = cb.checked ? "5px solid lime" : "5px solid red";
        cb.style.outlineOffset = "3px";
      });

      document.querySelectorAll("[role='checkbox']").forEach(cb => {
        const isChecked = cb.getAttribute("aria-checked") === "true";
        cb.style.border = isChecked ? "5px solid lime" : "5px solid orange";
      });

      const marker = document.querySelector("[data-ai-testing-agreement-clicked='1']");
      if (marker) {
        marker.style.border = "5px solid magenta";
        marker.style.boxShadow = "0 0 20px rgba(255,0,255,0.8)";
      }

      const policyElements = document.querySelectorAll(".policy, .policy-content");
      policyElements.forEach(el => {
        el.style.border = "3px solid cyan";
      });
    });

    console.log("\n" + "="*80);
    console.log("✨ 页面元素已高亮 - 浏览器将保持打开 60 秒");
    console.log("="*80);
    console.log("   🟢 绿色 = 已勾选");
    console.log("   🔴 红色 = 未勾选的 checkbox");
    console.log("   🟠 橙色 = 未勾选的 ARIA checkbox");
    console.log("   🟣 紫色 = 自定义点击标记");
    console.log("   🟦 青色 = 协议容器");
    console.log("="*80);

    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("\n❌ 测试出错:", error.message);
    console.error(error.stack);
    await page.waitForTimeout(10000);
  } finally {
    await browser.close();
    console.log("\n✅ 测试完成");
  }
}

testAgreementWithCLI().catch(console.error);
