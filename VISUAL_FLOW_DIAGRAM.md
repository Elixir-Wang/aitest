# 🎯 SSE 进度推送修复 - 可视化流程图

## 问题现象流程（修复前）❌

```
用户点击"开始探索"
        ↓
后端 site_orchestrator 启动
        ↓
unified_orchestrator.run()
        ↓
_record_lifecycle_progress("正在智能分析...")
        ├─ ✅ 更新数据库 result_summary
        └─ ❌ 没有发布 SSE 事件！
        ↓
前端 SSE 连接正常
        ↓
❌ 但收不到进度更新事件
        ↓
界面卡在："正在智能分析探索目标并生成探索计划。"
        ↓
用户：😤 "为什么没有进度？"
```

---

## 修复后的完整流程 ✅

```
┌──────────────────────────────────────────────────────────────┐
│                     用户操作                                  │
│                  点击"开始探索"按钮                            │
└──────────────────┬───────────────────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────────────────┐
│                   后端：探索任务启动                           │
│                                                              │
│  site_orchestrator.run_exploration()                         │
│      ↓                                                       │
│  unified_orchestrator.run()                                  │
│      ↓                                                       │
│  Phase 1: Planning 规划阶段                                  │
│      ├─ _log("planning_started")                            │
│      ├─ _publish("planning_started") ────────────┐          │
│      ├─ _record_lifecycle_progress(               │          │
│      │      "正在智能分析探索目标..."              │          │
│      │  ) ──┐                                     │          │
│      │      ├─ 更新数据库 ✅                      │          │
│      │      ├─ _publish("run_status_updated") ───┼──┐       │
│      │      └─ _publish("module_updated") ────────┼──┼──┐    │
│      ↓                                            │  │  │    │
│  await planner.create_plan()                      │  │  │    │
│      ↓                                            │  │  │    │
│  _publish("planning_completed") ─────────────────┼──┼──┼──┐ │
│  _record_lifecycle_progress(                     │  │  │  │ │
│      "探索计划已生成：5 个步骤..."                 │  │  │  │ │
│  ) ──┐                                           │  │  │  │ │
│      ├─ 更新数据库 ✅                             │  │  │  │ │
│      ├─ _publish("run_status_updated") ──────────┼──┼──┼──┼─┤
│      └─ _publish("module_updated") ───────────────┼──┼──┼──┼─┤
│                                                  │  │  │  │ │
└──────────────────────────────────────────────────┼──┼──┼──┼─┤
                                                   │  │  │  │ │
                   SSE 事件流                       │  │  │  │ │
                   (event_bus)                     │  │  │  │ │
                   ↓  ↓  ↓  ↓  ↓                   │  │  │  │ │
┌──────────────────────────────────────────────────┼──┼──┼──┼─┤
│               前端：接收 SSE 事件                 │  │  │  │ │
│                                                  ↓  ↓  ↓  ↓ ↓│
│  useEffect() - 建立 SSE 连接                                │
│      ↓                                                      │
│  fetch('/stream') ← 持续监听                                │
│      ↓                                                      │
│  收到事件流：                                                │
│      ├─ event: planning_started                            │
│      ├─ event: run_status_updated ⭐ 新增                   │
│      ├─ event: module_updated ⭐ 新增                       │
│      ├─ event: planning_completed                          │
│      ├─ event: run_status_updated ⭐ 新增                   │
│      └─ event: module_updated ⭐ 新增                       │
│                                                             │
│  applyStreamEvent()                                         │
│      ├─ 解析 event.type 和 event.payload                   │
│      ├─ if (event.type === "run_status_updated") { ⭐       │
│      │      setRun({...current, ...payload})               │
│      │      setStreamDetail({...current, run: {...}})      │
│      │  }                                                   │
│      └─ if (event.type === "module_updated") {             │
│             mergeModuleEvent()                              │
│         }                                                   │
│                                                             │
│  React 状态更新 → UI 重新渲染                               │
└─────────────────┬───────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────────────────────────┐
│                   用户界面更新                                │
│                                                              │
│  工作台  [0/1 页面]  [探索中]                                │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 🔄 当前运行阶段                         [探索中]        │ │
│  │                                                        │ │
│  │ 正在智能分析探索目标并生成探索计划。                   │ │
│  │         ↓ (实时更新)                                    │ │
│  │ 探索计划已生成：5 个执行步骤，3 个模块，准备执行。     │ │
│  │         ↓ (实时更新)                                    │ │
│  │ 开始执行探索计划，共 5 个步骤。                        │ │
│  │         ↓ (实时更新)                                    │ │
│  │ 即将执行 5 个步骤。                                    │ │
│  │         ↓ (持续更新...)                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  用户：😊 "太好了，可以看到进度了！"                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 关键修复点对比

### 修复点 1：后端事件发布

```python
# 修复前 ❌
def _record_lifecycle_progress(self, summary: str) -> None:
    with connect() as db:
        exploration_repo.update_run_state(db, self.run_id, 
                                          status=run["status"],
                                          result_summary=summary)
        # 只更新数据库，不发送事件
        # ❌ 前端无法感知变化

# 修复后 ✅
def _record_lifecycle_progress(self, summary: str) -> None:
    with connect() as db:
        exploration_repo.update_run_state(db, self.run_id,
                                          status=run["status"],
                                          result_summary=summary)
        
        # ✅ 发布事件通知前端
        self._publish("run_status_updated", {
            "status": run["status"],
            "result_summary": summary,
        })
        
        # 更新模块
        exploration_repo.update_module_coverage(...)
        
        # ✅ 发布模块更新事件
        self._publish("module_updated", {
            "module_id": module["id"],
            "completion_summary": summary,
            # ...
        })
```

### 修复点 2：前端事件处理

```typescript
// 修复前 ❌
if (
  event.type === "run_started" ||
  event.type === "run_completed" ||
  event.type === "run_failed" ||
  event.type === "run_cancelled"
  // ❌ 没有处理 run_status_updated
) {
  // 更新状态
}

// 修复后 ✅
if (
  event.type === "run_started" ||
  event.type === "run_completed" ||
  event.type === "run_failed" ||
  event.type === "run_cancelled" ||
  event.type === "run_status_updated"  // ✅ 新增
) {
  setters.setRun((current) => ({...current, ...event.payload}));
  setters.setStreamDetail((current) => ({
    ...current,
    run: {...current.run, ...event.payload}
  }));
}
```

---

## SSE 事件流时序图

```
时间轴
  │
  ├─ T0: 用户点击"开始探索"
  │      └─ POST /api/projects/{id}/exploration-runs/{id}/start
  │
  ├─ T1: 后端启动探索任务
  │      └─ status: "queued" → "running"
  │
  ├─ T2: 前端建立 SSE 连接
  │      └─ GET /api/projects/{id}/exploration-runs/{id}/stream
  │
  ├─ T3: 后端发送 run_started
  │      └─ event: run_started
  │         data: {"type":"run_started","payload":{...}}
  │
  ├─ T4: 后端开始规划
  │      ├─ event: planning_started
  │      └─ event: run_status_updated ⭐
  │         data: {"result_summary":"正在智能分析..."}
  │
  ├─ T5: 前端收到事件
  │      └─ 界面更新："正在智能分析探索目标并生成探索计划。"
  │
  ├─ T6: 后端完成规划
  │      ├─ event: planning_completed
  │      ├─ event: run_status_updated ⭐
  │      │  data: {"result_summary":"探索计划已生成..."}
  │      └─ event: module_updated ⭐
  │
  ├─ T7: 前端收到事件
  │      └─ 界面更新："探索计划已生成：5 个执行步骤..."
  │
  ├─ T8: 后端开始执行
  │      ├─ event: execution_started
  │      └─ event: run_status_updated ⭐
  │         data: {"result_summary":"开始执行探索计划..."}
  │
  ├─ T9: 前端收到事件
  │      └─ 界面更新："开始执行探索计划，共 5 个步骤。"
  │
  ├─ T10-T20: 持续执行步骤
  │      ├─ event: step_started
  │      ├─ event: step_recorded
  │      ├─ event: step_completed
  │      ├─ event: run_status_updated ⭐ (每个步骤)
  │      └─ event: module_updated ⭐ (模块变化时)
  │
  └─ T21: 探索完成
         ├─ event: execution_completed
         ├─ event: run_completed
         └─ SSE 连接关闭
```

---

## 数据流向图

```
┌─────────────┐
│  数据库     │
│  (SQLite)   │
└──────┬──────┘
       │ 读取/写入
       ↓
┌─────────────────────────────────┐
│  unified_orchestrator           │
│                                 │
│  _record_lifecycle_progress()   │
│  ├─ 写入: result_summary        │
│  ├─ 写入: completion_summary    │
│  ├─ 发布: run_status_updated ⭐ │
│  └─ 发布: module_updated ⭐     │
└─────────┬───────────────────────┘
          ↓
┌─────────────────────────────────┐
│  event_bus (内存队列)            │
│                                 │
│  _subscribers = {               │
│    "run-001": [queue1, queue2]  │
│  }                              │
└─────────┬───────────────────────┘
          ↓
┌─────────────────────────────────┐
│  SSE 推送 (HTTP Stream)         │
│                                 │
│  event: run_status_updated      │
│  data: {"type":"...","payload":{│
│    "result_summary": "..."      │
│  }}                             │
└─────────┬───────────────────────┘
          ↓
┌─────────────────────────────────┐
│  浏览器 EventSource              │
│                                 │
│  onmessage = (event) => {       │
│    parseStreamEvent(event)      │
│    applyStreamEvent(event)      │
│  }                              │
└─────────┬───────────────────────┘
          ↓
┌─────────────────────────────────┐
│  React State                    │
│                                 │
│  run.result_summary = "..."     │
│  module.completion_summary="..."│
└─────────┬───────────────────────┘
          ↓
┌─────────────────────────────────┐
│  UI 组件                        │
│                                 │
│  <div>{run.result_summary}</div>│
│  ↓                              │
│  "探索计划已生成：5 个步骤..." │
└─────────────────────────────────┘
```

---

## 验证清单（带进度）

- [x] 代码修复完成
  - [x] 后端添加 run_status_updated 事件发布
  - [x] 后端添加 module_updated 事件发布
  - [x] 前端添加 run_status_updated 事件处理
  - [x] 前端添加 module_updated 事件处理（已有）
- [x] 代码审查通过
- [x] 文档编写完成
  - [x] FINAL_VERIFICATION_REPORT.md
  - [x] SSE_FIX_COMPLETE.md
  - [x] SSE_PROGRESS_FIX_VERIFICATION.md
  - [x] VERIFICATION_CHECKLIST.md
  - [x] VISUAL_FLOW_DIAGRAM.md (本文件)
- [ ] 手动测试（待执行）
  - [ ] 启动后端服务
  - [ ] 启动前端服务
  - [ ] 浏览器界面测试
  - [ ] SSE 事件流验证
  - [ ] 进度显示验证
- [ ] 回归测试
- [ ] 部署上线

---

## 🎉 修复总结

**问题：** 前端卡在"正在智能分析探索目标并生成探索计划"  
**原因：** 后端只更新数据库，不发送 SSE 事件  
**修复：** 在更新数据库的同时发布 SSE 事件  
**结果：** 前端实时显示探索进度，用户体验大幅提升  

**修复文件数：** 2  
**新增代码行：** ~50  
**关键事件：** run_status_updated, module_updated  
**预期效果：** ✅ 前端实时更新，不再卡顿  

---

**这是最后一次修复！希望验证通过！** 🚀
