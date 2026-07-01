# 页面探索概览最小契约清理 Spec

## 背景

页面探索详情页正在改成：

- 左侧：探索阶段，展示当前完成到哪一步。
- 右侧：对话过程 + 执行动作信息，工具调用以内联块展示。

后端现有 `DeepAgents + FastAPI SSE + events.jsonl` 链路已经能提供实时事件，不需要整体重构，也不需要新增一套接口。本次目标是收敛探索概览主路径的接口字段、事件字段和前端展示模型，删除卡片墙时代遗留的无用字段和未使用入口。

## 目标

1. 保留现有页面探索执行链路，不替换 DeepAgents。
2. 保留现有详情接口和 SSE 接口，不新增运行态接口。
3. 后端 SSE 主事件只输出页面展示需要的最小字段。
4. 前端探索概览只消费“阶段”和“对话执行流”两类数据。
5. 删除或停止使用旧卡片墙字段、调试字段、重复展示字段。
6. 删除确认无引用的后端接口；有引用的接口只做字段收口。

## 非目标

- 不重写探索 Agent。
- 不重做探索报告页。
- 不改探索任务创建、编辑、开始、停止行为。
- 不迁移产物存储结构。
- 不删除 `events.jsonl` 原始事件记录。
- 不让前端靠 CSS 隐藏无用字段来伪装契约清理。

## 保留接口

这些接口当前仍被前端页面或工作台使用，第一版不删除：

```text
POST   /page-exploration/runs
PATCH  /page-exploration/runs/{run_id}
POST   /page-exploration/runs/{run_id}/start
POST   /page-exploration/runs/{run_id}/stop
GET    /page-exploration/runs/{run_id}
GET    /page-exploration/runs/{run_id}/stream
GET    /page-exploration/runs/{run_id}/artifacts
GET    /page-exploration/runs
GET    /page-exploration/runs-all
GET    /page-exploration/runs/{run_id}/pages
GET    /page-exploration/artifacts
GET    /page-exploration/artifacts/{artifact_id}/content
DELETE /page-exploration/runs/{run_id}
```

## 候选删除接口

删除前必须先用 `rg` 确认前端、后端测试和文档入口没有引用。

```text
GET /page-exploration/runs-running
GET /page-exploration/artifacts-tree
```

删除规则：

- 如果只有后端路由定义，无前端和测试引用，删除路由、service 函数和相关测试。
- 如果存在后台任务指示器或隐藏入口引用，保留接口，只收口响应字段。
- 不为了“可能以后用”保留空接口。

## 详情接口最小契约

`GET /page-exploration/runs/{run_id}` 第一版保留现有外层结构，但主视图只依赖以下字段：

```ts
type ExplorationRunDetail = {
  run: ExplorationRun;
  modules: ExplorationModule[];
  raw_events: PersistedExplorationEvent[];
  unsupported_artifact: boolean;
  unsupported_reason: string;
};
```

可停止作为主视图依赖：

```text
artifact_schema_version
```

处理规则：

- 第一版可兼容保留 `artifact_schema_version`，但前端探索概览不得再依赖它判断布局。
- 后续确认无其他页面依赖后，从 response model 和前端类型中删除。

## SSE 事件最小契约

保留事件类型：

```text
run_snapshot
run_completed
run_failed
run_cancelled
error
agent_thought
agent_tool_started
agent_tool_completed
agent_tool_failed
agent_plan_updated
```

### agent_thought

```ts
type AgentThoughtEvent = {
  type: "agent_thought";
  run_id: string;
  occurred_at: string;
  payload: {
    step_id: string;
    status: "completed";
    completed_at: string;
  };
  display: {
    kind: "model_analysis";
    title: string;
    summary: string;
    chips?: string[];
  };
};
```

### agent_tool_*

```ts
type AgentToolEvent = {
  type: "agent_tool_started" | "agent_tool_completed" | "agent_tool_failed";
  run_id: string;
  occurred_at: string;
  payload: {
    step_id: string;
    tool_name: string;
    status: "running" | "completed" | "failed";
    error_summary?: string;
  };
  display: {
    kind: string;
    title: string;
    summary: string;
    fields?: Array<{
      label: string;
      value: string;
      mono?: boolean;
      tone?: "default" | "success" | "warning" | "danger";
    }>;
  };
};
```

### agent_plan_updated

`agent_plan_updated` 只驱动左侧阶段，不进入右侧对话主 timeline。

```ts
type AgentPlanUpdatedEvent = {
  type: "agent_plan_updated";
  run_id: string;
  occurred_at: string;
  payload: {
    step_id: string;
    tool_name: "write_todos";
    status: "running" | "completed" | "failed";
    error_summary?: string;
  };
  display: {
    kind: "todo_update";
    title: string;
    summary: string;
    fields?: Array<{ label: string; value: string }>;
  };
};
```

## 必删字段

主 SSE payload 和前端主视图类型中删除：

```text
debug_ref
rawEventIds
displayFields
duration_ms
input
output
messages
response_metadata
raw_output
```

说明：

- `debug_ref` 只对排障有用，原始事件已经写入 `events.jsonl`，主 SSE 不再携带。
- `duration_ms` 当前没有真实计时，不能输出空值或伪值。
- `input/output/messages/response_metadata/raw_output` 不进入主 SSE；需要排障时读 `events.jsonl`。
- `displayFields/rawEventIds` 是旧前端卡片墙抽象，删除。

## 可保留字段

这些字段直接服务右侧工具调用内联展示，可以保留：

```text
display.kind
display.title
display.summary
display.fields
display.chips
payload.step_id
payload.tool_name
payload.status
payload.error_summary
```

字段规则：

- `display.fields` 只放用户能理解的短字段。
- 长文本、完整文件内容、完整模型对象不得进入 `display.fields`。
- `suggestion` 不作为通用字段输出；只有失败事件需要建议时，放入 `display.fields`，label 为 `建议`。

## 前端展示模型

探索概览只保留两个主模型。

```ts
type ExplorationStageItem = {
  id: string;
  title: string;
  status: "pending" | "running" | "completed" | "failed" | "blocked" | "skipped";
  order: number;
};

type ExplorationConversationEntry = {
  id: string;
  kind: "message" | "tool";
  role: "user" | "assistant" | "system";
  title: string;
  content: string;
  status: "pending" | "running" | "completed" | "failed" | "blocked" | "skipped";
  occurredAt: string;
  completedAt?: string;
  fields?: Array<{
    label: string;
    value: string;
    mono?: boolean;
    tone?: "default" | "success" | "warning" | "danger";
  }>;
  chips?: string[];
};
```

删除旧模型：

```text
ReadableExecutionCardView
buildReadableExecutionCards
readable card 主渲染入口
```

如果为了降低风险暂时保留旧函数名，主路径不得再渲染“实时动作”“动作列表”“张卡片”等文案。

## 最小任务

### Task 1：后端 SSE 字段瘦身

修改文件：

```text
apps/backend/app/services/exploration/page_exploration_service.py
apps/backend/tests/test_page_exploration_artifact_snapshot.py
```

任务：

- 从 `_agent_event_to_readable_stream_event` 删除 `debug_ref`。
- 删除 `duration_ms` 空字段。
- 将失败建议从 `payload.suggestion` 移到 `display.fields`。
- 保证主 SSE 不携带 `input/output/messages/response_metadata/raw_output`。
- 更新后端测试断言最小 payload。

验证：

```bash
cd apps/backend
uv run pytest tests/test_page_exploration_artifact_snapshot.py::test_agent_stream_tool_events_publish_readable_whitelisted_sse_payloads -q
uv run pytest tests/test_page_exploration_artifact_snapshot.py::test_agent_stream_write_todos_publishes_plan_update_display -q
```

### Task 2：前端探索概览契约收口

修改文件：

```text
apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx
apps/frontend/tests/exploration-detail-contract.test.mjs
```

任务：

- 右侧只使用 `ExplorationConversationEntry`。
- 左侧只使用阶段模型。
- 删除主路径中的 card 命名和 card 文案。
- 确认 `agent_plan_updated` 不进入右侧 timeline。
- 删除前端主视图类型中的 `displayFields`、`rawEventIds`、`debug_ref`。

验证：

```bash
cd apps/frontend
node --test tests/exploration-detail-contract.test.mjs
```

### Task 3：候选接口引用检查与删除

修改文件：

```text
apps/backend/app/api/v1/page_exploration.py
apps/backend/app/services/exploration/page_exploration_service.py
apps/backend/tests/*
apps/frontend/*
```

任务：

- 用 `rg` 检查 `/page-exploration/runs-running`。
- 用 `rg` 检查 `/page-exploration/artifacts-tree`。
- 无引用则删除路由、service 函数和测试。
- 有引用则保留接口，但响应字段按实际调用收口。

验证：

```bash
rg -n "runs-running|artifacts-tree" apps docs
cd apps/backend
uv run pytest tests/test_page_exploration_artifact_snapshot.py -q
cd ../frontend
node --test tests/exploration-detail-contract.test.mjs
```

## 验收标准

1. 探索概览左侧只展示“探索阶段”。
2. 探索概览右侧只展示“对话与执行”。
3. 右侧没有旧卡片墙文案。
4. `write_todos` 只更新左侧阶段。
5. 主 SSE payload 不再包含 `debug_ref`、`duration_ms`、`suggestion`、`input`、`output`、`messages`、`response_metadata`、`raw_output`。
6. 原始事件仍写入 `events.jsonl`。
7. 删除接口前有引用检查证据。
8. 前端契约测试通过。
9. 后端事件转换测试通过。
