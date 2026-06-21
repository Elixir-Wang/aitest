# 前后端对接问题 - 全面诊断与修复方案

## 🔍 当前问题诊断

### 问题现象
- 前端显示"探索中"状态，但后端不返回任何信息
- 任务状态卡在 `running`，无法完成
- 前端无法获取任务进度更新

### 数据库状态
```
explore-01b554b4f26ba242 | 探索 | running | 正在智能分析探索目标并生成探索计划。
started_at: 2026-06-21 05:33:44
```

**问题分析**：任务从 `05:33:44` 开始，现在是 `13:39`，已经运行了 **8小时**，显然已经卡死。

---

## 🎯 根本原因分析

### 1. **后台任务异常退出，但状态未更新**

**症状**：
- 任务状态保持 `running`
- 后台线程可能已崩溃或异常退出
- 数据库状态未更新为 `blocked`/`partial`/`completed`

**根本原因**：
```python
# apps/backend/app/api/v1/exploration.py:158-164
def _dispatch_exploration_run(run_id: str) -> None:
    thread = threading.Thread(
        target=site_exploration_orchestrator.run_exploration,
        args=(run_id,),
        daemon=True,  # ⚠️ daemon线程无法保证异常被捕获
    )
    thread.start()
```

**问题点**：
- 使用 `daemon=True` 的线程，主进程重启时线程直接终止
- 线程内异常未被捕获和记录
- 没有超时机制
- 没有心跳检测

### 2. **planner LLM调用失败导致任务卡死**

刚才修复的 `target_selector` 问题可能导致：
```python
# apps/backend/app/services/exploration/plan_and_execute/planner.py:339-363
async def _call_planner_llm(self, prompt: str) -> dict:
    # ...
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": prompt}]
    })
    
    plan_data = result.get("structured_response")
    if plan_data is None:
        raise ValueError("规划器未返回有效计划")  # ⚠️ 异常未被捕获
```

**问题点**：
- LLM可能生成无效的 `target_selector`（虽然系统提示词已更新，但旧任务已经开始）
- 异常抛出后，线程退出，但数据库状态未更新

### 3. **前端 SSE 流没有超时机制**

```python
# apps/backend/app/api/v1/exploration.py:99-108
def event_stream():
    for event in exploration_event_bus.subscribe(run_id):
        if event is None:
            yield ": keep-alive\n\n"
            continue
        event_type = str(event.get("type") or "message")
        data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        yield f"event: {event_type}\ndata: {data}\n\n"
```

**问题点**：
- `exploration_event_bus.subscribe(run_id)` 会一直阻塞等待事件
- 如果后台任务已死，事件永远不会到来
- 前端会一直等待，显示"探索中"

### 4. **序列化层的 Row 对象问题（已修复）**

之前的 `sqlite3.Row` 对象问题已修复，但可能还有其他序列化问题。

---

## 🛠️ 系统性修复方案

### 方案 A：立即修复（推荐）

#### 1. 恢复卡死的任务状态
```python
# 在 app/main.py 启动时自动恢复
from app.services.exploration import service as exploration_service

@app.on_event("startup")
async def recover_stale_runs():
    """恢复所有卡死的探索任务"""
    exploration_service.recover_interrupted_exploration_runs()
```

#### 2. 添加任务超时检测
```python
# app/services/exploration/site_orchestrator.py
def run_exploration(run_id: str) -> None:
    """执行探索，带超时和异常处理"""
    try:
        run = _get_run_with_timeout_check(run_id)
        
        # 启动超时定时器
        timeout_minutes = run["timeout_minutes"]
        start_time = datetime.now(timezone.utc)
        
        # 执行探索逻辑
        _execute_exploration_with_timeout(run_id, timeout_minutes, start_time)
        
    except TimeoutError as e:
        _mark_run_as_timeout(run_id, str(e))
    except Exception as e:
        _mark_run_as_failed(run_id, str(e))
        logger.exception(f"探索任务异常: {run_id}")
```

#### 3. 改进事件流超时机制
```python
# app/api/v1/exploration.py
def event_stream():
    start_time = time.time()
    timeout_seconds = 3600  # 1小时超时
    
    for event in exploration_event_bus.subscribe(run_id):
        if time.time() - start_time > timeout_seconds:
            # 检查任务状态
            run = exploration_service.get_project_run(project_id, run_id, actor)
            if run["status"] == "running":
                # 任务可能卡死，发送错误事件
                yield f"event: run_timeout\ndata: {json.dumps({'run_id': run_id})}\n\n"
            break
            
        if event is None:
            yield ": keep-alive\n\n"
            continue
            
        event_type = str(event.get("type") or "message")
        data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        yield f"event: {event_type}\ndata: {data}\n\n"
```

#### 4. 添加心跳检测
```python
# app/services/exploration/site_orchestrator.py
class ExplorationHeartbeat:
    """探索任务心跳"""
    def __init__(self, run_id: str, interval_seconds: int = 30):
        self.run_id = run_id
        self.interval = interval_seconds
        self.last_heartbeat = datetime.now(timezone.utc)
        
    def beat(self):
        """更新心跳时间"""
        self.last_heartbeat = datetime.now(timezone.utc)
        # 写入数据库或缓存
        
    def is_alive(self) -> bool:
        """检查任务是否存活"""
        return (datetime.now(timezone.utc) - self.last_heartbeat).seconds < self.interval * 3
```

---

### 方案 B：长期架构改进

#### 1. 使用任务队列（Celery / RQ）
替代 `threading.Thread`，使用专业的任务队列：

```python
from celery import Celery

celery_app = Celery('exploration', broker='redis://localhost:6379/0')

@celery_app.task(bind=True, time_limit=7200)
def run_exploration_task(self, run_id: str):
    """Celery任务：执行探索"""
    try:
        site_exploration_orchestrator.run_exploration(run_id)
    except Exception as e:
        self.retry(exc=e, countdown=60, max_retries=3)
```

**优势**：
- 自动异常捕获和重试
- 超时自动终止
- 任务状态持久化
- 支持分布式执行

#### 2. 使用 WebSocket 替代 SSE
WebSocket 支持双向通信，可以主动检测连接状态：

```python
from fastapi import WebSocket

@router.websocket("/ws/exploration/{run_id}")
async def exploration_websocket(websocket: WebSocket, run_id: str):
    await websocket.accept()
    
    try:
        async for event in exploration_event_bus.async_subscribe(run_id):
            await websocket.send_json(event)
            
            # 定期检查任务状态
            if should_check_status():
                run = get_run_status(run_id)
                if run["status"] in terminal_statuses:
                    break
    except WebSocketDisconnect:
        logger.info(f"客户端断开连接: {run_id}")
    finally:
        await websocket.close()
```

#### 3. 添加 API 健康检查端点
```python
@router.get("/exploration-runs/{run_id}/health")
def check_exploration_health(run_id: str):
    """检查探索任务健康状态"""
    run = exploration_service.get_run(run_id)
    
    if run["status"] != "running":
        return {"status": "ok", "run_status": run["status"]}
    
    # 检查心跳
    heartbeat = get_heartbeat(run_id)
    if not heartbeat.is_alive():
        return {
            "status": "stale",
            "message": "任务可能已卡死",
            "last_heartbeat": heartbeat.last_heartbeat
        }
    
    return {"status": "ok", "run_status": "running"}
```

---

## 🚀 立即执行的修复步骤

### Step 1: 恢复当前卡死的任务
```bash
cd /Users/wanghongbao/project/test_project/apps/backend

sqlite3 data/ai_testing.db "
UPDATE exploration_runs 
SET status = 'interrupted', 
    result_summary = '任务执行超时或异常中断，请重新启动。',
    finished_at = CURRENT_TIMESTAMP
WHERE status = 'running' 
  AND (datetime('now') - datetime(started_at)) > 3600;
"
```

### Step 2: 在 main.py 添加启动时恢复
```python
# app/main.py
@app.on_event("startup")
async def startup_event():
    logger.info("应用启动")
    
    # 恢复所有被中断的探索任务
    from app.services.exploration import service as exploration_service
    exploration_service.recover_interrupted_exploration_runs()
    logger.info("已恢复中断的探索任务")
```

### Step 3: 重启服务
```bash
# 停止旧服务
pkill -f uvicorn

# 启动新服务
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Step 4: 前端刷新页面
前端刷新后应该能看到任务状态已恢复为 `interrupted`。

---

## 📊 改进后的数据流

### 正常流程
```
用户点击"开始探索"
  ↓
API: POST /exploration-runs/{run_id}/start
  ↓
更新数据库: status = "queued"
  ↓
启动后台任务（带异常处理和超时）
  ↓
任务开始: status = "running" + 心跳启动
  ↓
定期发送进度事件 → event_bus → SSE → 前端
  ↓
任务完成: status = "completed" + 停止心跳
  ↓
SSE 发送 run_completed 事件 → 前端更新UI
```

### 异常恢复流程
```
任务卡死（心跳超时 > 90秒）
  ↓
定时检测器发现异常
  ↓
更新数据库: status = "interrupted"
  ↓
SSE 发送 run_failed 事件
  ↓
前端显示错误提示
```

---

## 🎯 优先级排序

### P0 - 立即修复（今天）
1. ✅ 修复 URL 导航问题（已完成）
2. 🔄 恢复卡死的任务状态
3. 🔄 添加启动时自动恢复逻辑

### P1 - 短期改进（本周）
1. 添加任务超时检测
2. 改进异常捕获和日志记录
3. SSE 流添加超时机制
4. 添加心跳检测

### P2 - 长期架构（下个迭代）
1. 迁移到 Celery 任务队列
2. 使用 WebSocket 替代 SSE
3. 添加分布式锁
4. 完善监控和告警

---

## 🔧 关键代码位置

| 文件 | 问题 | 修复优先级 |
|------|------|-----------|
| `app/api/v1/exploration.py:158-164` | daemon线程无异常处理 | P0 |
| `app/services/exploration/site_orchestrator.py` | 无超时和心跳机制 | P1 |
| `app/services/exploration/plan_and_execute/planner.py:339-363` | LLM调用异常未捕获 | P1 |
| `app/api/v1/exploration.py:99-108` | SSE流无超时 | P1 |
| `app/main.py` | 缺少启动恢复逻辑 | P0 |

---

## 📝 测试验证清单

### 功能测试
- [ ] 创建新的探索任务
- [ ] 任务能正常启动
- [ ] 前端能实时看到进度
- [ ] 任务能正常完成
- [ ] 失败时能看到错误信息

### 异常测试
- [ ] 手动kill后台线程，任务状态能恢复
- [ ] 服务重启后，running任务自动标记为interrupted
- [ ] 超时任务能自动终止
- [ ] LLM调用失败时，任务状态正确更新

### 性能测试
- [ ] SSE连接能正常保持
- [ ] 多个任务并发执行不互相干扰
- [ ] 心跳检测不影响性能

---

## 💡 建议

1. **立即执行 P0 修复**，恢复当前卡死的任务
2. **本周完成 P1 改进**，防止类似问题再次发生
3. **规划 P2 架构升级**，从根本上解决任务管理问题
4. **添加完善的日志和监控**，便于快速定位问题
5. **编写集成测试**，覆盖异常场景

---

**更新时间**: 2026-06-21 13:39  
**状态**: 🔴 待修复  
**负责人**: 后端团队
