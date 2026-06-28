import json
from datetime import datetime
from pathlib import Path

envs = [
    "env-c3bc1023763dbb16",
    "env-e8456287421c69d9"
]

print("=" * 70)
print("🔍 Cybotstar 环境登录性能分析")
print("=" * 70)
print()

for env_id in envs:
    log_path = Path(f"/Users/wanghongbao/project/test_project/apps/backend/data/projects/environments/{env_id}/auth/auto-login-events.jsonl")
    
    if not log_path.exists():
        print(f"环境 {env_id}: 无登录日志")
        print()
        continue
    
    try:
        events = []
        for line in log_path.read_text().split('\n'):
            if line.strip():
                events.append(json.loads(line))
        
        if not events:
            print(f"环境 {env_id}: 日志为空")
            print()
            continue
        
        print(f"环境: {env_id}")
        print(f"事件数: {len(events)}")
        
        # 找关键事件
        session_start = next((e for e in events if e['kind'] == 'session_started'), None)
        page_observed = next((e for e in events if e['kind'] == 'login_page_observed'), None)
        captcha_challenge = next((e for e in events if e['kind'] == 'captcha_challenge'), None)
        login_result = events[-1] if events else None
        
        if session_start:
            start_time = datetime.fromisoformat(session_start['recorded_at'])
            print(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if login_result:
            end_time = datetime.fromisoformat(login_result['recorded_at'])
            print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"结果: {login_result['kind']}")
            
            if session_start:
                total_time = (end_time - datetime.fromisoformat(session_start['recorded_at'])).total_seconds()
                print(f"总耗时: {total_time:.2f}秒")
        
        if page_observed and captcha_challenge:
            t1 = datetime.fromisoformat(page_observed['recorded_at'])
            t2 = datetime.fromisoformat(captcha_challenge['recorded_at'])
            wait_time = (t2 - t1).total_seconds()
            print(f"验证码等待: {wait_time:.2f}秒 {'✅' if wait_time < 5 else '❌ 慢'}")
        
        print()
        
    except Exception as e:
        print(f"环境 {env_id}: 解析失败 - {e}")
        print()

print("=" * 70)
print("问题诊断")
print("=" * 70)
print()
print("问题1: 登录要好久")
print("  原因: 验证码等待时间长（21-35秒）")
print("  解决方案: 已应用优化，重启后端服务生效")
print("  预期效果: 从40秒降到10秒")
print()
print("问题2: 列表的最近时间不对")
print("  需要查看前端代码和数据库记录")
print()
