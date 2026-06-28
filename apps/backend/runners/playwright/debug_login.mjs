import { chromium } from "playwright";
import { readFileSync } from "fs";

async function debugLogin() {
  console.log("=== 开始深度调试登录 ===\n");
  
  // 读取密码
  const password = process.env.AI_TESTING_LOGIN_PASSWORD || '';
  if (!password) {
    console.log("✗ 密码未设置");
    return;
  }
  
  const browser = await chromium.launch({ 
    headless: false
  });
  
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 }
  });
  
  const page = await context.newPage();
  
  // 监听所有网络请求
  const requests = [];
  page.on('request', request => {
    requests.push({
      type: 'request',
      method: request.method(),
      url: request.url(),
      postData: request.postData()
    });
  });
  
  page.on('response', async response => {
    if (response.request().method() === 'POST') {
      try {
        const body = await response.text();
        console.log(`← POST ${response.status()} ${response.url()}`);
        if (body.length < 1000) {
          console.log(`   响应: ${body}`);
        }
      } catch (e) {}
    }
  });
  
  // 访问登录页
  console.log("1. 访问登录页...");
  await page.goto('https://www.cybotstar.cn/login');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  
  // 填写账号
  console.log("\n2. 填写表单...");
  await page.getByPlaceholder('请输入邮箱/手机号').fill('hongbao.wang@brgroup.com');
  console.log(`   ✓ 账号已填写`);
  
  await page.getByPlaceholder('请输入密码').fill(password);
  console.log(`   ✓ 密码已填写 (长度: ${password.length})`);
  
  // 验证码 - 手动输入
  console.log(`\n3. 请在浏览器中手动输入验证码并点击登录`);
  console.log(`   观察网络请求和页面反应...`);
  
  // 勾选协议
  await page.getByText('我已阅读并同意').first().click();
  console.log(`   ✓ 协议已勾选`);
  
  console.log(`\n=== 等待60秒，请在浏览器中完成操作 ===`);
  await page.waitForTimeout(60000);
  
  // 检查最终状态
  const currentUrl = page.url();
  console.log(`\n最终 URL: ${currentUrl}`);
  
  if (!currentUrl.includes('/login')) {
    console.log(`✓ 登录成功！`);
  } else {
    console.log(`✗ 仍在登录页`);
  }
  
  // 显示所有POST请求
  console.log(`\n=== POST 请求记录 ===`);
  const postRequests = requests.filter(r => r.type === 'request' && r.method === 'POST');
  for (const req of postRequests) {
    console.log(`→ ${req.method} ${req.url}`);
    if (req.postData) {
      console.log(`   数据: ${req.postData.substring(0, 200)}`);
    }
  }
  
  await browser.close();
}

debugLogin().catch(err => {
  console.error("错误:", err);
  process.exit(1);
});
