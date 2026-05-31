# 站点探索 AgentPlan 页面状态规范化修复规范

## 背景

站点探索概览已经使用 `AgentPlan` 展示模块、页面和页面探索步骤。当前页面出现一种不一致展示：

```text
模块：已完成
  页面：待探索
    步骤：已完成
```

实际原因不是页面未探索，而是模块状态和页面状态使用了不同语义：

- 模块使用 `module.completion_status`，完成后为 `completed`。
- 页面使用 `page.status`，后端页面事实产物默认值为 `explored`。
- 前端 `AgentPlanStatus` 契约不包含 `explored`，因此 `explored` 被降级为 `pending`，展示为“待探索”。

该问题会让测试人员误以为模块已完成但页面仍未探索，破坏探索进度的可信度。

## 目标

- 消除“外层已完成、内层待探索”的矛盾展示。
- 保留页面节点状态，不删除内部状态展示。
- 后端 API 输出符合 `AgentPlan` 展示状态契约。
- 前端兼容历史数据中已有的 `explored` 页面状态。
- 页面 YAML 或事实产物可以继续保留 `explored` 作为事实状态，但不得直接泄漏为 `AgentPlan` 展示状态。

## 非目标

- 不移除页面节点右侧状态。
- 不把探索概览改回表格或旧的模块进度列表。
- 不让前端根据页面步骤、标题、URL、YAML 路径自行推断探索完成状态。
- 不修改模块状态计算规则。
- 不迁移或重写历史探索产物文件。
- 不引入新的状态枚举用于前端展示。

## 设计原则

- 后端是探索事实和展示状态的权威来源。
- `AgentPlan` 只消费展示契约内的状态。
- 页面事实状态和页面展示状态可以不同，但 API 边界必须明确。
- 前端兜底只能用于兼容历史数据，不能成为长期主要逻辑。

## 当前问题定位

### 后端页面事实状态

`apps/backend/app/services/site_exploration_orchestrator.py` 中页面归一化逻辑会设置：

```python
page["status"] = str(page.get("status") or "explored")
```

`apps/backend/app/schemas/exploration.py` 中 `ExplorationPageOut.status` 默认也是：

```python
status: str = "explored"
```

这表示“页面事实已被探索并生成结构化事实”，不是 `AgentPlan` 的展示状态。

### 前端展示状态

`apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx` 会把页面状态传给：

```ts
normalizeAgentPlanStatus(page.status || "pending")
```

`normalizeAgentPlanStatus` 不识别 `explored`，最终返回：

```ts
return "pending";
```

因此页面展示成“待探索”。

### 实时流和刷新不一致

完成持久化后，后端发布 `page_completed` 事件时使用：

```python
{**page, "status": "completed"}
```

所以实时流可能短暂显示页面“已完成”。刷新页面后，详情接口重新读取持久化状态 `explored`，前端又显示为“待探索”。

## 状态契约

### AgentPlan 展示状态

`AgentPlan` 只允许消费以下展示状态：

| 展示状态 | 文案 | 说明 |
| --- | --- | --- |
| `pending` | 待探索 | 已纳入计划但未开始 |
| `queued` | 排队中 | 任务已提交，等待执行 |
| `running` | 探索中 | 正在执行 |
| `in-progress` | 探索中 | 模块或页面进行中 |
| `stopping` | 正在停止 | 用户已请求停止 |
| `completed` | 已完成 | 已生成事实产物且无关键阻塞 |
| `partial` | 部分完成 | 有事实产物，但存在未覆盖或非关键阻塞 |
| `blocked` | 阻塞 | 关键阻塞导致不可继续 |
| `waiting_human` | 等待人工 | 需要人工处理 |
| `failed` | 失败 | runner 或编排异常 |
| `cancelled` | 已中止 | 用户中止或系统取消 |

### 页面事实状态兼容表

后端可以在 YAML 或内部事实对象中保留页面事实状态，但 detail API 需要转换为展示状态：

| 页面事实状态 | API 展示状态 | 说明 |
| --- | --- | --- |
| `explored` | `completed` | 已访问页面并生成事实产物 |
| `completed` | `completed` | 已完成 |
| `blocked` | `blocked` | 页面存在关键阻塞 |
| `partial` | `partial` | 页面有事实产物但不完整 |
| `pending` | `pending` | 已计划但未访问 |
| `running` | `running` | 正在探索 |
| `in-progress` | `in-progress` | 正在探索 |
| `waiting_human` | `waiting_human` | 等待人工处理 |
| `failed` | `failed` | 页面探索失败 |
| `cancelled` | `cancelled` | 页面探索被取消 |
| 未识别状态 | `pending` | 同时保留原始状态用于调试日志 |

## 后端修改方案

### 1. 增加页面状态规范化函数

在 `apps/backend/app/services/site_exploration_orchestrator.py` 或更靠近 detail 输出的服务层增加函数。

推荐放在 `apps/backend/app/services/exploration_service.py`，因为问题发生在 API 展示契约边界。

目标函数：

```python
def normalize_page_display_status(status: str | None) -> str:
    normalized = str(status or "").strip()
    if normalized == "explored":
        return "completed"
    if normalized in {
        "pending",
        "queued",
        "running",
        "in-progress",
        "stopping",
        "completed",
        "partial",
        "blocked",
        "waiting_human",
        "failed",
        "cancelled",
    }:
        return normalized
    return "pending"
```

要求：

- 不修改页面 YAML 中的原始 `page.status`。
- 不修改 runner 已有事实产物语义。
- detail API 返回的 `pages[].status` 必须是展示状态。

### 2. 详情接口输出规范化状态

在 `get_project_run_detail` 或组装 `ExplorationPageOut` 的位置，把：

```python
status=page_status
```

改为：

```python
status=normalize_page_display_status(page_status)
```

如果当前 detail 数据来自数据库，则在 repository 取出后、schema 返回前做转换。

### 3. SSE 页面事件保持 completed

`page_completed` 事件当前已经发布 `status: completed`，可以保留。

同时要求：

- `page_started` 或运行中页面事件使用 `running` 或 `in-progress`。
- `page_blocked` 使用 `blocked`。
- 不再通过 SSE 向前端发送 `explored` 作为展示状态。

### 4. Schema 默认值调整

`ExplorationPageOut.status` 是 API 展示字段，默认值应从：

```python
status: str = "explored"
```

改为：

```python
status: str = "completed"
```

说明：

- 这是 API 展示 schema 的默认值。
- 不代表页面 YAML 的事实状态默认值必须变化。

## 前端修改方案

### 1. 兼容 `explored`

在 `normalizeAgentPlanStatus` 中加入兼容：

```ts
if (status === "explored") {
  return "completed";
}
```

用途：

- 兼容历史 API 响应。
- 兼容浏览器未刷新、SSE 与快照交错时的旧状态。
- 不能替代后端状态规范化。

### 2. 保留页面状态展示

页面节点右侧状态继续展示。

原因：

- 现有 AgentPlan 契约要求“页面节点右侧只显示状态”。
- 页面状态能表达页面级阻塞、失败、等待人工。
- 删除页面状态会让模块内问题定位变弱。

### 3. 不做前端完成状态推断

前端不得根据以下条件自行把页面改成完成：

- `steps.length > 0`
- 存在 `yaml_path`
- 存在 `structure_summary`
- 存在完成步骤
- 模块状态为 `completed`

只有明确状态值可以触发展示。

## 测试要求

### 后端测试

在 `apps/backend/tests/test_exploration_service.py` 增加用例：

- 给页面记录或 page artifact 设置 `status: explored`。
- 调用 detail 服务或 detail API。
- 断言返回 `pages[].status == "completed"`。
- 断言页面 steps 不受影响。

建议用例名：

```python
test_run_detail_normalizes_explored_page_status_to_completed
```

在 `apps/backend/tests/test_site_exploration_orchestrator.py` 增加或确认：

- `page_completed` SSE 事件中的 `status` 为 `completed`。
- 完成 run 刷新 detail 后页面状态仍为 `completed`。

### 前端测试或静态验证

如果当前项目没有前端单测，可做最小静态验证：

- `normalizeAgentPlanStatus("explored")` 返回 `completed`。
- `AgentPlan` 页面子任务收到 `completed` 时展示“已完成”。
- `AgentPlan` 页面子任务收到未知状态时仍展示“待探索”。

如果有前端测试框架，增加用例：

```ts
expect(normalizeAgentPlanStatus("explored")).toBe("completed");
```

如果该函数不是导出函数，可以通过页面构造 `AgentPlanTask` 或将状态映射函数提取为可测试工具。

## 验收标准

- 完成探索后，模块显示“已完成”，其已探索页面也显示“已完成”。
- 刷新页面后，状态展示与实时流期间一致。
- 历史数据中 `page.status = explored` 的页面不再显示“待探索”。
- 阻塞页面仍显示“阻塞”，不会被统一转成“已完成”。
- 页面级状态仍然可见，没有被删除。
- 前端不根据模块状态或步骤数量推断页面状态。
- detail API 不再向 `AgentPlan` 暴露 `explored` 作为展示状态。

## 实施顺序

1. 后端 detail 输出增加页面展示状态规范化。
2. 后端 schema 默认值从 `explored` 调整为 `completed`。
3. 前端 `normalizeAgentPlanStatus` 兼容 `explored`。
4. 补后端 detail 测试。
5. 补 SSE 或 orchestrator 状态一致性测试。
6. 运行相关后端测试和前端 lint。

## 风险与边界

- 如果其他消费者依赖 detail API 返回 `explored`，需要同步改为使用页面 YAML 或新增原始字段。
- 不建议直接把所有历史 YAML 的 `page.status` 从 `explored` 改成 `completed`，这会混淆事实状态和展示状态。
- 如果未来需要展示原始事实状态，可新增 `artifact_status` 或 `raw_status` 字段，但本次不做。

## 最小补丁范围

推荐最小修改文件：

- `apps/backend/app/services/exploration_service.py`
- `apps/backend/app/schemas/exploration.py`
- `apps/backend/tests/test_exploration_service.py`
- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`

可选修改文件：

- `apps/backend/app/services/site_exploration_orchestrator.py`
- `apps/backend/tests/test_site_exploration_orchestrator.py`
- `apps/frontend/src/components/ui/agent-plan.tsx`

仅当当前状态映射函数位于 `AgentPlan` 组件内部时，才需要修改 `agent-plan.tsx`。
