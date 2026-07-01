# 页面探索实时执行流可读化 Spec

## 背景

页面探索详情页已经通过 SSE 展示实时执行流，但当前卡片直接展示 LangGraph / LangChain 原始对象，例如：

```text
Command(update={'messages': [AIMessage(...)]})
HumanMessage(...)
response_metadata={'finish_reason': 'tool_calls', ...}
```

这类内容对排障有价值，但不是人类理解探索过程所需的主信息。用户需要知道的是：

- Agent 当前在做什么。
- 打开了哪个页面。
- 点击了哪个元素。
- 采集到了什么页面信息。
- 写入了哪些产物。
- 为什么失败或停止。

本规范定义一次“执行流可读化”改造：页面使用两栏运行观察布局，左侧窄栏展示探索主信息和结果摘要，右侧宽栏只展示实时动作流；原始事件只保留在折叠调试层。

## 真实日志观察

样本运行：

```text
apps/backend/data/projects/project-75fec50973f2adf6/page_exploration/runs/exp_Z--zfm2jCwKmBiIoCDqg2w/events.jsonl
```

该运行共 5596 条事件。主要分布：

- `agent_stream_event`: 5582 条
- `agent_step_started`: 7 条
- `agent_step_failed`: 4 条
- `agent_step_completed`: 3 条

高频噪声事件：

- `on_chat_model_stream ChatOpenAI`: 2070 条
- `on_chain_stream LangGraph`: 655 条
- `on_chain_start/end/stream tools`
- `TodoListMiddleware.after_model`
- `SkillsMiddleware.before_agent`
- `PatchToolCallsMiddleware.before_agent`

对主视图有价值的事件：

- `on_chat_model_end ChatOpenAI`
- `on_chain_end model`
- `on_tool_start/on_tool_end/on_tool_error`
- `agent_step_started`
- `agent_step_completed`
- `agent_step_failed`
- `run_started/run_completed/run_failed`

真实工具分布：

- `playwright_snap_tool`: 73 次 start，72 次 end
- `playwright_navigate_tool`: 46 次 start，46 次 end
- `playwright_click_tool`: 43 次 start，40 次 end，3 次 error
- `write_page_artifact_tool`: 31 次 start，31 次 end
- `read_file`: 15 次 start，15 次 end
- `write_todos`: 15 次 start，15 次 end
- `update_explored_url_tool`: 9 次 start，9 次 end
- `playwright_extract_elements_tool`: 1 次 start，1 次 end

真实失败示例：

```text
stale_ref: Unknown element id: button-对话历史-028
Error code: 429 - rate_limit_exceeded: 5小时窗口内的配额已用完：(501/500)
```

该运行最终报告显示页面产物数为 0，因此最终摘要必须明确区分“工具执行过”和“最终产物已登记”。

## 当前代码现状

后端当前入口：

- `apps/backend/app/services/exploration/page_exploration_service.py`
  - `_invoke_agent_with_realtime_events(...)` 从 `agent.astream_events(...)` 接收 LangChain / DeepAgents 原始事件。
  - `_publish_agent_stream_event(run_id, event)` 把 `on_tool_start`、`on_tool_end`、`on_tool_error` 和部分 chain 事件转成 `step_started`、`step_completed`、`step_failed` 推到 `event_bus`。
  - `_compact_agent_event(event)` 把原始事件压缩后写入 `events.jsonl`。
  - `_compact_event_payload(value)` 目前会把 input/output/error 压成最长 240 字符串，但主 SSE 仍容易携带对 UI 无意义的原始对象摘要。
- `apps/backend/app/api/v1/page_exploration.py`
  - `stream_exploration_progress(...)` 直接转发 `event_bus.subscribe(run_id)` 的事件。
  - 终止态由 `run_completed` / `run_failed` / `run_cancelled` 或轮询快照补发。
- `apps/backend/app/services/exploration/event_bus.py`
  - 维持运行时订阅，不承担展示契约转换。

前端当前入口：

- `apps/frontend/src/app/(main)/projects/[projectId]/exploration/[runId]/page.tsx`
  - `parseStreamEvent(...)` 解析 SSE。
  - `mergeMonitorEvent(...)` 合并实时事件到 `monitor`。
  - `monitorTimelineEvent(...)` 将 SSE 事件转为 `ExplorationMonitorEvent`。
  - `buildReadableExecutionCards(...)` 已有本地可读化雏形，能够过滤部分 stream 事件并合并工具 start/end。
  - `readableToolCardFromEvent(...)` 已支持导航、点击、快照、产物、todo、URL 记录，但 `read_file` 当前仍落到通用 debug 卡，必须改为 `file_read` 一等卡。
  - `ExplorationModuleProgressPanel(...)` 当前布局更接近“左模块索引、右实时流”，需要调整为“左主要信息、右实时动作”。
  - `ExplorationRealtimeStreamPanel(...)` 当前内部同时展示概览和动作列表；改造后右侧只保留实时动作概览与动作列表，任务/产物/模块结果迁到左侧主体。

本次 spec 的实现必须基于这些现有函数改造，不新增并行事件通道，不绕开现有 SSE endpoint。

## 目标

1. 主执行流默认展示人类可读卡片，不展示原始 JSON、Python repr 或 LangChain message 对象。
2. 将多条底层事件合并为一个业务动作卡片，例如 `on_tool_start` + `on_tool_end` 合并为“点击元素”。
3. 高频 stream 和 middleware 事件默认过滤，不进入主执行流。
4. 所有卡片保留“原始事件”折叠区，用于排障。
5. 错误卡默认展开，并用中文解释影响和建议。
6. 前端使用两栏布局：左侧展示主要信息，右侧只展示实时动作。
7. `read_file`、`write_todos` 与浏览器工具一样进入右侧实时动作流，不降级为纯调试事件。
8. 后端主 SSE 输出最小可读事件 payload；无用内容字段必须删除，原始事件继续落 `events.jsonl` 并在详情调试区可查。
9. 实现时复用现有 SSE 路径、`event_bus` 和前端详情页组件边界，不新造一套运行态接口。

## 非目标

- 不改变探索执行逻辑。
- 不重写 LangGraph / DeepAgents 事件协议。
- 不把前端变成完整状态机。
- 不要求第一版准确恢复每个模型 token 或完整思维链。
- 不在主视图展示全部 5596 条原始事件。
- 不用原始日志替代操作日志或调试文件。
- 不展示真实模型隐藏推理链；“模型思考”只表示可展示的模型意图、工具决策或摘要。
- 不让前端通过 CSS 隐藏无用字段来伪装契约清理；主 SSE payload 中无用字段必须在后端转换层删除。

## 推荐方案

采用“左侧主信息、右侧实时动作、原文折叠、事件合并”的展示模型。

```text
页面探索详情 / 探索概览
  左侧窄栏：主要信息
    顶部状态与目标
    探索范围与入口
    错误/阻塞摘要
    页面产物与模块进度
    最终总结

  右侧宽栏：实时动作
    当前动作
    模型思考
    工具调用
    read_file 文件读取
    write_todos 计划更新
    浏览器动作
    产物写入
    调试事件折叠区
```

左侧回答“这次探索是什么、现在结果如何、产出了什么”；右侧回答“Agent 此刻做了哪些动作”。右侧是主要观察区域，主列表只展示“人类理解单元”，不是底层事件列表。

## 两栏职责

### 左侧：主要信息

左侧是窄摘要栏，承载稳定信息和探索结果摘要。

显示内容：

- 任务标题、状态、目标、入口、范围、上限。
- 探索模块进度和页面产物统计。
- 最近错误或阻塞摘要。
- 已发现页面、已写入产物、最终总结。
- 报告和产物入口。

左侧不展示逐条实时工具日志，不滚动追随最新事件。

左侧组件职责建议：

- 从 `run`、`detail`、`monitor.steps`、`monitor.events` 和可读卡片聚合信息。
- 使用稳定区块承载任务状态、模块进度、页面产物、错误/阻塞和最终总结。
- 可以展示“当前动作摘要”，但只能是聚合摘要，不渲染动作卡列表。

### 右侧：实时动作

右侧是宽运行流，只展示实时动作，不承载最终结果说明。

显示内容：

- 当前动作摘要。
- 模型思考卡。
- 工具调用卡。
- `read_file` 文件读取卡。
- `write_todos` 计划更新卡。
- 浏览器导航、点击、快照、元素提取卡。
- 写产物、记录 URL、错误卡。

右侧不重复展示左侧已有的完整任务信息、模块树、报告正文和产物列表。

右侧组件职责建议：

- 只接收 `ReadableExecutionCard[]`、运行状态和动作统计。
- 不直接读取报告正文、不渲染模块树、不展示页面产物列表。
- 对历史详情中的旧 `agent_stream_event` 使用本地解析兜底；对新 SSE 优先使用后端 `display`。

布局建议：

```text
lg:grid-cols-[360px_minmax(0,1fr)]
```

窄屏下上下堆叠：左侧主要信息在前，右侧实时动作在后。

## 左侧主要信息

位置：探索概览左侧窄栏顶部，始终可见或位于左栏首屏。

显示内容：

```text
探索中 / 已完成 / 已失败
目标：工作台
入口：https://www.cybotstar.cn/agentStore
关键动作：导航 46 次 · 点击 43 次 · 快照 73 次 · 写产物 31 次
最后状态：429 配额限制，探索中断
```

字段来源：

- `run.status`
- `run.goal`
- `run.scope`
- `run.environment_site_url`
- 由可读事件聚合出的工具计数
- 最近错误事件或最终状态事件

展示规则：

- 状态使用 `StatusBadge`。
- 工具计数使用紧凑 chip。
- 错误状态显示为红色提示行。
- 正常运行时显示当前动作摘要。
- 主要信息区只展示聚合结果，不追加逐条动作卡。

## 右侧实时动作条

位置：探索概览右侧宽栏。

显示内容：

```text
实时动作
当前：读取页面探索规则
读文件 2 · 更新计划 3 · 导航 4 · 点击 1 · 快照 4

[动作卡]
[动作卡]
[动作卡]
```

展示规则：

- 右侧列表使用内部滚动，避免事件增长撑高页面。
- 运行中的动作卡默认展开。
- 已完成动作卡默认收起关键字段，仍能一眼看到结果。
- 错误卡默认展开。
- 原始事件只在单卡折叠区展示。

## 卡片通用结构

所有主卡片统一三层：

```text
[图标] 标题                         [状态 Badge] [时间]
一句话摘要
关键字段区
[展开：原始事件 / 输入输出 / 调试信息]
```

字段区规则：

- 只展示存在且有意义的字段。
- URL 默认显示 path + 关键 query，完整 URL 放到 title 或展开区。
- 长文本最多 2 行，展开后再显示更多。
- 主 SSE 不携带完整原始 payload；折叠区通过 `debug_ref` 关联 `events.jsonl` 中的压缩原始事件，或使用详情接口返回的有限 `raw_events`。

## 卡片类型

### 1. 任务开始卡

适用事件：

- `run_started`
- `planning_completed`
- `agent_step_started`

显示内容：

```text
页面探索开始
目标：探索 https://www.cybotstar.cn/agentStore
范围：工作台
上限：最多 50 个页面
策略：使用浏览器工具探索页面并生成页面事实
时间：2026-06-30 17:10:39
```

展示方式：

- 普通信息卡。
- 默认展开。
- 不展示原始 message 对象。

### 2. 模型分析卡

适用事件：

- `on_chat_model_end ChatOpenAI`
- `on_chain_end model`

进入主视图条件：

- `output` 有可读文本；或
- `response_metadata.finish_reason` 为 `tool_calls`；或
- 能从 output 中识别到下一步工具调用。

显示内容：

```text
模型分析
状态：完成
模型：MiniMax-M3
意图：继续检查智能体设置页的资源配置、实时互动配置等标签页
下一步：调用 playwright_navigate_tool / playwright_snap_tool
```

提取规则：

- 从 `response_metadata.model_name` 提取模型名。
- 从 `<think>...</think>` 或模型自然语言输出中提取一句意图摘要。
- 若 `content` 为空但有 `tool_calls`，摘要为“模型请求工具调用，准备继续执行页面探索”。
- 不在主视图展示 `Command(update=...)`。

折叠区显示：

- 原始 input。
- 原始 output。
- tool calls 详情。

### 3. 导航卡

适用工具：

- `playwright_navigate_tool`

合并规则：

- 同一 `run_id` 的 `on_tool_start` 与 `on_tool_end/on_tool_error` 合并为一张卡。
- start 到达时显示运行中。
- end 到达时更新为成功或失败。

显示内容：

```text
打开页面
目标 URL：/botSetting?id=18922&tab=2
结果：成功
当前页面：百融百工
耗时：4.1s
```

失败内容：

```text
打开页面失败
目标 URL：...
原因：timeout / 访问失败 / 认证跳转
```

字段来源：

- input JSON 的 `url`
- output content JSON 的 `url`、`success`、`error`
- start/end 时间差

### 4. 点击卡

适用工具：

- `playwright_click_tool`

显示内容：

```text
点击元素
目标：基础配置 / 资源配置 / 高级配置 / 实时互动配置
定位器：button-基础配置-资源配置-高级配置-实时互动配置-003
结果：成功
```

失败内容：

```text
点击失败
目标：对话历史
定位器：button-对话历史-028
原因：元素引用已失效，当前页面快照中找不到该元素
建议：重新采集页面快照后再点击
```

提取规则：

- input JSON 的 `locator` 是主要字段。
- 若 locator 形如 `button-基础配置-资源配置-高级配置-实时互动配置-003`，展示目标时去掉类型和尾号，使用 ` / ` 连接中文片段。
- output content JSON 的 `success` 判断状态。
- `stale_ref` 或 `Unknown element id` 统一解释为“元素引用已失效”。

### 5. 页面快照卡

适用工具：

- `playwright_snap_tool`

显示内容：

```text
采集页面快照
页面：百融百工
URL：/botSetting?id=18922&tab=2
发现元素：按钮 12 · 输入框 3 · 链接 5
关键元素：历史版本、基础配置、资源配置、实时互动配置
结果：成功
```

字段来源：

- output content JSON 的 `url`
- output content JSON 的 `title`
- output content JSON 的 `elements`

元素统计规则：

- 按 `role` 聚合。
- 常见 role 中文名：
  - `button`: 按钮
  - `link`: 链接
  - `textbox`: 输入框
  - `checkbox`: 复选框
  - `tab`: 标签
- 关键元素最多展示 5 个，优先取 visible 且有 `name/text` 的元素。
- 完整元素列表只在展开区展示。

### 6. 写入产物卡

适用工具：

- `write_page_artifact_tool`

显示内容：

```text
写入页面事实
页面：智能体设置 / 资源配置
产物：page-xxx.yaml
包含：页面结构、元素定位器、操作路径
结果：成功
```

字段来源：

- input JSON 的 page title、url、artifact path 等字段。
- output content 的 success、path、error。

展示规则：

- 成功写入工具调用不等于最终登记成功。
- 最终总结卡必须结合 `summary.yaml` / run detail 的页面产物数展示最终产物结果。

### 7. 探索计划更新卡

适用工具：

- `write_todos`

显示内容：

```text
探索计划更新
当前进行：Navigate to agentStore and take initial snapshot
待处理：
1. Identify workspace main navigation
2. Explore key workspace pages
3. Capture page artifacts
```

展示规则：

- 进入右侧实时动作流。
- 多次 todo 更新可合并为最近一张，也可以按时间展示最近 3 次；默认推荐合并为最近一张，减少右侧刷屏。
- 运行中默认展开，已完成默认折叠。
- 如果没有中文摘要，不强制翻译任务内容。

### 8. 已探索 URL 更新卡

适用工具：

- `update_explored_url_tool`

显示内容：

```text
记录已探索页面
URL：/workspace
状态：已访问
```

展示规则：

- 默认轻量卡。
- 可与导航卡相邻展示。
- 如果该事件与前一个导航目标相同，可合并到导航卡的元信息里。

### 9. 技能/文件读取卡

适用工具：

- `read_file`

展示策略：

- 进入右侧实时动作流。
- 作为一等工具卡展示，不隐藏到调试事件。
- 只展示文件路径、读取目的、结果摘要，不在主内容铺开完整文件内容。

显示内容：

```text
读取文件
文件：app/agents/page_exploration/skills/page_explorer/SKILL.md
目的：加载页面探索规则
结果：完成
```

展示规则：

- 文件路径使用等宽字体，长路径中间截断。
- 输出内容最多展示 1-2 行摘要，完整 output 放原始事件折叠区。
- 读取技能文件时标题可显示为“加载探索规则”。
- 读取普通文件时标题显示为“读取文件”。

### 10. 错误卡

适用事件：

- `on_tool_error`
- `agent_step_failed`
- `run_failed`
- output content JSON 中 `success=false`
- output content JSON 中存在 `error`

显示内容：

```text
探索中断
原因：模型配额限制
详情：5 小时窗口内的配额已用完，501/500
影响：探索未完成，最终页面产物数为 0
建议：更换模型、等待配额恢复，或降低最大页面数后重试
```

错误解释规则：

- `rate_limit_exceeded` / `429`：模型配额限制。
- `stale_ref` / `Unknown element id`：元素引用已失效。
- `timeout`：操作超时。
- `Not yet implemented`：工具未实现或不可用。
- 其他错误保留原始错误摘要。

展示规则：

- 默认展开。
- 在列表中保持原发生位置。
- 顶部总览条同步显示最后错误摘要。

### 11. 最终总结卡

适用事件：

- `run_completed`
- `run_failed`
- `agent_step_completed`
- `agent_step_failed`
- 历史详情快照加载完成后补充生成

显示内容：

```text
探索结束：失败
入口：agentStore
范围：工作台
执行概况：导航 46 次，点击 43 次，快照 73 次，写产物 31 次
已访问重点页面：agentStore、workspace、botSetting、agreement、privacyPolicy
产物结果：页面产物数 0
失败原因：模型 429 配额限制
```

字段来源：

- `monitor.events`
- `run.result_summary`
- `streamDetail.modules`
- `summary.yaml` / report 中的页面产物数

展示规则：

- 成功时显示完成成果。
- 失败时显示失败原因、影响范围和建议。
- 如果工具执行过但最终产物为 0，要明确写出。

## 事件过滤规则

默认进入右侧实时动作流：

- `agent_step_started`
- `agent_step_completed`
- `agent_step_failed`
- `run_started`
- `run_completed`
- `run_failed`
- `on_chat_model_end`
- `on_tool_start`
- `on_tool_end`
- `on_tool_error`

其中 `read_file`、`write_todos`、`write_page_artifact_tool`、`update_explored_url_tool`、浏览器工具都属于主动作工具，不能因为不是浏览器动作而隐藏。

默认隐藏到调试层：

- `on_chat_model_stream`
- `on_chain_stream`
- `on_chain_start LangGraph`
- `on_chain_end LangGraph`
- `TodoListMiddleware.*`
- `SkillsMiddleware.*`
- `PatchToolCallsMiddleware.*`
- `on_chain_start/end tools`，除非无法匹配到 tool start/end
- `on_chain_start/end model` 的纯原始对象事件，除非能提取模型意图或工具调用

过滤后的事件不丢弃，只是不在主列表默认显示。

## 事件合并规则

### 工具调用合并

以 `payload.run_id` 为 key 合并：

```text
on_tool_start -> running card
on_tool_end   -> update card to completed
on_tool_error -> update card to failed
```

主动作卡保留字段：

- 工具调用关联 id
- 必要 input 摘要
- 必要 output 摘要
- 必要 error 摘要
- started_at
- completed_at
- duration_ms
- debug_ref

主动作卡不保留完整 input/output 对象，不传 LangChain message repr、response metadata、token stream、完整文件内容或大段工具输出。

### chain tools 兜底

如果存在 `on_chain_start tools` / `on_chain_end tools`，但没有匹配到 `on_tool_*`：

- 尝试解析 input 中的 tool call。
- 生成“工具调用”通用卡。
- 默认折叠。

### 模型回合合并

以相邻 `on_chat_model_start` 到 `on_chat_model_end` 为一个模型回合。

主卡只使用 end 事件生成。

如果 `on_chain_end model` 与前一个 `on_chat_model_end` 内容重复，只保留一张模型分析卡，并把 `on_chain_end model` 放入 raw_events。

## 数据结构

新增前端内部视图模型：

```ts
type ReadableExecutionCardKind =
  | "run_start"
  | "model_analysis"
  | "navigate"
  | "click"
  | "snapshot"
  | "file_read"
  | "artifact_write"
  | "todo_update"
  | "url_record"
  | "error"
  | "run_summary"
  | "debug";

type ReadableExecutionCard = {
  id: string;
  kind: ReadableExecutionCardKind;
  title: string;
  summary: string;
  status: AgentPlanStatus;
  occurred_at: string;
  completed_at?: string;
  duration_ms?: number | null;
  fields: Array<{
    label: string;
    value: string;
    mono?: boolean;
    tone?: "default" | "success" | "warning" | "danger";
  }>;
  chips?: string[];
  debug_ref?: {
    event_log_id?: string;
    raw_event_ids?: string[];
  };
  raw_events?: ExplorationMonitorEvent[];
  defaultExpanded?: boolean;
};
```

建议新增转换函数：

```ts
function buildReadableExecutionCards(
  events: ExplorationMonitorEvent[],
  detail: ExplorationRunDetail | null,
  run: ExplorationRun | null,
): ReadableExecutionCard[];
```

该函数是唯一负责过滤、合并、摘要提取的地方。

前端需要同时支持两类输入：

1. 新后端可读事件：事件顶层带 `display`，前端直接转为 `ReadableExecutionCard`，只补充状态、时间、折叠和排序。
2. 历史/旧事件：`agent_stream_event` 仍可能只有 `payload.event/name/input/output/error`，前端继续使用本地解析兜底。

新事件优先级：

```ts
const display = event.display ?? event.payload?.display;
if (display) {
  return readableCardFromDisplay(event, display);
}
return readableCardFromLegacyPayload(event);
```

实现要求：

- `ReadableExecutionCardKind` 必须包含 `"file_read"`。
- `read_file` 不允许再映射为 `"debug"`。
- `write_todos` 不允许只进入原始事件折叠区。
- `raw_events` 在新事件路径上是可选调试数据，不能成为主 UI 依赖。
- `debug_ref` 是新事件路径的首选调试入口。

## 后端事件契约

后端主 SSE 从“原始 LangChain 事件”升级为“最小可读事件”。原始事件仍写入 `events.jsonl`，但主 SSE 只发布思考、工具、文件读取、计划更新、错误和总结。

后端转换落点：

- 在 `_invoke_agent_with_realtime_events(...)` 循环内，继续先写 `events.jsonl`。
- 将 `_publish_agent_stream_event(...)` 改为只发布可读事件，或拆出 `_agent_event_to_readable_stream_event(...)` 后由 `_publish_agent_stream_event(...)` 发布转换结果。
- `_compact_agent_event(...)` 继续服务 `events.jsonl`，可以保留压缩后的 input/output/error，供调试关联。
- `stream_exploration_progress(...)` 不需要新增 endpoint，只负责转发新事件。
- `event_bus` 只传输已经裁剪后的主 SSE 事件，不承载原始 LangChain payload。

主 SSE payload 必须删除无用内容字段，只保留 UI 展示和事件合并需要的字段：

```json
{
  "event_id": "evt-live-000123",
  "run_id": "run-1",
  "type": "agent_tool_completed",
  "occurred_at": "2026-07-01T10:48:39Z",
  "payload": {
    "step_id": "agent-tool-tool-run-1",
    "tool_name": "read_file",
    "status": "completed",
    "started_at": "2026-07-01T10:48:38Z",
    "completed_at": "2026-07-01T10:48:39Z",
    "duration_ms": 810,
    "debug_ref": {
      "event_log_id": "evt-000123"
    }
  },
  "display": {
    "kind": "file_read",
    "title": "读取文件",
    "summary": "读取页面探索规则",
    "fields": [
      {"label": "文件", "value": "app/agents/page_exploration/skills/page_explorer/SKILL.md", "mono": true},
      {"label": "结果", "value": "完成", "tone": "success"}
    ]
  }
}
```

前端优先使用 `display`，不存在时使用本地解析兜底。为了兼容旧实现，也允许短期从 `payload.display` 读取，但新契约推荐 `display` 位于事件顶层。

主 SSE 必须删除的字段：

- `input` 完整对象。
- `output` 完整对象。
- `messages`、`AIMessage(...)`、`HumanMessage(...)`、`Command(update=...)`。
- `response_metadata`、token usage、headers 等模型技术字段。
- `raw_output`、完整文件内容、完整页面快照。
- middleware 内部状态。
- 空字符串、空数组、空对象、前端不展示也不参与合并的字段。

主 SSE 允许保留的字段：

- `event_id`、`run_id`、`type`、`occurred_at`。
- `step_id`、`tool_name`、`status`、`started_at`、`completed_at`、`duration_ms`。
- `display.kind`、`display.title`、`display.summary`、`display.fields`、`display.chips`。
- `debug_ref.event_log_id` 或有限 `raw_event_ids`。
- 错误事件的短错误码、短错误摘要和建议。

注意：

- 后端仍要保留原始事件，但只能落 `events.jsonl` 或详情调试数据，不进入主 SSE。
- `display` 是展示提示，不是业务状态源。
- 不允许后端只发纯文本导致调试信息丢失。
- `read_file` 和 `write_todos` 必须生成 `display`，避免前端只能展示原始 JSON。

推荐后端事件分工：

```text
agent raw event
  -> events.jsonl: compact raw event
  -> main SSE: minimal readable display event or None
```

主 SSE 推荐事件类型：

```text
agent_thought
agent_tool_started
agent_tool_completed
agent_tool_failed
agent_plan_updated
agent_error
agent_summary
```

### 后端可读事件映射

| 原始事件 | 条件 | 主 SSE 类型 | display.kind | 说明 |
| --- | --- | --- | --- | --- |
| `on_chat_model_end` | 有可读意图、工具调用或错误 | `agent_thought` | `model_analysis` | 只输出模型名、意图、下一步工具摘要 |
| `on_tool_start` + `read_file` | 总是 | `agent_tool_started` | `file_read` | 展示文件路径和读取目的，不传完整文件内容 |
| `on_tool_end` + `read_file` | 总是 | `agent_tool_completed` | `file_read` | 展示完成状态、耗时和 `debug_ref` |
| `on_tool_start/end` + `write_todos` | 总是 | `agent_plan_updated` | `todo_update` | 展示当前进行和待处理摘要 |
| `on_tool_start/end` + 浏览器工具 | 总是 | `agent_tool_started/completed` | `navigate` / `click` / `snapshot` | 展示动作目标、结果和耗时 |
| `on_tool_start/end` + `write_page_artifact_tool` | 总是 | `agent_tool_started/completed` | `artifact_write` | 展示页面、产物路径和结果 |
| `on_tool_start/end` + `update_explored_url_tool` | 总是 | `agent_tool_started/completed` | `url_record` | 展示 URL 和访问状态 |
| `on_tool_error` | 总是 | `agent_tool_failed` | `error` 或对应工具 kind | 错误卡默认展开 |
| `agent_step_failed` / `run_failed` | 总是 | `agent_error` | `error` | 展示原因、影响、建议 |
| `agent_step_completed` / `run_completed` | 总是 | `agent_summary` | `run_summary` | 展示执行概况和最终产物结果 |

### 字段删除策略

实现时应按白名单构造主 SSE，而不是从原始事件复制后再删除。推荐结构：

```python
readable_event = {
    "event_id": live_event_id,
    "run_id": run_id,
    "type": stream_type,
    "occurred_at": occurred_at,
    "payload": compact_payload,
    "display": display,
}
```

`compact_payload` 只允许包含：

- `step_id`
- `tool_name`
- `status`
- `started_at`
- `completed_at`
- `duration_ms`
- `debug_ref`
- `error_code`
- `error_summary`
- `suggestion`

任何未列入白名单的字段默认不进入主 SSE。尤其不能保留 `input`、`output`、`messages`、`response_metadata`、`raw_output`、`metadata`、`kwargs`、`serialized`、`parent_ids`、`tags`、完整文件内容、完整页面 elements 列表。

对于页面快照，主 SSE 只能保留聚合结果，例如：

```json
{
  "display": {
    "kind": "snapshot",
    "title": "采集页面快照",
    "summary": "采集智能体设置的页面结构",
    "fields": [
      {"label": "页面", "value": "智能体设置"},
      {"label": "URL", "value": "/botSetting?id=18922&tab=2", "mono": true},
      {"label": "发现元素", "value": "按钮 12 · 输入框 3 · 链接 5"},
      {"label": "关键元素", "value": "历史版本、基础配置、资源配置、实时互动配置"}
    ]
  }
}
```

完整 elements 只能通过 `events.jsonl`、详情调试数据或后续专门调试接口查看。

### 兼容策略

- 新运行：主 SSE 发布新可读事件。
- 旧历史：详情页继续从历史 `events.jsonl` / `monitor.events` 中解析旧 `agent_stream_event`。
- 短期前端兼容 `payload.display`，但后端新事件只写顶层 `display`。
- 若新后端无法从某个事件提取可读摘要，主 SSE 可以跳过该事件，但必须已经写入 `events.jsonl`。
- 跳过事件不能影响 `run_failed`、`agent_error`、`agent_summary` 等终态事件发布。

## UI 规范

视觉方向：

- 这是运行观察面板，不是终端日志。
- 主色保持当前蓝色系统，但错误、警告、成功状态要清晰分层。
- 卡片密度适中，适合持续扫描。

组件建议：

- 工具卡使用 lucide 图标：
  - 导航：`ExternalLink` 或 `Navigation`
  - 点击：`MousePointerClick`
  - 快照：`ScanSearch` 或 `Camera`
  - 写产物：`FileCheck`
  - 模型：`Brain` 或 `Sparkles`
  - 错误：`CircleAlert`
- 卡片圆角使用现有 `rounded-md`。
- 不使用大面积代码块作为主内容。
- 原始事件折叠区使用 `font-mono text-xs`，限制高度。

布局：

```text
探索概览
  [左侧主要信息 360px]
    状态与目标
    模块进度
    页面产物
    错误/阻塞
    最终总结

  [右侧实时动作 minmax(0,1fr)]
    当前动作
    动作统计
    滚动动作列表
      思考卡
      文件读取卡
      计划更新卡
      工具卡
      错误卡
```

右侧列表应有稳定高度和内部滚动，避免事件增长撑高页面。左侧保持页面主体正常滚动。

### 前端设计细则

- 桌面端：外层使用 `lg:grid-cols-[360px_minmax(0,1fr)]`，左侧固定窄栏，右侧 `min-w-0` 吃掉剩余空间。
- 右侧卡片列表使用 `overflow-y-auto` 和稳定高度，跟随最新动作时不影响左侧滚动位置。
- 移动端：左侧在上，右侧在下；右侧标题仍为“实时动作”，不使用“实时执行流”来暗示原始日志。
- 左侧区块不套多层卡片；模块进度、页面产物、错误摘要是同级区块。
- 右侧动作卡可使用卡片，因为它们是重复项；卡片内不再嵌套卡片。
- 主列表不渲染大段 `<pre>`；只有折叠调试区允许使用 `font-mono text-xs`。
- 右侧标题文案统一为“实时动作”，副文案为“只显示思考、工具调用和关键结果”。

## 空状态

未开始：

```text
左侧：任务尚未开始，开始后会显示模块进度和产物结果。
右侧：开始探索后会显示实时动作。
```

等待事件：

```text
右侧：已连接实时流，等待后端推送动作。
```

仅有调试事件：

```text
右侧：暂无可展示的实时动作。可展开调试事件查看原始流。
```

历史任务无事件：

```text
未找到实时事件记录。可查看探索报告和页面产物。
```

## 验证方案

### 单元测试

后端测试建议放在 `apps/backend/tests/`，覆盖可读事件转换函数或 `_publish_agent_stream_event(...)` 的发布结果。

前端测试建议继续使用现有 exploration detail contract 测试文件，或将 `buildReadableExecutionCards` 可测逻辑抽出到相邻 helper 后测试。

为 `buildReadableExecutionCards` 增加测试：

1. 过滤 `on_chat_model_stream`。
2. 合并 `on_tool_start` + `on_tool_end` 为一张导航卡。
3. `playwright_click_tool` 的 `stale_ref` 错误生成“元素引用已失效”。
4. `playwright_snap_tool` 从 elements 统计按钮、链接、输入框数量。
5. `on_chat_model_end` 从 `response_metadata` 提取模型名。
6. `429 rate_limit_exceeded` 生成模型配额限制错误卡。
7. `write_todos` 多次更新只保留最新计划卡。
8. `read_file` 生成文件读取卡，且不进入隐藏调试事件计数。
9. 主 SSE 可读事件不包含完整 `input` / `output` / `messages` / `response_metadata`。
10. 原始事件通过 `debug_ref` 或详情 `raw_events` 保留调试入口。
11. 后端对 `playwright_snap_tool` 只输出元素统计和关键元素，不输出完整 elements。
12. 后端对 `read_file` 只输出文件路径、目的和结果，不输出完整文件内容。
13. 后端对无法识别的 middleware / stream 事件返回 `None` 或跳过发布。

### 契约测试

1. 主执行流不直接渲染 `Command(update=`。
2. 主执行流不直接渲染 `HumanMessage(`。
3. 主执行流不直接渲染 `AIMessage(`。
4. 原始事件折叠区展开后可以看到原始 payload。
5. 错误卡默认展开。
6. 探索概览为两栏布局，左侧展示主要信息，右侧展示实时动作。
7. 右侧实时动作包含 `read_file` 和 `write_todos`。
8. 主 SSE payload 不包含前端不展示、也不参与合并的冗余字段。
9. 新事件顶层 `display.kind` 可直接驱动右侧动作卡。
10. 兼容旧事件时，`payload.display` 仍可被读取，但测试名称应标明这是兼容路径。

### 手动验证

使用样本日志或重新运行探索任务：

1. 确认 5596 条原始事件不会全部成为主卡片。
2. 确认左侧展示任务目标、模块进度、产物结果和最终总结。
3. 确认右侧只展示实时动作，不重复展示模块树和报告正文。
4. 确认导航、点击、快照、读文件、更新计划、写产物卡片能连续展示探索过程。
5. 确认点击失败时显示“元素引用已失效”。
6. 确认 429 失败时显示配额限制、影响和建议。
7. 确认最终总结显示页面产物数为 0。
8. 确认原始事件仍可展开查看。

## 实施顺序

1. 后端先写可读事件转换测试，锁定 `read_file`、`write_todos`、浏览器工具、错误事件和字段白名单。
2. 后端增加可读事件转换层，主 SSE 输出最小 `display` 事件，原始事件继续写 `events.jsonl`。
3. 后端按白名单构造主 SSE payload，删除不展示、不合并、不排障定位的冗余内容字段。
4. 后端为 `read_file`、`write_todos`、浏览器工具、产物工具和错误事件生成 display。
5. 前端先写/更新 `buildReadableExecutionCards` 测试，覆盖顶层 `display`、`payload.display` 兼容、旧事件解析和 `file_read`。
6. 前端更新 `ReadableExecutionCard` 类型和转换函数，优先使用顶层 `display`，短期兼容 `payload.display`。
7. 前端实现工具调用合并和噪声事件过滤兜底，确保旧历史运行仍可读。
8. 前端将探索概览改为左侧主要信息、右侧实时动作两栏。
9. 前端将右侧标题、统计、列表收敛为实时动作，不再重复模块树、报告正文和产物列表。
10. 前端为原始事件增加折叠区，通过 `debug_ref` 或详情 `raw_events` 关联。
11. 增加单元测试、契约测试和样本日志回放验证。
12. 使用真实探索或样本日志确认主 SSE 不再输出无用内容字段。

## 验收标准

- 主执行流默认不出现 `Command(update=...)`、`HumanMessage(...)`、`AIMessage(...)`。
- 高频 stream 事件不进入主列表。
- 探索概览左侧展示主要信息，右侧只展示实时动作。
- `read_file` 和 `write_todos` 在右侧作为一等动作卡展示。
- 工具 start/end/error 能合并为单张卡片。
- 每张卡片默认显示标题、状态、时间、摘要和关键字段。
- 错误卡用中文说明原因、影响和建议。
- 最终总结能显示执行概况和产物结果。
- 主 SSE 已删除无用内容字段，不携带完整 input/output/messages/response_metadata/raw_output。
- 原始事件未丢失，可通过 `events.jsonl`、`debug_ref` 或详情调试区查看。
- 不新增新的接口路径；现有 SSE payload 增强 `display` 后即可完成第一版改造。
- 后端实现不是“照旧推原始 payload，前端隐藏字段”；必须由后端转换层产出白名单事件。
- 旧历史运行仍能通过前端本地解析看到可读动作，至少不比改造前更差。
- 若主 SSE 中出现未列入白名单的冗余字段，视为验收失败。

## Spec 自检

- 无待定项：本 spec 不包含 TBD / TODO。
- 范围收敛：只改页面探索详情实时流的后端事件契约和前端展示，不改变探索执行逻辑。
- 兼容明确：新运行走顶层 `display`，旧历史走本地解析兜底。
- 字段删除明确：主 SSE 使用白名单构造，不能通过前端隐藏无用字段替代。
- UI 边界明确：左侧主要信息，右侧只显示实时动作。
