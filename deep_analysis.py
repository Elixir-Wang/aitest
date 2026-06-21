#!/usr/bin/env python3
"""
深度分析：为什么前端收不到消息
"""
import sqlite3
import glob
import os
from datetime import datetime

print("=" * 60)
print("深度分析：探索任务事件传递失败的原因")
print("=" * 60)
print()

# 检查数据库
db = sqlite3.connect('apps/backend/data/ai_testing.db')
cursor = db.cursor()

# 1. 当前任务状态
print("【步骤1】检查当前任务状态")
cursor.execute("""
    SELECT id, status, result_summary, started_at, updated_at
    FROM exploration_runs
    WHERE status = 'running'
""")
running = cursor.fetchone()

if running:
    task_id, status, summary, started, updated = running
    print(f"✗ 发现卡住的任务: {task_id}")
    print(f"  状态: {status}")
    print(f"  摘要: {summary}")
    print(f"  开始时间: {started}")
    print(f"  更新时间: {updated}")

    # 时间差分析
    if started == updated:
        print(f"  ⚠️  开始时间=更新时间，说明任务启动后立即卡住")
else:
    print("✓ 没有running状态的任务")

print()

# 2. 检查日志文件
print("【步骤2】检查日志文件是否生成")
if running:
    log_pattern = f"apps/backend/data/project-*/exploration/{task_id}/logs/run.log"
    log_files = glob.glob(log_pattern)

    if log_files:
        print(f"✓ 日志文件存在: {log_files[0]}")
        with open(log_files[0], 'r') as f:
            content = f.read()
            print(f"  大小: {len(content)} 字节")
            if content:
                print(f"  内容预览:\n{content[:300]}")
    else:
        print(f"✗ 日志文件不存在")
        print(f"  ⚠️  这说明 unified_orchestrator 根本没有开始执行")

print()

# 3. 检查代码是否包含修复
print("【步骤3】检查代码修复是否存在")
orchestrator_file = 'apps/backend/app/services/exploration/unified_orchestrator.py'
with open(orchestrator_file, 'r') as f:
    content = f.read()

checks = {
    'execution_starting': 'execution_starting 事件发布',
    'orchestrator_initialized': 'orchestrator_initialized 事件发布',
    'except Exception as error:': '异常捕获代码',
    'event_bus.publish(run_id, "execution_error"': '错误事件发布',
}

for key, desc in checks.items():
    if key in content:
        print(f"  ✓ {desc}")
    else:
        print(f"  ✗ {desc}")

print()

# 4. 执行流程分析
print("【步骤4】完整执行流程时序")
print("-" * 60)
print("""
前端点击"重新探索" 按钮
    ↓
① POST /api/v1/projects/{id}/exploration-runs/{id}/start
    ↓
② start_project_run() [exploration.py:148]
    ├─ exploration_service.start_project_run()
    │   └─ 更新数据库: status='queued' ✓
    └─ _dispatch_exploration_run(run_id)
        └─ threading.Thread(target=site_orchestrator.run_exploration).start()
    ↓
③ 后端立即返回 200 OK {status: 'queued'} ✓
    ↓
④ 前端收到响应后，立即发起 SSE 连接
    ↓
⑤ GET /api/v1/projects/{id}/exploration-runs/{id}/stream
    ↓
⑥ stream_project_run() [exploration.py:79]
    ├─ 检查任务状态
    ├─ 如果是 running: 调用 event_bus.subscribe(run_id)
    └─ 返回 StreamingResponse
    ↓
⑦ 前端 SSE 连接建立，开始等待事件 ✓
    ↓
⑧ [子线程] site_orchestrator.run_exploration(run_id) 开始执行
    ├─ _run_exploration()
    ├─ 更新状态: status='running' ✓
    ├─ 发布事件: exploration_event_bus.publish(run_id, 'run_started', ...)
    ├─ _execute_unified_exploration()
    │   └─ unified_orchestrator.run_unified_exploration_sync()
    │       ├─ [新增] event_bus.publish(run_id, 'execution_starting', ...)
    │       └─ asyncio.run(run_unified_exploration(...))
    │           ├─ [新增] self._publish('orchestrator_initialized', ...)
    │           ├─ self._publish('run_started', ...)
    │           └─ ... 更多事件
    └─ 所有事件通过 event_bus 发送到订阅者
    ↓
⑨ [主线程] stream endpoint 的生成器收到事件
    ↓
⑩ SSE 推送事件到前端 ✓

当前实际情况:
✓ 步骤 ①-③: POST /start 成功
✓ 步骤 ④-⑦: SSE 连接建立成功
✓ 步骤 ⑧: 状态更新为 running
✗ 步骤 ⑧: 没有发布任何事件
✗ 步骤 ⑨-⑩: 前端只收到 keep-alive
""")
print("-" * 60)

print()

# 5. 核心问题定位
print("【步骤5】核心问题定位")
print()
print("根据症状分析，问题出在:")
print()
print("❌ 问题点: unified_orchestrator.run_unified_exploration_sync() 没有被执行")
print()
print("可能的原因:")
print("  1. ❗️ 后端服务没有重启，还在使用旧代码（最可能）")
print("  2. 子线程启动失败")
print("  3. _execute_unified_exploration() 在调用前就出错")
print("  4. asyncio.run() 遇到运行时错误")
print()

# 6. 验证方案
print("【步骤6】立即验证方案")
print()
print("方案A: 检查后端服务是否使用新代码")
print("  1. 重启后端服务（务必确认重启成功）")
print("  2. 重置卡住的任务:")
print(f"     sqlite3 apps/backend/data/ai_testing.db \"UPDATE exploration_runs SET status='blocked', result_summary='已重置，请重新启动' WHERE status='running';\"")
print("  3. 创建新任务并观察")
print()

print("方案B: 添加临时调试日志")
print("  在 site_orchestrator.py 的 _execute_unified_exploration() 开始处添加:")
print("  ```python")
print("  log_path.write_text('DEBUG: _execute_unified_exploration called\\n', encoding='utf-8')")
print("  ```")
print()

print("方案C: 检查是否有运行时异常")
print("  查看后端控制台输出或日志文件")
print()

db.close()

print("=" * 60)
print("分析完成")
print("=" * 60)
