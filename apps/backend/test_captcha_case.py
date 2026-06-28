#!/usr/bin/env python3
"""
验证码大小写测试工具
用于测试不同大小写组合的验证码是否能成功登录
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import ddddocr
from playwright.async_api import async_playwright
from app.core.environment_credentials import load_credentials

async def test_captcha_with_case(case_type='lower'):
    """
    测试不同大小写的验证码
    case_type: 'lower', 'upper', 'original'
    """
    ocr = ddddocr.DdddOcr(show_ad=False)
    creds = load_credentials('env-c3bc1023763dbb16')

    if not creds:
        print("❌ 未找到账号配置")
        return False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = await context.new_page()

        print(f"\n{'='*60}")
        print(f"测试验证码大小写: {case_type.upper()}")
        print(f"{'='*60}\n")

        # 访问登录页
        await page.goto('https://www.cybotstar.cn/login')
        await page.wait_for_load_state('networkidle')
        await asyncio.sleep(1)

        # 填写账号
        username_input = page.get_by_placeholder('请输入邮箱/手机号')
        await username_input.fill(creds['username'])
        print(f"✓ 填写账号: {creds['username']}")

        # 填写密码
        password_input = page.get_by_placeholder('请输入密码')
        await password_input.fill(creds['password'])
        print(f"✓ 填写密码")

        # 识别验证码
        captcha_img = page.locator('img.verify-code').first
        captcha_bytes = await captcha_img.screenshot()
        captcha_text = ocr.classification(captcha_bytes)

        print(f"✓ 验证码识别: {captcha_text}")

        # 根据测试类型转换大小写
        if case_type == 'lower':
            captcha_to_enter = captcha_text.lower()
        elif case_type == 'upper':
            captcha_to_enter = captcha_text.upper()
        else:  # original
            captcha_to_enter = captcha_text

        print(f"✓ 实际输入: {captcha_to_enter}")

        # 填写验证码
        captcha_input = page.get_by_placeholder('请输入图形验证码')
        await captcha_input.fill(captcha_to_enter)

        # 勾选协议
        agreement = page.get_by_text('我已阅读并同意').first
        await agreement.click()
        print(f"✓ 勾选协议")

        await asyncio.sleep(0.5)

        # 点击登录
        login_btn = page.get_by_role('button', name='登录')
        await login_btn.click()
        print(f"✓ 点击登录")

        # 等待响应
        print("\n等待登录结果...")
        await asyncio.sleep(3)

        # 检查结果
        current_url = page.url
        print(f"\n当前 URL: {current_url}")

        if '/login' not in current_url:
            print(f"\n🎉 登录成功！")
            print(f"跳转到: {current_url}")

            # 保存登录态
            storage_state = await context.storage_state()
            save_path = Path('data/projects/environments/env-c3bc1023763dbb16/auth/storage-state.json')
            save_path.parent.mkdir(parents=True, exist_ok=True)

            import json
            with open(save_path, 'w') as f:
                json.dump(storage_state, f, indent=2)

            print(f"✓ 登录态已保存到: {save_path}")

            await asyncio.sleep(5)
            await browser.close()
            return True
        else:
            print(f"\n❌ 登录失败，仍在登录页")

            # 查找错误提示
            body_text = await page.locator('body').text_content()

            # 查找可能的错误信息
            error_keywords = ['错误', '失败', '无效', '不正确', 'error', 'invalid']
            found_errors = []

            for keyword in error_keywords:
                if keyword in body_text.lower():
                    import re
                    pattern = re.compile(f'.{{0,30}}{keyword}.{{0,30}}', re.IGNORECASE)
                    matches = pattern.findall(body_text)
                    found_errors.extend(matches[:2])

            if found_errors:
                print("\n可能的错误提示:")
                for error in found_errors:
                    print(f"  - {error.strip()}")
            else:
                print("\n未找到明确的错误提示")

            # 截图
            screenshot_path = f'/tmp/login_failed_{case_type}.png'
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n✓ 已保存截图: {screenshot_path}")

            print("\n等待10秒以便查看...")
            await asyncio.sleep(10)
            await browser.close()
            return False

async def main():
    """
    依次测试三种大小写组合
    """
    print("\n" + "="*60)
    print("验证码大小写测试工具")
    print("="*60)
    print("\n将依次测试三种大小写组合:")
    print("  1. 全小写 (lower)")
    print("  2. 全大写 (upper)")
    print("  3. 原始识别结果 (original)")
    print("\n按 Ctrl+C 可以随时停止测试")
    print("="*60)

    test_cases = ['lower', 'upper', 'original']

    for case_type in test_cases:
        try:
            success = await test_captcha_with_case(case_type)
            if success:
                print(f"\n✅ 成功！验证码使用 {case_type.upper()} 可以登录")
                return
            else:
                print(f"\n继续测试下一种...")
                await asyncio.sleep(2)
        except KeyboardInterrupt:
            print("\n\n测试已取消")
            return
        except Exception as e:
            print(f"\n❌ 测试出错: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
    print("\n所有大小写组合都失败了。")
    print("可能的原因:")
    print("  1. 账号或密码错误")
    print("  2. 验证码识别错误（字符识别错误，不只是大小写问题）")
    print("  3. 账号需要额外的验证步骤")

if __name__ == '__main__':
    asyncio.run(main())
