# 设计方案

## 1. 方案总览

```text
性能测试配置
  ├─ transport=http ──────────────────────────────→ 既有 HTTP Locust 路径
  └─ transport=sse ─┬→ 手工配置 / 样例预览
                    └→ 真实单接口/场景步骤探测 → 脱敏事件结构 → AI 候选 → 确定性回放 → 用户确认
                                      ↓
                              SSE 帧解析 → 标准事件 → 受限匹配器
                                                 ├─ 首次命中指标记录
                                                 ├─ 完成、超时与协议状态
                                                 └─ 独立 SSE 指标聚合
                                                               ↓
                                                运行详情 / 目标判定 / 分析报告
```

设计原则：传输协议负责产生标准事件，规则只负责匹配事件，指标只负责计时和聚合。数值由确定性代码计算；用户配置不可执行代码；AI 只生成现有 Schema 约束下的候选规则；原始流内容不进入数据库或报告。

## 2. 配置契约

### 2.1 请求传输

`PerformanceRequestConfig` 新增以下受控字段，默认值保证历史记录仍按 HTTP 执行：

```json
{
  "transport": "sse",
  "sse": {
    "max_stream_seconds": 60,
    "end_rule": {
      "source": "data_text",
      "operator": "equals",
      "expected": "[DONE]"
    },
    "metrics": []
  }
}
```

- `transport`：`http` 或 `sse`，默认 `http`。
- `max_stream_seconds`：从请求开始计时的流总超时，必须小于等于既有请求超时上限。
- `end_rule`：可选。命中后自然完成当前请求；未配置时以服务器正常关闭连接为完成。
- 选择 SSE 后，系统 SHALL 在运行时加入 `Accept: text/event-stream`；用户显式设置该头时值必须兼容 SSE。

### 2.2 指标规则

每条指标定义“请求开始后首次命中条件的时刻”：

```json
{
  "id": "first_tool_call",
  "name": "首次工具调用耗时",
  "match": {
    "event_name": "message",
    "source": "data_json",
    "path": "$.choices[*].delta.tool_calls[*]",
    "operator": "exists"
  },
  "occurrence": "first",
  "missing_policy": "record_null"
}
```

- `id`：小写字母、数字和下划线组成，在一个测试中唯一；预留 `first_content` 和 `first_tool_call` 为内置模板 ID。
- `name`：用户可读名称，最多 80 字符。
- `match.event_name`：可选，精确匹配 SSE `event:`；空值表示任意事件。
- `match.source`：`data_json`、`data_text` 或 `event_name`。
- `match.path`：仅 `data_json` 可用，使用受限 JSONPath：根 `$`、对象字段、数组下标和 `[*]`；不支持递归、过滤器、脚本或函数。
- `match.operator`：`exists`、`non_empty`、`equals`、`contains`、`matches`。`matches` 使用长度和复杂度受限的正则表达式，禁止回溯风险模式。
- `match.expected`：仅 `equals`、`contains`、`matches` 必填。
- `occurrence`：一期固定为 `first`，保留字段以避免后续破坏契约。
- `missing_policy`：`record_null`、`fail_request`、`ignore`。默认 `record_null`。

一个指标规则只能在同一请求内首次命中一次。对于 `data_json`，非 JSON 的 `data:` 不匹配规则但会计入解析质量；不会直接导致失败，除非规则或测试要求 JSON。

### 2.3 性能目标

性能目标新增按指标 ID 的目标，避免为每个业务字段不断增加 Schema 字段：

```json
{
  "sse_metric_goals": [
    {"metric_id": "first_content", "percentile": "p95", "operator": "lte", "target_ms": 3000},
    {"metric_id": "first_tool_call", "percentile": "p95", "operator": "lte", "target_ms": 5000}
  ]
}
```

同一 `metric_id + percentile` 只允许一个目标。目标仅对 `matched_count > 0` 且分布可信的指标判定；没有样本时为 `not_evaluated`，不会把缺失值按 0 处理。

## 3. 标准事件和匹配器

每个已完成的 SSE 帧标准化为内部对象，内部对象不持久化：

```json
{
  "event_name": "message",
  "data_text": "{...}",
  "data_json": {"...": "..."},
  "received_after_start_ms": 812.3
}
```

解析器 SHALL 遵循 SSE 帧规范：忽略注释行；合并同一帧的多行 `data:` 并以换行连接；空行提交一帧；无 `event:` 时使用空事件名；支持 UTF-8 BOM。单帧和单流均设置大小上限，超过上限即失败并记录稳定原因。

匹配器必须先校验 `event_name`，再从 `source` 取值，最后执行路径提取和操作符。数组通配符的任一候选值命中即视为该指标命中。时间使用单调时钟，单位毫秒，不能依赖系统墙钟。

内置模板只预填规则，用户可编辑：

| 模板 | 默认规则 |
|---|---|
| 首内容 | `data_json` 的 `$.choices[*].delta.content`，`non_empty` |
| 首次工具调用 | `data_json` 的 `$.choices[*].delta.tool_calls[*]`，`exists` |

## 4. 执行与结果采集

SSE 生成脚本 SHALL 使用流式 HTTP 请求并消费至结束规则、正常 EOF、超时或失败。命中时间指标后必须继续消费流，不能因为首个指标命中主动关闭连接，否则压测会低估服务端连接与生成负载。

每次请求生成以下临时测量结果：

```json
{
  "request_outcome": "completed",
  "stream_completed_ms": 4210.6,
  "metrics": {"first_content": 540.2, "first_tool_call": null},
  "missing_metric_ids": ["first_tool_call"],
  "parse_error_count": 0
}
```

HTTP 请求自身仍按既有规则上报到 Locust。SSE 指标不得通过自定义 `events.request` 混入 Locust 聚合 CSV；运行时 SHALL 写入版本化的独立 SSE 测量摘要文件，并由 headless worker 定期/结束时读取、校验和持久化。

运行级别按指标保存：

```json
{
  "metric_id": "first_content",
  "attempt_count": 1000,
  "matched_count": 986,
  "missing_count": 14,
  "failure_count": 3,
  "average_ms": 728.4,
  "p50_ms": 640,
  "p95_ms": 1680,
  "p99_ms": 2310
}
```

分位数必须从每次匹配到的原始时间样本或可信直方图计算；不得从平均值推导。原始时间样本文件应保存于当前运行目录，使用固定上限、版本、校验和和保留策略，并随运行级联清理。

## 5. 状态、失败与数据质量

| 情况 | 请求状态 | 指标状态 |
|---|---|---|
| HTTP 非 2xx | 失败 | 无有效指标 |
| SSE 帧格式错误或 JSON 解析失败 | 继续消费，记录质量问题 | 相关 JSON 指标不匹配 |
| 超过流总超时 | 失败 | 已命中指标保留，未命中记缺失 |
| 命中结束规则 | 完成 | 未命中按 `missing_policy` 处理 |
| 正常 EOF 且未配置结束规则 | 完成 | 未命中按 `missing_policy` 处理 |
| 正常 EOF 但配置结束规则未命中 | 失败，原因 `sse_end_rule_not_matched` | 已命中指标保留 |

`record_null` 绝不增加 HTTP 失败数，例如正常回答未发起工具调用。`fail_request` 则为该次请求追加可诊断失败原因。报告数据质量必须公开 `missing_count`、解析错误数、超时数、结束规则未命中数和指标样本量。

## 6. API、预览与前端

既有创建、更新、脚本生成、确认和启动 API 复用原路由，Schema 扩展必须兼容缺省 HTTP 配置。新增只读预览接口：

```http
POST /projects/{project_id}/performance-tests/sse-rule-preview
```

请求包含一段长度受限的 SSE 样本文本和待验证的 `sse` 配置；响应返回解析后的事件摘要、每条指标首次命中事件序号/时间（样例中无时间则仅返回序号）、无效路径与无命中原因。该接口不得执行目标请求，不持久化样例内容，并对返回数据脱敏截断。

前端在选择 SSE 后展示事件指标编辑器：传输与结束规则、内置模板、指标列表、字段路径和条件编辑器、样例验证器及缺失策略。普通 HTTP 模式不显示 SSE 配置。运行详情和报告将 HTTP 指标与“SSE 事件指标”分区呈现。

### 6.1 AI 指标生成

新增项目鉴权接口：

```http
POST /projects/{project_id}/performance-tests/sse-metrics/generate
```

单接口请求使用项目内 `endpoint_id`、`api_environment_id` 和表单中尚未保存的 path、query、header、body 及最大流时长。场景请求使用 `scenario_id`、`scenario_step_id` 和环境，按当前保存快照执行赋值、条件和前置 HTTP 步骤，到目标步骤时以 `stream=True` 捕获真实 SSE。场景探测和正式 Locust 脚本沿用接口自动化的 JSON Pointer/JSONPath 输出提取兼容语义，并保留 JSON、表单、multipart、Cookie 和 Header 请求编码。两种目标都只接受成功状态、`text/event-stream` 和至少一个有效事件。探测失败返回稳定的 `PERFORMANCE_SSE_PROBE_FAILED`，不得在没有样本时调用模型或宣称已识别指标。

采集使用客户端单调时钟记录每个事件相对请求开始的接收时间，并限制事件数量、单帧大小和流时长。模型输入只保留匹配所需的事件名、事件类型、角色、内容是否非空和接收偏移；认证信息、业务标识和回答正文不得发送给模型。

AI 输出复用 `PerformanceSseConfig`，首期必须包含 `call_llm_start` 和 `first_answer` 两个首次命中指标。服务端使用与 Locust 运行时相同的受限路径和匹配语义回放真实样本，并返回每条规则的命中数、首次事件序号和样本耗时。AI 调用失败、输出不合法、缺少必需指标或回放不通过时，服务端改用基于真实样本事件类型的确定性候选并返回 warning；不得直接采用未验证的模型输出。

用户编辑候选后可以通过同一接口提交 `candidate_sse` 重新探测和回放。前端只有在 `validation.valid=true` 时才允许应用；重新生成不得直接覆盖当前已确认配置。应用操作只把候选写入现有性能测试表单，最终仍通过既有创建或更新接口保存。脚本生成阶段读取已保存配置，不再次调用模型。

## 7. 兼容性与安全

- 历史记录缺失 `transport` 时解释为 `http`，历史脚本不可变。
- 仅允许当前项目可见的测试、脚本和运行访问 SSE 样例验证与指标结果。
- AI 指标生成要求管理员身份；endpoint，或 scenario、scenario step 和 environment 必须属于当前可见项目。
- 响应事件的字段值不得写入数据库日志、失败摘要、AI 证据或前端长期状态；仅保存脱敏、截断的协议错误上下文。
- 探测响应只返回状态码、事件数、截断状态、候选配置和受控命中证据，不持久化完整 SSE 样本。
- Header、请求体和现有环境认证处理沿用当前脱敏与运行时合并规则。
- SSE 配置、脚本计划、测量摘要和计算器版本参与输入哈希/来源指纹；不同规则或口径的运行不得被当作可比较基线。

## 8. 验证策略

- 单元测试：SSE 帧解析、多行 data、事件名、UTF-8 BOM、字段路径、通配符、比较操作符、时间首次命中和超时。
- 生成脚本测试：HTTP 路径不变，SSE 路径使用流式读取且不会早停。
- 运行采集测试：独立 SSE 指标不会影响 HTTP Locust 汇总；分位数、缺失和失败口径正确。
- API/权限测试：配置校验、样例限制、无持久化、历史 HTTP 兼容和越权保护。
- AI 生成测试：当前未保存请求参数、客户端接收偏移、敏感字段脱敏、必需指标回放、无效模型输出降级和用户候选重新验证。
- 前端测试：模板填充、规则验证、无匹配反馈、窄屏编辑器与运行详情渲染。
