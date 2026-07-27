# 接口场景智能编排智能体设计

## 1. 设计原则

接口场景智能编排采用“模型规划、服务端编译、确定性执行”的分层架构：

1. AI 负责理解业务目标、检索接口资产、选择接口和提出数据依赖。
2. 确定性服务负责解析接口 Schema、生成依赖候选、补全参数来源和验证计划。
3. 用户负责确认写操作、敏感参数处理、未解决项和最终场景草稿。
4. 场景 DSL 是唯一事实源，画布和代码都是可重建的派生视图。
5. 真实环境值和密钥只在运行时解析，不进入模型上下文和计划正文。
6. 相同场景快照和 Renderer 版本必须生成相同代码产物。

```text
业务目标 / cURL / 用户输入
          ↓
输入解析和敏感字段分类
          ↓
资产检索工具 ← 接口槽位索引 / 依赖候选图
          ↓
AI 语义规划
          ↓
ScenarioPlan 强类型输出
          ↓
Plan Compiler 参数补全
          ↓
统一 Validator
          ↓
持久化预览 → 用户修订 → 应用场景草稿
                              ↓
                      确定性 Renderer
                              ↓
                 编译 / pytest collect / Dry Run
                              ↓
                         发布和执行
```

## 2. 领域边界

### 2.1 AI 可以决定的内容

- 业务目标需要哪些当前项目接口。
- 接口的建议调用顺序和阶段。
- 哪些响应字段可能是后续请求输入。
- 建议的响应提取器、业务断言和失败策略。
- 是否需要等待、轮询、条件或 cleanup 步骤。
- 哪些信息缺失，需要用户确认。

### 2.2 AI 不可以决定的内容

- 真实 base URL、Token、Cookie、密码和密钥值。
- 未导入项目资产的可执行 URL。
- 绕过写操作授权、环境权限或项目权限。
- 最终请求合并顺序和鉴权注入顺序。
- 可直接运行的 Python、Shell、JavaScript、SQL 或任意脚本。
- 是否自动发布或自动执行场景。

### 2.3 服务端负责的内容

- OpenAPI 输入输出槽位提取。
- 接口依赖候选计算和评分。
- cURL 结构化解析和敏感信息分类。
- 环境 Schema 投影和运行时 Secret 解析。
- Plan 编译、默认值补全、类型转换和稳定 ID 生成。
- 项目归属、资产版本、变量可达性和执行器兼容校验。
- 场景应用、代码渲染、编译检查和执行。

## 3. 接口资产标准化

### 3.1 Endpoint Asset View

原始 `ApiAutomationEndpoint` 继续作为资产事实源。编排模块构建只读的标准化视图：

```json
{
  "endpoint_id": "apiend-create-order",
  "asset_version": "sha256:7f42",
  "method": "POST",
  "path": "/orders",
  "operation_id": "createOrder",
  "summary": "创建订单",
  "description": "创建待支付订单",
  "tags": ["订单"],
  "side_effect": "write",
  "auth_profile": "merchant_token",
  "inputs": [],
  "outputs": [],
  "response_variants": [],
  "source_document_id": "apidoc-1"
}
```

`side_effect` 取值为 `read`、`write`、`delete` 或 `unknown`。HTTP 方法只作为默认判断，资产显式元数据可以覆盖默认值，但覆盖必须可审计。

### 3.2 输入槽位

每个请求字段转换为统一输入槽位：

```json
{
  "slot_id": "request:multipart:/segment_code",
  "location": "multipart",
  "path": "/segment_code",
  "name": "segment_code",
  "value_type": "string",
  "format": "",
  "required": true,
  "description": "会话片段编码",
  "default_value": null,
  "example_value": null,
  "sensitive": false
}
```

支持的 `location`：

- `path`
- `query`
- `header`
- `cookie`
- `json_body`
- `form`
- `multipart`
- `raw_body`

Body 内部路径统一使用 JSON Pointer。Header 名称在匹配时大小写不敏感，持久化时保留资产声明名称。

### 3.3 输出槽位

响应字段转换为统一输出槽位：

```json
{
  "slot_id": "response:200:json:$.data.order_id",
  "response_status": "200",
  "source": "json_body",
  "path": "$.data.order_id",
  "name": "order_id",
  "value_type": "string",
  "description": "订单 ID",
  "confidence": 1.0
}
```

支持的输出来源：

- `json_body`
- `header`
- `cookie`
- `text_regex`
- `sse_event_json`
- `status_code`

当 OpenAPI 响应 Schema 缺失时，可以从经过脱敏的示例响应、历史接口调试结构和测试用例断言生成低置信度候选，但不得将运行时业务数据直接写入资产视图。

### 3.4 依赖候选

服务端针对输出槽位和输入槽位生成候选边：

```json
{
  "producer_endpoint_id": "apiend-create-order",
  "producer_slot_id": "response:200:json:$.data.order_id",
  "consumer_endpoint_id": "apiend-get-order",
  "consumer_slot_id": "request:path:/order_id",
  "score": 0.96,
  "reasons": ["exact_normalized_name", "compatible_type", "path_identifier"],
  "source": "deterministic"
}
```

评分顺序：

1. OpenAPI Link 或显式资产关系。
2. 完全一致的标准化字段名和兼容类型。
3. 常见 ID 关系，例如 `id`、`order_id`、`orderId`。
4. Path 参数与资源创建响应的语义匹配。
5. 描述、标签和 operationId 的语义相似度。
6. 经过脱敏且结构稳定的历史运行轨迹。

低于自动绑定阈值的候选只能作为建议。多个高分候选无法唯一选择时必须生成未解决项。

## 4. 编排智能体工具

### 4.1 工具集合

智能体通过受控工具逐步获取信息：

- `search_endpoints(query, methods, tags, side_effects, limit)`
- `get_endpoint_detail(endpoint_id)`
- `get_dependency_candidates(producer_endpoint_ids, consumer_endpoint_ids)`
- `get_environment_schema(environment_id)`
- `get_existing_scenario(scenario_id)`
- `validate_plan_draft(plan)`

工具返回结果必须包含项目过滤、长度限制、资产版本和脱敏标志。智能体不能传入 project ID 改变查询边界，项目 ID 由服务端工具上下文固定。

### 4.2 规划过程

规划智能体遵循固定阶段：

1. 将业务目标拆分为业务动作、必要输入、预期结果和 cleanup 要求。
2. 搜索候选接口摘要。
3. 仅读取实际需要的接口详情。
4. 查询候选接口之间的确定性依赖关系。
5. 选择调用顺序和阶段。
6. 为无法确定的参数选择用户输入、环境引用或未解决项。
7. 输出强类型 `ScenarioPlan`。
8. 调用 `validate_plan_draft` 获取错误。
9. 只允许针对 Schema 错误和明确校验错误进行有限次数修正。

工具调用摘要可以审计，但不得保存完整敏感请求值。

## 5. 强类型 ScenarioPlan

### 5.1 Plan 顶层

```json
{
  "schema_version": 2,
  "graph_version": 1,
  "scenario_name": "创建订单并验证状态",
  "description": "使用测试用户创建订单并查询待支付状态",
  "inputs": [],
  "steps": [],
  "edges": [],
  "assumptions": [],
  "warnings": [],
  "unresolved_items": [],
  "confidence": 0.91
}
```

### 5.2 用户输入

```json
{
  "name": "question",
  "label": "提问内容",
  "value_type": "string",
  "required": true,
  "default_value": null,
  "sensitive": false,
  "description": "发送给智能体的问题"
}
```

用户输入属于场景定义，不属于环境。敏感用户输入在运行创建时提交并使用受保护存储，不写入普通运行快照。

### 5.3 参数目标

```json
{
  "location": "multipart",
  "path": "/segment_code"
}
```

目标必须对应接口资产中的输入槽位。只有服务端编译器可以在兼容迁移时创建资产中不存在的可选扩展字段，并产生警告。

### 5.4 参数来源

参数来源使用判别联合：

```json
{"type": "literal", "value": "web_share"}
```

```json
{"type": "user_input", "name": "question"}
```

```json
{"type": "environment", "key": "message_source"}
```

```json
{"type": "secret", "key": "cybertron_robot_token"}
```

```json
{"type": "scenario", "name": "tenant_id"}
```

```json
{
  "type": "step_output",
  "step_id": "generate_segment_code",
  "variable": "segment_code"
}
```

```json
{"type": "generated", "generator": "uuid4"}
```

生成器第一阶段仅允许 `uuid4`、`timestamp_ms`、`timestamp_iso` 和受限随机字符串，不接受任意表达式或代码。

### 5.5 绑定

```json
{
  "target": {
    "location": "multipart",
    "path": "/segment_code"
  },
  "source": {
    "type": "step_output",
    "step_id": "generate_segment_code",
    "variable": "segment_code"
  },
  "required": true,
  "transform": null
}
```

第一阶段 `transform` 只允许注册转换器，例如 `string`、`integer`、`json_encode` 和 `url_encode`，不允许脚本表达式。

### 5.6 提取器

JSON 响应提取：

```json
{
  "name": "segment_code",
  "source": "json_body",
  "path": "$.data.segment_code",
  "value_type": "string",
  "required": true,
  "sensitive": false
}
```

SSE 事件提取：

```json
{
  "name": "dialog_id",
  "source": "sse_event_json",
  "event": "message",
  "path": "$.data.dialog_id",
  "value_type": "string",
  "required": true,
  "sensitive": false
}
```

### 5.7 阶段和步骤

步骤阶段：

- `setup`：登录、初始化、准备数据。
- `main`：核心业务调用。
- `verify`：查询、轮询和结果断言。
- `cleanup`：删除或恢复测试数据。

步骤继续复用 `api_request`、`condition`、`wait`、`poll` 和 `assign`。每个步骤使用稳定 ID，显示名称变化不得影响引用。

## 6. 输入解析和环境安全

### 6.1 cURL 解析

用户粘贴 cURL 后，服务端使用结构化解析器提取：

- method 和 URL；
- path、query、header 和 cookie；
- JSON、urlencoded、multipart 和 raw body；
- 文件字段元数据；
- 可用于匹配接口资产的请求特征。

解析器先匹配当前项目接口资产，再构造候选参数。URL 仅用于匹配，匹配完成后 Plan 只保存 endpoint ID。

### 6.2 敏感字段分类

以下字段默认敏感：

- `Authorization`
- `Cookie` 和 `Set-Cookie`
- 名称包含 token、secret、password、passwd、api-key、robot-key、robot-token 的字段
- 环境鉴权配置声明的密钥字段

敏感值在进入模型前替换为引用：

```json
{
  "header": "cybertron-robot-token",
  "source": {"type": "secret", "key": "cybertron_robot_token"},
  "configured": true
}
```

模型只能看到 key、类型、是否已配置和用途描述。

### 6.3 环境投影

环境投影示例：

```json
{
  "environment_id": "apienv-test",
  "name": "测试环境",
  "base_url_configured": true,
  "auth_type": "cybertron_agent",
  "variables": [
    {"key": "message_source", "value_type": "string", "configured": true}
  ],
  "secrets": [
    {"key": "cybertron_robot_token", "configured": true}
  ]
}
```

环境投影不得包含 base URL 原文、变量值、默认 Header 值或认证值。

### 6.4 请求解析顺序

运行时按以下顺序构造请求：

1. 接口资产中的结构默认值。
2. 环境普通变量和默认 Header。
3. 场景变量和本次运行用户输入。
4. 步骤 literal 和 generated 参数。
5. 前序步骤输出绑定。
6. 服务端鉴权和 Secret 注入。

第 6 层为最终层。受保护鉴权字段不允许被前五层覆盖。缺少必填来源时必须在执行前失败，不得发送部分请求。

## 7. Plan Compiler

Plan Compiler 将 AI 语义计划转换为可执行场景草稿，主要步骤：

1. 将 endpoint ID 解析为当前资产版本。
2. 将语义参数目标解析为资产输入槽位。
3. 将依赖候选转换为提取器和 `step_output` 绑定。
4. 将环境字段转换为 environment 或 secret 引用。
5. 将用户提供的业务数据转换为 user_input 或 literal。
6. 补全稳定步骤 ID、阶段、step order 和解释性边。
7. 为请求步骤补全基础状态码断言。
8. 对 poll 步骤补全受限间隔、超时和最大次数。
9. 生成未解决项和字段级错误位置。
10. 计算资产、环境 Schema 和场景草稿指纹。

编译器不调用模型。相同输入必须产生相同规范化结果。

## 8. 统一验证

Validator 在生成、编辑、应用、发布和执行前复用，验证顺序如下：

1. Schema 版本和字段类型。
2. 项目权限和 endpoint 归属。
3. endpoint 资产版本和状态。
4. 节点 ID、边、顺序和无环性。
5. 参数目标是否存在于接口资产。
6. 所有必填输入是否存在来源。
7. 来源类型与目标类型是否兼容。
8. `step_output` 是否来自拓扑上游和已声明提取器。
9. 环境变量和 Secret key 是否存在且已配置。
10. 提取路径、断言和控制配置是否受执行器支持。
11. 写操作、删除操作和 cleanup 策略。
12. 任意 URL、代码、模板表达式和敏感明文扫描。
13. 场景修订号、草稿指纹和资产指纹冲突。

错误返回稳定位置：

```json
{
  "code": "SCENARIO_BINDING_SOURCE_MISSING",
  "message": "步骤 start_sse 引用了不存在的变量 segment_code",
  "step_id": "start_sse",
  "field_path": "/bindings/0/source/variable",
  "severity": "error"
}
```

`validation.valid=false` 的计划可以预览和编辑，但不能应用。

## 9. 异步生成和持久化

### 9.1 创建生成任务

```http
POST /projects/{project_id}/api-scenarios/ai-plan-runs
```

请求包含 goal、scenario_id、environment_id、source_scope、inputs 和 constraints。响应快速返回：

```json
{
  "run_id": "aiplanrun-1",
  "status": "queued",
  "stage": "queued"
}
```

### 9.2 查询进度

```http
GET /projects/{project_id}/api-scenarios/ai-plan-runs/{run_id}
```

阶段：

- `queued`
- `parsing_input`
- `retrieving_assets`
- `analyzing_dependencies`
- `planning`
- `compiling`
- `validating`
- `completed`
- `failed`
- `cancelled`

前端可以轮询或复用平台现有任务事件机制。断开后通过 run ID 恢复状态。

### 9.3 Plan 生命周期

Plan 状态：

- `preview`
- `invalid`
- `applied`
- `discarded`
- `expired`
- `superseded`

读取、编辑、重新校验、局部重新规划、应用和放弃均使用独立接口。Plan 必须保存 expected revision、draft hash、asset hash、environment schema hash、model、prompt version 和 compiler version。

## 10. 应用和代码生成

### 10.1 应用场景草稿

应用接口重新读取 Plan 和所有指纹，调用统一 Validator，然后复用现有步骤替换服务。应用结果始终为 draft，不自动发布、不自动执行。

### 10.2 确定性 Renderer

Renderer 输入为已验证场景快照，不读取自然语言 goal，也不再次调用模型。Renderer 负责生成：

- 场景测试文件；
- 场景输入定义；
- 环境和 Secret 运行时引用；
- 变量提取与绑定代码；
- 条件、等待、轮询和 cleanup 控制；
- 步骤级结果记录。

产物元数据：

```json
{
  "scenario_id": "apiscn-1",
  "scenario_revision": 4,
  "plan_id": "aiplan-1",
  "asset_hash": "sha256:asset",
  "environment_schema_hash": "sha256:env",
  "renderer_version": "scenario-pytest-v2",
  "source_hash": "sha256:source",
  "status": "current"
}
```

场景修订、接口资产或 Renderer 版本变化后，旧产物标记为 `stale`。执行入口只能使用 current 产物，或在运行前同步重新生成并验证。

### 10.3 代码验证

生成代码后依次执行：

1. 安全路径检查。
2. Python 编译检查。
3. pytest collect。
4. 敏感明文扫描。
5. 可选 Dry Run。

失败只更新代码产物状态，不回滚或覆盖场景草稿。

## 11. 前端体验

### 11.1 输入态

用户配置：

- 业务目标；
- 目标环境；
- 接口范围和标签；
- 用户输入参数；
- 可选 cURL；
- 是否允许写操作；
- 是否要求 cleanup；
- 最大步骤数和超时策略。

cURL 解析后显示字段分类和敏感引用，不显示完整密钥。

### 11.2 生成态

弹窗或工作区显示资产检索、依赖分析、规划、编译和校验阶段。生成超过普通请求时间时不阻塞页面，用户可以关闭后重新进入。

### 11.3 预览态

预览至少包含：

- 步骤顺序和 setup/main/verify/cleanup 阶段；
- 接口方法、路径摘要和资产来源；
- 依赖边和变量映射；
- 每个参数的来源徽标；
- 提取器、断言和失败策略；
- 假设、警告和未解决项；
- 字段级错误定位。

用户可以补充输入、切换参数来源、修改提取路径、重新校验和局部重新规划。只有校验通过时才能应用。

### 11.4 应用后

场景编辑器提供画布、步骤和代码三个视图。代码视图明确展示 current、generating、invalid 或 stale 状态。画布能力由 `add-api-scenario-ai-canvas` 提供；在其完成前使用增强线性依赖图预览。

## 12. 安全和审计

- Prompt、工具入参、工具结果、Plan、日志、运行快照和生成代码均执行敏感信息扫描。
- 模型上下文不包含真实密钥、Cookie、密码、完整 Authorization 和受保护 Header 值。
- 工具固定项目上下文，模型不能通过参数跨项目查询。
- 写操作和删除操作必须由请求约束允许，并在应用时再次确认。
- Plan 生成、编辑、应用、放弃、过期、代码生成和执行均记录审计事件。
- 审计记录保存引用 key、是否已配置和操作结果，不保存 Secret 值。

## 13. 失败处理

- 输入解析失败：返回字段级错误，不调用模型。
- 没有匹配接口资产：保留输入并提示调整资产范围或先导入文档。
- 模型超时：生成任务标记失败，场景草稿不变。
- 模型输出非法：有限重试后保存可诊断错误，不接受部分计划。
- 依赖不唯一：生成未解决项，不自动绑定。
- 环境变量缺失：计划可预览但不可应用或运行。
- 资产变化：Plan 标记 superseded，要求重新编译或重新规划。
- 场景冲突：应用返回 409，不静默覆盖。
- Renderer 失败：保留场景草稿，代码状态 invalid。

## 14. 迁移和兼容

- 历史 `bindings` 字符串格式在读取时迁移为强类型来源；无法迁移的记录返回校验错误，不猜测语义。
- 历史场景继续按 `step_order` 执行。
- 新 Plan 只能写入 Schema v2，不再产生松散绑定字典。
- 现有 `/api-scenarios/ai-plan` 可以在过渡期作为同步兼容入口，内部创建异步任务并等待受限时间；新前端使用 run API。
- 现有脚本生成和单接口脚本不受影响，场景 Renderer 使用独立产物类型。

## 15. 验证策略

- Schema：所有判别联合、路径格式、枚举和版本迁移。
- 资产：输入输出槽位、OpenAPI Link、multipart、SSE 和缺失 Schema。
- 依赖：精确匹配、多候选、类型冲突、后向引用和环。
- 安全：cURL 凭据、环境 Secret、Prompt、Plan、日志和代码扫描。
- 编译：用户输入、环境、Secret、场景变量、前序输出和生成值。
- API：异步状态、恢复、编辑、重新校验、局部重规划、应用和冲突。
- Renderer：稳定输出、stale 检测、编译、collect、Dry Run 和失败隔离。
- 前端：进度、刷新恢复、变量边、来源徽标、错误定位和窄屏布局。
- 兼容：历史线性场景、现有发布运行和版本恢复。
