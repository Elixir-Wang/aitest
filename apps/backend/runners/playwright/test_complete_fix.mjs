#!/usr/bin/env node
/**
 * 完整验证修复后的登录流程
 * 模拟实际Python后端的完整调用
 */

import { runAiLetterLogin } from "./ai-letter-login.mjs";
import { readFileSync, writeFileSync, mkdirSync } from "fs";

const TARGET_URL = "https://www.cybotstar.cn/agentStore";
const TEST_USERNAME = process.env.TEST_USERNAME || "test_user";
const TEST_PASSWORD = process.env.TEST_PASSWORD || "test_pass";
const STORAGE_PATH = "data/projects/debug/test-storage-state.json";
const LOGIN_PLAN_PATH = "data/projects/debug/test-login-plan.json";

console.log("=" .repeat(60));
console.log("🧪 完整登录流程修复验证");
console.log("=" .repeat(60));
console.log();

const events = [];
const timings = {
  start: Date.now(),
  pageObserved: 0,
  captchaChallenge: 0,
  loginSucceeded: 0,
};

function onEvent(event) {
  const timestamp = Date.now();
  events.push({ ...event, timestamp });

  console.log(`[${new Date().toISOString()}] ${event.kind}`);

  if (event.kind === "login_page_observed") {
    timings.pageObserved = timestamp;
  } else if (event.kind === "captcha_challenge") {
    timings.captchaChallenge = timestamp;
    const waitTime = timings.captchaChallenge - timings.pageObserved;
    console.log(`   ⏱️  验证码等待时间: ${waitTime}ms (${(waitTime/1000).toFixed(2)}秒)`);
    if (waitTime < 3000) {
      console.log(`   🎉 优化生效！验证码加载很快`);
    } else if (waitTime < 10000) {
      console.log(`   ⚠️  验证码加载较慢`);
    } else {
      console.log(`   ❌ 验证码加载很慢，优化未生效`);
    }
  } else if (event.kind === "login_succeeded") {
    timings.loginSucceeded = timestamp;
  }
}

async function waitForLoginFormPlan() {
  console.log("   等待登录表单分析...");
  // 返回启发式策略
  return {
    type: "login_form_plan",
    strategy: "heuristic"
  };
}

async function waitForAnswer(attempt, expectedLength) {
  console.log(`   等待验证码答案（尝试${attempt}，长度${expectedLength}）...`);
  // 模拟验证码识别
  await new Promise(resolve => setTimeout(resolve, 100));
  // 返回模拟答案
  return "test";
}

try {
  const result = await runAiLetterLogin({
    startUrl: TARGET_URL,
    storageStatePath: STORAGE_PATH,
    channel: "chrome",
    username: TEST_USERNAME,
    password: TEST_PASSWORD,
    maxAttempts: 3,
    loginPlanPath: LOGIN_PLAN_PATH,
    onEvent,
    waitForLoginFormPlan,
    waitForAnswer,
  });

  console.log();
  console.log("=" .repeat(60));
  console.log("📊 测试结果");
  console.log("=" .repeat(60));
  console.log();

  const totalTime = timings.loginSucceeded - timings.start;
  const captchaWaitTime = timings.captchaChallenge - timings.pageObserved;

  console.log(`登录结果: ${result.success ? '✅ 成功' : '❌ 失败'}`);
  if (result.success) {
    console.log(`尝试次数: ${result.attempt}`);
  } else {
    console.log(`失败原因: ${result.reason}`);
  }
  console.log();

  console.log(`⏱️  性能数据:`);
  console.log(`   总耗时:        ${totalTime}ms (${(totalTime/1000).toFixed(2)}秒)`);
  console.log(`   验证码等待:    ${captchaWaitTime}ms (${(captchaWaitTime/1000).toFixed(2)}秒)`);
  console.log();

  console.log(`📈 对比基准:`);
  console.log(`   验证码等待:`);
  console.log(`     优化前: 21.84秒 / 34.91秒`);
  console.log(`     本次:   ${(captchaWaitTime/1000).toFixed(2)}秒`);

  if (captchaWaitTime < 3000) {
    console.log(`     评价:   ✅✅✅ 优异！优化完全生效`);
  } else if (captchaWaitTime < 10000) {
    console.log(`     评价:   ⚠️ 一般，仍有优化空间`);
  } else {
    console.log(`     评价:   ❌ 未达标，优化未生效`);
  }
  console.log();

  // 保存事件日志供分析
  const logPath = "data/projects/debug/test-fix-events.jsonl";
  mkdirSync("data/projects/debug", { recursive: true });
  writeFileSync(logPath, events.map(e => JSON.stringify(e)).join('\n'));
  console.log(`📝 事件日志已保存: ${logPath}`);

  process.exit(result.success ? 0 : 1);

} catch (error) {
  console.error();
  console.error("❌ 测试失败:", error.message);
  console.error(error.stack);
  process.exit(2);
}
