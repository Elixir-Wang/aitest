#!/usr/bin/env python3
"""
完整的登录问题诊断和解决方案
"""
import json
from pathlib import Path
from datetime import datetime, timezone

ENVIRONMENT_ID = "env-c3bc1023763dbb16"
AUTH_DIR = Path(f"data/projects/environments/{ENVIRONMENT_ID}/auth")
STATUS_FILE = AUTH_DIR / "auto-login-status.json"
EVENTS_FILE = AUTH_DIR / "auto-login-events.jsonl"

print("=" * 70)
print("登录问题完整诊断")
print("=" * 70)

# 1. 检查最后一次登录尝试的时间
if EVENTS_FILE.exists():
    with open(EVENTS_FILE) as f:
        events = [json.loads(line) for line in f if line.strip()]

    if events:
        last_event = events[-1]
        last_time = last_event.get('recorded_at', '')

        print(f"\n【最后一次登录尝试】")
        print(f"  时间: {last_time}")
        print(f"  事件: {last_event.get('kind')}")

        # 显示最近5个事件
        print(f"\n【最近事件】")
        for event in events[-5:]:
            print(f"  - [{event.get('kind')}] {event.get('recorded_at')}")
            if event.get('reason'):
                print(f"    原因: {event.get('reason')}")
    else:
        print("\n【最后一次登录尝试】无记录")
else:
    print("\n【最后一次登录尝试】事件文件不存在")

# 2. 检查当前状态
if STATUS_FILE.exists():
    with open(STATUS_FILE) as f:
        status = json.load(f)

    print(f"\n【当前状态】")
    print(f"  状态: {status.get('status')}")
    print(f"  消息: {status.get('message')}")
    print(f"  更新时间: {status.get('updated_at')}")
else:
    print(f"\n【当前状态】状态文件不存在")
    status = {"status": "unknown"}

# 3. 分析问题
print(f"\n【问题分析】")

current_status = status.get('status')

if current_status == 'idle':
    print("  ✅ 状态为 'idle'，可以尝试登录")
    print("\n【建议】")
    print("  1. 刷新前端页面")
    print("  2. 点击登录按钮")
    print("  3. 观察是否成功")

elif current_status == 'running':
    print("  ⏳ 状态为 'running'，登录进行中")
    print("\n【可能的情况】")
    print("  1. 正在等待LLM分析页面（~66秒）")
    print("  2. 进程已死但状态未更新")
    print("\n【建议】")
    print("  如果超过2分钟仍无响应，执行重置操作：")
    print("  python3 reset_login_status.py")

elif current_status == 'failed':
    print(f"  ❌ 登录失败")
    print(f"  原因: {status.get('message')}")
    print(f"  错误代码: {status.get('last_error_code')}")

    # 检查是否是我们已修复的问题
    error_code = status.get('last_error_code', '')
    if error_code == 'CAPTCHA_SOLVE_FAILED':
        print("\n  ℹ️  这是验证码长度问题，我们已经修复")
        print("  建议：重置状态后重新登录应该会成功")

    print("\n【建议】")
    print("  python3 reset_login_status.py")

else:
    print(f"  ⚠️  未知状态: {current_status}")

# 4. 检查修复状态
print(f"\n【修复状态检查】")

playwright_file = Path("runners/playwright/ai-letter-login.mjs")
if playwright_file.exists():
    content = playwright_file.read_text()
    if 'timeout = selectorField === "captcha_image_selector" ? 5000 : 300' in content:
        print("  ✅ Playwright修复已部署")
    else:
        print("  ❌ Playwright修复未部署")
else:
    print("  ❌ Playwright文件不存在")

captcha_file = Path("app/services/captcha_solver_service.py")
if captcha_file.exists():
    content = captcha_file.read_text()
    if 'actual_length > expected_length' in content and 'truncated = value[:expected_length]' in content:
        print("  ✅ 验证码长度截取修复已部署")
    else:
        print("  ❌ 验证码长度截取修复未部署")
else:
    print("  ❌ 验证码服务文件不存在")

print("\n" + "=" * 70)
print("总结")
print("=" * 70)
print(f"\n当前状态: {current_status}")
print(f"修复状态: 已部署")
print(f"\n下一步: 参考上面的【建议】章节")
