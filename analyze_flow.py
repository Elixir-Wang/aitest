#!/usr/bin/env python3
"""
分析探索任务的完整执行流程
"""
import sqlite3
import threading
import time

print("=== 探索任务执行流程分析 ===\n")

# 1. 检查后端进程和线程
print("1. 检查后端服务状态...")
import subprocess
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
backend_processes = [line for line in result.stdout.split('\n') if 'uvicorn' in line or 'python' in line and 'backend' in line]
if backend_processes:
    print(f"   找到 {len(backend_processes)} 个可能的后端进程:")
    for proc in backend_processes[:3]:
        print(f"   {proc[:100]}...")
else:
    print("   ⚠️  未找到运行中的后端进程")
print()

# 2. 检查数据库状态
print("2. 检查数据库中的任务状态...")
db = sqlite3.connect('apps/backend/data/ai_testing.db')
cursor = db.cursor()

# 查看最近的任务
cursor.execute("""
    SELECT id, status, result_summary, created_at, started_at, updated_at
    FROM exploration_runs
    ORDER BY created_at DESC
    LIMIT 3
""")
recent_tasks = cursor.fetchall()
print("   最近3个任务:")
for task in recent_tasks:
    print(f"   - ID: {task[0]}")
    print(f"     状态: {task[1]}")
    print(f"     摘要: {task[2][:60]}...")
    print(f"     创建: {task[3]}")
    print(f"     开始: {task[4]}")
    print(f"     更新: {task[5]}")
    print()

# 3. 分析问题
print("3. 问题分析...")
running_tasks = [t for t in recent_tasks if t[1] == 'running']
if running_tasks:
    task = running_tasks[0]
    task_id = task[0]
    started_at = task[4]
    updated_at = task[5]

    print(f"   任务 {task_id} 状态为 running")
    print(f"   开始时间: {started_at}")
    print(f"   更新时间: {updated_at}")

    # 检查时间差
    if started_at and updated_at:
        print(f"   ⚠️  任务启动后没有再更新，可能卡死了")

    # 检查日志
    import glob
    log_files = glob.glob(f"apps/backend/data/project-*/exploration/{task_id}/logs/run.log")
    if not log_files:
        print(f"   ✗ 日志文件不存在")
        print(f"   ⚠️  关键问题: 任务线程可能根本没有启动或立即崩溃")
    else:
        print(f"   ✓ 日志文件: {log_files[0]}")
        with open(log_files[0], 'r') as f:
            content = f.read()
            print(f"   日志内容 ({len(content)} 字节):")
            print(f"   {content[:500]}")

print()

# 4. 检查后端日志
print("4. 检查后端服务日志...")
import glob
backend_log_files = glob.glob("apps/backend/*.log") + glob.glob("apps/backend/logs/*.log")
if backend_log_files:
    print(f"   找到日志文件: {backend_log_files}")
    # 读取最近的错误
    for log_file in backend_log_files[:2]:
        print(f"\n   读取 {log_file} 最后50行:")
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-50:]:
                    if 'error' in line.lower() or 'exception' in line.lower() or 'traceback' in line.lower():
                        print(f"     {line.strip()}")
        except Exception as e:
            print(f"     读取失败: {e}")
else:
    print("   未找到后端日志文件")

print()

# 5. 执行流程时序分析
print("5. 执行流程时序分析...")
print("""
   正常流程应该是:

   [前端] 点击"重新探索"
      ↓
   [前端] POST /api/v1/projects/{project_id}/exploration-runs/{run_id}/start
      ↓
   [后端] start_project_run() 被调用
      ↓
   [后端] exploration_service.start_project_run()
      - 更新数据库状态为 'queued'
      - 返回任务信息
      ↓
   [后端] _dispatch_exploration_run(run_id)
      - 创建新线程: threading.Thread(target=site_orchestrator.run_exploration)
      - thread.start()
      ↓
   [后端] 立即返回响应给前端
      ↓
   [前端] 收到响应后，立即调用 GET /api/v1/projects/{project_id}/exploration-runs/{run_id}/stream
      ↓
   [后端] stream_project_run() 被调用
      - exploration_event_bus.subscribe(run_id) 开始订阅
      - 返回 StreamingResponse
      ↓
   [子线程] site_orchestrator.run_exploration(run_id) 执行
      - 更新状态为 'running'
      - 调用 unified_orchestrator.run_unified_exploration_sync()
      - 发布事件到 event_bus
      ↓
   [主线程] stream endpoint 的生成器从 event_bus 读取事件
      ↓
   [前端] 通过 SSE 接收事件

   当前问题:
   ✗ 子线程启动后没有发布任何事件
   ✗ 前端只收到 keep-alive (15秒超时返回的None)

   可能的原因:
   A. 子线程启动失败或立即崩溃
   B. unified_orchestrator 中抛出异常但没被捕获
   C. event_bus.publish() 没有被调用
   D. 代码修改后没有重启服务（还在用旧代码）
""")

print()

# 6. 验证修复是否生效
print("6. 验证代码修复是否生效...")
with open('apps/backend/app/services/exploration/unified_orchestrator.py', 'r') as f:
    content = f.read()
    if 'execution_starting' in content:
        print("   ✓ 修复代码已存在")
    else:
        print("   ✗ 修复代码不存在")

    if 'except Exception as error:' in content and 'run_unified_exploration_sync' in content:
        print("   ✓ 异常捕获代码已添加")
    else:
        print("   ✗ 异常捕获代码缺失")

print()
print("=== 核心结论 ===")
print("问题: 后端服务可能没有重启，还在使用旧代码！")
print("解决方案:")
print("1. 立即重启后端服务")
print("2. 重置卡住的任务")
print("3. 重新测试")

db.close()
