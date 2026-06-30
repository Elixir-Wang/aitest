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

本规范定义一次“执行流可读化”改造：主视图展示关键摘要，原始事件只保留在折叠调试层。

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

## 目标

1. 主执行流默认展示人类可读卡片，不展示原始 JSON、Python repr 或 LangChain message 对象。
2. 将多条底层事件合并为一个业务动作卡片，例如 `on_tool_start` + `on_tool_end` 合并为“点击元素”。
3. 高频 stream 和 middleware 事件默认过滤，不进入主执行流。
4. 所有卡片保留“原始事件”折叠区，用于排障。
5. 错误卡默认展开，并用中文解释影响和建议。
6. 不新增后端接口；优先复用现有 SSE payload。后续可由后端补充 `display` 字段增强摘要。

## 非目标

- 不改变探索执行逻辑。
- 不重写 LangGraph / DeepAgents 事件协议。
- 不把前端变成完整状态机。
- 不要求第一版准确恢复每个模型 token 或完整思维链。
- 不在主视图展示全部 5596 条原始事件。
- 不用原始日志替代操作日志或调试文件。

## 推荐方案

采用“摘要优先、原文折叠、事件合并”的展示模型。

```text
实时执行流
  顶部总览条
  错误/阻塞摘要
  模型分析卡
  浏览器动作卡
  页面快照卡
  产物写入卡
  计划更新卡
  最终总结卡
  调试事件抽屉
```

主列表只展示“人类理解单元”，不是底层事件列表。

## 顶部总览条

位置：实时执行流面板顶部，始终可见。

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
- 原始 payload 放在折叠区，使用等宽字体和 `max-height` 滚动。

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

- 多次 todo 更新合并，只保留最近一张。
- 默认折叠。
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

- 默认不进入主执行流。
- 进入“调试事件”分组。

如果必须展示，使用摘要：

```text
加载探索规则
内容：页面探索策略、定位器最佳实践
结果：完成
```

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

默认进入主视图：

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

保留字段：

- start input
- end output
- error
- started_at
- completed_at
- duration_ms
- raw_events[]

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

新增前端内部视图模型，不要求后端接口变更：

```ts
type ReadableExecutionCardKind =
  | "run_start"
  | "model_analysis"
  | "navigate"
  | "click"
  | "snapshot"
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
  raw_events: ExplorationMonitorEvent[];
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

## 后端增强建议

第一版不新增接口。后续可在 SSE payload 中增加可选字段：

```json
{
  "display": {
    "title": "模型分析完成",
    "summary": "模型请求工具调用，准备继续探索页面",
    "fields": [
      {"label": "模型", "value": "MiniMax-M3"},
      {"label": "下一步", "value": "playwright_snap_tool"}
    ]
  }
}
```

前端优先使用 `payload.display`，不存在时使用本地解析兜底。

注意：

- 后端仍要保留原始 payload。
- `display` 是展示提示，不是业务状态源。
- 不允许后端只发纯文本导致调试信息丢失。

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
实时执行流
  [总览条]
  [错误摘要，可选]
  [滚动列表]
    卡片
    卡片
    卡片
```

列表应有稳定高度和内部滚动，避免事件增长撑高页面。

## 空状态

未开始：

```text
开始探索后会在这里显示执行过程。
```

等待事件：

```text
已连接实时流，等待后端推送探索事件。
```

仅有调试事件：

```text
暂无可展示的关键动作。可展开调试事件查看原始流。
```

历史任务无事件：

```text
未找到实时事件记录。可查看探索报告和页面产物。
```

## 验证方案

### 单元测试

为 `buildReadableExecutionCards` 增加测试：

1. 过滤 `on_chat_model_stream`。
2. 合并 `on_tool_start` + `on_tool_end` 为一张导航卡。
3. `playwright_click_tool` 的 `stale_ref` 错误生成“元素引用已失效”。
4. `playwright_snap_tool` 从 elements 统计按钮、链接、输入框数量。
5. `on_chat_model_end` 从 `response_metadata` 提取模型名。
6. `429 rate_limit_exceeded` 生成模型配额限制错误卡。
7. `write_todos` 多次更新只保留最新计划卡。
8. 原始事件保留在 `raw_events`。

### 契约测试

1. 主执行流不直接渲染 `Command(update=`。
2. 主执行流不直接渲染 `HumanMessage(`。
3. 主执行流不直接渲染 `AIMessage(`。
4. 原始事件折叠区展开后可以看到原始 payload。
5. 错误卡默认展开。

### 手动验证

使用样本日志或重新运行探索任务：

1. 确认 5596 条原始事件不会全部成为主卡片。
2. 确认导航、点击、快照、写产物卡片能连续展示探索过程。
3. 确认点击失败时显示“元素引用已失效”。
4. 确认 429 失败时显示配额限制、影响和建议。
5. 确认最终总结显示页面产物数为 0。
6. 确认原始事件仍可展开查看。

## 实施顺序

1. 在前端新增 `ReadableExecutionCard` 类型和转换函数。
2. 实现工具调用合并和噪声事件过滤。
3. 实现每类卡片的摘要提取函数。
4. 替换实时执行流列表渲染，改用 `ReadableExecutionCard`。
5. 为原始事件增加折叠区。
6. 增加顶部总览条。
7. 增加单元测试和契约测试。
8. 使用样本日志做回放验证。

## 验收标准

- 主执行流默认不出现 `Command(update=...)`、`HumanMessage(...)`、`AIMessage(...)`。
- 高频 stream 事件不进入主列表。
- 工具 start/end/error 能合并为单张卡片。
- 每张卡片默认显示标题、状态、时间、摘要和关键字段。
- 错误卡用中文说明原因、影响和建议。
- 最终总结能显示执行概况和产物结果。
- 原始事件未丢失，可在折叠区查看。
- 不新增后端接口也能完成第一版改造。
