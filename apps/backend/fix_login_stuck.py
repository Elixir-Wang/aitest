#!/usr/bin/env python3
"""
登录卡住问题诊断和修复工具
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ENVIRONMENT_ID = "env-c3bc1023763dbb16"
AUTH_DIR = Path(f"data/projects/environments/{ENVIRONMENT_ID}/auth")
STATUS_FILE = AUTH_DIR / "auto-login-status.json"
EVENTS_FILE = AUTH_DIR / "auto-login-events.jsonl"

def diagnose():
    print("=" * 70)
    print("登录卡住问题诊断")
    print("=" * 70)

    # 1. 检查状态文件
    if STATUS_FILE.exists():
        with open(STATUS_FILE) as f:
            status = json.load(f)
        print(f"\n【当前状态】")
        print(f"  状态: {status.get('status')}")
        print(f"  消息: {status.get('message')}")
        print(f"  更新时间: {status.get('updated_at')}")
        print(f"  错误代码: {status.get('last_error_code')}")
    else:
        print("\n【当前状态】状态文件不存在")
        status = None

    # 2. 检查最后的事件
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            events = [json.loads(line) for line in f if line.strip()]

        print(f"\n【最近事件】（最后5条）")
        for event in events[-5:]:
            print(f"  [{event.get('recorded_at')}] {event.get('kind')}")
            if event.get('reason'):
                print(f"    原因: {event.get('reason')}")

        last_event = events[-1] if events else None
    else:
        print("\n【最近事件】事件文件不存在")
        last_event = None

    # 3. 诊断问题
    print(f"\n【问题诊断】")
    if status and status.get('status') == 'running':
        print("  ❌ 状态显示'运行中'，但可能进程已死")
        print("  原因: Playwright进程意外终止，状态文件未更新")
        return "stuck_in_running"

    if last_event and last_event.get('kind') == 'login_plan_invalid':
        print("  ❌ 登录计划失效")
        print(f"  原因: {last_event.get('reason')}")
        return "plan_invalid"

    if last_event and last_event.get('kind') == 'login_page_observed':
        print("  ⏳ 正在等待LLM分析页面")
        print("  状态: 这是正常流程，但可能很慢（~66秒）")
        return "waiting_llm"

    print("  ℹ️  状态正常或未知问题")
    return "unknown"

def fix_stuck_status():
    """修复卡住的状态"""
    print("\n" + "=" * 70)
    print("修复操作")
    print("=" * 70)

    new_status = {
        "status": "idle",
        "message": "已重置状态，请重新尝试登录",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_error_code": ""
    }

    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATUS_FILE, 'w') as f:
        json.dump(new_status, f, ensure_ascii=False, indent=2)

    print(f"✅ 已重置状态为 'idle'")
    print(f"✅ 前端应该不再显示'登录中'")
    print(f"\n请刷新前端页面并重新尝试登录")

def check_playwright_fix():
    """检查Playwright修复是否生效"""
    print("\n" + "=" * 70)
    print("检查修复状态")
    print("=" * 70)

    playwright_file = Path("runners/playwright/ai-letter-login.mjs")
    if not playwright_file.exists():
        print(f"❌ 文件不存在: {playwright_file}")
        return False

    content = playwright_file.read_text()
    if 'timeout = selectorField === "captcha_image_selector" ? 5000 : 300' in content:
        print(f"✅ Playwright修复已部署（验证码图片等待5秒）")
        return True
    else:
        print(f"❌ Playwright修复未生效（仍然等待300ms）")
        return False

if __name__ == "__main__":
    import os
    os.chdir("/Users/wanghongbao/project/test_project/apps/backend")

    issue = diagnose()
    playwright_fixed = check_playwright_fix()

    print("\n" + "=" * 70)
    print("建议操作")
    print("=" * 70)

    if issue == "stuck_in_running":
        print("\n【立即执行】重置状态")
        fix_stuck_status()

    elif issue == "plan_invalid":
        if not playwright_fixed:
            print("\n❌ 问题：登录计划失效，但修复未生效")
            print("   原因：Playwright脚本可能未重新加载")
            print("   解决：需要重启后端服务")
        else:
            print("\n⚠️  问题：即使修复已部署，登录计划仍然失效")
            print("   原因：可能是在修复前启动的进程")
            print("   解决：")
            print("   1. 重置状态（执行下面的修复）")
            print("   2. 重新尝试登录")
        fix_stuck_status()

    elif issue == "waiting_llm":
        print("\n⏳ 状态：正在等待LLM分析（这是正常的，但很慢）")
        print("   预计耗时：~66秒")
        print("   说明：登录计划失效后需要重新分析页面")
        if not playwright_fixed:
            print("\n   ⚠️  修复未生效，下次登录仍会失效")
            print("   建议：重启后端服务以加载修复")
        else:
            print("\n   ✅ 修复已生效，下次登录应该会快很多")

    else:
        print("\n✅ 状态正常或问题未知")
        if not playwright_fixed:
            print("   ⚠️  但Playwright修复未生效")
            print("   建议：重启后端服务")

    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print(f"\n问题类型: {issue}")
    print(f"修复状态: {'✅ 已生效' if playwright_fixed else '❌ 未生效'}")
    print(f"\n操作：")
    if issue in ["stuck_in_running", "plan_invalid"]:
        print("  1. ✅ 已重置状态文件")
        print("  2. 🔄 请刷新前端页面")
        print("  3. 🔄 重新尝试登录")
    if not playwright_fixed:
        print("  4. ⚠️  建议重启后端服务以加载修复")
