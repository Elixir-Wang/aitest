# SSE 进度推送修复验证指南

## 问题描述

前端探索任务界面一直卡在"正在智能分析探索目标并生成探索计划"阶段，无法收到后续的进度更新。

## 根本原因

`unified_orchestrator.py` 中的 `_record_lifecycle_progress` 方法：
- ✅ 正确更新了数据库中的 `result_summary` 和 `completion_summary`
- ❌ **但没有发布 SSE 事件通知前端**

导致：
- 前端 SSE 连接正常建立
- 但收不到进度更新事件
- 界面显示停留在初始状态

## 修复内容

### 1. 后端修复 (apps/backend/app/services/exploration/unified_orchestrator.py)

```python
def _record_lifecycle_progress(self, summary: str) -> None:
    with connect() as db:
        run = exploration_repo.find_by_id(db, self.run_id)
        if not run:
            return
        exploration_repo.update_run_state(
            db,
            self.run_id,
            status=run["status"],
            result_summary=summary,
        )

        # 🔥 新增：发布运行状态更新事件
        self._publish("run_status_updated", {
            "status": run["status"],
            "result_summary": summary,
        })

        modules = exploration_repo.list_module_coverages(db, self.run_id)
        if not modules:
            return
        module = modules[0]
        exploration_repo.update_module_coverage(
            db,
            exploration_run_id=self.run_id,
            module_key=module["module_key"],
            module_name=module["module_name"],
            entry_path=module["entry_path"],
            planned_page_count=module["planned_page_count"],
            explored_page_count=module["explored_page_count"],
            blocked_page_count=module["blocked_page_count"],
            action_count=module["action_count"],
            field_count=module["field_count"],
            state_transition_count=module["state_transition_count"],
            completion_status=run["status"],
            completion_summary=summary,
        )

        # 🔥 新增：发布模块更新事件
        self._publish("module_updated", {
            "module_id": module["id"],
            "module_key": module["module_key"],
            "module_name": module["module_name"],
            "entry_path": module["entry_path"],
            "planned_page_count": module["planned_page_count"],
            "explored_page_count": module["explored_page_count"],
            "blocked_page_count": module["blocked_page_count"],
            "action_count": module["action_count"],
            "field_count": module["field_count"],
            "state_transition_count": module["state_transition_count"],
            "completion_status": run["status"],
            "completion_summary": summary,
        })
```

### 2. 前端修复 (apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx)

```typescript
// 处理运行状态事件
if (
  event.type === "run_started" ||
  event.type === "run_completed" ||
  event.type === "run_failed" ||
  event.type === "run_cancelled" ||
  event.type === "run_status_updated"  // 🔥 新增
) {
  setters.setRun((current) => (current ? { ...current, ...(event.payload as Partial<ExplorationRun>) } : current));
  setters.setStreamDetail((current) =>
    current ? { ...current, run: { ...current.run, ...(event.payload as Partial<ExplorationRun>) } } : current,
  );
}
```

## 验证步骤

### 方式一：手动测试（推荐）

1. **启动后端服务**
   ```bash
   cd /Users/wanghongbao/project/test_project
   cd apps/backend
   source .venv/bin/activate  # 如果有虚拟环境
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **启动前端服务**（新终端）
   ```bash
   cd /Users/wanghongbao/project/test_project/apps/frontend
   npm run dev
   ```

3. **打开浏览器**
   - 访问：http://localhost:3000
   - 登录系统
   - 进入某个探索任务详情页

4. **点击"重新开始"或"开始探索"按钮**

5. **观察前端界面**
   - ✅ 应该能看到进度实时更新
   - ✅ "当前运行阶段"的文字会动态变化
   - ✅ 从"正在智能分析探索目标" → "探索计划已生成" → "开始执行探索计划" → ...

### 方式二：使用 SSE 监控脚本

1. **获取项目和任务 ID**
   - 从浏览器 URL 中获取：`/projects/{project_id}/exploration/{run_id}`

2. **运行监控脚本**
   ```bash
   ./test_sse_events.sh <project_id> <run_id>
   ```

3. **在另一个终端启动探索任务**
   ```bash
   curl -X POST http://localhost:8000/api/projects/{project_id}/exploration-runs/{run_id}/start \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer <your_token>"
   ```

4. **观察 SSE 事件流**
   - 应该能看到大量的事件流输出，包括：
     - `run_started`
     - `planning_started`
     - `planning_completed`
     - `run_status_updated` ⭐ 关键事件
     - `module_updated` ⭐ 关键事件
     - `step_recorded`
     - `step_started`
     - `step_completed`
     - ...

### 方式三：浏览器开发者工具

1. 打开浏览器开发者工具（F12）
2. 切换到 Network 标签
3. 过滤：`stream`
4. 点击"开始探索"
5. 查看 SSE 连接的实时数据流
6. 应该能看到 `event: run_status_updated` 和 `event: module_updated`

## 预期结果

### 修复前
- ❌ 前端显示卡在"正在智能分析探索目标并生成探索计划"
- ❌ SSE 连接建立但没有收到 `run_status_updated` 事件
- ❌ 数据库有更新，但前端无法感知

### 修复后
- ✅ 前端实时显示进度："正在智能分析..." → "探索计划已生成" → "开始执行..." → ...
- ✅ SSE 流中能看到 `run_status_updated` 和 `module_updated` 事件
- ✅ 前端界面随着后端进度动态更新

## 关键事件说明

| 事件类型 | 触发时机 | 前端效果 |
|---------|---------|---------|
| `run_started` | 探索任务启动 | 显示"探索中"状态 |
| `run_status_updated` | 每次更新进度 | 更新 `result_summary` 显示 |
| `module_updated` | 模块状态变化 | 更新模块的 `completion_summary` |
| `planning_started` | 开始规划 | 日志记录 |
| `planning_completed` | 规划完成 | 日志记录 |
| `step_recorded` | 记录步骤 | 在任务树中显示步骤 |
| `page_completed` | 页面探索完成 | 添加页面到列表 |
| `run_completed` | 探索完成 | 显示完成状态 |

## 数据流说明

```
后端执行流程：
┌─────────────────────────────────────────────┐
│ unified_orchestrator.run()                  │
│                                             │
│ 1. _record_lifecycle_progress()             │
│    ├─ 更新数据库 (result_summary)           │
│    ├─ _publish("run_status_updated") 🔥新增 │
│    └─ _publish("module_updated") 🔥新增      │
│                                             │
│ 2. _execute_unified()                       │
│    ├─ _publish_step_recorded()              │
│    └─ _publish("step_completed")            │
│                                             │
│ 3. event_bus.publish() → SSE 推送           │
└─────────────────────────────────────────────┘
                    ↓
                 SSE 流
                    ↓
┌─────────────────────────────────────────────┐
│ 前端接收流程：                               │
│                                             │
│ 1. useEffect() 建立 SSE 连接                │
│    └─ /stream endpoint                      │
│                                             │
│ 2. parseStreamEvent() 解析事件              │
│                                             │
│ 3. applyStreamEvent() 应用事件              │
│    ├─ run_status_updated → 更新 run 🔥新增  │
│    ├─ module_updated → 更新 module          │
│    ├─ step_recorded → 添加步骤              │
│    └─ page_completed → 添加页面             │
│                                             │
│ 4. React 状态更新 → UI 重新渲染             │
└─────────────────────────────────────────────┘
```

## 常见问题排查

### 1. 前端还是收不到事件？
- 检查浏览器控制台是否有错误
- 检查 Network 标签中 SSE 连接状态
- 确认后端服务正常运行
- 检查跨域配置（CORS）

### 2. 事件收到了但界面不更新？
- 检查浏览器控制台 `[探索进度]` 日志
- 确认 React 状态是否正确更新
- 检查 `applyStreamEvent` 函数逻辑

### 3. 后端没有发送事件？
- 检查 `event_bus.publish` 是否被调用
- 确认 `_publish` 方法没有被覆盖
- 查看后端日志是否有异常

## 技术细节

### SSE 事件总线实现 (event_bus.py)
```python
# 基于内存的发布订阅模式
_subscribers: dict[str, set[queue.Queue]] = {}

def publish(run_id: str, event_type: str, payload: dict) -> None:
    event = {"type": event_type, "run_id": run_id, "payload": payload}
    with _lock:
        subscribers = list(_subscribers.get(run_id, set()))
    for subscriber in subscribers:
        subscriber.put(event)  # 推送到订阅者队列

def subscribe(run_id: str) -> Iterator[dict | None]:
    subscriber = queue.Queue()
    with _lock:
        _subscribers.setdefault(run_id, set()).add(subscriber)
    try:
        while True:
            event = subscriber.get(timeout=heartbeat_seconds)
            yield event
    finally:
        # 清理订阅
```

## 总结

本次修复解决了探索任务进度推送的核心问题，确保：
1. ✅ 每次数据库更新都同步发送 SSE 事件
2. ✅ 前端能实时收到并显示进度变化
3. ✅ 用户体验大幅提升，不再卡在加载状态

修复文件：
- `apps/backend/app/services/exploration/unified_orchestrator.py`
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

验证完成后，这应该是**最后一次修复**！🎉
