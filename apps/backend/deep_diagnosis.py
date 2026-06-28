#!/usr/bin/env python3
"""
深度诊断：分析协议按钮点击和登录失败的真实原因
"""
import json
from pathlib import Path

def analyze_login_events():
    """分析登录事件日志"""
    events_path = Path("data/projects/environments/env-c3bc1023763dbb16/auth/auto-login-events.jsonl")

    if not events_path.exists():
        print(f"❌ 事件日志不存在: {events_path}")
        return

    print("="*80)
    print("🔍 登录流程深度分析")
    print("="*80)

    events = []
    with open(events_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    # 分析每次登录尝试
    attempts = {}
    for event in events:
        kind = event.get('kind', '')

        if kind == 'login_attempt_diagnostics':
            attempt = event.get('attempt', 0)
            attempts[attempt] = event

    print(f"\n📊 共进行了 {len(attempts)} 次登录尝试\n")

    for attempt_num, event in sorted(attempts.items()):
        print(f"{'='*80}")
        print(f"第 {attempt_num} 次尝试分析")
        print(f"{'='*80}")

        diagnostics = event.get('diagnostics', {})

        # 1. 协议处理状态
        print(f"\n【协议处理】")
        print(f"  ✓ agreement_handled: {event.get('agreement_handled')}")
        print(f"  ✓ agreement_checked: {diagnostics.get('agreement_checked')}")
        print(f"  ✓ agreement_clicked_marker: {diagnostics.get('agreement_clicked_marker')}")
        print(f"  ✓ agreement_aria_checked: '{diagnostics.get('agreement_aria_checked')}'")

        # 2. 验证码状态
        print(f"\n【验证码】")
        print(f"  验证码答案长度: {diagnostics.get('answer_length')}")
        print(f"  输入框的值: '{diagnostics.get('captcha_input_value')}'")
        print(f"  是否匹配: {diagnostics.get('captcha_input_matches_answer')}")

        # 3. 提交状态
        print(f"\n【表单提交】")
        print(f"  submitted: {event.get('submitted')}")
        print(f"  post_submit_dialog_handled: {event.get('post_submit_dialog_handled')}")

        # 4. 页面状态
        print(f"\n【页面状态】")
        print(f"  URL: {diagnostics.get('url')}")
        print(f"  标题: {diagnostics.get('title')}")

        # 5. 错误消息
        likely_messages = diagnostics.get('likely_messages', [])
        if likely_messages:
            print(f"\n【可疑消息】")
            for msg in likely_messages:
                print(f"  • {msg}")

        # 6. 页面内容摘要
        body_excerpt = diagnostics.get('body_excerpt', '')
        if body_excerpt:
            print(f"\n【页面内容摘要】")
            # 查找关键词
            keywords = ['错误', '失败', '验证码', '密码', '绑定', '手机']
            excerpt_lines = []
            for keyword in keywords:
                if keyword in body_excerpt:
                    start = max(0, body_excerpt.find(keyword) - 20)
                    end = min(len(body_excerpt), body_excerpt.find(keyword) + 50)
                    excerpt_lines.append(f"  ...{body_excerpt[start:end]}...")

            if excerpt_lines:
                for line in excerpt_lines[:5]:  # 只显示前5条
                    print(line)
            else:
                print(f"  {body_excerpt[:200]}...")

        print()

    # 分析结论
    print("="*80)
    print("📝 分析结论")
    print("="*80)

    all_agreement_handled = all(
        attempts[i].get('agreement_handled', False)
        for i in attempts
    )

    all_agreement_checked = all(
        attempts[i].get('diagnostics', {}).get('agreement_checked', False)
        for i in attempts
    )

    print(f"\n1. 协议按钮点击:")
    if all_agreement_handled and all_agreement_checked:
        print(f"   ✅ 所有尝试中协议都被成功勾选")
        print(f"   ✅ 协议按钮的定位和点击逻辑没有问题")
    else:
        print(f"   ❌ 部分尝试中协议未被正确勾选")

    print(f"\n2. 登录失败原因:")
    # 检查是否所有尝试都显示相同的 URL
    urls = [attempts[i].get('diagnostics', {}).get('url') for i in attempts]
    if all(url == urls[0] for url in urls):
        print(f"   ❌ 所有尝试后仍停留在登录页面: {urls[0]}")
        print(f"   ❌ 说明登录从未成功，可能原因:")
        print(f"      • 验证码识别错误")
        print(f"      • 账号密码错误")
        print(f"      • 需要额外的验证步骤（如短信验证）")

    # 检查可疑消息
    all_messages = []
    for i in attempts:
        all_messages.extend(attempts[i].get('diagnostics', {}).get('likely_messages', []))

    if any('手机' in msg or '绑定' in msg for msg in all_messages):
        print(f"\n3. 额外发现:")
        print(f"   ⚠️  页面提示需要绑定手机号")
        print(f"   ⚠️  可能需要短信验证才能完成登录")

    print(f"\n{'='*80}")
    print("💡 建议:")
    print("="*80)
    print("1. 使用浏览器手动登录，确认是否需要短信验证")
    print("2. 检查验证码识别的准确率（可以运行验证码测试脚本）")
    print("3. 如果确实需要短信验证，需要更新登录策略")
    print()


def check_login_success_detection():
    """检查登录成功检测逻辑"""
    print("\n" + "="*80)
    print("🔍 登录成功检测逻辑分析")
    print("="*80)

    print("\n从 manual-auth-session.mjs 中查看登录成功的判断标准:")
    print("  • URL 是否变化（离开登录页）")
    print("  • Cookie 数量增加")
    print("  • localStorage 有新数据")
    print("  • 页面出现登录后的特征（如用户名、退出按钮等）")

    print("\n如果这些信号都没有被触发，系统会认为登录失败。")
    print()


if __name__ == '__main__':
    analyze_login_events()
    check_login_success_detection()
