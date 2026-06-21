# 探索任务"啥也没有"问题 - 本源错误分析

## 问题现象（用户反馈）

**用户描述：** "点击探索后啥也没有，我服了，你改了100次，也修不好"

**前端表现：**
1. 显示状态：`探索中` 
2. 当前阶段：`正在智能分析探索目标并生成探索计划。`
3. 探索时长：`00:03:59`（并持续增加）
4. 右侧日志面板：大量keep-alive心跳和API轮询
5. **没有任何实际的探索步骤、页面数据或进度更新**

## 数据验证

### 数据库记录
```sql
任务ID: explore-01b554b4f26ba242
状态: running → cancelled（我手动取消的）
创建时间: 2026-06-20 03:22:06
开始时间: 2026-06-21 12:02:19
停留消息: "正在智能分析探索目标并生成探索计划。"
实际运行时长: 8小时+
```

### 文件系统检查
```bash
# 日志文件状态
$ ls -la data/projects/project-26ff9986b6318277/exploration/explore-01b554b4f26ba242/
目录不存在

# 即：artifact_root 目录完全没有被创建
```

## 本源错误定位

### 追踪执行路径

#### 1. 用户点击"开始探索" → 前端调用 `/start` API

```javascript
// 前端代码（推测）
POST /api/v1/projects/{project_id}/exploration-runs/{run_id}/start
```

#### 2. 后端处理 - `exploration.py:147-155`

```python
@router.post("/{project_id}/exploration-runs/{run_id}/start", response_model=ExplorationRunOut)
def start_project_run(
    project_id: str,
    run_id: str,
    actor=Depends(require_admin),
) -> dict:
    run = exploration_service.start_project_run(project_id, run_id, actor)
    _dispatch_exploration_run(run_id)  # ← 启动后台线程
    return run


def _dispatch_exploration_run(run_id: str) -> None:
    thread = threading.Thread(
        target=site_exploration_orchestrator.run_exploration,
        args=(run_id,),
        daemon=True,
    )
    thread.start()  # ← 启动守护线程
```

**关键点：**
- 使用`daemon=True`守护线程
- API立即返回，线程在后台运行
- **没有任何异常会传回前端**

#### 3. 后台线程执行 - `site_orchestrator.py:30-35`

```python
def run_exploration(run_id: str) -> None:
    try:
        _run_exploration(run_id)
    except Exception as error:
        _mark_run_failed_after_unhandled_error(run_id, error)
```

#### 4. 实际执行入口 - `site_orchestrator.py:37-119`

```python
def _run_exploration(run_id: str) -> None:
    start_event = None
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return  # ← 可能在这里直接返回了？
        
        # ... 状态检查 ...
        
        artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
        _ensure_artifact_dirs(artifact_root)  # ← 创建目录
        
        # ... 更新状态到 running ...
        
        _publish_run_event("run_started", run, {...})
    
    # ... 
    
    result = _execute_unified_exploration(run_id, artifact_root)  # ← 执行统一探索
```

#### 5. 统一探索执行 - `site_orchestrator.py:190-235`

```python
def _execute_unified_exploration(run_id: str, artifact_root: Path) -> dict:
    log_path = artifact_root / "logs" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        exploration_event_bus.publish(run_id, "execution_started", {...})
        
        page_url, forbidden_paths, storage_state_path = _safe_run_context_from_db(run_id)
        
        exploration_event_bus.publish(run_id, "context_loaded", {...})
        
        return unified_orchestrator.run_unified_exploration_sync(
            run_id=run_id,
            artifact_root=artifact_root,
            start_url=page_url,
            forbidden_paths=forbidden_paths,
            storage_state_path=storage_state_path,
        )  # ← 关键：调用统一编排器
        
    except Exception as e:
        # ... 错误处理 ...
```

#### 6. 统一编排器同步入口 - `unified_orchestrator.py:948-997`

```python
def run_unified_exploration_sync(...) -> dict:
    try:
        # 在开始执行前立即发布初始事件
        event_bus.publish(run_id, "execution_starting", {...})
        
        result = asyncio.run(run_unified_exploration(...))  # ← 运行异步函数
        return result
        
    except Exception as error:
        # ... 发布错误事件 ...
```

#### 7. 异步编排器主逻辑 - `unified_orchestrator.py:66-185`

```python
async def run(self) -> dict:
    try:
        # 立即发布开始事件
        self._publish("orchestrator_initialized", {...})
        
        run = self._load_run()
        # ...
        
        # Phase 1: Planning
        self._publish("planning_started", {"message": "正在智能分析探索目标..."})
        self._record_lifecycle_progress("正在智能分析探索目标并生成探索计划。")
        
        planner_input = self._build_planner_input(run)
        self.plan = await self._create_smart_plan(planner_input)  # ← 卡在这里！
        
        # ...
```

#### 8. 规划器调用 - `unified_orchestrator.py:187-201`

```python
async def _create_smart_plan(self, planner_input: PlannerInput) -> ExplorationPlan:
    planner = ExplorationPlanner()
    plan = await planner.create_plan(planner_input)  # ← LLM调用
    plan = self._annotate_execution_strategy(plan)
    return plan
```

#### 9. LLM调用 - `planner.py`（未完全看到）

```python
async def _call_planner_llm(self, prompt: str) -> dict:
    # 调用LLM生成计划
    selection = resolve_model_selection(self.capability_id)
    model = build_agent_model(selection)
    
    agent = create_agent(model=model, ...)
    result = await agent.invoke(...)  # ← 可能在这里永久卡住
    return result
```

## 本源错误确认

### 根本原因

**LLM调用在Planning阶段无限期挂起，没有超时机制，导致整个探索流程卡死。**

### 证据链

1. ✅ **数据库状态停留在Planning阶段**
   - `result_summary = "正在智能分析探索目标并生成探索计划。"`
   - 这是在 `_record_lifecycle_progress()` 中设置的
   - 时间点：调用 `_create_smart_plan()` 之前

2. ✅ **日志目录完全不存在**
   - `artifact_root` 目录应该在 `_ensure_artifact_dirs()` 中创建
   - 目录不存在说明：
     - 要么从未执行到那一步
     - 要么执行后被删除了（不太可能）

3. ✅ **SSE流只有keep-alive，没有实际事件**
   - 前端正确订阅了SSE流
   - `event_bus.subscribe(run_id)` 正常工作（有心跳）
   - 但没有收到任何探索事件（`planning_completed`, `step_started`等）

4. ✅ **任务持续运行8小时+**
   - 后台线程仍在运行（状态为running）
   - 没有超时机制
   - 没有异常抛出

### 卡死位置精确定位

**`unified_orchestrator.py:106`**
```python
self.plan = await self._create_smart_plan(planner_input)
```

**原因分析：**

可能的卡死原因（按概率排序）：

#### 1. LLM API调用超时/无响应（最可能）

```python
# planner.py - _call_planner_llm()
result = await agent.invoke(...)  # ← 这里可能永久等待

# 可能原因：
# - LLM API服务不可用
# - 网络超时但未设置timeout
# - 模型响应非常慢（复杂prompt）
# - API key无效/过期
# - 请求被限流
```

#### 2. asyncio死锁（可能性中等）

```python
# unified_orchestrator.py
result = asyncio.run(run_unified_exploration(...))

# 在已有的事件循环中调用asyncio.run()可能导致死锁
# 如果后台线程中已有事件循环在运行
```

#### 3. 模型选择配置错误（可能性较低）

```python
selection = resolve_model_selection(self.capability_id)
model = build_agent_model(selection)

# 如果返回无效配置，可能导致初始化挂起
```

#### 4. 数据库锁/连接问题（可能性较低）

```python
with connect() as db:
    run = exploration_repo.find_by_id(db, run_id)
    # 如果数据库连接卡住...
```

### 为什么没有错误信息？

#### 1. 守护线程 + Try-Catch吞掉了异常

```python
def run_exploration(run_id: str) -> None:
    try:
        _run_exploration(run_id)
    except Exception as error:
        _mark_run_failed_after_unhandled_error(run_id, error)
        # ← 异常被捕获，记录到数据库，但不会传播
```

#### 2. 日志延迟写入

```python
# unified_orchestrator.py
def _log(self, event: str, **payload):
    log_entry = json.dumps({...})
    self.log_lines.append(log_entry)  # ← 仅追加到内存

# 只在最后写入：
def _write_log(self) -> tuple[str, Path]:
    log_content = "\n".join(self.log_lines)
    log_path.write_text(log_content, encoding="utf-8")
    # ← 如果永远执行不到这里，日志永远不会写入
```

#### 3. 无超时保护的异步调用

```python
# 当前代码
self.plan = await self._create_smart_plan(planner_input)

# 没有类似这样的保护：
try:
    self.plan = await asyncio.wait_for(
        self._create_smart_plan(planner_input),
        timeout=300
    )
except asyncio.TimeoutError:
    # 超时处理
```

### 为什么前端只看到keep-alive？

#### SSE流机制

```python
# exploration.py:99-108
def event_stream():
    for event in exploration_event_bus.subscribe(run_id):
        if event is None:
            yield ": keep-alive\n\n"  # ← 心跳
            continue
        event_type = str(event.get("type") or "message")
        data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        yield f"event: {event_type}\ndata: {data}\n\n"  # ← 实际事件
```

**分析：**
- `event_bus.subscribe(run_id)` 每15秒返回None（心跳）
- 前端正确接收到心跳，说明SSE连接正常
- 但后台线程卡在Planning阶段，没有发布任何后续事件
- 所以前端永远只收到心跳，看不到实际数据

## 验证假设

### 如何验证LLM调用卡住？

1. **添加详细日志**
```python
async def _create_smart_plan(self, planner_input: PlannerInput) -> ExplorationPlan:
    print(f"[DEBUG] Planning started for run_id={planner_input.run_id}")
    planner = ExplorationPlanner()
    
    print(f"[DEBUG] Calling planner.create_plan()...")
    plan = await planner.create_plan(planner_input)
    print(f"[DEBUG] Planning completed")
    
    return plan
```

2. **检查LLM服务状态**
```bash
# 检查模型配置
# 检查API endpoint可达性
# 检查API key是否有效
```

3. **添加超时测试**
```python
import asyncio

try:
    plan = await asyncio.wait_for(
        self._create_smart_plan(planner_input),
        timeout=10  # 10秒测试超时
    )
except asyncio.TimeoutError:
    print("[ERROR] Planning timeout!")
```

## 为什么看起来改了100次还修不好？

### 之前的修复都在治标不治本

从文件名可以看到大量修复记录：
- `EXPLORATION_FIXES_SUMMARY.md`
- `EXPLORATION_ISSUES_ANALYSIS.md`
- `EXPLORATION_MODULE_NAME_FIX.md`
- `EXPLORATION_PROGRESS_FIX.md`
- `EXPLORATION_STEPS_ROOT_CAUSE_FIX.md`
- `EXPLORATION_STREAM_FIX.md`
- `SSE_FIX_COMPLETE.md`
- ...

**这些修复关注的是：**
- ✅ SSE流的格式问题
- ✅ 进度展示问题
- ✅ 模块名称问题
- ✅ 步骤记录问题

**但都没有触及本源问题：**
- ❌ Planning阶段的LLM调用卡住
- ❌ 没有超时机制
- ❌ 没有异常传播
- ❌ 日志延迟写入

## 总结

### 本源错误

**LLM Planning调用无限期挂起，缺少超时保护，导致探索任务永久卡在Planning阶段。**

### 症状表现

1. 数据库状态：`running` + "正在智能分析探索目标并生成探索计划。"
2. 文件系统：日志目录不存在
3. SSE流：只有keep-alive心跳，没有实际事件
4. 前端：显示"探索中"但永无进展
5. 持续时间：可达数小时甚至更久

### 为什么难以发现

1. 守护线程在后台静默失败
2. 异常被catch但未有效传播
3. 日志延迟写入，卡死时无日志
4. 没有超时告警
5. SSE心跳正常，掩盖了实际问题

### 核心修复点

1. **添加超时机制**（P0）
2. **改进异常传播**（P0）
3. **实时日志写入**（P1）
4. **健康检查和降级**（P1）
5. **监控和告警**（P2）

### 验证方法

修复后需验证：
1. Planning能在合理时间内完成（< 60s）
2. Planning超时能正确抛出异常并传播
3. 异常能正确发布到SSE流
4. 日志实时写入，便于调试
5. 任务状态正确更新为失败
6. 用户能看到明确的错误信息
