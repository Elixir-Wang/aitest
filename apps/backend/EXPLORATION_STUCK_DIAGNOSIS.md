# 探索任务卡住问题诊断报告

## 问题描述

用户反馈：**点击探索后啥也没有**，前端显示"探索中"但没有任何实际进展。

## 问题现象

### 前端表现
1. SSE连接已建立（有keep-alive心跳）
2. 显示状态：`探索中`
3. 显示进度：`正在智能分析探索目标并生成探索计划。`
4. **但没有任何后续事件数据**

### 后端状态
```sql
-- 任务信息
ID: explore-01b554b4f26ba242
状态: running
创建时间: 2026-06-20 03:22:06
开始时间: 2026-06-21 12:02:19
当前时间: 2026-06-21 20:08:xx (运行8小时+)
结果摘要: 正在智能分析探索目标并生成探索计划。
```

### 日志情况
- 日志目录存在：`data/projects/.../logs/`
- 日志文件**完全为空**（0字节）
- 没有任何错误信息

## 根本原因分析

### 1. 卡死位置定位

通过代码追踪，定位到卡死点在 `unified_orchestrator.py:106`：

```python
# Phase 1: Planning - 所有探索都先规划
self._log("planning_started", message="分析目标并生成探索计划...")
self._publish("planning_started", {"message": "正在智能分析探索目标..."})
self._record_lifecycle_progress("正在智能分析探索目标并生成探索计划。")

# ❌ 卡在这里！
self.plan = await self._create_smart_plan(planner_input)  # 第106行
```

### 2. 根本原因

**LLM调用卡住，没有超时机制**

在 `planner.py` 中：

```python
async def _call_planner_llm(self, prompt: str) -> dict:
    """调用LLM生成计划"""
    from langchain.agents import create_agent
    
    # 使用高质量模型进行规划
    selection = resolve_model_selection(self.capability_id)
    model = build_agent_model(selection)
    
    # ❌ 问题：这个调用可能永久挂起
    agent = create_agent(
        model=model,
        tools=[],
        system_prompt=PLANNER_SYSTEM_PROMPT,
        ...
    )
    
    # ❌ 没有设置超时
    # ❌ 异常被静默吞掉
    result = await agent.invoke(...)
```

### 3. 可能的触发条件

1. **AI模型服务不可用**
   - API端点无响应
   - 网络超时
   - 模型服务宕机

2. **异步调用死锁**
   - asyncio事件循环阻塞
   - 资源竞争

3. **模型选择配置错误**
   - `resolve_model_selection()` 返回无效配置
   - 模型初始化失败但未抛出异常

4. **输入过大导致超时**
   - 探索目标过于复杂
   - Prompt过长导致模型处理缓慢

## 影响范围

### 当前影响
- ✅ SSE流正常建立和keep-alive
- ✅ 数据库状态更新正常
- ❌ Planning阶段完全卡死
- ❌ 没有任何日志输出
- ❌ 没有错误信息
- ❌ 后续执行完全无法进行

### 用户体验
- 用户看到"探索中"但永远没有进展
- 没有错误提示，用户不知道发生了什么
- 任务占用数据库记录，影响后续探索

## 代码缺陷总结

### 1. 缺少超时机制
```python
# 当前代码
self.plan = await self._create_smart_plan(planner_input)

# 应该添加超时
try:
    self.plan = await asyncio.wait_for(
        self._create_smart_plan(planner_input),
        timeout=300  # 5分钟超时
    )
except asyncio.TimeoutError:
    raise PlanningTimeoutError("规划超时")
```

### 2. 异常处理不完善
```python
# 当前代码 - 异常被静默吞掉
try:
    result = await self.run()
except Exception as e:
    # 仅记录到日志，但没有发布到SSE
    self._log("error", message=f"探索执行异常: {str(e)}")
    return self._error_result(...)
```

### 3. 缺少心跳/进度机制
Planning阶段没有发送进度事件，用户无法感知进展。

### 4. 日志延迟写入
```python
# 当前设计
self.log_lines.append(log_entry)  # 仅追加到内存
# ...
# 只在最后统一写入
self._write_log()  # 任务卡死时永远不会执行
```

## 修复方案

### 短期修复（紧急）

#### 1. 添加超时机制
```python
# unified_orchestrator.py
PLANNING_TIMEOUT_SECONDS = 300  # 5分钟

async def run(self) -> dict:
    try:
        # 添加超时保护
        self.plan = await asyncio.wait_for(
            self._create_smart_plan(planner_input),
            timeout=PLANNING_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        error_msg = f"探索规划超时（{PLANNING_TIMEOUT_SECONDS}秒），请检查AI模型服务状态"
        self._publish("error", {"message": error_msg})
        return self._error_result(error_msg)
```

#### 2. 改进异常发布
```python
except Exception as e:
    error_msg = f"探索执行异常: {str(e)}"
    self._log("error", message=error_msg)
    # ✅ 立即发布到SSE
    self._publish("error", {"message": error_msg, "traceback": traceback.format_exc()})
    # ✅ 立即写入日志
    self._write_log()
    return self._error_result(error_msg)
```

#### 3. 实时日志写入
```python
def _log(self, event: str, **payload):
    """记录日志 - 立即写入磁盘"""
    log_entry = json.dumps({
        "ts": exploration_now_iso(),
        "event": event,
        **payload
    }, ensure_ascii=False)
    self.log_lines.append(log_entry)
    
    # ✅ 立即追加写入
    log_path = self.artifact_root / "logs" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry + "\n")
```

#### 4. Planning进度心跳
```python
async def _create_smart_plan(self, planner_input: PlannerInput) -> ExplorationPlan:
    # 发送进度事件
    self._publish("planning_progress", {"stage": "analyzing_goal"})
    
    planner = ExplorationPlanner()
    
    self._publish("planning_progress", {"stage": "calling_llm"})
    plan = await planner.create_plan(planner_input)
    
    self._publish("planning_progress", {"stage": "validating_plan"})
    plan = self._annotate_execution_strategy(plan)
    
    return plan
```

### 中期优化

1. **健康检查机制**
   - Planning前先ping模型服务
   - 失败快速降级到简单计划

2. **降级策略**
   - Planning超时后使用默认计划
   - 简单目标直接生成步骤，跳过LLM

3. **监控和告警**
   - 记录Planning耗时指标
   - 超过阈值告警

### 长期改进

1. **重构异步架构**
   - 使用更健壮的任务队列（如Celery）
   - 独立的worker进程

2. **完善的超时策略**
   - 分级超时（Planning/Execution/Total）
   - 可配置超时时间

3. **更好的可观测性**
   - 结构化日志
   - 实时指标
   - 分布式追踪

## 临时解决方案

### 对于已卡住的任务

```sql
-- 取消卡住的任务
UPDATE exploration_runs 
SET status='cancelled', 
    result_summary='任务超时已取消（Planning阶段卡住超过8小时）',
    finished_at=datetime('now')
WHERE id='explore-01b554b4f26ba242';
```

### 对于新任务

在修复代码之前，建议：
1. 检查AI模型服务是否正常
2. 简化探索目标描述
3. 避免过于复杂的多模块目标
4. 监控任务状态，超时手动取消

## 验证步骤

修复后需要验证：

1. ✅ Planning正常完成（< 60秒）
2. ✅ Planning超时能正确抛出异常
3. ✅ 异常能正确发布到SSE前端
4. ✅ 日志实时写入磁盘
5. ✅ 用户能看到明确的错误信息
6. ✅ 任务状态正确更新为`blocked`/`cancelled`

## 总结

**根本原因**：Planning阶段的LLM调用缺少超时保护，导致任务永久卡住。

**核心缺陷**：
1. 无超时机制
2. 异常处理不完善
3. 日志延迟写入
4. 缺少进度反馈

**修复优先级**：P0（紧急）

**预计影响**：修复后探索功能将恢复正常，用户体验显著改善。
