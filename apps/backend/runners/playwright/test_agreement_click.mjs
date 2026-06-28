#!/usr/bin/env node
/**
 * 测试协议点击 - 有头模式
 * 用于直观观察协议是否被勾选
 *
 * 使用方法:
 * AI_TESTING_LOGIN_USERNAME='user' AI_TESTING_LOGIN_PASSWORD='pass' node test_agreement_click.mjs
 */
import { chromium } from "playwright";

async function testAgreementClick() {
  console.log("================================================================");
  console.log("🔍 协议点击测试 - 有头模式");
  console.log("================================================================");

  // 从环境变量读取凭据
  const username = process.env.AI_TESTING_LOGIN_USERNAME;
  const password = process.env.AI_TESTING_LOGIN_PASSWORD;

  if (!username || !password) {
    console.log("\n❌ 请设置环境变量:");
    console.log("   export AI_TESTING_LOGIN_USERNAME='your_username'");
    console.log("   export AI_TESTING_LOGIN_PASSWORD='your_password'");
    console.log("\n或者直接运行:");
    console.log("   AI_TESTING_LOGIN_USERNAME='user' AI_TESTING_LOGIN_PASSWORD='pass' node test_agreement_click.mjs\n");
    return;
  }

  // 启动浏览器（有头模式）
  const browser = await chromium.launch({
    headless: false,  // 🔥 有头模式
    slowMo: 800,      // 放慢操作速度，便于观察
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });

  const page = await context.newPage();

  try {
    console.log("\n✓ 浏览器已启动（有头模式）");
    console.log("✓ 正在访问登录页...");

    // 访问登录页
    await page.goto("https://www.cybotstar.cn/login");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    console.log("✓ 页面加载完成\n");

    // 填写账号
    console.log(`✓ 填写账号: ${username}`);
    await page.getByPlaceholder("请输入邮箱/手机号").fill(username);
    await page.waitForTimeout(500);

    // 填写密码
    console.log("✓ 填写密码: ******");
    await page.getByPlaceholder("请输入密码").fill(password);
    await page.waitForTimeout(500);

    console.log("\n" + "=".repeat(60));
    console.log("🎯 准备分析协议元素...");
    console.log("=".repeat(60) + "\n");
    await page.waitForTimeout(1000);

    // 分析页面中的协议相关元素
    console.log("【页面元素分析】");
    const elementAnalysis = await page.evaluate(() => {
      const checkboxes = Array.from(document.querySelectorAll("input[type='checkbox']"));
      const ariaCheckboxes = Array.from(document.querySelectorAll("[role='checkbox']"));
      const policyElements = Array.from(document.querySelectorAll(".policy, .policy-content, [class*='checkbox']"));

      return {
        checkboxes: checkboxes.map((cb, i) => ({
          index: i,
          visible: cb.offsetParent !== null,
          checked: cb.checked,
          class: cb.className,
          id: cb.id,
        })),
        ariaCheckboxes: ariaCheckboxes.map((cb, i) => ({
          index: i,
          visible: cb.offsetParent !== null,
          ariaChecked: cb.getAttribute("aria-checked"),
          class: cb.className,
        })),
        policyElements: policyElements.map((el, i) => ({
          index: i,
          tag: el.tagName.toLowerCase(),
          class: el.className,
          text: el.innerText?.substring(0, 50) || "",
        })),
      };
    });

    console.log(`  找到 ${elementAnalysis.checkboxes.length} 个 <input type="checkbox">`);
    elementAnalysis.checkboxes.forEach(cb => {
      if (cb.visible) {
        console.log(`    #${cb.index}: checked=${cb.checked}, class="${cb.class}"`);
      }
    });

    console.log(`\n  找到 ${elementAnalysis.ariaCheckboxes.length} 个 [role="checkbox"]`);
    elementAnalysis.ariaCheckboxes.forEach(cb => {
      if (cb.visible) {
        console.log(`    #${cb.index}: aria-checked="${cb.ariaChecked}", class="${cb.class}"`);
      }
    });

    console.log(`\n  找到 ${elementAnalysis.policyElements.length} 个协议相关元素`);
    elementAnalysis.policyElements.slice(0, 5).forEach(el => {
      console.log(`    ${el.tag}.${el.class}: "${el.text}"`);
    });

    // 查找协议元素
    const agreementLocator = page.getByText("我已阅读并同意").first();

    console.log("\n" + "=".repeat(60));
    console.log("🖱️  执行点击操作...");
    console.log("=".repeat(60) + "\n");

    // 点击协议
    await agreementLocator.click({ force: true });
    await page.waitForTimeout(1500);

    console.log("✓ 已点击协议元素\n");

    // 点击后状态检查
    console.log("【点击后状态检查】");
    const afterClick = await page.evaluate(() => {
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
          visible: cb.offsetParent !== null,
          class: cb.className,
        })),
        ariaCheckboxes: ariaCheckboxes.map(cb => ({
          ariaChecked: cb.getAttribute("aria-checked"),
          visible: cb.offsetParent !== null,
          class: cb.className,
        })),
        hasClickedMarker: Boolean(clickedMarker),
        clickedMarkerClass: clickedMarker?.className || "",
        anyChecked,
      };
    });

    console.log("  普通复选框:");
    afterClick.checkboxes.forEach((cb, i) => {
      if (cb.visible) {
        const status = cb.checked ? "✅ 已勾选" : "❌ 未勾选";
        console.log(`    #${i}: ${status} - ${cb.class}`);
      }
    });

    console.log("\n  ARIA复选框:");
    afterClick.ariaCheckboxes.forEach((cb, i) => {
      if (cb.visible) {
        const status = cb.ariaChecked === "true" ? "✅ 已勾选" : "❌ 未勾选";
        console.log(`    #${i}: ${status} (aria-checked="${cb.ariaChecked}") - ${cb.class}`);
      }
    });

    console.log(`\n  自定义点击标记: ${afterClick.hasClickedMarker ? "✅ 已设置" : "❌ 未设置"}`);
    if (afterClick.hasClickedMarker) {
      console.log(`    标记元素 class: "${afterClick.clickedMarkerClass}"`);
    }

    console.log(`\n  【最终结果】任意控件被勾选: ${afterClick.anyChecked ? "✅ 是" : "❌ 否"}`);

    // 高亮显示协议相关元素
    await page.evaluate(() => {
      // 高亮所有复选框
      document.querySelectorAll("input[type='checkbox']").forEach(cb => {
        cb.style.outline = "5px solid red";
        cb.style.outlineOffset = "3px";
        if (cb.checked) {
          cb.style.outline = "5px solid lime";
        }
      });

      // 高亮ARIA复选框
      document.querySelectorAll("[role='checkbox']").forEach(cb => {
        const isChecked = cb.getAttribute("aria-checked") === "true";
        cb.style.border = isChecked ? "5px solid lime" : "5px solid orange";
        cb.style.boxShadow = "0 0 10px rgba(255,165,0,0.8)";
      });

      // 高亮协议文本
      const policyElements = document.querySelectorAll(".policy, .policy-content");
      policyElements.forEach(el => {
        el.style.border = "3px solid cyan";
        el.style.backgroundColor = "rgba(0,255,255,0.1)";
      });

      // 高亮点击标记
      const marker = document.querySelector("[data-ai-testing-agreement-clicked='1']");
      if (marker) {
        marker.style.border = "5px solid magenta";
        marker.style.boxShadow = "0 0 20px rgba(255,0,255,0.8)";
      }
    });

    console.log("\n" + "=".repeat(60));
    console.log("✨ 页面元素已高亮显示:");
    console.log("=".repeat(60));
    console.log("   🟢 绿色边框 = 已勾选的复选框");
    console.log("   🔴 红色边框 = 未勾选的普通 checkbox");
    console.log("   🟠 橙色边框 = 未勾选的 ARIA checkbox");
    console.log("   🟦 青色边框 = 协议容器");
    console.log("   🟣 紫色边框 = 自定义点击标记");
    console.log("=".repeat(60));

    console.log("\n⏸️  浏览器将保持打开 60 秒，请仔细观察页面状态...\n");
    await page.waitForTimeout(60000);

  } catch (error) {
    console.error("\n❌ 测试过程出错:", error.message);
    console.error(error.stack);
    await page.waitForTimeout(10000);
  } finally {
    console.log("\n✓ 关闭浏览器");
    await browser.close();
  }
}

// 运行测试
testAgreementClick().catch(console.error);
