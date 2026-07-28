# API 场景统一编排模型 V2 设计

**状态**：设计已确认，待实施

**日期**：2026-07-28

## 1. 背景

API 场景智能编排已经引入强类型 `ScenarioPlan`，支持 `literal`、`user_input`、`environment`、`secret`、`scenario`、`step_output` 和 `generated` 七类参数来源，并由确定性编译器补全接口依赖。

当前实现仍保留旧场景模型和旧校验链路，导致 AI 计划生成后被转换为普通场景步骤，再由只认识部分来源类型的旧校验器重复校验。实际案例中，由此产生以下问题：

- `secret` 和 `user_input` 被判定为不支持的变量来源；
- `form` 与 `multipart` 被视为不同目标，产生重复 Binding 和重复用户输入；
- 接口资产已经声明 `/data/segment_code`，但模型只获得槽位数量，生成了错误路径 `/segment_code`；
- 编译器只补充缺少的 Extractor，不校准已存在但错误的 Extractor；
- SSE 响应缺少结构化事件元数据时，无法生成稳定的事件提取和完成断言；
- unresolved 项同时进入 warnings 和 errors，造成重复展示；
- AI 计划校验、普通场景校验、前端校验和运行器分别维护来源规则，形成契约漂移。

本设计不要求兼容旧场景数据。发生模型冲突时允许删除旧草稿、旧 AI Plan 和不符合 V2 契约的场景步骤，不引入历史格式适配层。

## 2. 目标

- 建立唯一的 Canonical Scenario Model V2，贯穿 AI 生成、手工编辑、保存、发布、代码生成和运行。
- 只保留一套 ValueSource、ParameterTarget、Binding、Extractor、Assertion 和 Validation Issue 契约。
- 由确定性编译器负责接口路径、参数位置、依赖关系和敏感来源校准，模型不拥有可执行结构的最终决定权。
- 消除 `form`/`multipart` 重复绑定和同一参数的重复用户输入。
- 使用完整但脱敏的接口槽位投影，避免模型猜测 JSONPath。
- 将 SSE 支持建模为显式接口能力，而不是从普通 JSON Schema 或示例文本中猜测。
- 将 unresolved 改为结构化问题并分级，确保错误和警告不重复。
- 所有入口复用同一个编译与校验模块，避免规则复制。

## 3. 非目标

- 不迁移旧式字符串 Binding target。
- 不保留旧来源白名单或旧场景校验语义。
- 不通过兼容 Adapter 同时支持 V1 和 V2。
- 不要求 AI 解析完整 OpenAPI 或决定最终 JSON Pointer。
- 不从自由文本 SSE 示例自动推断完成协议。
- 不在本次设计中改变 API 请求执行器的网络协议和认证机制。

## 4. 设计原则

### 4.1 单一事实来源

后端强类型领域模型是场景契约的唯一事实来源。API Schema、编译器、校验器、Renderer 和前端类型均从该模型派生或保持机械一致，不再独立维护来源枚举。

### 4.2 AI 负责语义，服务端负责可执行性

AI 可以决定业务步骤、参数意图、依赖意图和断言意图。服务端必须决定：

- endpoint 是否真实存在；
- 参数目标对应哪个接口槽位；
- 最终 Content-Type 和参数位置；
- 输出字段的准确 JSON Pointer；
- Secret 是否存在并已配置；
- 依赖是否来自拓扑上游；
- 计划是否可以安全执行。

### 4.3 编译后只有一种表示

语义计划可以不完整，但 `PreparedScenarioPlan` 必须规范化、无重复、路径已校准并完成统一校验。保存和发布只能接受该表示。

### 4.4 不兼容优于双轨

旧数据可以删除，禁止为了保留历史格式继续维护两套来源、目标或校验协议。

## 5. Canonical Scenario Model V2

### 5.1 ValueSource

V2 仅支持以下判别联合：

```text
literal
user_input
environment
secret
scenario
step_output
generated
```

字段约束：

```json
{"type": "literal", "value": "web_share"}
{"type": "user_input", "name": "username"}
{"type": "environment", "key": "message_source"}
{"type": "secret", "key": "cybertron_robot_token"}
{"type": "scenario", "name": "tenant_id"}
{"type": "step_output", "step_id": "gen_segment_code", "variable": "segment_code"}
{"type": "generated", "generator": "uuid4"}
```

不再接受 `environment.name`、空类型、任意字典或其他别名。所有来源在进入编译器前必须通过判别联合解析。

### 5.2 ParameterTarget

参数目标使用结构化位置和 JSON Pointer：

```json
{
  "location": "multipart",
  "path": "/segment_code"
}
```

支持的位置：

```text
path
query
header
cookie
json_body
form
multipart
raw_body
```

旧式 `/request/multipart_form/segment_code` 字符串 target 不再接受。

### 5.3 Binding

```json
{
  "target": {
    "location": "multipart",
    "path": "/segment_code"
  },
  "source": {
    "type": "step_output",
    "step_id": "gen_segment_code",
    "variable": "segment_code"
  },
  "required": true
}
```

Binding 的规范唯一键为：

```text
(endpoint_id, canonical_location, path)
```

同一规范目标只能保留一个来源。

### 5.4 Extractor

Extractor 使用 JSON Pointer，不再混用 JSONPath：

```json
{
  "name": "segment_code",
  "source": "json_body",
  "path": "/data/segment_code",
  "value_type": "string",
  "required": true,
  "sensitive": false
}
```

SSE Extractor 额外要求 event：

```json
{
  "name": "answer",
  "source": "sse_event_json",
  "event": "message",
  "path": "/data/answer",
  "value_type": "string"
}
```

### 5.5 ValidationIssue

所有错误、警告和自动修正使用统一结构：

```json
{
  "code": "SSE_COMPLETION_UNKNOWN",
  "severity": "warning",
  "node_id": "multi_agent_sse",
  "field_path": "/nodes/1/assertions",
  "message": "接口资产未声明 SSE 完成条件。",
  "resolvable_by": "asset_configuration"
}
```

`severity` 仅允许：

- `error`：无法安全执行或请求结构无效；
- `warning`：可以执行，但覆盖或确定性不足；
- `info`：编译器完成了自动规范化或修正。

同一 issue code、node ID 和 field path 只允许出现一次。

## 6. 接口资产投影

### 6.1 模型可见投影

`endpoint_summary()` 不再只提供槽位数量。模型需要获得完整但脱敏的槽位结构：

```json
{
  "id": "apiend-5ba6a6e1fdf76150",
  "method": "POST",
  "path": "/openapi/v1/gw/multi-agent/segment-code/gen",
  "summary": "生成 SegmentCode",
  "request_slots": [
    {
      "name": "message_source",
      "location": "json_body",
      "path": "/message_source",
      "value_type": "string",
      "required": true,
      "sensitive": false
    }
  ],
  "response_slots": [
    {
      "name": "segment_code",
      "location": "json_body",
      "path": "/data/segment_code",
      "value_type": "string",
      "response_status": "200"
    }
  ]
}
```

敏感槽位可以暴露名称、位置、类型和是否已配置，但不得暴露值。

### 6.2 编译器资产视图

编译器继续使用完整 endpoint 资产，包括 parameters、request body、responses、content type 和可选 SSE 元数据。模型投影不能替代编译器核验。

## 7. 编译架构

### 7.1 唯一入口

新增或重构为唯一公开入口：

```python
prepare_scenario_plan(
    semantic_plan: ScenarioPlanResult,
    endpoints: list[EndpointAsset],
    environment_schema: EnvironmentSchemaProjection,
) -> PreparedScenarioPlan
```

调用方不得在该入口之外重复执行来源校验、目标校验、依赖补全或 unresolved 拼接。

### 7.2 编译阶段

编译器按固定顺序执行：

1. 强类型解析语义计划。
2. 校验 endpoint ID 和项目归属。
3. 将语义 target 匹配到真实 request slot。
4. 根据接口 Content-Type 规范化 target location。
5. 合并并解决同目标 Binding 冲突。
6. 为敏感槽位绑定 Secret。
7. 为普通必填槽位选择已有来源或创建 user input。
8. 使用 response slot 校准 Extractor。
9. 根据依赖候选创建 step output Binding 和图边。
10. 根据 SSE 能力补充事件提取和完成断言。
11. 补充基础状态码断言。
12. 运行统一 Validator。
13. 返回 PreparedScenarioPlan 和结构化 issues。

相同输入必须产生相同输出。

## 8. 参数位置归一化

### 8.1 规则

语义位置必须根据 endpoint 的真实请求体 Content-Type 归一化：

| Content-Type | 输入位置 | 规范位置 |
|---|---|---|
| `multipart/form-data` | `form` | `multipart` |
| `multipart/form-data` | `multipart` | `multipart` |
| `application/x-www-form-urlencoded` | `form` | `form` |
| `application/x-www-form-urlencoded` | `multipart` | `form` |
| `application/json` | `json_body` | `json_body` |

无法匹配 endpoint slot 的位置产生 `SCENARIO_TARGET_NOT_FOUND` 错误。

### 8.2 冲突优先级

同一规范目标存在多个来源时：

1. 完全相同来源自动去重。
2. 敏感槽位只允许 `secret`，其他来源产生错误。
3. `step_output` 优先于同目标 `user_input`，并记录 info issue。
4. endpoint 已配置环境变量时，显式用户来源优先于编译器自动补充的 environment 来源。
5. 无法确定唯一来源时产生阻断错误，不静默覆盖。

## 9. Extractor 校准

### 9.1 匹配规则

编译器根据 Extractor 的语义名称、来源类型和值类型匹配 response slot：

1. 名称完全匹配；
2. location 匹配；
3. value type 兼容；
4. 成功状态码优先；
5. 只有唯一最高分候选时自动校准。

### 9.2 自动修正

如果模型生成：

```json
{"name": "segment_code", "source": "json_body", "path": "/segment_code"}
```

而接口资产唯一匹配为 `/data/segment_code`，编译器必须覆盖模型路径并输出：

```json
{"name": "segment_code", "source": "json_body", "path": "/data/segment_code"}
```

同时产生 `EXTRACTOR_PATH_NORMALIZED` info issue。不得保留已知错误路径。

多个候选或无候选时产生结构化 unresolved issue。

## 10. SSE 能力模型

### 10.1 接口资产扩展

接口资产允许声明：

```json
{
  "sse": {
    "event_name": "message",
    "data_format": "json",
    "completion": {
      "path": "/data/finish",
      "operator": "equals",
      "expected": "y"
    },
    "fields": [
      {
        "name": "answer",
        "path": "/data/answer",
        "value_type": "string"
      }
    ]
  }
}
```

### 10.2 缺失能力的行为

SSE 元数据缺失时：

- 请求步骤仍可生成和执行；
- 保留状态码或连接建立断言；
- 不生成猜测性的事件字段断言；
- 输出 `SSE_SCHEMA_MISSING` 或 `SSE_COMPLETION_UNKNOWN` warning；
- 不因缺少业务级 SSE 断言将整个计划标记为无效。

只有执行器完全不支持 SSE 协议时才产生阻断错误。

## 11. 统一校验

Validator 是纯函数，输入 PreparedScenarioPlan、endpoint 资产和环境投影，输出去重后的 ValidationIssue 列表。

校验内容：

1. Schema 版本和强类型字段。
2. endpoint 存在性和项目归属。
3. 节点 ID 唯一性和图无环性。
4. 规范 target 是否存在于 endpoint request slot。
5. 同一 target 是否只有一个 Binding。
6. ValueSource 字段是否完整。
7. user input 是否存在于 plan inputs。
8. environment key 是否存在。
9. secret key 是否存在并已配置。
10. scenario variable 是否声明。
11. step output 是否来自拓扑上游真实输出。
12. generated 配置是否合法。
13. Extractor 是否对应真实 response slot 或已声明 SSE 字段。
14. Assertion 是否受当前执行器支持。
15. 是否包含可执行 URL、敏感明文或非法模板表达式。

生成预览、手工保存、发布、代码生成和执行前必须复用同一个 Validator。

## 12. 输入和 unresolved 语义

### 12.1 用户输入

缺少运行值不等于计划结构错误。以下情况应保留有效计划：

- user input 已声明但没有默认值；
- 用户需要在运行前填写 username、question 或 data；
- SSE 业务内容属于运行时输入。

运行前缺值由 preflight 返回 `INPUT_VALUE_REQUIRED`，不得在计划生成阶段写成泛化的“未解决”错误。

### 12.2 阻断条件

以下情况才使 `validation.valid=false`：

- 参数没有任何来源且也未声明 user input；
- Secret key 不存在或未配置；
- target 不属于 endpoint；
- step output 引用不存在、来自后续步骤或变量不存在；
- Binding 冲突无法确定唯一来源；
- Extractor 无法映射且后续步骤依赖该输出；
- 执行器不支持计划要求的协议或断言。

## 13. 前端设计

### 13.1 类型和渲染

前端使用与后端 V2 一致的判别联合，不再通过独立字符串数组判断来源是否合法。

来源显示：

- user input：显示输入名称和默认值状态；
- environment：显示环境变量 key；
- secret：只显示 key 和已配置状态；
- step output：显示步骤名称和变量；
- generated：显示生成器类型。

### 13.2 问题展示

按 severity 分区展示 issues。相同 issue 不得在错误和警告区域重复出现。

需要运行时填写的 input 显示在“待填写输入”区域，不计入错误数量。

### 13.3 编辑限制

前端可以编辑语义来源，但保存时必须提交结构化 V2 Binding。禁止生成旧式字符串 target。

## 14. 持久化和删除策略

### 14.1 Schema 版本

场景和 AI Plan 保存 `schema_version=2`。服务端拒绝保存其他版本。

### 14.2 删除范围

实施期间允许删除：

- `api_scenario_ai_plans` 中所有 V1 或缺少 V2 schema version 的计划；
- 使用旧式字符串 target 的场景步骤；
- 含有不受 V2 支持来源结构的草稿场景；
- 当前已知失败计划 `aiplan-0ed16a34cfa994a9`；
- 为排查问题生成的重复草稿。

保留：

- API 文档；
- endpoint 资产；
- API 环境及其加密凭据；
- 与场景编排无关的接口测试用例和运行记录。

删除动作必须限定表和项目范围，执行前输出待删除记录数量并在事务中完成。

## 15. 服务接口行为

### 15.1 生成计划

生成接口返回 PreparedScenarioPlan，不再返回未经编译的 Binding 或重复拼接的 validation：

```json
{
  "plan_id": "aiplan-...",
  "schema_version": 2,
  "compiler_version": 2,
  "plan": {},
  "issues": [],
  "valid": true
}
```

### 15.2 应用计划

应用时只验证：

- plan 未过期；
- scenario revision 未变化；
- asset fingerprint 未变化；
- environment schema fingerprint 未变化；
- PreparedScenarioPlan 仍通过统一 Validator。

不得再次转换为旧步骤结构并调用旧校验器。

### 15.3 保存和发布

手工保存和发布均调用与 AI Plan 相同的 prepare/validate 流程。发布产物保存规范化后的 V2 snapshot。

## 16. 安全设计

- 用户 cURL 中的敏感值在进入模型和计划持久化前替换为 secret key 引用。
- 模型只看到环境 key、类型和 configured 状态。
- secret Binding 不包含明文值。
- 敏感 endpoint slot 不允许 user input、literal、scenario 或 step output 覆盖。
- issue message 不回显敏感值。
- 计划日志和审计日志使用脱敏 goal。

## 17. 可观测性

每次计划准备记录：

- plan ID；
- schema version；
- compiler version；
- endpoint asset fingerprint；
- environment schema fingerprint；
- 自动添加 Binding 数量；
- 去重 Binding 数量；
- 自动修正 Extractor 数量；
- error、warning、info 数量；
- 编译耗时。

日志只记录 key 和路径，不记录用户输入值、环境值或 Secret。

## 18. 实施边界

主要修改区域：

- `apps/backend/app/agents/api_automation/orchestration/schemas.py`
- `apps/backend/app/services/api_automation/orchestration_asset_analysis.py`
- `apps/backend/app/services/api_automation/orchestration_compiler.py`
- `apps/backend/app/services/api_automation/service.py`
- `apps/backend/app/schemas/api_automation.py`
- `apps/backend/app/agents/api_automation/pytest_requests/renderer.py`
- `apps/frontend/src/components/ai-testing/api-automation/api-scenario-model.mjs`
- `apps/frontend/src/components/ai-testing/api-automation/use-api-scenario-editor.ts`
- `apps/frontend/src/components/ai-testing/api-automation/api-scenario-editor.tsx`

旧 `_validate_scenario_source()`、重复 AI Plan 二次校验和旧 target 转换逻辑应删除，而不是继续扩展。

## 19. 验证策略

### 19.1 单元测试

- 七类 ValueSource 均能解析和序列化。
- 不合法来源和缺失字段被强类型模型拒绝。
- form/multipart 按 Content-Type 归一化。
- 同目标重复 Binding 被去重。
- step output 优先于编译器补充的 user input。
- 敏感 target 只接受 secret。
- `/segment_code` 被校准为 `/data/segment_code`。
- 多个响应候选时产生结构化 issue。
- unresolved issue 去重并保持单一 severity。

### 19.2 集成测试

- AI 计划生成后不再进入旧校验器。
- 包含 secret 和 user input 的计划可以应用。
- 应用后场景保存、发布和生成代码使用同一 V2 数据。
- 用户输入无默认值时计划有效，运行前 preflight 阻止缺值执行。
- SSE 无元数据时计划有效并产生 warning。
- SSE 有元数据时生成事件提取器和完成断言。
- asset fingerprint 或环境 Schema 变化时拒绝应用旧计划。

### 19.3 回归场景

使用“生成 SegmentCode，再发起 Multi-Agent SSE 对话”作为固定回归案例，预期：

- 两个步骤；
- 第一步两个 secret header Binding；
- 第一步一个 message_source Binding；
- 第一步 Extractor 路径为 `/data/segment_code`；
- 第二步只有一组 multipart 参数 Binding；
- segment_code 来源为第一步 step output；
- message_source、username 和 data 各只有一个 user input；
- 不生成重复 `data` 和 `data_json`；
- SSE 元数据缺失时只有 warning；
- validation errors 为 0；
- issue 列表没有重复项。

### 19.4 代码生成验证

- Renderer 能解析七类来源。
- 生成代码不包含 Secret 明文。
- multipart 请求只写入一组字段。
- Extractor 从 `/data/segment_code` 获得真实值。
- 缺少运行时 input 时在发送请求前失败。

## 20. 验收标准

- 同一来源和目标契约不再在多个模块独立定义。
- AI 计划生成、场景保存、发布、代码生成和执行使用同一个 Validator。
- 目标接口场景生成后错误数量为 0。
- `secret`、`user_input` 和 `generated` 不再被判为不支持。
- `form`/`multipart` 不产生重复 Binding。
- `segment_code` 提取路径稳定为 `/data/segment_code`。
- 缺少 SSE 业务 Schema 只产生单条 warning。
- unresolved、warning 和 error 不重复展示。
- 全部编排专项测试和新增端到端测试通过。

## 21. 风险与控制

### 数据删除风险

删除语句必须按 schema version 和明确表范围执行，先统计后删除，并使用事务。不得删除 endpoint、环境和接口文档。

### 前后端切换风险

后端 V2 API 和前端 V2 类型必须在同一次发布中切换，避免前端发送旧 target。

### SSE 资产不足

V2 不尝试猜测事件协议。资产未配置时保持可执行但降低断言覆盖，并通过 warning 明确提示。

### 模型输出不稳定

模型输出始终经过强类型解析、资产校准和统一校验。模型不能直接生成可保存或可执行的最终场景。

## 22. 后续实施顺序

1. 固化 V2 强类型模型和 ValidationIssue。
2. 重构接口资产槽位投影。
3. 实现 target 归一化、Binding 去重和 Extractor 校准。
4. 建立唯一 prepare/validate 入口。
5. 切换 AI Plan 生成与应用链路。
6. 切换手工保存、发布和 Renderer。
7. 切换前端类型与问题展示。
8. 删除旧校验和旧 target 支持。
9. 清理冲突数据。
10. 完成端到端回归验证。
