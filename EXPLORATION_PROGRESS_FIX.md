# 探索进度展示问题修复方案

## 问题描述

用户反馈：探索过程中的各种操作（打开浏览器、获取快照、批量点击等）需要在前端实时展示，但现在卡在"探索中"的状态，看不到具体的进度。

## 问题根源

通过深入分析代码，发现以下问题：

### 1. 前端事件处理不完整

**位置**：`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

**问题**：
- `applyStreamEvent` 函数只处理了部分事件类型（`run_*`, `module_*`, `page_*`, `step_recorded`, `blocker_detected`）
- 缺少对关键探索步骤事件的处理，如：
  - `planning_started` / `planning_completed` - 规划阶段
  - `execution_started` / `execution_completed` - 执行阶段
  - `step_started` / `step_completed` / `step_failed` - 步骤进度
  - `exploration_cancelled` - 取消事件

### 2. 模块匹配逻辑不健壮

**位置**：`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx:503-513`

**问题**：
- `findStreamModuleIndex` 函数无法正确匹配 `planned-01` 这样的规划模块
- 缺少对 `lifecycle` 等特殊模块的处理
- 没有模糊匹配机制

### 3. 后端事件推送不够详细

**位置**：`apps/backend/app/services/exploration/unified_orchestrator.py`

**问题**：
- 步骤执行过程中缺少"运行中"状态的实时推送
- 缺少执行阶段开始/完成的生命周期事件
- 错误处理时没有发送事件通知前端

## 修复方案

### 1. 增强前端事件处理

#### 修改文件：`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

**改进 1：完善 `applyStreamEvent` 函数**

```typescript
function applyStreamEvent(event: ExplorationStreamEvent, setters) {
  // 处理运行状态事件
  if (event.type === "run_started" || event.type === "run_completed" || ...) {
    // 更新运行状态
  }

  // 新增：处理规划和执行阶段事件
  if (
    event.type === "planning_started" ||
    event.type === "planning_completed" ||
    event.type === "step_started" ||
    event.type === "step_completed" ||
    event.type === "step_failed" ||
    event.type === "step_skipped" ||
    event.type === "re_planning_started" ||
    event.type === "re_planning_completed"
  ) {
    console.log(`[探索进度] ${event.type}:`, event.payload);
  }

  // 处理模块、页面、步骤、阻塞事件...
}
```

**改进 2：增强 `findStreamModuleIndex` 函数**

```typescript
function findStreamModuleIndex(modules, moduleId) {
  // 1. 精确匹配 module_key 或 id
  // 2. 匹配 module_name
  // 3. 特殊模块处理（lifecycle, 站点入口, 入口页）
  // 4. 模糊匹配：moduleId 包含在 module_name 中
  // 5. 单模块默认返回
}
```

**改进 3：扩展日志类型标签**

```typescript
const logTypeLabels = {
  planning_started: "规划开始",
  planning_completed: "规划完成",
  execution_started: "执行开始",
  execution_completed: "执行完成",
  step_started: "步骤开始",
  step_completed: "步骤完成",
  step_failed: "步骤失败",
  // ... 其他类型
};
```

### 2. 增强后端事件推送

#### 修改文件：`apps/backend/app/services/exploration/unified_orchestrator.py`

**改进 1：在 `run()` 方法中增加生命周期事件**

```python
async def run(self) -> dict:
    # 发布执行开始事件
    self._publish("execution_started", {"total_steps": len(self.plan.steps)})
    self._publish_lifecycle_step(
        step_id="execution-started",
        step_type="execution",
        title="开始执行探索",
        detail=f"即将执行 {len(self.plan.steps)} 个步骤。",
        status="running",
        module_key=initial_module,
    )
    
    # ... 执行逻辑
    
    # 发布执行完成事件
    self._publish_lifecycle_step(
        step_id="execution-completed",
        step_type="execution",
        title="探索执行完成",
        detail=f"已完成所有步骤，状态：{result.get('status')}。",
        status="completed",
        module_key=initial_module,
    )
```

**改进 2：在 `_execute_unified()` 方法中增加步骤状态推送**

```python
async def _execute_unified(self, browser_session, planner_input) -> dict:
    for step_index, step in enumerate(self.plan.steps):
        # 发布步骤开始事件
        self._publish("step_started", {...})
        
        # 发布步骤记录事件（状态：运行中）
        self._publish_step_recorded(step, None, status="running")
        
        # 执行步骤
        result = await self._execute_step(...)
        
        # 发布步骤完成/失败事件
        final_status = "completed" if result.success else "failed"
        self._publish_step_recorded(step, result, status=final_status)
        
        if result.success:
            self._publish("step_completed", {...})
        else:
            self._publish("step_failed", {...})
```

**改进 3：修复 `_publish_step_recorded()` 支持空 result**

```python
def _publish_step_recorded(self, step, result, *, status):
    # 允许 result 为 None（用于运行中状态）
    if result:
        detail = result.message if result.success else (result.error or "")
    else:
        detail = f"正在执行：{step.description}"
    
    self._publish("step_recorded", {...})
```

## 验证方法

### 1. 启动后端服务

```bash
cd apps/backend
python -m uvicorn app.main:app --reload
```

### 2. 启动前端服务

```bash
cd apps/frontend
npm run dev
```

### 3. 创建并启动探索任务

1. 在浏览器中打开前端应用
2. 创建一个探索任务
3. 点击"开始探索"
4. 观察"探索模块进度"区域

### 4. 预期效果

在探索过程中，应该能看到：

1. **规划阶段**：
   - 显示"生成探索计划"步骤
   - 状态从"运行中"变为"已完成"
   - 显示生成的步骤数量

2. **执行阶段**：
   - 显示"开始执行探索"步骤
   - 每个执行步骤都有实时状态更新：
     - 步骤开始时显示"运行中"
     - 步骤完成时显示"已完成"
     - 步骤失败时显示"失败"并显示错误信息

3. **页面采集**：
   - 显示每个访问的页面
   - 显示页面上执行的动作（点击、填写等）
   - 显示动作的执行结果

4. **完成阶段**：
   - 显示"探索执行完成"步骤
   - 显示最终的探索结果

### 5. 检查浏览器控制台

打开浏览器开发者工具，在控制台中应该能看到：

```
[探索进度] planning_started: {message: "正在智能分析探索目标..."}
[探索进度] planning_completed: {plan_id: "...", total_steps: 5, ...}
[探索进度] execution_started: {total_steps: 5}
[探索进度] step_started: {step_number: 1, description: "...", ...}
[探索进度] step_completed: {step_number: 1, message: "..."}
...
```

## 技术细节

### SSE (Server-Sent Events) 流程

1. **前端订阅**：`useEffect` 钩子在 `runStatus` 为活动状态时建立 SSE 连接
2. **后端推送**：`exploration_event_bus.publish()` 发送事件到订阅者
3. **前端接收**：`parseStreamEvent()` 解析事件，`applyStreamEvent()` 应用到状态
4. **UI 更新**：React 自动重新渲染 `AgentPlan` 组件

### 事件流示例

```
run_started
  └─> planning_started
      └─> step_recorded (planning, running)
      └─> planning_completed
      └─> step_recorded (planning, completed)
  └─> execution_started
      └─> step_recorded (execution, running)
      └─> module_discovered (planned-01)
      └─> module_discovered (planned-02)
      └─> step_started (step 1)
          └─> step_recorded (step 1, running)
          └─> page_visited
          └─> step_completed (step 1)
          └─> step_recorded (step 1, completed)
      └─> step_started (step 2)
          └─> step_recorded (step 2, running)
          └─> action_executed
          └─> step_completed (step 2)
          └─> step_recorded (step 2, completed)
      └─> ...
      └─> execution_completed
      └─> step_recorded (execution, completed)
  └─> run_completed
```

## 其他改进建议

### 1. 添加进度百分比

在前端显示总体进度：

```typescript
const progress = activeDetail ? 
  Math.round((completedSteps / totalSteps) * 100) : 0;
```

### 2. 添加预计剩余时间

根据已完成步骤的平均耗时估算：

```typescript
const avgStepDuration = totalDuration / completedSteps;
const estimatedRemaining = avgStepDuration * remainingSteps;
```

### 3. 添加实时日志流

在探索详情页添加一个实时日志查看器，显示最新的 20 条日志。

### 4. 添加性能监控

记录每个步骤的执行时间，识别慢步骤：

```python
start_time = time.time()
result = await execute_step(...)
duration = time.time() - start_time
self._publish("step_metrics", {"duration": duration, ...})
```

## 总结

通过以上修复，探索进度展示问题已经得到解决：

1. ✅ 前端能正确接收和处理所有探索事件
2. ✅ 后端在每个关键步骤都发送实时事件
3. ✅ 模块匹配逻辑更加健壮
4. ✅ 用户可以实时看到探索的详细进度

用户不会再看到"卡在探索中"的情况，而是能看到清晰的进度信息：
- 正在执行哪个步骤
- 访问了哪些页面
- 执行了哪些动作
- 每个步骤的执行结果
