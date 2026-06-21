#!/usr/bin/env python3
import sqlite3
import glob
import os

print("=== 探索任务诊断 ===\n")

# 1. 检查running任务
db = sqlite3.connect('apps/backend/data/ai_testing.db')
cursor = db.cursor()
cursor.execute("SELECT id, status, result_summary FROM exploration_runs WHERE status = 'running'")
running_tasks = cursor.fetchall()

if running_tasks:
    print(f"发现 {len(running_tasks)} 个running任务:")
    for task_id, status, summary in running_tasks:
        print(f"  ID: {task_id}")
        print(f"  状态: {status}")
        print(f"  摘要: {summary}")

        # 检查日志目录
        log_pattern = f"apps/backend/data/project-*/exploration/{task_id}/logs/run.log"
        log_files = glob.glob(log_pattern)
        if log_files:
            print(f"  ✓ 日志文件存在: {log_files[0]}")
        else:
            print(f"  ✗ 日志文件不存在")
            print(f"  ⚠️  问题: 任务标记为running但没有生成日志")
            print(f"  ⚠️  原因: 异步任务可能卡住或异常退出")
        print()
else:
    print("没有running状态的任务\n")

db.close()

print("\n=== 建议 ===")
if running_tasks and not glob.glob(f"apps/backend/data/project-*/exploration/{running_tasks[0][0]}/logs"):
    print("1. 任务卡在初始化阶段，需要检查:")
    print("   - unified_orchestrator.py 的异步执行")
    print("   - 是否有未捕获的异常")
    print("   - playwright依赖是否正常")
    print("\n2. 修复步骤:")
    print("   - 添加详细的异常日志")
    print("   - 在run()方法开始时立即发布事件")
    print("   - 确保所有异常都被捕获并发布错误事件")
