import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "fs";
import { execSync } from "child_process";

// 使用Python的ddddocr进行识别
function recognizeCaptcha(imageBytes) {
  // 保存图片到临时文件
  const tmpPath = '/tmp/captcha_debug.png';
  writeFileSync(tmpPath, imageBytes);

  // 调用Python脚本识别
  const result = execSync(
    `cd ../.. && .venv/bin/python -c "import ddddocr; import sys; ocr = ddddocr.DdddOcr(show_ad=False); print(ocr.classification(open('${tmpPath}', 'rb').read()))"`,
    { encoding: 'utf8' }
  );

  return result.trim();
}

async function debugLogin() {
  console.log("=== 深度登录调试 - 自动填写验证码版本 ===\n");

  const password = process.env.AI_TESTING_LOGIN_PASSWORD || '';
  if (!password) {
    console.log("✗ 密码未设置");
    return;
  }

  const browser = await chromium.launch({
    headless: false,
    slowMo: 500  // 放慢操作以便观察
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 }
  });

  const page = await context.newPage();

  // 捕获所有网络活动
  const networkLog = [];

  page.on('request', request => {
    const entry = {
      type: 'request',
      time: new Date().toISOString(),
      method: request.method(),
      url: request.url(),
      headers: request.headers(),
      postData: request.postData()
    };
    networkLog.push(entry);

    if (request.method() === 'POST' && request.url().includes('cybotstar')) {
      console.log(`\n→ POST ${request.url()}`);
      if (request.postData()) {
        console.log(`   数据: ${request.postData().substring(0, 300)}`);
      }
    }
  });

  page.on('response', async response => {
    if (response.request().method() === 'POST' && response.url().includes('cybotstar')) {
      console.log(`← ${response.status()} ${response.url()}`);
      try {
        const body = await response.text();
        console.log(`   响应 (${body.length} 字节): ${body.substring(0, 500)}`);

        networkLog.push({
          type: 'response',
          time: new Date().toISOString(),
          status: response.status(),
          url: response.url(),
          body: body
        });
      } catch (e) {
        console.log(`   响应读取失败: ${e.message}`);
      }
    }
  });

  // 捕获控制台错误
  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warning') {
      console.log(`[浏览器 ${msg.type()}] ${msg.text()}`);
    }
  });

  page.on('pageerror', err => {
    console.log(`[页面错误] ${err.message}`);
  });

  // 1. 访问登录页
  console.log("1. 访问登录页...");
  await page.goto('https://www.cybotstar.cn/login');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  console.log("   ✓ 页面加载完成");

  // 2. 填写账号
  console.log("\n2. 填写账号...");
  const usernameInput = page.getByPlaceholder('请输入邮箱/手机号');
  await usernameInput.fill('hongbao.wang@brgroup.com');
  const usernameValue = await usernameInput.inputValue();
  console.log(`   ✓ 账号: ${usernameValue}`);

  // 3. 填写密码
  console.log("\n3. 填写密码...");
  const passwordInput = page.getByPlaceholder('请输入密码');
  await passwordInput.fill(password);
  const passwordValue = await passwordInput.inputValue();
  console.log(`   ✓ 密码长度: ${passwordValue.length}`);

  // 4. 识别并填写验证码
  console.log("\n4. 识别验证码...");
  const captchaImg = page.locator('img.verify-code').first();
  await captchaImg.waitFor({ state: 'visible', timeout: 5000 });

  // 截图验证码
  const captchaBytes = await captchaImg.screenshot();

  // 识别
  const captchaText = recognizeCaptcha(captchaBytes);
  console.log(`   ✓ OCR识别: ${captchaText}`);

  // 填入
  const captchaInput = page.getByPlaceholder('请输入图形验证码');
  await captchaInput.fill(captchaText);
  const captchaValue = await captchaInput.inputValue();
  console.log(`   ✓ 验证码已填入: ${captchaValue}`);

  // 5. 勾选协议 - 查找 aria-checked 的自定义 checkbox
  console.log("\n5. 勾选协议...");

  // 查找所有可能的协议checkbox
  const checkboxSelectors = [
    '[class*="checkbox"][aria-checked="false"]',
    '[role="checkbox"][aria-checked="false"]',
    '[class*="checkbox"]',
    '[role="checkbox"]'
  ];

  let agreementChecked = false;

  for (const selector of checkboxSelectors) {
    const checkboxes = page.locator(selector);
    const count = await checkboxes.count();
    console.log(`   尝试选择器: ${selector}, 找到 ${count} 个元素`);

    for (let i = 0; i < count; i++) {
      const checkbox = checkboxes.nth(i);

      // 检查是否可见
      const isVisible = await checkbox.isVisible().catch(() => false);
      if (!isVisible) continue;

      // 获取相关文本
      const text = await checkbox.evaluate((el) => {
        const root = el.closest("div, label, form") || el.parentElement;
        return (root?.textContent || el.textContent || "").slice(0, 200);
      }).catch(() => "");

      console.log(`   元素 ${i} 文本: ${text.substring(0, 50)}`);

      // 检查是否是协议checkbox
      if (/我已阅读|用户协议|隐私|同意|agreement|policy|terms/i.test(text)) {
        console.log(`   ✓ 找到协议checkbox`);

        // 点击前状态
        const ariaCheckedBefore = await checkbox.getAttribute('aria-checked').catch(() => 'unknown');
        console.log(`   点击前 aria-checked: ${ariaCheckedBefore}`);

        // 点击
        await checkbox.click({ force: true, timeout: 1000 }).catch(() => {});
        await page.waitForTimeout(300);

        // 如果还没勾选，触发原生事件
        const ariaCheckedAfter = await checkbox.getAttribute('aria-checked').catch(() => 'unknown');
        console.log(`   点击后 aria-checked: ${ariaCheckedAfter}`);

        if (ariaCheckedAfter !== 'true') {
          console.log(`   尝试触发原生点击事件...`);
          await checkbox.evaluate((el) => {
            el.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
          }).catch(() => {});
          await page.waitForTimeout(300);

          const finalState = await checkbox.getAttribute('aria-checked').catch(() => 'unknown');
          console.log(`   最终 aria-checked: ${finalState}`);
        }

        agreementChecked = true;
        break;
      }
    }

    if (agreementChecked) break;
  }

  if (agreementChecked) {
    console.log(`   ✓ 协议已勾选`);
  } else {
    console.log(`   ✗ 警告：未找到协议checkbox`);
  }

  // 6. 再次确认所有字段
  console.log("\n6. 确认表单状态...");
  console.log(`   账号: ${await usernameInput.inputValue()}`);
  console.log(`   密码: ${'*'.repeat((await passwordInput.inputValue()).length)}`);
  console.log(`   验证码: ${await captchaInput.inputValue()}`);

  // 7. 点击登录
  console.log("\n7. 点击登录按钮...");
  const loginBtn = page.getByRole('button', { name: '登录' });

  // 确认按钮可见且可点击
  await loginBtn.waitFor({ state: 'visible' });
  const isEnabled = await loginBtn.isEnabled();
  console.log(`   登录按钮状态: ${isEnabled ? '可点击' : '禁用'}`);

  if (!isEnabled) {
    console.log(`   ✗ 登录按钮被禁用！检查表单验证...`);
  }

  await loginBtn.click();
  console.log(`   ✓ 已点击登录按钮`);

  // 8. 等待并观察
  console.log("\n8. 等待登录响应 (10秒)...");
  await page.waitForTimeout(10000);

  // 9. 检查结果
  console.log("\n9. 检查登录结果...");
  const currentUrl = page.url();
  console.log(`   当前URL: ${currentUrl}`);

  if (currentUrl.includes('/login')) {
    console.log(`   ✗ 仍在登录页面`);

    // 查找错误提示
    console.log("\n10. 查找错误信息...");

    const bodyText = await page.locator('body').textContent();

    // 查找错误关键词
    const errorKeywords = [
      '账号或密码错误',
      '密码错误',
      '验证码错误',
      '验证码不正确',
      '登录失败',
      '请输入正确',
      'error',
      'invalid'
    ];

    let foundError = false;
    for (const keyword of errorKeywords) {
      if (bodyText.toLowerCase().includes(keyword.toLowerCase())) {
        console.log(`   ✗ 找到错误: "${keyword}"`);
        foundError = true;
      }
    }

    if (!foundError) {
      console.log(`   未找到明确错误提示`);
    }

    // 截图
    await page.screenshot({ path: '/tmp/login_failed_final.png', fullPage: true });
    console.log(`\n   ✓ 截图: /tmp/login_failed_final.png`);

  } else {
    console.log(`   ✓ 登录成功！跳转到: ${currentUrl}`);
  }

  // 输出网络日志统计
  console.log("\n=== 网络请求统计 ===");
  const postRequests = networkLog.filter(l => l.type === 'request' && l.method === 'POST' && l.url.includes('cybotstar'));
  console.log(`POST 请求数: ${postRequests.length}`);

  for (const req of postRequests) {
    console.log(`\n→ ${req.url}`);
    if (req.postData) {
      console.log(`  数据: ${req.postData.substring(0, 200)}`);
    }

    // 找对应的响应
    const resp = networkLog.find(l => l.type === 'response' && l.url === req.url && l.time > req.time);
    if (resp) {
      console.log(`← ${resp.status}`);
      if (resp.body) {
        console.log(`  响应: ${resp.body.substring(0, 200)}`);
      }
    }
  }

  console.log("\n=== 等待5秒后关闭 ===");
  await page.waitForTimeout(5000);

  await browser.close();
}

debugLogin().catch(err => {
  console.error("错误:", err);
  process.exit(1);
});
