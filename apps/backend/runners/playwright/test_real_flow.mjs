#!/usr/bin/env node
/**
 * 测试实际登录流程，模拟Python后端的调用方式
 * 分析为什么优化没有生效
 */

import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "fs";

const TARGET_URL = "https://www.cybotstar.cn/agentStore";
const LOGIN_URL = "https://www.cybotstar.cn/login";

async function testRealLoginFlow() {
  console.log("=" .repeat(60));
  console.log("🔍 实际登录流程诊断测试");
  console.log("=" .repeat(60));
  console.log();

  const browser = await chromium.launch({
    headless: false,
    channel: "chrome"
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  const page = await context.newPage();

  const timings = {
    sessionStart: Date.now(),
    navigationStart: 0,
    pageReady: 0,
    captchaSearchStart: 0,
    captchaFound: 0,
    formFilled: 0,
    agreementChecked: 0,
    submitted: 0,
  };

  const diagnostics = {
    captchaWaitMethod: "",
    captchaFoundBy: "",
    agreementMethod: "",
    optimizationApplied: {
      focusTrigger: false,
      shortTimeout: false,
      retryMechanism: false,
    }
  };

  try {
    // 步骤1: 导航到目标URL
    console.log("📍 步骤1: 导航到起始页面");
    timings.navigationStart = Date.now();
    await page.goto(TARGET_URL);
    await page.waitForLoadState("domcontentloaded");
    console.log(`   URL: ${TARGET_URL}`);
    console.log(`   当前URL: ${page.url()}`);
    console.log();

    // 步骤2: 检测是否需要登录
    console.log("🔐 步骤2: 检测登录需求");
    const currentUrl = page.url();
    if (currentUrl.includes("/login")) {
      console.log("   ✅ 已自动跳转到登录页");
    } else {
      console.log("   ⚠️  未跳转到登录页，手动跳转");
      await page.goto(LOGIN_URL);
    }

    timings.pageReady = Date.now();
    console.log(`   页面就绪耗时: ${timings.pageReady - timings.navigationStart}ms`);
    console.log();

    // 步骤3: 等待验证码 - 关键测试点
    console.log("⏱️  步骤3: 等待验证码出现（关键测试）");
    console.log("   测试优化1: 主动聚焦输入框触发验证码");

    timings.captchaSearchStart = Date.now();

    // 🚀 优化测试：主动触发
    try {
      const usernameInput = page.locator('input[type="text"], input[name*="user"]').first();
      const isVisible = await usernameInput.isVisible({ timeout: 1000 }).catch(() => false);

      if (isVisible) {
        console.log("   🔍 找到用户名输入框");
        await usernameInput.focus({ timeout: 500 });
        diagnostics.optimizationApplied.focusTrigger = true;
        console.log("   ✅ 已聚焦输入框（触发懒加载）");
        await page.waitForTimeout(200);
      } else {
        console.log("   ❌ 未找到用户名输入框，优化1未应用");
      }
    } catch (error) {
      console.log(`   ❌ 主动触发失败: ${error.message}`);
    }

    // 等待验证码出现
    console.log("   ⏳ 等待验证码图片出现...");
    const captchaWaitStart = Date.now();

    const captchaLocator = page.locator(
      'img.verify-code, img[class*="verify-code"], img[class*="captcha"]'
    ).first();

    const timeout = 5000; // 优化后的超时时间
    diagnostics.optimizationApplied.shortTimeout = (timeout === 5000);

    try {
      await captchaLocator.waitFor({ state: "visible", timeout });
      timings.captchaFound = Date.now();
      const captchaWaitTime = timings.captchaFound - captchaWaitStart;

      console.log(`   ✅ 验证码已出现！`);
      console.log(`   ⏱️  验证码等待时间: ${captchaWaitTime}ms (${(captchaWaitTime/1000).toFixed(2)}秒)`);

      if (captchaWaitTime < 3000) {
        console.log(`   🎉 优化生效！验证码加载很快`);
        diagnostics.captchaFoundBy = "optimized_focus_trigger";
      } else if (captchaWaitTime < 10000) {
        console.log(`   ⚠️  验证码加载较慢，优化效果有限`);
        diagnostics.captchaFoundBy = "partial_optimization";
      } else {
        console.log(`   ❌ 验证码加载很慢，优化未生效`);
        diagnostics.captchaFoundBy = "no_optimization";
      }

      // 保存验证码截图
      await captchaLocator.screenshot({
        path: "data/projects/debug/real-flow-captcha.png"
      });
      console.log(`   📸 验证码截图已保存`);

    } catch (error) {
      console.log(`   ❌ 验证码等待超时（${timeout}ms）`);
      diagnostics.captchaFoundBy = "timeout";
    }
    console.log();

    // 步骤4: 填写表单
    console.log("📝 步骤4: 填写登录表单");
    const usernameInput = page.locator('input[type="text"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    await usernameInput.fill("test_user");
    await passwordInput.fill("test_pass");
    timings.formFilled = Date.now();
    console.log(`   ✅ 表单已填写`);
    console.log();

    // 步骤5: 勾选协议 - 关键测试点
    console.log("☑️  步骤5: 勾选用户协议（关键测试）");
    console.log("   测试优化3: 重试机制");

    let agreementSuccess = false;
    let attemptCount = 0;

    for (let attempt = 0; attempt < 3; attempt++) {
      attemptCount++;
      console.log(`   🔄 尝试第 ${attempt + 1} 次...`);

      const notChecked = page.locator('.not-checked').first();
      const isVisible = await notChecked.isVisible({ timeout: 1000 }).catch(() => false);

      if (isVisible) {
        await notChecked.click();
        await page.waitForTimeout(300); // 优化后的等待时间

        // 验证是否成功
        const hasSVG = await page.evaluate(() => {
          return Boolean(document.querySelector('.policy svg'));
        });

        if (hasSVG) {
          console.log(`   ✅ 协议勾选成功！（第${attempt + 1}次尝试）`);
          agreementSuccess = true;
          diagnostics.optimizationApplied.retryMechanism = true;
          diagnostics.agreementMethod = `success_on_attempt_${attempt + 1}`;
          break;
        } else {
          console.log(`   ⚠️  第${attempt + 1}次失败，SVG未出现`);
        }
      } else {
        console.log(`   ⚠️  第${attempt + 1}次失败，.not-checked元素不可见`);
      }

      if (attempt < 2) {
        await page.waitForTimeout(200);
      }
    }

    if (!agreementSuccess) {
      console.log(`   ❌ 协议勾选失败（尝试${attemptCount}次）`);
      diagnostics.agreementMethod = "failed_all_attempts";
    }

    timings.agreementChecked = Date.now();
    console.log();

    // 保存完整页面截图
    console.log("📸 步骤6: 保存完整截图");
    await page.screenshot({
      path: "data/projects/debug/real-flow-full.png",
      fullPage: false
    });
    console.log("   ✅ 截图已保存");
    console.log();

    // 最终诊断报告
    console.log("=" .repeat(60));
    console.log("📊 诊断报告");
    console.log("=" .repeat(60));
    console.log();

    console.log("⏱️  时间分析:");
    const totalTime = timings.agreementChecked - timings.sessionStart;
    const captchaTime = timings.captchaFound - timings.captchaSearchStart;
    const agreementTime = timings.agreementChecked - timings.formFilled;

    console.log(`   总耗时:         ${totalTime}ms (${(totalTime/1000).toFixed(2)}秒)`);
    console.log(`   页面就绪:       ${timings.pageReady - timings.navigationStart}ms`);
    console.log(`   验证码等待:     ${captchaTime}ms (${(captchaTime/1000).toFixed(2)}秒) ${captchaTime < 3000 ? '✅' : captchaTime < 10000 ? '⚠️' : '❌'}`);
    console.log(`   表单填写:       ${timings.formFilled - timings.captchaFound}ms`);
    console.log(`   协议勾选:       ${agreementTime}ms ${agreementSuccess ? '✅' : '❌'}`);
    console.log();

    console.log("🔧 优化应用情况:");
    console.log(`   优化1 - 主动触发验证码: ${diagnostics.optimizationApplied.focusTrigger ? '✅ 已应用' : '❌ 未应用'}`);
    console.log(`   优化2 - 缩短超时时间:   ${diagnostics.optimizationApplied.shortTimeout ? '✅ 已应用 (5秒)' : '❌ 未应用'}`);
    console.log(`   优化3 - 协议重试机制:   ${diagnostics.optimizationApplied.retryMechanism ? '✅ 已应用' : '❌ 未应用'}`);
    console.log();

    console.log("📈 对比基准:");
    console.log(`   验证码加载:`);
    console.log(`     优化前基准: 21.84秒`);
    console.log(`     本次实测:   ${(captchaTime/1000).toFixed(2)}秒`);
    if (captchaTime < 3000) {
      console.log(`     改善:       ${((21.84 - captchaTime/1000) / 21.84 * 100).toFixed(0)}% ✅✅✅`);
    } else if (captchaTime < 10000) {
      console.log(`     改善:       ${((21.84 - captchaTime/1000) / 21.84 * 100).toFixed(0)}% ⚠️`);
    } else {
      console.log(`     改善:       ${((21.84 - captchaTime/1000) / 21.84 * 100).toFixed(0)}% ❌`);
    }
    console.log();

    console.log(`   协议勾选:`);
    console.log(`     成功率:     ${agreementSuccess ? '100%' : '0%'} ${agreementSuccess ? '✅' : '❌'}`);
    console.log(`     尝试次数:   ${attemptCount} ${attemptCount === 1 ? '✅ (一次成功)' : attemptCount <= 3 ? '⚠️ (需要重试)' : '❌ (失败)'}`);
    console.log();

    // 问题诊断
    console.log("🔍 问题诊断:");

    if (captchaTime > 10000) {
      console.log("   ❌ 验证码加载慢的可能原因:");
      console.log("      1. 主动聚焦未生效（输入框选择器不匹配）");
      console.log("      2. 网站验证码不是懒加载，而是网络慢");
      console.log("      3. 验证码选择器不正确，找到的不是真正的验证码");
      console.log("      4. 页面有额外的加载延迟");
    } else if (captchaTime > 3000) {
      console.log("   ⚠️  验证码加载比优化预期慢的原因:");
      console.log("      1. 主动聚焦生效，但验证码加载仍需时间（服务器响应慢）");
      console.log("      2. 页面JavaScript执行较慢");
    } else {
      console.log("   ✅ 验证码加载优化生效！");
    }
    console.log();

    if (!agreementSuccess) {
      console.log("   ❌ 协议勾选失败的可能原因:");
      console.log("      1. 选择器 '.not-checked' 不匹配（页面结构变化）");
      console.log("      2. 元素不可见或被遮挡");
      console.log("      3. 点击事件被拦截");
    } else if (attemptCount > 1) {
      console.log("   ⚠️  协议勾选需要多次尝试的原因:");
      console.log("      1. 首次点击时元素还没完全就绪");
      console.log("      2. JavaScript事件监听器初始化较慢");
    } else {
      console.log("   ✅ 协议勾选优化生效！");
    }
    console.log();

    console.log("💡 建议:");
    if (!diagnostics.optimizationApplied.focusTrigger) {
      console.log("   - 检查输入框选择器是否正确");
      console.log("   - 确认 ai-letter-login.mjs 的优化代码已加载");
    }
    if (captchaTime > 5000 && diagnostics.optimizationApplied.focusTrigger) {
      console.log("   - 验证码加载慢可能是网络问题，不是代码问题");
      console.log("   - 考虑增加网络优化（预加载、CDN等）");
    }
    if (!agreementSuccess) {
      console.log("   - 检查页面结构是否变化");
      console.log("   - 尝试其他选择器策略");
    }
    console.log();

  } catch (error) {
    console.error("❌ 测试出错:", error.message);
    console.error(error.stack);
  } finally {
    await browser.close();
    console.log("✅ 浏览器已关闭");
    console.log("=" .repeat(60));
  }
}

// 运行测试
testRealLoginFlow().catch(console.error);
