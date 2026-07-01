# 站点探索概览对话式执行流 Spec

## 背景

站点探索详情页当前已经有实时 SSE 链路、`monitor` 运行态、`write_todos` 计划更新事件和可读执行事件。页面也已经具备左右分栏雏形：

- 左侧展示模板步骤或模块进度。
- 右侧展示实时动作。

新的目标是进一步调整交互表达：左侧只展示“探索阶段完成到哪一步”，右侧不再用卡片墙展示工具调用，而是展示类似目标前端 Agent 工具调用样式的“对话过程 + 内联执行动作信息”。

## 目标

1. 左侧展示探索阶段 todo，回答“当前完成到哪一步”。
2. 右侧展示 Agent 对话过程，回答“Agent 在怎么判断、怎么执行”。
3. 工具调用信息以内联执行块展示在对话流中，不使用大卡片列表。
4. 工具调用样式参考目标前端的工具调用折叠块：状态图标、工具名、参数、结果、错误、可展开明细。
5. 继续复用现有 `DeepAgents + FastAPI SSE + events.jsonl` 链路，不新增 LangGraph SDK 前端运行层。
6. `write_todos` / `agent_plan_updated` 只驱动左侧阶段，不在右侧重复刷屏。

## 非目标

- 不新增后端接口。
- 不替换现有 `GET /page-exploration/runs/{runId}/stream`。
- 不把右侧做成工具调用卡片墙。
- 不在右侧展示每一次 `write_todos` 更新。
- 不重做探索报告页。
- 不改探索任务创建、编辑、开始、停止行为。
- 不要求第一版精确把每个工具调用挂到某条 Agent 消息下；如果缺少关联信息，可以按时间顺序归并。

## 当前实现依据

后端当前页面探索 Agent 已使用 DeepAgents：

```text
apps/backend/app/agents/page_exploration/agent.py
  -> create_deep_agent(...)
```

探索执行已经监听 Agent 流式事件：

```text
apps/backend/app/services/exploration/page_exploration_service.py
  -> agent.astream_events(...)
  -> _publish_agent_stream_event(...)
  -> event_bus.publish(...)
```

前端详情页已经建立 SSE：

```text
apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx
  -> fetch /page-exploration/runs/{runId}/stream
  -> parseStreamEvent
  -> applyStreamEvent
  -> monitor / streamDetail / run
```

本次设计是在这些现有边界内重组展示，不重建运行框架。

## 推荐页面结构

```text
探索概览
  左侧：探索阶段
    - 阶段状态
    - 当前阶段
    - 已完成阶段
    - 失败/阻塞阶段

  右侧：对话与执行
    - 用户输入
    - Agent 分析/回复
    - 内联工具调用
    - 工具参数/结果折叠区
    - 错误和建议
```

布局建议：

```text
lg:grid-cols-[360px_minmax(0,1fr)]
```

移动端堆叠：

```text
grid-cols-1
```

## 运行态视图模型

前端增加一个展示适配层，将现有 `monitor.events`、`monitor.steps`、`run_snapshot.raw_events` 归一化为页面视图模型。

```ts
type ExplorationRunViewState = {
  stages: ExplorationStageItem[];
  timeline: ExplorationConversationItem[];
  status: string;
};

type ExplorationStageItem = {
  id: string;
  title: string;
  status: "pending" | "running" | "completed" | "failed" | "blocked" | "skipped";
  order: number;
};

type ExplorationConversationItem =
  | ExplorationMessageItem
  | ExplorationToolCallItem;

type ExplorationMessageItem = {
  id: string;
  type: "message";
  role: "user" | "assistant" | "system";
  content: string;
  occurredAt: string;
};

type ExplorationToolCallItem = {
  id: string;
  type: "tool_call";
  name: string;
  summary: string;
  status: "running" | "completed" | "failed" | "interrupted";
  occurredAt: string;
  completedAt?: string;
  args?: Record<string, unknown>;
  result?: unknown;
  error?: string;
};
```

## 事件映射规则

### 左侧阶段

优先来源：

```text
agent_plan_updated
  display.kind === "todo_update"
  tool_name === "write_todos"
```

映射规则：

- `pending` -> 待执行
- `in_progress` -> 当前阶段
- `completed` -> 已完成
- 工具失败、步骤失败或 run 失败时，将当前阶段标记为 `failed`

如果当前运行没有 `write_todos`，则回退到现有 `planning_completed.steps` / `monitor.steps`。

### 右侧对话

来源：

```text
run_started
agent_thought
agent_tool_started
agent_tool_completed
agent_tool_failed
run_completed
run_failed
run_cancelled
```

映射规则：

- `agent_thought` -> assistant message
- `agent_tool_started` -> running tool_call
- `agent_tool_completed` -> completed tool_call
- `agent_tool_failed` -> failed tool_call
- `run_completed` -> assistant summary message
- `run_failed` -> assistant error message
- `agent_plan_updated` 默认不进入右侧 timeline

## 左侧组件设计

### ExplorationStageSidebar

职责：

- 展示探索阶段列表。
- 高亮当前阶段。
- 展示状态图标。
- 保持布局稳定，不随右侧执行流增长而变化。

建议结构：

```text
探索阶段
  状态 badge
  目标/入口/范围摘要

  ✓ 准备探索入口
  ◐ 分析当前页面
  ○ 识别关键元素
  ○ 写入页面事实
  ○ 汇总探索结果
```

展示规则：

- `completed`：Check 图标。
- `running`：Loader 或 Clock 图标。
- `pending`：Circle 图标。
- `failed` / `blocked`：Alert 图标。
- 当前阶段背景轻微高亮。
- 阶段文本尽量短，不展示工具参数。

## 右侧组件设计

### ExplorationConversationPanel

替代当前“实时动作”面板。

职责：

- 展示用户和 Agent 的对话过程。
- 在 Agent 消息下方或相邻位置展示工具调用信息。
- 保持内部滚动。
- 保持自动跟随底部，但用户向上滚动后不强制拉回。

标题：

```text
对话与执行
```

副文案：

```text
展示 Agent 分析、工具调用和关键执行结果
```

不再展示：

```text
N 张卡片 · 原始 N 条
```

### ConversationMessageBubble

用于渲染对话消息。

用户消息：

- 右对齐或使用淡色背景。
- 内容就是探索目标或用户输入。

Agent 消息：

- 左对齐。
- 以普通文本/Markdown 展示分析过程。
- 不用卡片边框。

### ToolCallInlineBlock

用于渲染工具调用信息，参考目标前端工具调用样式，但作为对话流中的内联块。

默认折叠规则：

- `running` 默认展开或显示简短 loading 行。
- `completed` 默认折叠。
- `failed` 默认展开。

结构：

```text
  ✓ playwright_snap_tool
    采集登录页页面结构

    参数  v
    结果  v
```

折叠头信息：

- 状态图标
- 工具名
- 一句话摘要
- 时间
- 展开/收起图标

展开内容：

- 参数
- 结果
- 错误原因
- 建议

样式要求：

- 不使用大卡片边框。
- 使用左侧缩进、细竖线、浅色背景或 hover 背景区分工具调用。
- 参数和结果可用等宽字体。
- 长结果截断，提供展开。
- 错误使用红色文本和错误图标。

示例：

```text
Agent
我先打开入口页面并采集结构。

  ⏳ playwright_navigate_tool
     打开 /login

  ✓ playwright_snap_tool
     采集登录页页面结构
     发现元素：输入框 2 · 按钮 3
```

## 工具调用展示映射

### playwright_navigate_tool

标题：

```text
打开页面
```

摘要：

```text
打开 {url}
```

字段：

- 目标 URL
- 结果

### playwright_click_tool

标题：

```text
点击元素
```

字段：

- 目标
- 定位器
- 结果

### playwright_snap_tool / playwright_extract_elements_tool

标题：

```text
采集页面快照
```

字段：

- 页面
- URL
- 发现元素
- 关键元素
- 结果

### write_page_artifact_tool

标题：

```text
写入页面事实
```

字段：

- 页面
- 产物
- 结果

### update_explored_url_tool

标题：

```text
记录已探索页面
```

字段：

- URL
- 状态

### read_file

标题：

```text
加载探索规则
```

字段：

- 文件
- 结果

### write_todos

不进入右侧主 timeline。只用于左侧阶段。

## 后端调整

第一版不要求新增接口。

可以保留现有后端事件：

- `agent_thought`
- `agent_tool_started`
- `agent_tool_completed`
- `agent_tool_failed`
- `agent_plan_updated`

主路径只消费页面渲染和状态恢复需要的字段，不新增调试专用字段，不引入 `debug_ref`、`rawEventIds`、`displayFields` 这类仅供排查的信息。

## 前端实现范围

主要修改：

```text
apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx
```

建议新增/替换函数：

```ts
buildExplorationRunViewState(...)
buildConversationTimeline(...)
buildStageItems(...)
mergeToolCallLifecycle(...)
```

建议新增组件：

```ts
ExplorationStageSidebar
ExplorationConversationPanel
ConversationMessageBubble
ToolCallInlineBlock
ToolCallInlineDetails
```

建议废弃主路径：

```ts
ReadableExecutionCardView
buildReadableExecutionCards
```

如果为了降低改动风险，第一版可以保留函数名，但输出不再叫 card，UI 不再渲染卡片样式。

## 验收标准

1. 探索概览左侧标题为“探索阶段”。
2. 左侧展示 todo/stage 列表，并能反映当前进行、完成、失败状态。
3. 右侧标题为“对话与执行”。
4. 右侧不出现“实时动作”“动作列表”“N 张卡片”等卡片墙文案。
5. 右侧 Agent 分析以对话消息形式展示。
6. 右侧工具调用以内联执行块展示，不使用大卡片列表。
7. `write_todos` 更新不在右侧重复展示，只更新左侧阶段。
8. 工具调用参数和结果可展开查看。
9. 失败工具调用默认展开，并展示错误原因。
10. 刷新页面后，历史 `events.jsonl` 能恢复左侧阶段和右侧执行过程。
11. 不新增后端接口。

## 测试建议

更新：

```text
apps/frontend/tests/exploration-detail-contract.test.mjs
```

建议断言：

- 存在 `ExplorationStageSidebar`
- 存在 `ExplorationConversationPanel`
- 存在 `ToolCallInlineBlock`
- 不存在主展示文案 `实时动作`
- 不存在主展示文案 `张卡片`
- `agent_plan_updated` 或 `write_todos` 不进入右侧 timeline 主渲染

运行：

```bash
node --test apps/frontend/tests/exploration-detail-contract.test.mjs
```

后端如有轻量字段调整，再运行：

```bash
cd apps/backend
uv run pytest tests/test_page_exploration_artifact_snapshot.py -q
```
