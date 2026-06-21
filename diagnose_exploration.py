#!/usr/bin/env python3
"""
诊断探索任务实时传递问题
"""
import sys
import os

# 添加backend到路径
sys.path.insert(0, 'apps/backend')
os.chdir('apps/backend')

print("=== 探索任务实时传递问题诊断 ===\n")

# 1. 检查数据库中的任务状态
print("1. 检查数据库中的任务状态...")
import sqlite3
db = sqlite3.connect('data/ai_testing.db')
cursor = db.cursor()

cursor.execute("""
    SELECT id, title, status, result_summary, started_at, finished_at
    FROM exploration_runs
    WHERE status = 'running'
    ORDER BY created_at DESC
""")

running_tasks = cursor.fetchall()
if running_tasks:
    print(f"   发现 {len(running_tasks)} 个运行中的任务:")
    for task in running_tasks:
        print(f"   - ID: {task[0]}")
        print(f"     标题: {task[1]}")
        print(f"     状态: {task[2]}")
        print(f"     摘要: {task[3]}")
        print(f"     开始时间: {task[4]}")
        print()
else:
    print("   没有运行中的任务\n")

# 2. 检查事件总线状态
print("2. 检查事件总线状态...")
try:
    # 直接检查event_bus模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("event_bus", "app/services/exploration/event_bus.py")
    event_bus_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(event_bus_module)

    subscribers = event_bus_module._subscribers
    print(f"   当前订阅者字典: {subscribers}")
    print(f"   订阅者数量: {len(subscribers)}")

    if subscribers:
        for run_id, subscriber_set in subscribers.items():
            print(f"   - Run ID: {run_id}, 订阅者: {len(subscriber_set)}")
    else:
        print("   没有活跃的订阅者")
except Exception as e:
    print(f"   错误: {e}")

print()

# 3. 检查线程状态
print("3. 检查后台线程...")
import threading
threads = threading.enumerate()
print(f"   当前线程数: {len(threads)}")
for thread in threads:
    print(f"   - {thread.name} (daemon={thread.daemon}, alive={thread.is_alive()})")

print()

# 4. 检查日志文件
print("4. 检查探索任务日志...")
if running_tasks:
    for task in running_tasks:
        run_id = task[0]
        log_path = f"data/project-*/exploration/{run_id}/logs/run.log"
        import glob
        log_files = glob.glob(log_path)
        if log_files:
            print(f"   找到日志文件: {log_files[0]}")
            with open(log_files[0], 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
                print(f"   日志行数: {len(lines)}")
                if lines:
                    print(f"   最后几行:")
                    for line in lines[-5:]:
                        print(f"     {line}")
        else:
            print(f"   ⚠️  未找到 {run_id} 的日志文件")

print()

# 5. 诊断结论
print("=== 诊断结论 ===")
if running_tasks:
    import glob
    log_dirs = glob.glob(f"data/project-*/exploration/{running_tasks[0][0]}/logs")
    if not log_dirs:
        print("❌ 问题: 任务状态为running，但日志目录不存在")
        print("   原因: 异步任务可能遇到错误但没有被正确捕获")
        print("   解决方案: ")
        print("   1. 检查unified_orchestrator中的异步执行")
        print("   2. 确保所有异常都被捕获并记录")
        print("   3. 添加更多的调试日志")

if not subscribers:
    print("❌ 问题: 没有活跃的事件订阅者")
    print("   原因: 前端可能没有正确订阅，或订阅后断开")
    print("   解决方案: 检查前端SSE连接逻辑")

print("\n诊断完成。")

db.close()
