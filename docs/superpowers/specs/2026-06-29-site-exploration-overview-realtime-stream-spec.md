# 站点探索概览实时执行流展示 Spec

## 背景

站点探索详情页当前有三个 tab：

- `探索计划`
- `探索概览`
- `探索报告`

运行中的探索任务已经通过 `GET /page-exploration/runs/{runId}/stream` 建立实时流。前端在详情页内用 `fetch` + `ReadableStream` 读取 SSE chunk，并通过 `applyStreamEvent` 增量更新 `monitor`、`streamDetail` 和 `run`。

现有展示存在职责错位：`探索计划` tab 中包含 `ExplorationRealtimeMonitor`，它展示规划结果、当前步骤、步骤表和实时事件；`探索概览` tab 的“探索模块进度”主要展示 `AgentPlan` 模块树。探索执行过程中的实时信息应该属于运行概览，而不是任务计划定义。

本 spec 定义一次前端展示重组：把探索过程中的 SSE 信息从 `探索计划` tab 移除，迁移到 `探索概览` tab 的“探索模块进度”区域，并采用左右分栏布局，左侧保留模块树，右侧展示实时执行流。

## 目标

- `探索计划` tab 不再展示 SSE 实时事件、步骤表或执行监控。
- `探索概览` tab 的“探索模块进度”成为运行态主区域。
- “探索模块进度”使用左右分栏：
  - 左侧展示模块、页面、步骤层级进度。
  - 右侧展示实时探索流水、当前步骤和工具/动作调用信息。
- 继续复用现有 SSE 链路和 `monitor` / `streamDetail` 状态，不新增后端接口。
- 参考 `playwright-cli` 和前端对话样式，把工具调用、输出回复、动作结果展示成可折叠、可扫描的卡片。
- 保持实时更新：流事件到达后，模块树和右侧执行流都应立即反映最新状态。

## 非目标

- 不改后端 SSE 协议。
- 不新增 WebSocket。
- 不把前端变成探索状态机。
- 不在前端猜测模块归属或业务语义。
- 不重做探索报告。
- 不改变探索任务创建、编辑、开始、停止的行为。
- 不要求第一版按模块精确归档每一条事件；只有事件 payload 已携带明确模块/页面信息时才做关联展示。

## 当前链路

### 现有实时流

详情页在 run 状态为 `queued`、`running`、`stopping`、`in-progress` 时打开流：

```text
GET {API_BASE_URL}/page-exploration/runs/{runId}/stream
  -> parseStreamEvent(chunk)
  -> applyStreamEvent(event, { setMonitor, setStreamDetail, setRun })
```

`applyStreamEvent` 已处理：

- `run_snapshot`
- `run_started`
- `run_completed`
- `run_failed`
- `run_cancelled`
- `run_status_updated`
- `planning_started`
- `planning_completed`
- `step_started`
- `step_completed`
- `step_failed`
- `step_skipped`
- `step_retrying`
- `module_*`
- `page_*`
- `step_recorded`
- `blocker_detected`

### 当前展示问题

`探索计划` tab 当前渲染 `ExplorationTaskInfoPanel`，其顶部包含 `ExplorationRealtimeMonitor`。这会让用户在查看任务输入、范围、禁止路径时看到运行日志，职责混杂。

`探索概览` tab 当前已有“探索模块进度”，但只展示 `AgentPlan`。用户需要在运行时同时看模块树和实时输出，现有右侧“执行时间线”粒度偏粗，不适合作为详细 SSE 流水。

## 推荐方案

采用 B 方案：`探索模块进度` 区域左右分栏。

```text
探索概览
  指标卡
  探索模块进度
    左侧：AgentPlan 模块树
    右侧：实时执行流
  执行时间线
  其他概览信息
```

布局比例建议：

```text
lg:grid-cols-[minmax(0,1fr)_420px]
```

左侧以模块树为主，保证宽度优先给页面标题、步骤描述和状态标签。右侧固定宽度，展示当前步骤和事件流水，类似对话侧栏。

## Tab 职责

### 探索计划

只展示任务定义和执行边界：

- 探索范围
- 禁止路径
- 探索目标
- 环境信息
- 执行边界
- 补充信息

保留编辑入口。开始、停止按钮是否出现仍沿用现有 `showRunActions` 规则。

不展示：

- 实时执行监控
- 实时事件
- 步骤表
- 当前执行步骤
- 工具/动作调用卡片

### 探索概览

展示运行态信息：

- 顶部指标卡
- 探索模块进度左右分栏
- 当前执行步骤
- 实时探索流水
- 执行时间线
- 阻塞、产物和报告入口等现有概览内容

## 组件设计

### 1. ExplorationTaskInfoPanel

调整为纯任务信息组件。

输入：

```ts
type ExplorationTaskInfoPanelProps = {
  run: ExplorationRun | null;
};
```

职责：

- 渲染探索范围、禁止路径、探索目标。
- 渲染环境、执行边界、备注。
- 不接收 `monitor`。
- 不渲染 `ExplorationRealtimeMonitor`。

### 2. ExplorationModuleProgressPanel

新增或提取组件，承载“探索模块进度”区域。

输入：

```ts
type ExplorationModuleProgressPanelProps = {
  loading: boolean;
  run: ExplorationRun | null;
  monitor: ExplorationMonitorState;
  agentPlanTasks: AgentPlanTask[];
  isUnsupportedArtifact: boolean;
  unsupportedArtifactReason: string;
  restarting: boolean;
  onRestart: () => Promise<void> | void;
};
```

职责：

- 维护左右分栏布局。
- 左侧渲染模块树或空状态。
- 右侧渲染实时执行流。
- 不直接解析 SSE，不直接请求数据。

### 3. ExplorationRealtimeStreamPanel

新增右侧实时执行流组件。

输入：

```ts
type ExplorationRealtimeStreamPanelProps = {
  monitor: ExplorationMonitorState;
  run: ExplorationRun | null;
};
```

展示结构：

```text
实时执行流
  状态徽标
  统计：规划步骤、完成、失败、当前步骤
  当前执行步骤卡片
  事件/工具调用列表
```

右侧面板需要有稳定高度和内部滚动，避免实时事件不断增加时撑高整个概览页。

建议：

```text
max-h: 680px
overflow-y: auto
```

### 4. ExplorationEventCard

普通 SSE 事件卡片。

输入：

```ts
type ExplorationEventCardProps = {
  event: ExplorationMonitorEvent;
};
```

展示：

- 事件中文名。
- 状态图标。
- 发生时间。
- 摘要。

普通事件适合轻量样式，不需要默认展开。

### 5. ExplorationToolCallCard

工具/动作调用卡片，参考参考项目的 `ToolCallCard`。

输入建议：

```ts
type ExplorationToolCallCardProps = {
  event: ExplorationMonitorEvent;
  payload?: Record<string, unknown>;
  defaultExpanded?: boolean;
};
```

第一版可以从 `ExplorationMonitorEvent` 和已有 payload 兼容生成展示内容。后端没有提供的字段不做假数据。

展示：

- Header：
  - 展开/收起按钮。
  - 动作或工具名称。
  - 状态。
  - 时间。
- 展开内容：
  - 输入：目标描述、selector、value、expected_result。
  - 输出：message、result、error。
  - 元信息：duration_ms、attempt、matched_element、page_state。

运行中的工具/动作默认展开；已完成和历史事件默认折叠。

## 事件分类

### 普通事件

以下事件默认使用 `ExplorationEventCard`：

- `run_started`
- `planning_started`
- `planning_completed`
- `execution_started`
- `execution_completed`
- `run_completed`
- `run_cancelled`
- `module_*`
- `page_*`
- `blocker_detected`
- `artifact_written`
- `edge_created`
- `raw`

### 工具/动作事件

以下事件优先使用 `ExplorationToolCallCard`：

- `action_started`
- `action_result`
- `action_completed`
- `step_started`
- `step_completed`
- `step_failed`
- `step_retrying`
- `direct_step_started`
- `agentic_step_started`
- `agent_decision`
- `agent_decision_fallback`
- `agent_observed`
- `observe`

判断函数建议：

```ts
function isToolLikeMonitorEvent(type: string): boolean {
  return (
    type.startsWith("action_") ||
    type.startsWith("step_") ||
    type.startsWith("agent_") ||
    type === "observe" ||
    type === "direct_step_started" ||
    type === "agentic_step_started"
  );
}
```

## 数据兼容

当前 `monitor.events` 只保留：

```ts
type ExplorationMonitorEvent = {
  id: string;
  type: string;
  label: string;
  summary: string;
  occurred_at: string;
  status: AgentPlanStatus;
};
```

若要展示工具输入/输出，需要保留事件 payload。第一版推荐扩展为：

```ts
type ExplorationMonitorEvent = {
  id: string;
  type: string;
  label: string;
  summary: string;
  occurred_at: string;
  status: AgentPlanStatus;
  payload?: Record<string, unknown>;
};
```

`monitorTimelineEvent(event)` 生成事件时，把 `event.payload` 透传进去。

兼容规则：

- `payload` 不存在时，卡片只展示 summary。
- 字段不存在时显示 `-` 或不渲染该行。
- 不因 payload 缺字段而阻塞实时渲染。
- 不把完整 JSON 默认铺开，避免噪声。

## 样式规范

整体风格沿用当前项目的 shadcn、Tailwind、`StatusBadge` 和 `Card`。

右侧实时流参考前端对话展示：

- Agent 输出使用轻量标题行。
- 工具调用使用折叠卡片。
- 运行中使用 spinner。
- 成功用绿色状态。
- 失败用红色状态。
- 跳过、重试、取消用 amber/neutral 状态。

避免：

- 大面积深色终端风格。
- 把 JSON 原文作为默认主内容。
- 在模块树内嵌过多事件导致主进度难以扫描。
- `探索计划` 和 `探索概览` 双处重复展示同一组实时事件。

## 空状态

### 任务未开始

左侧：

```text
任务尚未开始，点击「开始探索」后将显示进度信息。
```

右侧：

```text
开始探索后会在这里显示实时执行流。
```

### 流连接中

右侧保留 run 状态徽标，列表展示：

```text
等待后端推送探索事件。
```

### 历史任务无事件

右侧展示：

```text
暂无实时事件记录。
```

模块树仍从详情快照展示历史产物。

### 不支持的历史产物

左侧沿用 `UnsupportedArtifactNotice`。右侧展示空状态，不提示实时流错误。

## 错误处理

- SSE 连接失败仍沿用当前重连策略。
- 右侧执行流不额外弹 toast，避免运行中频繁扰动。
- 页面级加载失败仍使用现有 `ExplorationFailureNotice`。
- 单条事件 payload 解析失败时跳过该事件，不影响后续事件。

## 验证方案

### 静态契约验证

新增或更新前端 contract test：

- `探索计划` tab 不包含“实时执行监控”。
- `探索概览` tab 包含“探索模块进度”和“实时执行流”。
- 模块树和实时执行流可同时存在。
- 工具类事件渲染为可折叠卡片。

### 手动验证

启动前端并进入运行中的探索详情页：

1. 点击 `探索计划`，确认只展示任务定义信息。
2. 点击 `探索概览`，确认左侧模块树存在。
3. 运行探索任务，确认右侧实时执行流持续追加事件。
4. 观察 `step_started` 到达时当前步骤高亮。
5. 观察 `action_result` / `step_completed` 到达时卡片状态更新。
6. 停止或完成任务后，确认最终状态可通过刷新页面恢复。

### 回归风险

- `monitor.events` 当前最多保留 80 条，右侧只展示最近事件；这是合理的运行态视图，不替代完整操作日志。
- 若后端 payload 字段不稳定，工具卡片只能展示摘要；这不影响模块进度实时刷新。
- 分栏在窄屏下应自动堆叠，避免右侧挤压模块树。

## 实施顺序

1. 扩展 `ExplorationMonitorEvent`，保留可选 `payload`。
2. 调整 `monitorTimelineEvent`，透传 payload。
3. 修改 `ExplorationTaskInfoPanel`，移除 `ExplorationRealtimeMonitor`。
4. 提取 `ExplorationModuleProgressPanel`。
5. 新增 `ExplorationRealtimeStreamPanel`。
6. 新增普通事件卡片和工具/动作调用卡片。
7. 替换 `探索概览` 中“探索模块进度”的单列内容为左右分栏。
8. 更新前端 contract test。
9. 运行前端测试，并用浏览器检查运行态布局。

## 验收标准

- `探索计划` tab 不再出现 SSE 执行流信息。
- `探索概览` 的“探索模块进度”左侧展示模块树，右侧展示实时执行流。
- SSE 事件到达后，左侧模块树和右侧执行流实时更新。
- 工具/动作类事件以可折叠卡片展示。
- 普通事件以轻量事件卡片展示。
- 不改后端接口也能工作。
- 刷新页面后仍能通过详情快照恢复模块进度。
