# 前后端架构设计 - 探索步骤实时传递与展示

## 📐 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          前端 (React)                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  exploration-workspace.tsx                                │  │
│  │  - 创建探索任务                                            │  │
│  │  - 监听SSE事件流                                          │  │
│  │  - 实时展示步骤进度                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↕ SSE (Server-Sent Events)           │
└─────────────────────────────────────────────────────────────────┘
                               ↕ HTTP/SSE
┌─────────────────────────────────────────────────────────────────┐
│                       后端 (FastAPI)                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  API Layer (exploration.py)                               │  │
│  │  - POST /exploration-runs (创建任务)                       │  │
│  │  - POST /exploration-runs/{id}/start (启动)               │  │
│  │  - GET  /exploration-runs/{id}/stream (SSE流)             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↕                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Event Bus (event_bus.py)                                 │  │
│  │  - publish(run_id, event_type, payload)                   │  │
│  │  - subscribe(run_id) → Iterator[event]                    │  │
│  │  - 内存队列 (Queue) 实现                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            ↕                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Orchestrator (unified_orchestrator.py)                   │  │
│  │  - 执行探索任务                                            │  │
│  │  - 发布实时事件                                            │  │
│  │  - Phase 1: Planning                                      │  │
│  │  - Phase 2: Execution                                     │  │
│  │  - Phase 3: Monitoring                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 完整数据流

### 1️⃣ **创建探索任务**

```typescript
// 前端：exploration-workspace.tsx
async function saveExplorationRun() {
  const payload = {
    environment_id: explorationForm.environmentId,
    title: explorationForm.title,
    scope: explorationForm.scope,
    goal: explorationForm.goal,
    // ...
  };
  
  // POST 创建任务
  const created = await apiRequest<ExplorationRun>(
    `/projects/${targetProjectId}/exploration-runs`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    }
  );
  
  toast.success("探索任务已创建");
}
```

```python
# 后端：exploration.py
@router.post("/{project_id}/exploration-runs", response_model=ExplorationRunOut)
def create_project_run(
    project_id: str,
    payload: ExplorationRunCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return exploration_service.create_project_run(project_id, payload, actor)
```

**结果**：探索任务创建完成，状态为 `pending`

---

### 2️⃣ **启动探索任务**

```typescript
// 前端：点击"启动"按钮
// （实际代码在 exploration run detail 页面，这里简化展示）
async function startExploration(runId: string) {
  await apiRequest(`/projects/${projectId}/exploration-runs/${runId}/start`, {
    method: "POST",
  });
  
  // 立即开始监听SSE流
  connectToEventStream(runId);
}
```

```python
# 后端：exploration.py
@router.post("/{project_id}/exploration-runs/{run_id}/start")
def start_project_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> dict:
    run = exploration_service.start_project_run(project_id, run_id, actor)
    _dispatch_exploration_run(run_id)  # 启动后台线程
    return run

def _dispatch_exploration_run(run_id: str) -> None:
    thread = threading.Thread(
        target=site_exploration_orchestrator.run_exploration,
        args=(run_id,),
        daemon=True,
    )
    thread.start()
```

**结果**：
- 探索任务状态变为 `queued` → `running`
- 后台线程开始执行探索
- 前端开始监听SSE事件流

---

### 3️⃣ **后端执行探索 & 发布事件**

```python
# 后端：unified_orchestrator.py
class UnifiedExplorationOrchestrator:
    async def run(self) -> dict:
        # Phase 1: Planning
        self._publish("planning_started", {"message": "正在智能分析探索目标..."})
        
        self.plan = await self._create_smart_plan(planner_input)
        
        self._publish("planning_completed", {
            "plan_id": self.plan.plan_id,
            "total_steps": len(self.plan.steps),
            "modules": self.plan.modules,
        })
        
        # Phase 2: Execution - 逐步执行
        for step_index, step in enumerate(self.plan.steps):
            # 发布步骤开始事件
            self._publish("step_started", {
                "step_number": step.step_number,
                "total_steps": len(self.plan.steps),
                "description": step.description,
                "module": step.module_name,
                "strategy": step.execution_strategy,
            })
            
            # 执行步骤
            result = self._execute_step(step)
            
            # 发布步骤完成事件
            if result.success:
                self._publish("step_completed", {
                    "step_number": step.step_number,
                    "description": step.description,
                    "message": result.message,
                })
            else:
                self._publish("step_failed", {
                    "step_number": step.step_number,
                    "error": result.error,
                })
        
        # Phase 3: Completion
        self._publish("run_completed", {
            "status": "completed",
            "summary": "探索完成",
        })
        
        return result
    
    def _publish(self, event_type: str, payload: dict):
        """发布事件到事件总线"""
        event_bus.publish(self.run_id, event_type, payload)
```

---

### 4️⃣ **事件总线 - 内存队列**

```python
# 后端：event_bus.py
_subscribers: dict[str, set[queue.Queue]] = {}  # run_id -> 订阅者队列集合
_lock = threading.Lock()

def publish(run_id: str, event_type: str, payload: dict | None = None) -> None:
    """发布事件到所有订阅者"""
    event = {
        "type": event_type,
        "run_id": run_id,
        "payload": payload or {},
    }
    
    # 获取该 run_id 的所有订阅者
    with _lock:
        subscribers = list(_subscribers.get(run_id, set()))
    
    # 将事件推送到每个订阅者的队列
    for subscriber in subscribers:
        subscriber.put(event)

def subscribe(run_id: str, *, heartbeat_seconds: float = 15.0) -> Iterator[dict | None]:
    """订阅事件流（Generator）"""
    subscriber: queue.Queue = queue.Queue()
    
    # 注册订阅者
    with _lock:
        _subscribers.setdefault(run_id, set()).add(subscriber)
    
    try:
        while True:
            try:
                # 阻塞等待事件（带超时）
                event = subscriber.get(timeout=heartbeat_seconds)
            except queue.Empty:
                # 超时，发送心跳保活
                yield None
                continue
            
            if event is _TERMINAL_EVENT:
                # 探索结束，关闭订阅
                return
            
            yield event
    finally:
        # 清理订阅者
        with _lock:
            subscribers = _subscribers.get(run_id)
            if subscribers is not None:
                subscribers.discard(subscriber)
```

**关键设计**：
- 每个 `run_id` 对应一组订阅者队列
- 发布事件时，将事件推送到所有订阅者的队列
- 订阅者从队列中读取事件（Generator 模式）
- 支持心跳保活（15秒超时发送 `None`）

---

### 5️⃣ **SSE 端点 - 流式传输**

```python
# 后端：exploration.py
@router.get("/{project_id}/exploration-runs/{run_id}/stream")
def stream_project_run(project_id: str, run_id: str, actor=Depends(current_user)) -> StreamingResponse:
    run = exploration_service.get_project_run(project_id, run_id, actor)
    
    # 如果已经完成，直接返回终态事件
    if run["status"] in {"completed", "partial", "blocked", "cancelled"}:
        event_type = _terminal_stream_event_type(run["status"])
        
        def terminal_event_stream():
            data = json.dumps({
                "type": event_type,
                "run_id": run_id,
                "payload": run,
            }, ensure_ascii=False, separators=(",", ":"))
            yield f"event: {event_type}\ndata: {data}\n\n"
        
        return StreamingResponse(terminal_event_stream(), media_type="text/event-stream")
    
    # 探索进行中，返回实时事件流
    def event_stream():
        for event in exploration_event_bus.subscribe(run_id):
            if event is None:
                # 心跳保活
                yield ": keep-alive\n\n"
                continue
            
            event_type = str(event.get("type") or "message")
            data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            
            # SSE 格式：event: <type>\ndata: <json>\n\n
            yield f"event: {event_type}\ndata: {data}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**SSE 格式示例**：
```
event: planning_started
data: {"type":"planning_started","run_id":"exprun-abc123","payload":{"message":"正在智能分析探索目标..."}}

event: planning_completed
data: {"type":"planning_completed","run_id":"exprun-abc123","payload":{"plan_id":"plan-001","total_steps":12}}

event: step_started
data: {"type":"step_started","run_id":"exprun-abc123","payload":{"step_number":1,"total_steps":12,"description":"导航到工作台"}}

event: step_completed
data: {"type":"step_completed","run_id":"exprun-abc123","payload":{"step_number":1,"message":"导航成功"}}

: keep-alive
```

---

### 6️⃣ **前端监听 SSE 流**

```typescript
// 前端：创建 EventSource 监听 SSE
function connectToEventStream(runId: string) {
  const eventSource = new EventSource(
    `/api/v1/projects/${projectId}/exploration-runs/${runId}/stream`
  );
  
  // 监听 planning_started 事件
  eventSource.addEventListener("planning_started", (e: MessageEvent) => {
    const event = JSON.parse(e.data);
    console.log("Planning started:", event.payload);
    setCurrentPhase("planning");
    setStatusMessage(event.payload.message);
  });
  
  // 监听 planning_completed 事件
  eventSource.addEventListener("planning_completed", (e: MessageEvent) => {
    const event = JSON.parse(e.data);
    console.log("Planning completed:", event.payload);
    setTotalSteps(event.payload.total_steps);
    setCurrentPhase("execution");
  });
  
  // 监听 step_started 事件
  eventSource.addEventListener("step_started", (e: MessageEvent) => {
    const event = JSON.parse(e.data);
    console.log("Step started:", event.payload);
    
    // 更新 UI 显示
    setCurrentStep(event.payload.step_number);
    setCurrentStepDescription(event.payload.description);
    setProgress((event.payload.step_number / event.payload.total_steps) * 100);
  });
  
  // 监听 step_completed 事件
  eventSource.addEventListener("step_completed", (e: MessageEvent) => {
    const event = JSON.parse(e.data);
    console.log("Step completed:", event.payload);
    
    // 添加到已完成步骤列表
    setCompletedSteps((prev) => [
      ...prev,
      {
        stepNumber: event.payload.step_number,
        description: event.payload.description,
        status: "success",
        message: event.payload.message,
      },
    ]);
  });
  
  // 监听 step_failed 事件
  eventSource.addEventListener("step_failed", (e: MessageEvent) => {
    const event = JSON.parse(e.data);
    console.error("Step failed:", event.payload);
    
    setCompletedSteps((prev) => [
      ...prev,
      {
        stepNumber: event.payload.step_number,
        description: event.payload.description,
        status: "error",
        message: event.payload.error,
      },
    ]);
  });
  
  // 监听 run_completed 事件
  eventSource.addEventListener("run_completed", (e: MessageEvent) => {
    const event = JSON.parse(e.data);
    console.log("Exploration completed:", event.payload);
    
    setCurrentPhase("completed");
    setStatusMessage(event.payload.summary);
    eventSource.close();  // 关闭连接
    
    // 刷新探索结果
    loadExplorationResult(runId);
  });
  
  // 监听错误
  eventSource.onerror = (error) => {
    console.error("SSE error:", error);
    eventSource.close();
  };
  
  // 返回清理函数
  return () => {
    eventSource.close();
  };
}
```

---

## 📊 前端展示组件设计

### 实时进度展示
```typescript
interface ExplorationProgressProps {
  runId: string;
}

function ExplorationProgress({ runId }: ExplorationProgressProps) {
  const [phase, setPhase] = useState<"planning" | "execution" | "completed">("planning");
  const [currentStep, setCurrentStep] = useState(0);
  const [totalSteps, setTotalSteps] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<StepResult[]>([]);
  const [statusMessage, setStatusMessage] = useState("");
  
  useEffect(() => {
    const cleanup = connectToEventStream(runId);
    return cleanup;
  }, [runId]);
  
  return (
    <div className="exploration-progress">
      {/* Phase 指示器 */}
      <div className="phase-indicator">
        <PhaseStep active={phase === "planning"} completed={phase !== "planning"}>
          Planning
        </PhaseStep>
        <PhaseStep active={phase === "execution"} completed={phase === "completed"}>
          Execution
        </PhaseStep>
        <PhaseStep active={phase === "completed"}>
          Completed
        </PhaseStep>
      </div>
      
      {/* 进度条 */}
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${(currentStep / totalSteps) * 100}%` }} />
        <span className="progress-text">{currentStep} / {totalSteps}</span>
      </div>
      
      {/* 状态消息 */}
      <div className="status-message">
        {statusMessage}
      </div>
      
      {/* 步骤列表 */}
      <div className="steps-list">
        {completedSteps.map((step) => (
          <div key={step.stepNumber} className={`step-item ${step.status}`}>
            <div className="step-number">{step.stepNumber}</div>
            <div className="step-content">
              <div className="step-description">{step.description}</div>
              <div className="step-message">{step.message}</div>
            </div>
            <div className="step-status">
              {step.status === "success" ? "✓" : "✗"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## 📋 完整事件类型清单

### 1. **运行级别事件**

| 事件类型 | Payload | 说明 |
|---------|---------|------|
| `run_started` | `{status: "running", mode: "unified"}` | 探索开始 |
| `run_completed` | `{status: "completed", summary: "..."}` | 探索完成 |
| `run_failed` | `{status: "blocked", error: "..."}` | 探索失败 |
| `run_cancelled` | `{status: "cancelled"}` | 用户取消 |

### 2. **规划阶段事件**

| 事件类型 | Payload | 说明 |
|---------|---------|------|
| `planning_started` | `{message: "正在分析..."}` | 开始规划 |
| `planning_completed` | `{plan_id, total_steps, modules, strategy}` | 规划完成 |
| `re_planning_started` | `{reason: "遇到阻塞..."}` | 开始重新规划 |
| `re_planning_completed` | `{new_steps, message}` | 重新规划完成 |

### 3. **执行阶段事件**

| 事件类型 | Payload | 说明 |
|---------|---------|------|
| `step_started` | `{step_number, total_steps, description, module, strategy}` | 步骤开始 |
| `step_completed` | `{step_number, description, message}` | 步骤完成 |
| `step_failed` | `{step_number, description, error}` | 步骤失败 |
| `step_skipped` | `{step_number, description, reason}` | 步骤跳过 |

### 4. **页面级别事件**

| 事件类型 | Payload | 说明 |
|---------|---------|------|
| `page_discovered` | `{page_id, url, title}` | 发现新页面 |
| `page_completed` | `{page_id, url, elements_count}` | 页面探索完成 |
| `page_blocked` | `{page_id, url, reason}` | 页面访问失败 |

### 5. **模块级别事件**

| 事件类型 | Payload | 说明 |
|---------|---------|------|
| `module_discovered` | `{module_key, module_name}` | 发现模块 |
| `module_updated` | `{module_key, explored_page_count, ...}` | 模块进度更新 |

### 6. **阻塞事件**

| 事件类型 | Payload | 说明 |
|---------|---------|------|
| `blocker_detected` | `{module_key, page_ref, reason_type, reason}` | 检测到阻塞 |

---

## 🎯 关键设计优势

### 1. **解耦架构**
- **后端**：Orchestrator 只负责发布事件，不关心谁在监听
- **Event Bus**：内存队列，轻量高效
- **前端**：通过 SSE 被动接收事件，实时更新 UI

### 2. **实时性**
- SSE 单向流，低延迟（~50ms）
- 事件驱动，步骤完成即发送
- 支持心跳保活，避免连接断开

### 3. **可扩展性**
- 新增事件类型只需：
  1. 后端：`_publish("new_event_type", {...})`
  2. 前端：`eventSource.addEventListener("new_event_type", handler)`

### 4. **容错性**
- SSE 自动重连（浏览器原生支持）
- 探索已完成时，直接返回终态事件
- 订阅者清理机制，避免内存泄漏

---

## 🔍 调试技巧

### 1. **后端日志**
```python
# unified_orchestrator.py
def _publish(self, event_type: str, payload: dict):
    print(f"[SSE Event] {event_type}: {payload}")  # 调试日志
    event_bus.publish(self.run_id, event_type, payload)
```

### 2. **前端日志**
```typescript
eventSource.addEventListener("message", (e: MessageEvent) => {
  console.log("[SSE Received]", e.type, JSON.parse(e.data));
});
```

### 3. **浏览器 Network 面板**
- 打开开发者工具 → Network → EventStream
- 查看实时接收的 SSE 事件流

### 4. **curl 测试**
```bash
curl -N http://localhost:8000/api/v1/projects/proj-123/exploration-runs/exprun-abc123/stream
```

---

## 📈 性能优化

### 1. **事件聚合**
对于高频事件（如元素发现），可以批量发送：
```python
# 每秒最多发送一次 elements_discovered 事件
if len(self.discovered_elements) >= 10 or time_since_last_publish > 1.0:
    self._publish("elements_discovered", {"elements": self.discovered_elements})
    self.discovered_elements.clear()
```

### 2. **Payload 精简**
只发送必要字段，避免大对象：
```python
# ❌ 不好：发送完整页面对象
self._publish("page_completed", {"page": full_page_object})

# ✅ 好：只发送关键信息
self._publish("page_completed", {
    "page_id": page.id,
    "url": page.url,
    "elements_count": len(page.elements),
})
```

### 3. **连接复用**
前端一个探索任务只创建一个 EventSource 连接。

---

## 🎉 总结

### **数据流路径**
```
后端执行步骤
    ↓
orchestrator._publish()
    ↓
event_bus.publish() → 推送到订阅者队列
    ↓
SSE endpoint → event_bus.subscribe() → Generator
    ↓
StreamingResponse → yield SSE 格式事件
    ↓
前端 EventSource → 监听事件
    ↓
React setState → 更新 UI
```

### **核心组件**
1. **unified_orchestrator.py** - 探索执行，发布事件
2. **event_bus.py** - 内存队列，事件中转
3. **exploration.py** - SSE 端点，流式传输
4. **exploration-workspace.tsx** - 前端监听，实时展示

### **技术栈**
- **后端**：FastAPI + SSE + threading + Queue
- **前端**：React + EventSource + useState
- **协议**：HTTP/1.1 + SSE (text/event-stream)

---

**这就是统一探索架构的完整前后端设计！** 🚀
