# API 场景 AI 编排审阅式生成前后端改造设计

**状态**：设计已确认，待实施

**日期**：2026-08-01

## 1. 背景

当前 API 场景 AI 编排使用 LangChain `create_agent` 和 `ToolStrategy` 直接生成完整 `ScenarioPlanResult`。模型既负责接口选择、执行顺序、依赖关系和 Mock 数据，又直接承担最终可执行结构的生成。

该方案存在以下根本问题：

- 明确选择两个接口后，模型仍可能进入开放式结构化输出循环；
- AI 规划、字段来源选择、Mock 数据生成和最终场景编译耦合在一次 Agent 执行中；
- 模型输出不符合结构化协议时，框架内部可能持续重试，业务层无法控制总调用次数；
- 当前预览只展示最终节点，用户无法按接口逐项确认 Header、Query、Body、Form Data 等字段；
- 环境变量、上游输出、已有值和 AI 生成值没有清晰区分；
- AI 生成的字段值无法在应用前独立编辑和持久化；
- 任务超过五分钟后仅修改数据库状态，实际后台模型调用不会停止；
- AI 推断的接口顺序和依赖关系缺少直观、可修改的人工审阅界面。

实际任务 `aiplan-983bb977d423847b` 仅选择两个接口，却在后台连续调用模型 237 次，最终触发模型限流。这说明问题不是接口数量，而是开放式 Agent 与编排任务之间的模型不匹配。

本设计将 AI 编排改造为：

```text
有限调用 AI Planner
        ↓
服务端确定性校验与规范化
        ↓
按接口步骤生成审阅卡片
        ↓
人工确认或修改字段
        ↓
服务端编译为 Canonical Scenario Model
        ↓
应用到场景草稿
```

## 2. 设计决策

最终采用：

> AI 负责接口选择、执行顺序、数据依赖、字段来源和 Mock 建议；服务端负责资产校验、字段校准、确认状态、可执行性校验和最终编译；用户按接口步骤卡片完成审阅。

不再使用开放式 Agent 循环直接生成最终可执行场景。

## 3. 目标

- 保留 AI 对接口选择、顺序、依赖、Mock 和断言的语义分析能力。
- 单个编排任务最多执行一次 Planning 和一次 Repair 模型调用。
- 用户选择的候选接口必须作为 AI 分析边界，不向模型发送无关项目接口。
- 每次接口调用作为独立步骤卡片展示，而不是按接口资产去重。
- 每张步骤卡片按 Header、Path、Query、Cookie、Body、Form 和 Multipart 分区。
- 每个待审阅字段只展示字段、AI 建议、最终值和状态。
- 环境已有值优先引用环境，不由 AI 重新生成。
- 上游接口输出优先建模为 `step_output` 数据来源。
- 无确定来源的字段由 AI 生成候选值，人工可以修改。
- AI 推断的顺序、依赖和模糊环境映射必须允许人工调整。
- 人工修改后的审阅结果必须持久化，刷新页面不能丢失。
- 只有必填待确认项全部处理并通过服务端校验后才能应用。
- 超时必须终止实际生成流程，不能只改变展示状态。

## 4. 非目标

- 不重写现有 Canonical Scenario Model V2。
- 不改变场景执行器、pytest Requests 生成器和运行时请求协议。
- 不新增通用工作流引擎或分布式任务队列。
- 不允许用户在审阅抽屉中编辑任意脚本或表达式。
- 不展示模型内部推理过程、原因文本或置信度。
- 不维护旧 AI Plan 和新版审阅计划的双轨前端渲染。
- 不自动执行 AI 生成的计划。

## 5. 核心原则

### 5.1 AI 负责语义，编译器负责执行

AI 可以建议：

- 使用哪些候选接口；
- 每个接口调用出现几次；
- 接口调用顺序；
- 请求字段使用环境变量、上游输出、场景变量、固定值或运行时输入；
- 上游响应字段与下游请求字段之间的依赖；
- 缺失字段的 Mock 候选值；
- 提取器和断言意图；
- 清理步骤和失败策略。

AI 不可以决定：

- 不存在的 endpoint ID；
- 不存在的请求字段位置；
- 不存在的响应 JSON Pointer；
- Secret 的实际值；
- 最终可执行节点的内部格式；
- 是否绕过必填字段确认；
- 是否跳过服务端可执行性校验。

### 5.2 每次调用是一个步骤卡片

步骤卡片代表一次接口调用。同一 endpoint 可以产生多个步骤卡片。

```text
步骤 1 · 创建订单
步骤 2 · 查询订单
步骤 3 · 再次查询订单
```

步骤 ID 是编排实例 ID，不能使用 endpoint ID 代替。

### 5.3 只确认不确定内容

默认只展开待确认字段。已由确定性规则解析的字段折叠展示。

以下来源可以自动确定：

- 已有场景 Binding；
- 用户本次明确输入；
- 精确匹配且类型兼容的环境变量；
- 已配置的 Secret 引用；
- 已校验的上游步骤输出；
- OpenAPI `const`；
- 明确的 schema `default`；
- 只有一个候选值的 enum。

以下情况必须人工确认：

- AI 生成的 literal Mock；
- AI 通过语义而非精确名称匹配的环境变量；
- AI 推断的场景变量；
- AI 推断但无法由响应 schema 唯一证明的上游字段；
- 多个候选来源均合法；
- AI 新增的可选业务字段；
- 用户修改过 AI 建议但尚未确认的字段。

### 5.4 不展示无行动价值的信息

审阅界面不展示：

- “当前环境未提供该字段”之类原因；
- 模型置信度；
- 模型推理文本；
- 重复的当前值与来源列；
- 与用户决策无关的资产元数据。

用户只需要看到：

```text
字段
AI 建议
最终值
状态
```

## 6. 端到端流程

### 6.1 创建任务

前端提交：

```json
{
  "goal": "编排2个接口",
  "scenario_id": "apiscn-a9828f6b5477e890",
  "source_scope": {
    "endpoint_ids": [
      "apiend-5ba6a6e1fdf76150",
      "apiend-2335bd7dbb86c233"
    ]
  },
  "constraints": {
    "environment_id": "apienv-df3e7415a26e6021",
    "require_cleanup": false
  }
}
```

服务端完成以下操作后立即返回 `202`：

1. 校验项目、场景、环境和候选接口。
2. 创建 `api_scenario_ai_plans` 记录。
3. 保存候选接口资产指纹。
4. 设置 `lifecycle_status = generating`。
5. 提交给应用级有界编排执行器。

### 6.2 AI Planning

服务端仅向模型发送：

- 用户目标；
- 用户选择的候选接口；
- 候选接口完整但脱敏的请求槽位；
- 候选接口响应 schema 和示例；
- 当前场景已有步骤和变量；
- 环境变量名称、类型和非敏感值；
- Secret 名称，不发送 Secret 实际值；
- 是否要求清理；
- Planner 输出 JSON Schema。

Planning 必须一次性输出：

- 步骤实例；
- endpoint 选择；
- 执行顺序；
- 字段来源建议；
- 数据依赖建议；
- Mock 候选值；
- 提取器和断言意图；
- 控制依赖；
- 无法提出候选值的字段。

### 6.3 服务端规范化

服务端将 Planner 输出转换为审阅计划：

1. 校验 endpoint ID。
2. 将 AI 字段名称校准到真实 `ParameterTarget`。
3. 将响应字段校准到真实提取路径。
4. 校验值类型。
5. 识别精确环境匹配和模糊环境匹配。
6. 建立字段确认状态。
7. 根据 `step_output` 推导数据依赖。
8. 校验步骤拓扑顺序。
9. 生成每个步骤卡片所需的字段分组。
10. 编译一份临时 Canonical Plan 用于可执行性校验。

### 6.4 Repair

只有 Planner 输出无法解析或存在可自动修复的结构错误时，允许调用一次 Repair。

Repair 输入仅包含：

- 原始 Planner 输出；
- 服务端结构化校验错误；
- 相关接口槽位；
- 相同的输出 JSON Schema。

Repair 后仍无法解析时，任务失败，不继续调用模型。

业务字段无法确定不属于生成失败。服务端应生成空的待确认字段或 AI 候选值，让用户处理。

### 6.5 人工审阅

生成完成后：

- `lifecycle_status = completed`；
- `review_status = pending` 或 `ready`；
- 前端打开审阅抽屉；
- 用户按步骤修改顺序、字段来源和值；
- 修改通过统一审阅保存接口持久化；
- 服务端每次保存后重新规范化和校验。

### 6.6 应用

应用前必须满足：

- 所有必填字段不存在 `pending` 状态；
- 所有 `step_output` 来源指向拓扑上游；
- 所有来源类型和值通过 schema 校验；
- 当前场景 revision 与 `expected_revision` 一致；
- endpoint asset fingerprint 未发生冲突；
- 编译后的 Canonical Plan 通过现有运行时能力校验。

应用时继续复用现有覆盖草稿确认流程。

## 7. AI Planner 设计

### 7.1 删除开放式 Agent

`api_scenario_orchestration_agent` 不再通过 `create_agent`、`ToolStrategy` 和 Agent 图循环执行。

改为一个深模块：

```python
class ApiScenarioPlanner:
    async def plan(self, snapshot: PlanningSnapshot) -> PlannerProposal:
        ...
```

该接口隐藏：

- Prompt 构造；
- 模型选择；
- JSON 提取；
- Pydantic 校验；
- 一次 Repair；
- 超时；
- 调用次数统计；
- 日志脱敏。

调用方只接收成功的 `PlannerProposal` 或明确的 `PlannerError`。

### 7.2 模型输出协议

模型输出使用普通 JSON 内容，不再依赖 Provider Tool Calling。

```json
{
  "scenario_name": "生成 SegmentCode 后发起 SSE 对话",
  "steps": [
    {
      "client_step_id": "step-1",
      "endpoint_id": "apiend-5ba6a6e1fdf76150",
      "order": 1,
      "phase": "setup",
      "name": "生成 SegmentCode",
      "fields": [],
      "extractors": [],
      "assertions": [],
      "depends_on": []
    }
  ]
}
```

模型只能引用输入快照中出现的 endpoint、环境变量、场景变量和响应字段。

### 7.3 调用预算

每个任务固定预算：

```text
Planning 调用：最多 1 次
Repair 调用：最多 1 次
模型总调用：最多 2 次
单次调用超时：45 秒
任务总 deadline：90 秒
Provider 自动 HTTP 重试：最多 1 次
```

超过任意限制必须：

1. 取消当前协程或 Future。
2. 停止后续模型调用。
3. 更新任务为 `failed`。
4. 记录当前阶段和模型调用次数。
5. 禁止已超时执行器继续覆盖任务结果。

## 8. 审阅计划模型

### 8.1 Plan 层级

新增 `schema_version = 3` 的审阅计划：

```json
{
  "plan_id": "aiplan-xxx",
  "schema_version": 3,
  "lifecycle_status": "completed",
  "review_status": "pending",
  "review_revision": 0,
  "scenario_name": "生成 SegmentCode 后发起 SSE 对话",
  "steps": [],
  "validation": {},
  "expected_revision": 0,
  "asset_fingerprint": "...",
  "expires_at": "..."
}
```

### 8.2 步骤模型

```json
{
  "step_id": "step-1",
  "endpoint_id": "apiend-xxx",
  "order": 1,
  "phase": "main",
  "name": "发起 SSE 对话",
  "method": "POST",
  "path": "/chat",
  "depends_on": [],
  "field_groups": [],
  "extractors": [],
  "assertions": [],
  "on_failure": "stop",
  "enabled": true,
  "review_summary": {
    "pending_count": 2,
    "resolved_count": 6,
    "blocking_count": 1
  }
}
```

`depends_on` 仅保存没有字段传值的控制依赖。数据依赖由字段 `step_output` 来源推导，不重复保存。

### 8.3 字段分组

支持以下分组：

```text
path
query
headers
cookies
json_body
form
multipart
raw_body
```

```json
{
  "location": "multipart",
  "label": "Form Data",
  "pending_count": 1,
  "fields": []
}
```

空分组不返回，前端不渲染。

### 8.4 字段模型

```json
{
  "field_id": "field-step-2-username",
  "path": "/username",
  "display_name": "username",
  "required": true,
  "value_type": "string",
  "sensitive": false,
  "proposal": {
    "type": "environment",
    "key": "username"
  },
  "resolved": {
    "type": "environment",
    "key": "username"
  },
  "status": "resolved"
}
```

AI literal 候选值：

```json
{
  "field_id": "field-step-2-question",
  "path": "/data/question",
  "display_name": "question",
  "required": true,
  "value_type": "string",
  "sensitive": false,
  "proposal": {
    "type": "literal",
    "value": "查询当前用户资料"
  },
  "resolved": {
    "type": "literal",
    "value": "查询当前用户资料"
  },
  "status": "pending"
}
```

### 8.5 字段状态

字段只保留三个状态：

```text
resolved   由确定性规则自动确认
pending    需要人工确认
confirmed  已由人工确认或修改
```

不增加 `confidence`、`reason` 或其他展示状态。

### 8.6 来源类型

审阅计划直接复用 Canonical Model V2 的 ValueSource：

```text
literal
user_input
environment
secret
scenario
step_output
generated
object
```

前端不创建新的来源枚举。

## 9. 字段解析规则

### 9.1 优先级

服务端按以下顺序解析字段：

1. 已有场景 Binding。
2. 用户本次明确设置。
3. 已校验的上游步骤输出。
4. 精确匹配的环境变量。
5. 已配置 Secret。
6. 现有场景变量。
7. OpenAPI `const` 或明确 `default`。
8. 唯一 enum 值。
9. AI 推荐的环境、场景或上游来源。
10. AI 生成的 literal 或 object Mock。
11. 运行时输入。

前八类在确定性校验通过后可以标记 `resolved`。第九和第十类默认 `pending`。第十一类若用户明确选择则标记 `confirmed`。

### 9.2 环境变量匹配

以下情况可以自动确定：

- 字段规范名与环境 key 完全一致；
- 已有 Binding 明确指向该环境 key；
- 类型兼容；
- 环境 key 存在；
- 非空约束得到满足。

以下情况必须待确认：

- 仅通过字段描述语义匹配；
- 一个字段存在多个环境候选；
- 类型需要转换；
- 环境变量为空；
- 字段名不同且没有既有映射。

环境引用不向前端返回敏感实际值。

### 9.3 AI Mock

AI Mock 必须满足接口 schema：

- 类型正确；
- enum 值合法；
- 长度和数值边界合法；
- object 结构完整；
- 不生成真实 Secret；
- 不生成脚本；
- 不使用未声明变量；
- 使用稳定值，不生成无必要的随机内容。

AI Mock 默认写入 `proposal` 和 `resolved`，但状态保持 `pending`。用户可以直接确认，也可以修改最终值或切换来源。

## 10. 后端改造

### 10.1 模块划分

新增以下深模块：

```text
orchestration_planner.py
  AI Planning、JSON 解析、一次 Repair、调用预算

orchestration_review.py
  PlannerProposal → ReviewPlan、字段确认规则、顺序调整

orchestration_validator.py
  endpoint、字段、来源、类型、拓扑和确认状态校验

orchestration_compiler.py
  ReviewPlan → Canonical Scenario Plan

orchestration_job_runner.py
  有界后台执行、任务取消、deadline 和并发控制
```

外部调用只通过以下接口：

```python
enqueue_plan(project_id, request, actor) -> AcceptedPlan
get_plan(project_id, plan_id, actor) -> PlanStatus | ReviewPlan
save_review(project_id, plan_id, review, actor) -> ReviewPlan
apply_plan(project_id, plan_id, request, actor) -> ApiScenario
```

路由层不直接构建模型、编译器或线程。

### 10.2 后台执行器

本次不引入分布式队列。新增应用级有界执行器，复用项目现有 `ThreadPoolExecutor` 模式：

```text
max_workers = 2
每个 plan_id 只允许一个 Future
支持 cancel(plan_id)
支持 deadline
进程退出时停止接收新任务
启动时将遗留 generating 任务标记为 failed
```

禁止继续使用 FastAPI `BackgroundTasks` 承载 AI 编排。

后台执行函数不得抛出 `HTTPException`。所有异常必须转换为任务状态和结构化错误。

### 10.3 数据表

在 `api_scenario_ai_plans` 增加：

```text
proposal_json       AI Planner 原始结构化提案
review_json         当前人工审阅计划
review_revision     审阅乐观锁版本
generation_meta_json 阶段、调用次数和耗时
asset_fingerprint   生成时使用的候选接口资产指纹
```

继续复用：

```text
request_json
plan_json
validation_json
lifecycle_status
status
model_provider
model_name
expected_revision
error_message
created_at
updated_at
expires_at
```

其中：

- `proposal_json` 仅用于诊断和重新规范化，不直接应用；
- `review_json` 是前端审阅的唯一事实来源；
- `plan_json` 保存由 `review_json` 编译出的 Canonical Plan；
- `validation_json` 保存当前审阅版本的校验结果。
- `review_status` 不增加数据库列，由 `review_json` 的字段状态和 `validation_json` 实时派生。

### 10.4 创建接口

继续使用：

```text
POST /projects/{project_id}/api-scenarios/ai-plan
```

返回：

```json
{
  "plan_id": "aiplan-xxx",
  "scenario_id": "apiscn-xxx",
  "lifecycle_status": "generating"
}
```

重复提交规则：

- 同一场景存在未完成任务时返回已有任务句柄；
- 已超过 deadline 的旧任务先取消并标记失败；
- 已完成但未应用的任务不阻止用户重新生成。

### 10.5 查询接口

继续使用：

```text
GET /projects/{project_id}/api-scenarios/ai-plans/{plan_id}
```

生成中返回：

```json
{
  "plan_id": "aiplan-xxx",
  "scenario_id": "apiscn-xxx",
  "lifecycle_status": "generating"
}
```

完成后返回完整 `ReviewPlan`。

查询接口只读取状态，不负责将超时任务标记失败。超时由执行器控制。

失败时必须返回错误摘要：

```json
{
  "plan_id": "aiplan-xxx",
  "scenario_id": "apiscn-xxx",
  "lifecycle_status": "failed",
  "error": {
    "stage": "planning",
    "code": "API_SCENARIO_AI_PLANNING_TIMEOUT",
    "message": "AI 规划请求超时"
  }
}
```

### 10.6 保存审阅接口

新增：

```text
PUT /projects/{project_id}/api-scenarios/ai-plans/{plan_id}/review
```

请求发送完整可编辑审阅部分。`steps` 必须包含当前计划的全部步骤和完整顺序，每个步骤必须包含全部可编辑字段的最终来源与确认状态；不可编辑的 endpoint、method、path 和 schema 元数据不回传。以下示例仅缩写为一个步骤：

```json
{
  "expected_review_revision": 3,
  "steps": [
    {
      "step_id": "step-1",
      "order": 1,
      "fields": [
        {
          "field_id": "field-step-1-question",
          "resolved": {
            "type": "literal",
            "value": "查询当前用户资料"
          },
          "status": "confirmed"
        }
      ]
    }
  ]
}
```

服务端必须：

1. 校验 `expected_review_revision`。
2. 校验只能修改允许审阅的字段。
3. 重新排序步骤。
4. 重新推导数据依赖。
5. 重新编译 Canonical Plan。
6. 更新确认统计。
7. 更新 `review_json`、`plan_json` 和 `validation_json`。
8. 递增 `review_revision`。
9. 返回完整最新 ReviewPlan。

版本冲突返回 `409 API_SCENARIO_AI_REVIEW_CONFLICT`。

### 10.7 应用接口

继续使用：

```text
POST /projects/{project_id}/api-scenarios/ai-plans/{plan_id}/apply
```

应用接口不接收任意 Plan JSON，只应用服务端已持久化并校验的当前 `review_revision`。

请求增加：

```json
{
  "scenario_id": "apiscn-xxx",
  "confirmation": "overwrite_draft",
  "expected_review_revision": 4
}
```

存在以下情况时禁止应用：

- 必填字段仍为 `pending`；
- 校验存在 blocking error；
- review revision 冲突；
- 场景 revision 冲突；
- 资产指纹冲突；
- Plan 已过期；
- Plan 已应用或废弃。

## 11. 前端改造

### 11.1 抽屉职责

继续复用 `AiOrchestrationDrawer`，但从只读 Plan 预览改为审阅式编辑器。

抽屉包含：

```text
顶部：目标、步骤数、待确认数、保存状态
中部：步骤卡片列表
底部：全部确认、应用到场景
```

不再展示全局置信度、assumptions 和重复 unresolved 文案。

阻断错误在顶部统一展示，并定位到具体步骤和字段。

### 11.2 步骤卡片

每张卡片头部展示：

- 拖动手柄；
- 步骤序号；
- 步骤名称；
- HTTP Method；
- Path；
- 阶段；
- 上游步骤摘要；
- 待确认数量；
- 展开或折叠。

示例：

```text
步骤 2 · 发起 SSE 对话
POST /chat
依赖步骤 1：segment_code
1 项待确认
```

### 11.3 请求分区

卡片内部按实际存在的字段渲染：

```text
Path
Query
Headers
Cookies
Body
Form
Form Data
Raw Body
```

每个分区默认展示待确认字段，并显示：

```text
Headers · 待确认 1
已自动确定 3 项 [展开]
```

空分区不渲染。

### 11.4 字段行

桌面端字段行固定为：

```text
字段 | AI 建议 | 最终值 | 状态
```

必填字段通过字段名后的 `*` 表示，不新增必填列。

AI 建议根据来源显示：

```text
环境变量 username
步骤 1 输出 segment_code
固定值 查询当前用户资料
运行时输入 question
```

最终值由来源选择器和对应编辑器组成：

```text
[固定值 ▼] [查询当前用户资料]
[环境变量 ▼] [username]
[上游输出 ▼] [步骤 1] [segment_code]
[场景变量 ▼] [tenant_id]
[运行时输入 ▼] [question]
```

Secret 只允许选择 Secret key，不显示实际值。

### 11.5 类型化编辑器

根据字段类型使用不同编辑器：

- string：文本输入；
- integer/number：数字输入；
- boolean：开关或下拉；
- enum：选项下拉；
- object：结构化 JSON 编辑器；
- array：列表编辑器；
- file：文件来源配置，不接受 AI literal；
- secret：Secret key 下拉。

前端编辑器只提供输入体验，最终类型校验以服务端为准。

### 11.6 顺序调整

步骤卡片支持拖动排序。

拖动后：

1. 更新本地 order。
2. 立即检查明显的上游引用倒置。
3. 保存完整审阅计划。
4. 使用服务端返回结果刷新依赖和校验状态。

如果移动导致 `step_output` 指向下游，相关字段标记为阻断错误，禁止应用。

### 11.7 确认行为

保留三个操作：

```text
确认字段
确认本步骤
全部确认
```

规则：

- 用户修改最终值后，该字段标记为 `confirmed`；
- 用户接受 AI 建议时，可以直接确认字段；
- “确认本步骤”确认当前步骤所有非阻断 pending 字段；
- “全部确认”确认全部非阻断 pending 字段；
- 空值、类型错误或非法来源不能被确认。

### 11.8 保存策略

前端维护本地 draft，但不将其作为事实来源。

以下操作触发保存：

- 字段失焦；
- 来源切换完成；
- 确认字段；
- 确认步骤；
- 拖动排序完成；
- 点击应用前。

连续输入使用 500ms debounce。任意时刻只允许一个保存请求在途，后续修改合并后继续保存。

顶部显示：

```text
正在保存
已保存
保存失败
```

应用前必须等待保存完成。

### 11.9 应用按钮

底部显示：

```text
2 个步骤 · 3 个字段待确认
```

`应用到场景` 在以下情况禁用：

- 正在生成；
- 正在保存；
- 保存失败；
- 存在必填 pending；
- 存在 blocking error；
- review revision 冲突；
- Plan 已过期。

## 12. 状态模型

### 12.1 生命周期状态

继续使用：

```text
generating
completed
failed
expired
```

仅描述 AI 生成任务生命周期。

### 12.2 业务状态

继续使用：

```text
preview
applied
discarded
expired
```

### 12.3 审阅状态

新增：

```text
pending   存在待确认或阻断问题
ready     已确认且通过编译校验
```

应用后业务状态改为 `applied`，无需额外 `review_status = applied`。

## 13. 校验规则

### 13.1 阻断错误

- endpoint 不存在或不属于当前项目；
- 请求字段不存在；
- 必填字段没有 resolved 来源；
- 值类型不匹配；
- enum、长度或数值边界不合法；
- `step_output` 指向当前步骤或下游步骤；
- extractor 路径不存在；
- 依赖图存在环；
- Secret key 不存在；
- 环境变量不存在；
- 不支持的 ValueSource；
- 当前运行器不支持目标位置或 transform；
- 必填字段仍为 pending；
- 场景或资产版本冲突。

### 13.2 非阻断提示

- 可选字段保持空值；
- 没有响应 schema，提取器只能人工确认；
- 断言仅包含状态码；
- 清理步骤未生成；
- AI 建议值已被人工修改。

提示不得阻止保存，是否阻止应用由明确规则决定。

## 14. 错误处理与可观测性

每个生成任务至少记录：

```text
plan_id
stage
provider
model
model_call_count
planning_duration_ms
repair_duration_ms
normalization_duration_ms
compile_duration_ms
total_duration_ms
result
error_type
```

阶段限定为：

```text
queued
planning
repairing
normalizing
compiling
completed
failed
cancelled
```

禁止记录：

- Secret 实际值；
- 完整认证 Header；
- 用户环境中的敏感值；
- 模型 API Key。

任务失败摘要必须反映真实阶段，例如：

```text
AI 规划请求超时
AI 返回内容无法解析，修复后仍不符合协议
编排字段无法映射到接口资产
模型服务限流
```

不得继续使用“超过五分钟未完成”覆盖真实错误。

## 15. 兼容与迁移

### 15.1 计划版本

新版审阅计划使用：

```text
schema_version = 3
```

实施发布时：

- 未应用的旧 `schema_version < 3` Plan 标记为 `expired`；
- 前端不渲染旧版 Plan；
- 已应用场景不受影响；
- 不编写 V2 ReviewPlan Adapter；
- 不修改现有 Canonical Scenario Model V2 的场景数据。

### 15.2 当前前端类型

删除前端独立维护的宽松 `ApiScenarioAiPlanNode` 预览类型，新增与后端机械一致的：

```text
ApiScenarioAiReviewPlan
ApiScenarioAiReviewStep
ApiScenarioAiReviewFieldGroup
ApiScenarioAiReviewField
ApiScenarioAiReviewSaveIn
```

ValueSource 类型继续复用现有场景 Binding 类型。

## 16. 预计文件改造

### 后端

- `apps/backend/app/api/v1/api_automation.py`
- `apps/backend/app/schemas/api_automation.py`
- `apps/backend/app/services/api_automation/service.py`
- `apps/backend/app/services/api_automation/orchestration_compiler.py`
- `apps/backend/app/services/api_automation/orchestration_planner.py`
- `apps/backend/app/services/api_automation/orchestration_review.py`
- `apps/backend/app/services/api_automation/orchestration_validator.py`
- `apps/backend/app/services/api_automation/orchestration_job_runner.py`
- `apps/backend/app/agents/api_automation/orchestration/schemas.py`
- `apps/backend/app/seed/schema.py`
- `apps/backend/app/seed/seeds.py`
- `apps/backend/tests/test_api_scenario_ai_orchestration.py`

当前 `apps/backend/app/agents/api_automation/orchestration/agent.py` 删除或停止被生产代码引用。

### 前端

- `apps/frontend/src/lib/api-client.ts`
- `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`
- `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- 新增独立步骤卡片和字段编辑器文件，避免继续扩大 `api-scenario-editor.tsx`
- `apps/frontend/tests/api-scenario-ai-generation-drawer-contract.test.mjs`
- 新增审阅卡片、字段确认、排序和保存测试

## 17. 自动化测试

### 17.1 后端单元测试

- Planner 最多调用模型一次。
- Planner 解析失败时最多 Repair 一次。
- Repair 失败后停止，不进行第三次调用。
- 模型调用超时后任务停止并进入 failed。
- 任务失败后后台结果不能覆盖状态。
- 查询接口不修改任务状态。
- 只向 Planner 发送用户选择的候选接口。
- 精确环境匹配自动 resolved。
- 模糊环境匹配保持 pending。
- AI literal Mock 保持 pending。
- `step_output` 自动推导数据依赖。
- 步骤顺序调整后检测倒置依赖。
- 审阅保存执行乐观锁。
- 必填 pending 阻止应用。
- review revision 冲突阻止应用。
- 保存后重新生成 Canonical Plan。
- Secret 实际值不进入 Planner 输入和 ReviewPlan。

### 17.2 后端集成测试

固定场景：生成 SegmentCode，再发起 SSE 对话。

验证：

1. AI 选择两个接口并生成正确顺序。
2. 第二步 `segment_code` 引用第一步输出。
3. 环境中的 `username` 生成环境引用并自动确定。
4. 环境中的认证信息生成 Secret 或环境引用，不暴露值。
5. 无确定来源的 `question` 生成 AI 候选并待确认。
6. 修改 question 后保存成功。
7. 调整顺序导致依赖倒置时应用被阻止。
8. 恢复正确顺序并确认字段后可以应用。
9. 应用后的场景可由现有执行链路运行。

### 17.3 前端测试

- 每个步骤独立渲染一张卡片。
- 同一 endpoint 的两个步骤不会合并。
- 空请求分区不渲染。
- 默认只展开 pending 字段。
- 已自动确定字段可展开查看。
- 字段列只有字段、AI 建议、最终值和状态。
- 环境引用显示 key，不显示实际值。
- 最终值可以切换来源。
- 修改最终值后状态变为 confirmed。
- 确认本步骤只处理当前步骤。
- 全部确认跳过阻断字段。
- 拖动步骤后保存新顺序。
- 保存冲突时重新加载最新 ReviewPlan。
- 存在必填 pending 时应用按钮禁用。
- 保存进行中或失败时应用按钮禁用。
- 刷新页面后恢复人工修改内容。

## 18. 验收标准

### 18.1 功能验收

- 用户选择接口并提交后，AI 能分析接口顺序、依赖和字段 Mock。
- 两个接口生成任务最多调用模型两次。
- 生成任务在 90 秒内完成或明确失败。
- 每次接口调用独立显示为步骤卡片。
- 每张卡片按请求位置展示字段。
- 环境已有 `username` 时默认使用环境引用。
- AI 只为无法确定的字段生成候选值。
- 用户可以修改字段值和来源。
- 用户可以调整接口步骤顺序。
- 人工修改刷新后仍然存在。
- 所有必填待确认项处理后才能应用。
- 应用后生成的场景符合现有 Canonical Model 和运行时能力。

### 18.2 性能验收

- 创建任务接口在 500ms 内返回任务句柄，不包含模型耗时。
- 单个任务模型调用次数不超过 2。
- 本地规范化、校验和编译总耗时目标小于 1 秒。
- 同一进程最多并发执行 2 个 AI 编排任务。
- 前端字段编辑期间不进行逐键网络请求。

### 18.3 安全验收

- 模型输入、ReviewPlan、日志和前端响应均不包含 Secret 实际值。
- 用户不能通过审阅接口修改 endpoint ID、项目 ID 或不可编辑资产字段。
- 应用接口只使用服务端持久化的当前审阅版本。
- 过期、冲突或未确认 Plan 不能应用。

## 19. 实施顺序

1. 增加 ReviewPlan 后端 Schema 和数据库字段。
2. 实现 Planner 单次调用、一次 Repair 和调用预算。
3. 实现 ReviewPlan 规范化、字段确认和统一校验。
4. 将 AI 编排切换到应用级有界执行器。
5. 实现审阅保存接口和乐观锁。
6. 调整应用接口从持久化 ReviewPlan 编译和应用。
7. 更新前端 API 类型和 editor hook。
8. 将当前只读抽屉拆分为步骤卡片和字段编辑器。
9. 实现字段确认、来源切换、折叠和步骤排序。
10. 实现审阅自动保存、冲突恢复和应用门禁。
11. 补齐后端和前端自动化测试。
12. 使用固定 SSE 场景完成端到端验证。

## 20. 拒绝的方案

### 20.1 用户选择接口后不调用 AI

拒绝原因：接口顺序、依赖关系、字段映射和最佳 Mock 仍然需要 AI 语义分析。

### 20.2 保留 Agent，只增加超时

拒绝原因：超时只能限制损失，不能消除开放式 Agent 与确定性编排任务之间的逻辑错误。

### 20.3 前端直接编辑最终 ScenarioPlan

拒绝原因：暴露过多内部结构，前端需要理解 Binding、Extractor、Assertion 和编译约束，形成浅模块和契约漂移。

### 20.4 将所有字段放入全局待确认列表

拒绝原因：字段失去接口步骤和请求位置上下文，用户难以判断字段属于哪个请求。

### 20.5 同时展示当前值、来源、AI 建议、最终值、原因和置信度

拒绝原因：信息重复且增加判断负担。最终界面只保留字段、AI 建议、最终值和状态。

## 21. 最终架构

```text
候选接口与环境快照
        ↓
ApiScenarioPlanner
Planning 1 次 + Repair 最多 1 次
        ↓
PlannerProposal
        ↓
ReviewPlanNormalizer + Validator
        ↓
按步骤卡片人工审阅
        ↓
PUT ReviewPlan
        ↓
ReviewPlanCompiler
        ↓
Canonical Scenario Model V2
        ↓
应用到场景草稿
```

该架构保留 AI 对接口编排的核心价值，同时将模型调用、人工确认、字段来源和最终可执行结构分离。对用户而言，编排结果是按步骤组织、可以直接检查和修改的请求配置；对系统而言，AI 提案永远不能绕过服务端校验和人工确认直接执行。
