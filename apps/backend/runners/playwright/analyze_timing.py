import json

with open('data/projects/debug/test-fix-events.jsonl', 'r') as f:
    events = [json.loads(line) for line in f if line.strip()]

print("=" * 60)
print("详细时间分析")
print("=" * 60)
print()

for i, event in enumerate(events):
    if event['kind'] == 'captcha_challenge':
        attempt = event.get('attempt', 0)
        
        # 找前一个事件
        prev_event = events[i-1] if i > 0 else None
        
        if prev_event:
            time_diff = event['timestamp'] - prev_event['timestamp']
            print(f"第{attempt}次尝试:")
            print(f"  前一事件: {prev_event['kind']}")
            print(f"  时间差: {time_diff}ms ({time_diff/1000:.2f}秒)")
            
            # 如果是第2、3次，找login_attempt事件
            if attempt > 1:
                for j in range(i-1, -1, -1):
                    if events[j]['kind'] == 'login_attempt':
                        prep_time = event['timestamp'] - events[j]['timestamp']
                        print(f"  从login_attempt到captcha_challenge: {prep_time}ms ({prep_time/1000:.2f}秒)")
                        print(f"  ⚠️  这段时间在做: refreshCaptchaImage + waitForCaptchaSurface")
                        break
            print()
