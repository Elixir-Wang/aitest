#!/usr/bin/env node
/**
 * 测试validateLoginPlan函数是否真的等待5秒
 */
import { chromium } from "playwright";
import { validateLoginPlan, loadLoginPlan } from "./ai-letter-login.mjs";

const LOGIN_PLAN_PATH = "../../data/projects/environments/env-c3bc1023763dbb16/auth/login-plan.json";
const SITE_URL = "https://www.cybotstar.cn/agentStore";

async function test() {
  console.log("=" .repeat(70));
  console.log("测试 validateLoginPlan 修复是否生效");
  console.log("=" .repeat(70));

  const browser = await chromium.launch({
    headless: true,
    channel: "chrome"
  });

  try {
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log(`\n🌐 访问登录页: ${SITE_URL}`);
    await page.goto(SITE_URL, { waitUntil: "networkidle", timeout: 30000 });
    await page.waitForURL("**/login", { timeout: 10000 }).catch(() => {});

    const plan = loadLoginPlan(LOGIN_PLAN_PATH);
    console.log(`\n📋 加载登录计划`);
    console.log(`   策略: ${plan.strategy}`);
    console.log(`   验证码图片选择器: ${plan.captcha_image_selector}`);

    console.log(`\n⏱️  测试验证（应该等待最多5秒）`);
    const startTime = Date.now();

    const result = await validateLoginPlan(page, plan);

    const elapsed = Date.now() - startTime;

    console.log(`\n【验证结果】`);
    console.log(`   有效: ${result.valid}`);
    console.log(`   原因: ${result.reason || 'N/A'}`);
    console.log(`   耗时: ${elapsed}ms`);

    if (result.valid) {
      console.log(`\n✅ 成功！登录计划验证通过`);
      console.log(`   这意味着修复生效了，验证码图片等待了足够的时间`);
    } else {
      console.log(`\n❌ 失败！登录计划仍然失效`);
      console.log(`   原因: ${result.reason}`);

      if (result.reason === 'captcha_image_selector_not_visible') {
        if (elapsed < 4000) {
          console.log(`   ⚠️  只等待了 ${elapsed}ms，说明5秒等待没有生效`);
          console.log(`   问题: 修复可能没有正确应用到validateLoginPlan函数`);
        } else {
          console.log(`   ⚠️  已经等待了 ${elapsed}ms，但图片仍不可见`);
          console.log(`   问题: 可能是选择器本身有问题，或者页面结构变化`);
        }
      }
    }

    await browser.close();

  } catch (error) {
    console.error("\n❌ 测试失败:", error.message);
    await browser.close();
    process.exit(1);
  }
}

test();
