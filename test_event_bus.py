import sys
sys.path.insert(0, 'apps/backend')

from app.services.exploration import event_bus

# 检查事件总线状态
print("=== Event Bus 状态 ===")
print(f"订阅者字典: {event_bus._subscribers}")
print(f"订阅者数量: {len(event_bus._subscribers)}")

for run_id, subscribers in event_bus._subscribers.items():
    print(f"\nRun ID: {run_id}")
    print(f"  订阅者数量: {len(subscribers)}")

# 测试发布事件
test_run_id = "explore-01b554b4f26ba242"
print(f"\n=== 测试发布事件到 {test_run_id} ===")
event_bus.publish(test_run_id, "test_event", {"message": "测试消息"})
print("事件已发布")
