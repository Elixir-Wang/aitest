#!/usr/bin/env node
/**
 * 性能优化验证脚本
 * 用于对比优化前后的登录流程耗时
 */

import { chromium } from "playwright";
import { readFileSync } from "fs";

const TARGET_URL = "https://www.cybotstar.cn/login";

async function measureLoginPerformance() {
  console.log("🚀 开始性能测试...\n");

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  const timings = {
    start: Date.now(),
    pageLoad: 0,
    captchaVisible: 0,
    formFilled: 0,
    agreementChecked: 0,
    submitted: 0,
    end: 0,
  };

  try {
    // 1. 页面加载
    console.log("⏱️  步骤1: 加载登录页面...");
    await page.goto(TARGET_URL);
    await page.waitForLoadState("domcontentloaded");
    timings.pageLoad = Date.now();
    console.log(`   ✅ 完成 (${timings.pageLoad - timings.start}ms)\n`);

    // 2. 主动触发验证码加载（新优化）
    console.log("⏱️  步骤2: 触发验证码加载...");
    const usernameInput = page.locator('input[type="text"]').first();
    if (await usernameInput.isVisible({ timeout: 500 }).catch(() => false)) {
      await usernameInput.focus();
      await page.waitForTimeout(200);
      console.log("   🚀 已聚焦输入框触发懒加载");
    }

    // 3. 等待验证码出现
    const captchaStart = Date.now();
    await page
      .locator('img.verify-code, img[class*="verify-code"]')
      .first()
      .waitFor({ state: "visible", timeout: 5000 })
      .catch(() => {});
    timings.captchaVisible = Date.now();
    const captchaLoadTime = timings.captchaVisible - captchaStart;
    console.log(`   ✅ 验证码出现 (${captchaLoadTime}ms)`);

    if (captchaLoadTime > 5000) {
      console.log("   ⚠️  警告: 验证码加载超过5秒，优化可能未生效");
    } else if (captchaLoadTime < 3000) {
      console.log("   🎉 优化生效！验证码加载很快");
    }
    console.log();

    // 4. 填写表单
    console.log("⏱️  步骤3: 填写表单...");
    const passwordInput = page.locator('input[type="password"]').first();
    await usernameInput.fill("test_user");
    await passwordInput.fill("test_pass");
    timings.formFilled = Date.now();
    console.log(`   ✅ 完成 (${timings.formFilled - timings.captchaVisible}ms)\n`);

    // 5. 勾选协议（测试重试机制）
    console.log("⏱️  步骤4: 勾选协议...");
    let agreementSuccess = false;
    for (let attempt = 0; attempt < 3; attempt++) {
      const notChecked = page.locator('.not-checked').first();
      if (await notChecked.isVisible({ timeout: 1000 }).catch(() => false)) {
        await notChecked.click();
        await page.waitForTimeout(300);

        const hasSVG = await page.evaluate(() => {
          return Boolean(document.querySelector('.policy svg'));
        });

        if (hasSVG) {
          console.log(`   ✅ 成功 (第${attempt + 1}次尝试)`);
          agreementSuccess = true;
          break;
        }
      }
      if (attempt < 2) {
        console.log(`   ⚠️  第${attempt + 1}次失败，重试中...`);
        await page.waitForTimeout(200);
      }
    }

    if (!agreementSuccess) {
      console.log("   ❌ 协议勾选失败");
    }
    timings.agreementChecked = Date.now();
    console.log();

    // 6. 截图保存
    console.log("⏱️  步骤5: 保存测试截图...");
    await page.screenshot({
      path: "data/projects/debug/optimization-test.png",
      fullPage: false
    });
    console.log("   ✅ 截图已保存\n");

    timings.end = Date.now();

    // 性能报告
    console.log("=" .repeat(60));
    console.log("📊 性能测试报告");
    console.log("=" .repeat(60));
    console.log();

    const totalTime = timings.end - timings.start;
    console.log(`⏱️  总耗时: ${totalTime}ms (${(totalTime / 1000).toFixed(2)}秒)`);
    console.log();

    console.log("详细耗时:");
    console.log(`  - 页面加载:      ${timings.pageLoad - timings.start}ms`);
    console.log(`  - 验证码出现:    ${timings.captchaVisible - timings.pageLoad}ms ${captchaLoadTime < 3000 ? '✅' : '⚠️'}`);
    console.log(`  - 表单填写:      ${timings.formFilled - timings.captchaVisible}ms`);
    console.log(`  - 协议勾选:      ${timings.agreementChecked - timings.formFilled}ms ${agreementSuccess ? '✅' : '❌'}`);
    console.log();

    // 对比基准
    console.log("📈 优化效果对比:");
    console.log(`  - 验证码加载:`);
    console.log(`    优化前: ~21秒`);
    console.log(`    当前:   ${(captchaLoadTime / 1000).toFixed(2)}秒 ${captchaLoadTime < 5000 ? '✅' : '❌'}`);
    console.log(`    改善:   ${((21 - captchaLoadTime / 1000) / 21 * 100).toFixed(0)}%`);
    console.log();

    console.log(`  - 协议勾选:`);
    console.log(`    成功率: ${agreementSuccess ? '100%' : '0%'} ${agreementSuccess ? '✅' : '❌'}`);
    console.log(`    目标:   99%+`);
    console.log();

    // 判断
    console.log("🎯 优化验证结果:");
    if (captchaLoadTime < 5000 && agreementSuccess) {
      console.log("   ✅✅✅ 优化效果显著！所有指标达标");
    } else if (captchaLoadTime < 5000) {
      console.log("   ✅⚠️  验证码优化成功，但协议勾选需要检查");
    } else if (agreementSuccess) {
      console.log("   ⚠️✅ 协议勾选正常，但验证码加载仍然较慢");
    } else {
      console.log("   ❌ 优化未达到预期，请检查代码");
    }
    console.log();

  } catch (error) {
    console.error("❌ 测试出错:", error.message);
  } finally {
    await browser.close();
    console.log("✅ 测试完成，浏览器已关闭");
  }
}

// 运行测试
measureLoginPerformance().catch(console.error);
