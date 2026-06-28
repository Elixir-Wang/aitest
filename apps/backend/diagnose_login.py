#!/usr/bin/env python3
"""
深度诊断登录问题：捕获控制台日志、网络请求和错误
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import ddddocr
from app.core.environment_credentials import load_credentials

# 尝试导入 playwright
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("❌ playwright 未安装，使用 Node.js 脚本进行测试")

async def diagnose_with_playwright():
    """使用 playwright 进行深度诊断"""
    ocr = ddddocr.DdddOcr(show_ad=False)
    creds = load_credentials('env-c3bc1023763dbb16')

    if not creds:
        print("❌ 未找到账号配置")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = await context.new_page()

        # 收集日志
        console_logs = []
        network_requests = []
        errors = []

        # 监听控制台消息
        page.on('console', lambda msg: console_logs.append({
            'type': msg.type,
            'text': msg.text
        }))

        # 监听网络请求
        page.on('request', lambda req: network_requests.append({
            'method': req.method,
            'url': req.url,
            'type': 'request'
        }))

        page.on('response', lambda res: network_requests.append({
            'status': res.status,
            'url': res.url,
            'type': 'response'
        }))

        # 监听页面错误
        page.on('pageerror', lambda err: errors.append(str(err)))

        print("="*60)
        print("开始深度诊断")
        print("="*60)

        # 访问登录页
        await page.goto('https://www.cybotstar.cn/login')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(2)

        print("\n✓ 页面加载完成")

        # 填写表单
        await page.get_by_placeholder('请输入邮箱/手机号').fill(creds['username'])
        print(f"✓ 填写账号")

        await page.get_by_placeholder('请输入密码').fill(creds['password'])
        print(f"✓ 填写密码")

        # 识别并填写验证码
        captcha_img = page.locator('img.verify-code').first
        captcha_bytes = await captcha_img.screenshot()
        captcha_text = ocr.classification(captcha_bytes)
        print(f"✓ 验证码识别: {captcha_text}")

        await page.get_by_placeholder('请输入图形验证码').fill(captcha_text)
        print(f"✓ 填写验证码")

        # 勾选协议
        await page.get_by_text('我已阅读并同意').first.click()
        print(f"✓ 勾选协议")

        await asyncio.sleep(0.5)

        # 清空之前的网络请求记录
        network_requests.clear()

        # 点击登录
        print(f"\n点击登录按钮...")
        await page.get_by_role('button', name='登录').click()

        # 等待并监控
        await asyncio.sleep(5)

        # 输出诊断信息
        print("\n" + "="*60)
        print("诊断结果")
        print("="*60)

        print(f"\n【控制台日志】({len(console_logs)} 条)")
        print("-"*60)
        for log in console_logs[-10:]:  # 只显示最后10条
            print(f"  [{log['type']}] {log['text'][:100]}")

        print(f"\n【网络请求】(登录后的请求，共 {len(network_requests)} 个)")
        print("-"*60)
        login_requests = [r for r in network_requests if 'login' in r.get('url', '').lower()]
        for req in login_requests:
            if req['type'] == 'request':
                print(f"  → {req['method']} {req['url']}")
            else:
                print(f"  ← {req['status']} {req['url']}")

        print(f"\n【页面错误】({len(errors)} 个)")
        print("-"*60)
        for error in errors:
            print(f"  ✗ {error}")

        print(f"\n【当前状态】")
        print("-"*60)
        print(f"  URL: {page.url}")
        print(f"  标题: {await page.title()}")

        # 检查是否有错误提示
        print(f"\n【错误提示检测】")
        print("-"*60)

        # 查找常见的错误元素
        error_selectors = [
            '.error', '.message', '.ant-message-error',
            '[role="alert"]', '.el-message--error'
        ]

        found_error = False
        for selector in error_selectors:
            elements = await page.locator(selector).all()
            for elem in elements:
                if await elem.is_visible():
                    text = await elem.text_content()
                    if text and text.strip():
                        print(f"  ✗ {text.strip()}")
                        found_error = True

        if not found_error:
            print("  未找到错误提示元素")

        # 截图
        screenshot_path = '/tmp/login_diagnose.png'
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"\n✓ 截图已保存: {screenshot_path}")

        print("\n等待10秒以便查看...")
        await asyncio.sleep(10)

        await browser.close()

def diagnose_with_nodejs():
    """使用现有的 Node.js 脚本进行诊断"""
    import subprocess

    print("="*60)
    print("使用 Node.js 脚本进行诊断")
    print("="*60)

    # 运行现有的登录脚本
    script_path = 'runners/playwright/ai-letter-login.mjs'
    storage_path = 'data/projects/environments/env-c3bc1023763dbb16/auth/storage-state.json'
    login_plan_path = 'data/projects/environments/env-c3bc1023763dbb16/auth/login-plan.json'

    env = {
        'AI_TESTING_LOGIN_USERNAME': 'hongbao.wang@brgroup.com',
        'AI_TESTING_LOGIN_PASSWORD': '',  # 从配置加载
        'AI_TESTING_CAPTCHA_MAX_ATTEMPTS': '1',
        'AI_TESTING_LOGIN_PLAN_PATH': login_plan_path,
    }

    # 加载密码
    creds = load_credentials('env-c3bc1023763dbb16')
    if creds:
        env['AI_TESTING_LOGIN_PASSWORD'] = creds['password']

    cmd = [
        'node',
        script_path,
        'https://www.cybotstar.cn/agentStore',
        storage_path,
        '',  # channel
        login_plan_path
    ]

    print(f"\n运行命令: {' '.join(cmd[:3])}")
    print("\n输出:")
    print("-"*60)

    # 运行并实时显示输出
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**subprocess.os.environ, **env}
    )

    for line in process.stdout:
        print(line, end='')

    process.wait()
    print("-"*60)
    print(f"\n退出码: {process.returncode}")

if __name__ == '__main__':
    if PLAYWRIGHT_AVAILABLE:
        asyncio.run(diagnose_with_playwright())
    else:
        diagnose_with_nodejs()
