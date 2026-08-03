# 压测 SSE 指标 AI 生成设计规范

## 1. 目标

在新建接口压测信息时，允许用户先运行一次真实接口编排，采集 SSE 响应样本，再由 AI 基于样本生成声明式指标匹配参数。参数经程序确定性回放校验和用户确认后，保存到压测请求配置，并在生成 Locust 脚本时传入固定模板。

首期必须支持以下两个业务耗时指标：

- `call_llm_start_ms`：从客户端发起请求到首次收到 `event_type = call_llm_start` 的耗时。
- `first_answer_ms`：从客户端发起请求到首次收到 `event_type = answer` 的耗时。

系统可派生以下诊断指标，但不要求将其作为独立 SSE 匹配规则保存：

- `llm_start_to_first_answer_ms = first_answer_ms - call_llm_start_ms`。

## 2. 背景与问题

SSE 接口的业务事件结构并不统一。不同接口可能使用不同的事件名、JSON 层级、字段名和结束事件。如果仅根据接口文档或字段名称猜测 JSONPath，容易生成无法命中的压测指标。

现有性能测试模块已经具备以下能力：

- `PerformanceRequestConfig.transport` 区分 HTTP 和 SSE。
- `PerformanceSseConfig` 保存流超时、结束规则和指标规则。
- `PerformanceSseMetric` 支持首次命中语义和缺失策略。
- `PerformanceSseMatch` 支持事件名、JSONPath、文本和操作符匹配。
- Locust 固定模板可以实时解析 SSE 数据帧并记录首次命中耗时。

本功能不创建第二套 SSE 指标模型，也不让 AI 直接生成或修改任意 Python 代码。功能重点是补齐“真实采样、AI 识别、规则验证、用户确认、配置传递”的闭环。

## 3. 范围

### 3.1 范围内

- 在新建或编辑压测信息时运行一次接口编排。
- 获取状态码、响应头和标准化 SSE 事件样本。
- 将经过裁剪和脱敏的事件摘要交给 AI 分析。
- AI 生成 `request_config.sse` 候选配置。
- 程序使用采样事件回放并校验候选规则。
- 用户查看命中结果、样本耗时、置信度和警告。
- 用户确认后保存配置。
- Locust 脚本生成器复用已保存配置并记录两个首次事件耗时。
- 运行结果支持展示原始指标及派生指标。

### 3.2 范围外

- AI 生成完整 Locust Python 脚本。
- AI 执行任意 Python、JSONPath 扩展表达式或正则代码。
- 根据服务端时间戳替代客户端耗时。
- 自动修改接口编排定义。
- 首期支持同一请求内多 Agent、多模型或多轮回答的分组指标。
- 首期支持基于多个条件的复合匹配表达式。

## 4. 核心原则

### 4.1 先运行，后生成

系统必须先运行真实接口编排并获得有效 SSE 样本，AI 才能生成指标规则。没有可用样本时不得宣称已自动识别，只能提示用户重试或切换手动配置。

### 4.2 AI 只生成声明式配置

AI 输出必须符合受限 Schema，只允许描述：

- 指标 ID 和名称。
- SSE 事件名。
- 匹配来源。
- JSONPath。
- 匹配操作符和期望值。
- 首次命中语义。
- 缺失策略。
- 流结束规则。
- 生成理由和置信度。

AI 不得输出可执行代码，也不得绕过服务端 Schema 校验。

### 4.3 程序负责确定性验证

AI 输出不能直接保存。服务端必须使用同一套 SSE 解析器和匹配器回放采样事件，确认规则是否真实命中，并返回命中次数、首次命中序号和样本耗时。

### 4.4 客户端时钟是压测时间源

正式压测指标统一使用 Locust 进程中的单调时钟计算：

```python
elapsed_ms = (time.perf_counter() - request_started_at) * 1000
```

SSE 数据中的服务端 `timestamp` 仅用于样本分析和辅助排障，不作为正式压测耗时来源，避免客户端与服务端时钟偏移造成误差。

## 5. 业务时间定义

### 5.1 请求开始时间

`request_started_at` 必须在 Locust 客户端实际发起 HTTP 请求前使用 `time.perf_counter()` 记录。

### 5.2 LLM 调用开始时间

首次出现满足以下规则的 SSE 数据帧时记录：

```json
{
  "event_name": "message",
  "source": "data_json",
  "path": "$.data.event_type",
  "operator": "equals",
  "expected": "call_llm_start"
}
```

指标值为该帧到达客户端时相对 `request_started_at` 的毫秒数。

### 5.3 首次回答时间

首次出现满足以下规则的 SSE 数据帧时记录：

```json
{
  "event_name": "message",
  "source": "data_json",
  "path": "$.data.event_type",
  "operator": "equals",
  "expected": "answer"
}
```

后续其他 `answer` 数据帧不得覆盖首次记录。

### 5.4 LLM 启动到首次回答

当同一次请求同时命中 `call_llm_start_ms` 和 `first_answer_ms` 时，运行结果可派生：

```text
llm_start_to_first_answer_ms = first_answer_ms - call_llm_start_ms
```

若任一原始指标缺失，派生指标必须为空，不得按零计算。

## 6. 样本结构与 JSONPath 边界

接口编排运行结果可能使用包装结构展示事件：

```json
{
  "body": {
    "streaming": true,
    "events": [
      {
        "event": "message",
        "data": {
          "code": "000000",
          "data": {
            "event_type": "answer"
          }
        }
      }
    ]
  }
}
```

该包装结构只用于接口编排结果展示。Locust 实时解析的是单个 SSE `data:` 字段中的 JSON，因此实际匹配路径必须相对于单帧 `data` 内容：

```text
$.data.event_type
```

不得生成以下基于编排结果包装层的路径：

```text
$.body.events[*].data.data.event_type
```

服务端在调用 AI 前应将样本标准化为单帧视角，减少 AI 混淆展示包装层和真实流数据层的风险。

## 7. 端到端流程

```text
用户选择接口或接口场景
        ↓
用户点击“运行接口编排并生成 SSE 指标”
        ↓
系统以当前环境和请求参数执行一次编排
        ↓
捕获并标准化 SSE 事件样本
        ↓
裁剪、脱敏并生成事件结构摘要
        ↓
AI 生成候选 request_config.sse
        ↓
服务端 Schema 校验
        ↓
使用真实样本进行确定性回放验证
        ↓
返回候选规则、命中证据、样本耗时和警告
        ↓
用户确认或手工调整
        ↓
保存到压测 request_config.sse
        ↓
脚本生成器写入固定 Locust PLAN
        ↓
Locust 实时采集首次命中耗时
```

## 8. AI 输入契约

AI 输入应包含以下最小信息：

```json
{
  "target": {
    "name": "对话接口",
    "method": "POST",
    "path": "/chat/stream",
    "content_type": "text/event-stream"
  },
  "sampling": {
    "status_code": 200,
    "event_count": 13,
    "truncated": false
  },
  "events": [
    {
      "sequence": 1,
      "event_name": "message",
      "received_offset_ms": 0,
      "data_json": {
        "code": "000000",
        "data": {
          "event_type": "start",
          "role": "user",
          "answer": "<redacted>"
        },
        "type": "multi_agent"
      }
    }
  ],
  "requested_metrics": [
    "首次 call_llm_start",
    "首次 answer"
  ]
}
```

要求：

- `received_offset_ms` 使用编排客户端接收时间计算，不依赖服务端业务时间戳。
- 请求头中的认证信息、Cookie、Token 和敏感业务内容必须脱敏。
- 长文本字段可以替换为长度、类型和短摘要。
- 输入事件数量和总字节数必须设置上限。
- 应优先保留事件字段结构、事件类型值和首尾事件，不需要把完整回答内容发送给 AI。

## 9. AI 输出契约

AI 返回候选配置和解释信息：

```json
{
  "transport": "sse",
  "sse": {
    "max_stream_seconds": 60,
    "metrics": [
      {
        "id": "call_llm_start",
        "name": "LLM 调用开始时间",
        "match": {
          "event_name": "message",
          "source": "data_json",
          "path": "$.data.event_type",
          "operator": "equals",
          "expected": "call_llm_start"
        },
        "occurrence": "first",
        "missing_policy": "record_null"
      },
      {
        "id": "first_answer",
        "name": "首次回答时间",
        "match": {
          "event_name": "message",
          "source": "data_json",
          "path": "$.data.event_type",
          "operator": "equals",
          "expected": "answer"
        },
        "occurrence": "first",
        "missing_policy": "fail_request"
      }
    ],
    "end_rule": {
      "event_name": "message",
      "source": "data_json",
      "path": "$.data.event_type",
      "operator": "equals",
      "expected": "query_end"
    }
  },
  "explanations": [
    {
      "metric_id": "call_llm_start",
      "reason": "样本中首次出现 call_llm_start，表示模型调用开始",
      "confidence": 0.99
    },
    {
      "metric_id": "first_answer",
      "reason": "样本中 answer 事件携带助手输出，取首次出现作为首次回答",
      "confidence": 0.99
    }
  ]
}
```

约束：

- `transport` 必须为 `sse`。
- 指标数量不得超过现有 Schema 上限。
- `occurrence` 首期只能为 `first`。
- JSONPath 只能使用现有匹配器支持的字段、数组下标和 `[*]`。
- 正则匹配必须受现有长度和编译校验约束。
- `confidence` 仅用于界面解释，不参与运行时匹配。
- 保存到压测信息时只保存正式配置，不要求把 AI 解释写入 Locust 脚本。

## 10. 确定性回放验证

服务端接收 AI 候选结果后必须执行以下验证：

1. 使用 Pydantic Schema 校验结构和字段范围。
2. 使用现有 JSONPath 校验器检查路径合法性。
3. 使用与 Locust 模板等价的 SSE 匹配语义回放所有采样事件。
4. 统计每条指标的总命中次数。
5. 记录首次命中事件序号和 `received_offset_ms`。
6. 校验结束规则是否命中。
7. 生成阻断错误和非阻断警告。

示例验证结果：

```json
{
  "valid": true,
  "metrics": [
    {
      "id": "call_llm_start",
      "matched_count": 1,
      "first_event_sequence": 2,
      "sample_elapsed_ms": 341
    },
    {
      "id": "first_answer",
      "matched_count": 9,
      "first_event_sequence": 3,
      "sample_elapsed_ms": 2999
    }
  ],
  "end_rule": {
    "matched_count": 1,
    "first_event_sequence": 13
  },
  "warnings": []
}
```

### 10.1 阻断错误

出现以下情况时不得自动保存：

- 编排请求失败或状态码不满足成功条件。
- 响应不是 SSE，且用户未明确切换到 HTTP 模式。
- 没有捕获到有效 SSE 事件。
- AI 输出不符合 Schema。
- JSONPath 不合法。
- `call_llm_start` 或 `answer` 候选规则完全不命中。
- 结束规则不命中且流只能依赖超时结束。

### 10.2 非阻断警告

以下情况允许用户确认后保存：

- `call_llm_start` 出现多次，系统仍取首次。
- `answer` 出现多次，系统明确提示只取首次。
- 样本被截断，但目标指标已经命中。
- 没有识别到稳定结束事件，但用户选择仅使用最大流时长。
- AI 置信度低于建议阈值。

## 11. 缺失策略

推荐默认值：

- `call_llm_start` 使用 `record_null`：部分协议可能不暴露模型调用事件，不应默认把所有请求判定为业务失败。
- `first_answer` 使用 `fail_request`：成功的流式问答请求应至少产生一个有效回答事件，缺失时应作为请求失败暴露。

用户可以在确认界面修改缺失策略。运行时必须区分：

- 指标未命中但请求仍成功。
- 指标未命中并按规则判定请求失败。
- 指标被明确忽略。

缺失值不得作为 `0 ms` 进入百分位和平均值统计。

## 12. 配置保存与脚本传递

确认后的配置直接保存到现有压测信息的 `request_config`：

```json
{
  "path_parameters": {},
  "query_parameters": {},
  "headers": {},
  "body": {},
  "transport": "sse",
  "sse": {
    "max_stream_seconds": 60,
    "metrics": [],
    "end_rule": {}
  }
}
```

脚本生成阶段必须复用该配置生成固定 `PLAN`，而不是再次调用 AI 推测规则。这样可以保证：

- 用户确认的规则与实际脚本一致。
- 重新生成脚本不会产生规则漂移。
- 相同压测配置可以稳定复现。
- 脚本验证可以直接检查 `PLAN` 中的 SSE 规则。

## 13. Locust 运行行为

每次请求必须独立维护：

```python
request_started_at = time.perf_counter()
observed = {}
```

每完成一个 SSE 数据帧解析后：

1. 遍历尚未命中的指标。
2. 使用固定匹配器判断当前帧。
3. 首次命中时记录相对请求开始时间。
4. 已命中的指标不再重复计算。
5. 命中结束规则时正常结束流读取。
6. 达到 `max_stream_seconds` 时按超时策略结束。
7. 请求结束后处理未命中指标的缺失策略。

记录到指标系统的数据必须包含：

- 性能测试 ID。
- 压测运行 ID。
- 请求名称。
- 指标 ID。
- 指标名称。
- 耗时毫秒数或空值。
- 是否命中。
- 缺失策略。
- 请求成功或失败状态。

## 14. 前端交互设计

前端首期采用最小方案：主表单一个摘要区块，加一个配置 Dialog。不新增独立页面、抽屉、页签、时间轴或完整 SSE 事件浏览器。

### 14.1 主表单摘要区块

在压测信息的新建或编辑表单中，当当前请求使用 SSE，或请求预览识别到 `text/event-stream` 时显示“业务响应指标”区块。

未配置状态：

```text
业务响应指标

运行一次真实接口编排，自动识别 LLM 调用开始、首次回答和流结束事件。

[运行接口编排并生成指标]
```

按钮执行前必须校验：

- 已选择项目和环境。
- 已选择接口或接口场景。
- 当前请求参数可运行。
- 必要认证信息已经配置。

已配置状态：

```text
业务响应指标                                      已验证

✓ LLM 调用开始  call_llm_start  样本 341 ms  命中 1 次
✓ 首次回答      answer          样本 2999 ms 命中 9 次，仅取首次

流结束：query_end · 已验证

[重新生成] [配置指标]
```

要求：

- 样本时间必须标记为“样本”，不得表现为正式压测结果。
- 多次命中的指标必须显示总命中次数，并明确正式压测只记录首次命中。
- 主表单只保存用户最终确认的 `request_config.sse`，不保存 Dialog 内未确认的临时结果。

### 14.2 生成状态

生成过程中复用同一个按钮或区块展示简短状态，不增加复杂步骤条：

```text
正在运行接口编排…
正在生成指标…
正在验证指标…
```

运行期间禁止重复提交。生成失败时显示明确原因，并提供重试和手工配置入口。

### 14.3 配置 Dialog

点击“配置指标”或生成成功后打开一个 Dialog：

```text
SSE 指标配置

☑ LLM 调用开始                                  已验证
  $.data.event_type = call_llm_start
  样本事件 #2 · 341 ms · 命中 1 次
  缺失处理：[记录为空]
  [查看样本] [展开配置]

☑ 首次回答                                      已验证
  $.data.event_type = answer
  样本事件 #3 · 2999 ms · 命中 9 次，仅取首次
  缺失处理：[请求失败]
  [查看样本] [展开配置]

流结束：$.data.event_type = query_end            已验证

[重新验证]                              [取消] [应用]
```

Dialog 默认只展示指标名称、匹配摘要、命中证据、缺失策略和验证状态。用户点击“展开配置”后才显示：

- 指标名称。
- SSE 事件名。
- 匹配来源。
- JSONPath。
- 匹配操作符。
- 期望值。

`occurrence` 首期固定为 `first`，不展示无意义的单选下拉框。指标 ID 创建后只读，避免破坏历史指标关联。

### 14.4 命中证据

每个候选指标必须展示以下最小证据：

- 首次命中的样本事件序号。
- 首次样本耗时。
- 总命中次数。
- 是否只记录首次命中。

点击“查看样本”只展开当前指标首次命中的一条脱敏事件摘要，不提供完整事件列表、筛选器或复制工作台。例如：

```json
{
  "event": "message",
  "event_type": "answer",
  "role": "assistant",
  "answer": "你好呀！"
}
```

### 14.5 修改后重新验证

用户修改事件名、JSONPath、操作符或期望值后，该指标状态立即变为“待验证”，并禁用“应用”按钮。

```text
待验证

[重新验证] [应用（禁用）]
```

重新验证只使用当前已经捕获的样本回放规则，不需要再次运行接口编排或再次调用 AI。验证成功后恢复“已验证”状态并允许应用。

指标名称和缺失策略的修改不影响匹配语义，不强制重新回放验证。

### 14.6 重新生成保护

已有指标配置时，点击“重新生成”不得直接覆盖当前配置。界面提示：

```text
重新运行将生成新的指标建议，当前配置不会立即被覆盖。

[取消] [继续运行]
```

新建议生成并验证完成后，用户只能选择：

- 保留当前配置。
- 使用新配置。

首期不提供逐字段差异对比或配置合并。

### 14.7 明确不实现

首期前端不实现：

- 事件时间轴。
- 多页签指标工作台。
- 完整 SSE 事件浏览器。
- JSONPath 自动补全。
- AI 置信度展示。
- 新旧配置逐字段差异对比。
- 派生指标配置界面。
- 本功能范围内的压测结果报表改版。

## 15. API 设计边界

优先复用现有接口编排执行和 SSE 配置验证能力，不为每个步骤创建孤立接口。

服务端需要提供一个面向压测表单的编排能力，完成以下编排：

1. 接收当前压测目标、环境和请求配置。
2. 复用现有接口编排执行能力进行一次探测运行。
3. 标准化和脱敏 SSE 样本。
4. 调用性能测试脚本生成 Agent 的受限指标生成能力。
5. 调用现有 SSE 匹配器回放验证。
6. 返回候选配置和验证证据，但不自动保存压测信息。

推荐使用单一业务动作表达该流程，避免前端分别编排“运行、生成、验证”三个低层接口而产生中间状态不一致。

请求应携带当前表单中的未保存参数，不能只依赖数据库中的旧配置。

响应应至少包含：

```json
{
  "sample": {
    "status_code": 200,
    "event_count": 13,
    "truncated": false
  },
  "candidate_request_config": {
    "transport": "sse",
    "sse": {}
  },
  "validation": {
    "valid": true,
    "metrics": [],
    "end_rule": {},
    "warnings": []
  },
  "explanations": []
}
```

## 16. 安全与资源限制

- 探测运行必须使用服务端允许的目标环境，不能接受任意外部 URL。
- 复用现有环境认证和密钥解析机制，响应中不得回传明文密钥。
- SSE 探测必须限制总时长、事件数、单帧大小和总字节数。
- AI 输入必须脱敏 Authorization、Cookie、Token、会话 ID 和个人信息。
- AI 输出必须经过严格 Schema 校验，不得通过字符串拼接写入 Python。
- 正则表达式继续使用现有限长和编译校验。
- 探测运行应记录操作日志，便于追踪谁在何时对哪个目标发起了真实请求。

## 17. 兼容性

- 现有 HTTP 压测配置不受影响。
- 已存在的 SSE 压测配置无需迁移。
- 未使用 AI 生成的手工 SSE 配置继续可用。
- 脚本生成器继续只依赖正式 `request_config`，不依赖历史采样结果。
- AI 生成失败时不得清空或覆盖用户已有配置。
- 接口场景压测应在场景编译为可执行请求后复用同一套 SSE 指标生成和验证流程。

## 18. 失败处理

| 场景 | 系统行为 |
|---|---|
| 编排请求网络失败 | 返回可重试错误，不调用 AI |
| 返回非 2xx | 展示状态码和脱敏响应摘要，不调用 AI |
| Content-Type 不是 SSE | 提示检查接口或切换 HTTP 模式 |
| SSE 无事件 | 提示检查请求参数、鉴权或超时设置 |
| AI 调用失败 | 保留样本，允许重试或手工配置 |
| AI 规则不命中 | 展示回放证据，不允许直接接受 |
| 只有部分指标命中 | 阻断必选指标，允许删除非必选指标后继续 |
| 结束规则不命中 | 警告并允许改用最大流时长结束 |
| 用户取消 | 不修改当前压测配置 |

## 19. 可观测性

服务端日志和操作日志应记录：

- 项目、环境、接口或场景标识。
- 探测运行状态和耗时。
- 捕获事件数、截断状态和总字节数。
- AI 生成状态，不记录敏感完整提示词。
- 每个候选规则的命中次数。
- 用户是否接受、修改或放弃建议。

不得在普通日志中记录：

- Authorization 和 Cookie。
- 完整请求体中的敏感内容。
- 完整 SSE 回答文本。
- 环境密钥。

## 20. 测试要求

### 20.1 后端单元测试

- 标准化编排包装事件为单帧 SSE 视角。
- 正确生成 `$.data.event_type`，不包含 `body.events` 包装路径。
- 首次 `call_llm_start` 命中并返回首次样本耗时。
- 多个 `answer` 事件只返回第一次命中时间。
- `query_end` 正确作为结束规则。
- 非法 JSONPath 被拒绝。
- AI 规则不命中时验证失败。
- 服务端时间戳不参与正式 Locust 耗时计算。
- 脱敏逻辑不会把认证信息传给 AI。

### 20.2 脚本生成测试

- 保存的 `request_config.sse.metrics` 原样进入生成计划。
- 生成脚本包含单调时钟请求起点。
- 指标只在首次命中时写入。
- 后续 `answer` 不覆盖 `first_answer`。
- 未命中指标按 `missing_policy` 处理。
- 派生指标仅在两个原始指标均存在时计算。
- 重新生成脚本不会再次调用 AI 改写规则。

### 20.3 API 测试

- 使用未保存的表单参数执行探测。
- 编排失败时不调用 AI。
- AI 成功但回放失败时返回不可接受状态。
- 响应包含候选配置、命中证据、警告和解释。
- 用户确认前不写入压测信息。
- 无权限用户不能发起探测运行。

### 20.4 前端测试

- SSE 目标显示生成入口，普通 HTTP 目标不误显示。
- 运行过程中按钮不可重复提交。
- 主表单使用一个摘要区块展示指标状态，不新增独立页面或复杂工作台。
- 配置 Dialog 展示路径、期望值、首次事件序号、命中次数和样本耗时。
- 多次 `answer` 明确提示取首次。
- 点击“查看样本”只展示首次命中的一条脱敏事件摘要。
- 修改匹配语义后状态变为“待验证”，且“应用”按钮不可用。
- 使用当前样本重新验证成功后才允许应用。
- 用户取消不会修改表单配置。
- AI 失败后可以重试或手工编辑。
- 重新生成和生成失败都不会直接覆盖已有配置。
- 用户可以明确选择保留当前配置或使用新配置。

## 21. 验收标准

1. 用户可以从新建压测页面运行一次真实接口编排并获得 SSE 样本。
2. 系统可以从示例结构识别 `$.data.event_type`。
3. 系统生成 `call_llm_start` 和 `first_answer` 两个首次事件指标。
4. 系统使用真实样本回放验证规则，不能只依赖 AI 声明成功。
5. 示例数据中 `call_llm_start` 首次样本耗时显示约 `341 ms`，首次 `answer` 显示约 `2999 ms`。
6. 用户确认后，配置保存到现有 `request_config.sse`。
7. 生成的 Locust 脚本从请求开始时刻计算两个指标。
8. 多个 `answer` 事件只记录第一次，不被后续事件覆盖。
9. 正式压测不使用服务端业务 `timestamp` 作为耗时时间源。
10. AI 不生成可执行脚本，只生成受限声明式规则。
11. AI 输出必须通过 Schema 校验和真实样本回放验证。
12. HTTP 压测和已有 SSE 压测保持兼容。
13. 前端只使用一个主表单摘要区块和一个配置 Dialog 完成首期交互。
14. 每个指标展示首次命中事件、样本耗时和总命中次数。
15. 修改 JSONPath 等匹配语义后必须重新验证，验证前不能应用配置。
16. 重新生成的新建议必须由用户确认后才可替换已有配置。

## 22. 设计决策

### 22.1 选择“真实采样 + AI 识别 + 程序验证”

该方案比根据文档直接猜测更准确，也比完全手工配置更易用。AI 负责处理非标准业务语义，程序负责安全边界和可重复验证。

### 22.2 复用现有 SSE 配置模型

现有 `PerformanceSseConfig`、`PerformanceSseMetric` 和 `PerformanceSseMatch` 已覆盖本需求。复用现有模型可以避免数据库、API、脚本模板和运行结果出现两套不一致的指标定义。

### 22.3 将 AI 生成放在保存之前

AI 建议属于配置辅助，不是脚本生成时的隐藏行为。用户必须在压测信息保存前看到并确认规则，保证脚本行为可解释、可复现。

### 22.4 使用单调时钟计算正式指标

服务端时间戳适合日志关联，但不能保证与 Locust 节点时钟同步。使用 `time.perf_counter()` 可以稳定测量单次请求内的相对耗时。

## 23. 未决问题

首期设计没有阻断性未决问题。后续可根据运行数据评估：

- 是否将 `llm_start_to_first_answer_ms` 持久化为正式派生指标。
- 是否支持按 `agent_id`、`agent_name` 或 `index` 分组统计。
- 是否支持复合条件，例如同时要求 `event_type = answer` 且 `answer` 非空。
- 是否支持从多个探测样本生成更稳定的规则，而不是只使用单次样本。
