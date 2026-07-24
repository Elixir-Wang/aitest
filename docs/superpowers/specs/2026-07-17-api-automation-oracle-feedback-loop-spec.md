# 接口自动化用例 Oracle 反馈闭环 Spec

## 1. 背景

当前接口资产生成接口自动化用例时，模型同时承担测试点识别、用例数量决策、请求数据构造和预期断言生成。由于 OpenAPI 经常只描述成功响应，未描述负向输入与错误响应的映射，模型会在“覆盖完整性”和“预期可执行性”之间自行取舍，导致同一接口的生成数量不稳定，并且可能出现重复用例、错误状态码和请求语义不一致。

本方案将“测试点覆盖”和“Oracle 准确性”解耦：

- 测试点只要有事实依据，就完整生成并允许执行；
- 预期不确定时，执行真实请求并采集响应，不直接丢弃测试点；
- 系统根据实际响应生成预期修正建议；
- 只有人工审批通过后，才更新正式测试用例、接口资产和接口自动化用例。

## 2. 目标

### 2.1 必须实现

1. 同一接口在相同资产输入下，测试点集合稳定，不由模型自由决定数量。
2. 不因缺少错误状态码、业务错误码或错误消息而丢弃有事实依据的负向场景。
3. `inferred` 和 `needs_confirmation` 用例均可执行。
4. `needs_confirmation` 用例只采集真实响应，不因缺少可靠预期直接判定失败。
5. 执行完成后，系统可以基于请求、预期、实际响应和错误信息生成校准建议。
6. 人工审批后，建议可以版本化更新到：
   - 接口自动化测试用例；
   - 接口资产的响应或约束信息；
   - 后续用例生成所使用的历史事实。
7. 所有自动更新必须可追溯、可回滚，不能静默覆盖原始资产。

### 2.2 不在本期范围

- 自动修改生产接口实现；
- 自动将单次响应直接视为永久接口契约；
- 自动审批 AI 的推断结果；
- 跨多个接口的业务链路推断；
- 压测、并发、限流、超时和稳定性专项 Oracle 推断；
- 根据一次异常响应自动删除测试点。

## 3. 核心原则

### 3.1 覆盖优先，判定分级

测试点是否生成由接口事实和测试点规划器决定；是否可以直接判定通过由 Oracle 状态决定。

### 3.2 执行和判定分离

所有生成用例都可以进入执行器，但执行结果必须区分：

- 有可靠预期时进行通过/失败判定；
- 无可靠预期时进行响应观测，不伪造失败结论。

### 3.3 推断不等于事实

规则推断、模型推断和真实响应必须分别记录，不能把推断结果写入接口事实来源后冒充 OpenAPI 声明。

### 3.4 人工审批是契约变更闸门

执行结果只能产生“变更建议”，不能直接修改正式用例和接口资产。审批通过后生成新的用例版本和资产版本。

### 3.5 一次只改变一个测试变量

负向和边界用例保持合法基线，只改变当前测试目标，确保实际响应可以归因到单个测试点。

## 4. 总体架构

```text
OpenAPI / 环境 / 历史事实
          |
          v
  确定性测试点规划器
          |
          v
  测试点覆盖矩阵
          |
          v
  LLM 用例内容生成器
          |
          v
  用例结构校验与去重
          |
          v
  接口自动化用例资产
          |
          v
  统一执行器
          |
          v
  执行记录 + 实际响应 + 错误证据
          |
          v
  Oracle 推断器
          |
          v
  人工审批建议
      |           |
      | 驳回      | 通过
      v           v
  保留原版本   创建新版本并回写资产
```

## 5. 状态模型

### 5.1 `oracle_status`

数据库只新增一个 Oracle 状态字段，字段名为 `oracle_status`。

```text
confirmed
inferred
needs_confirmation
```

#### `confirmed`

预期来自以下至少一种可靠事实：

- OpenAPI 明确声明；
- 已审批的接口资产事实；
- 已审批的历史执行结果；
- 用户明确提供的接口契约；
- 稳定且已审批的业务规则。

执行行为：

- 默认执行；
- 按断言判定通过或失败；
- 失败可进入 Oracle 校准流程。

#### `inferred`

用例具有完整可执行请求和可执行断言，但断言至少部分来自规则或模型推断，尚未被人工确认。

执行行为：

- 默认执行；
- 可判定通过或失败；
- 页面和报告必须显示“预期待校准”；
- 失败时优先生成校准建议，而不是直接认为接口资产错误。

#### `needs_confirmation`

测试点和请求有事实依据，但无法形成可靠的预期断言。例如接口只声明通用 `404`，没有说明缺字段、错误日期或鉴权失败是否触发该状态码。

执行行为：

- 默认执行；
- 记录真实响应、响应体、响应头和执行错误；
- 观察证据写入运行摘要，不覆盖测试运行的通过或失败状态；
- 执行完成后生成审批建议。

### 5.2 执行结果状态

执行结果不放入 `oracle_status`，使用运行记录已有的执行状态语义扩展：

```text
passed
failed
blocked
error
```

- `passed`：测试执行完成且断言全部通过；观察证据作为附加摘要保留。
- `failed`：测试执行存在失败断言。
- `blocked`：执行前置条件不足，例如环境不可用或缺少必要数据。
- `error`：执行器自身异常，例如网络错误、解析错误或脚本异常。

历史数据中的 `observed` 状态按 `passed` 兼容展示。

### 5.3 审批状态

Oracle 推断建议使用独立的建议记录表达审批生命周期，不复用 `oracle_status`：

```text
pending
approved
rejected
superseded
```

审批通过后，正式用例创建新版本，并将新版本的 `oracle_status` 更新为 `confirmed`。

## 6. 生成流程

### 6.1 阶段一：确定性测试点规划

规划器根据 endpoint 资产生成测试点集合，不调用 LLM 决定数量。

规划维度包括：

1. 成功基线：最小合法请求、增加可选字段后的完整请求。
2. required 字段：每个 required 字段分别缺失。
3. 空值语义：空字符串、空白、`null`、空对象、空数组，依据字段类型和 nullable 语义决定。
4. 类型和格式：类型错误、格式错误、枚举非法值、约束边界。
5. 字段关系：日期相等、起止颠倒、上下限关系、互斥和依赖。
6. requestBody：请求体不发送、空对象、空内容，必须区分执行语义。
7. 鉴权：每个可真实覆盖的 required 鉴权字段分别生成空值场景；如果执行器不能删除默认 Header，则不得生成伪造的“缺失 Header”场景。
8. 响应契约：只对资产明确声明或已审批的响应结构生成强断言。
9. 未声明字段和 Content-Type：只有执行器能准确表达且资产具有事实依据时生成。
10. 文件上传、下载、分页、查询和数据影响：仅在 endpoint 事实适用时生成。

规划器输出稳定的 `test_point_key`，例如：

```text
body.required.start_date.missing
body.required.end_date.missing
body.date_relation.start_after_end
header.required.cybertron-robot-key.empty
request_body.missing
success.minimum_valid
```

### 6.2 阶段二：LLM 内容生成

LLM 只负责根据测试点生成：

- 用例标题和描述；
- 合法或错误 Mock 数据；
- 请求表达；
- 断言建议；
- `generation_notes`；
- `oracle_status` 初始值。

LLM 不得：

- 删除规划器输出的测试点；
- 合并不同 `test_point_key`；
- 自行决定覆盖数量；
- 用随机 400/401/403/404 替代缺失事实而不标记推断；
- 生成与执行器语义不一致的请求体缺失或 Header 缺失场景。

### 6.3 阶段三：结构校验和去重

后端必须校验：

1. 每个规划测试点都有且只有一个主用例，除非规则明确允许多数据变体。
2. `test_point_key` 不同的用例不能仅因标题不同而被合并。
3. 相同 `test_point_key` 的重复用例必须被拒绝或合并。
4. 最小合法请求和完整合法请求字段集合相同时，只保留一个成功基线。
5. 标题描述与请求变化一致。
6. `requestBody` 缺失必须真实表达为无 body，而不是 `{}`。
7. 鉴权 Header 空值必须真实覆盖目标 Header。
8. 每条可判定用例至少有一个状态码或明确业务断言。
9. `needs_confirmation` 可以只有响应观测配置，但必须标记默认执行模式为观察执行。
10. `summary` 数量必须等于实际用例数量。

### 6.4 阶段四：落库

只有结构校验通过后，才创建接口自动化测试用例。

落库时保存：

- `test_point_key`；
- `oracle_status`；
- 原始生成来源；
- 测试点规划来源；
- 断言来源和置信说明；
- 生成批次、生成尝试和模型信息。

## 7. 执行流程

### 7.1 执行前

执行器根据 `oracle_status` 选择判定策略：

```text
confirmed             -> assertion mode
inferred              -> assertion mode + calibration warning
needs_confirmation    -> observation mode
```

所有模式都发送真实请求，区别只在结果判定方式。

### 7.2 `needs_confirmation` 的观察执行

观察执行必须采集：

- HTTP 状态码；
- 响应头；
- 响应体摘要和脱敏原文；
- 请求实际发送快照；
- 执行器异常信息；
- 环境、接口版本和用例版本；
- 请求与响应时间。

观察执行不能把“实际返回 400”自动解释成“正式预期就是 400”，只能生成建议。

### 7.3 安全与脱敏

执行证据不得持久化：

- 明文 Token；
- Cookie；
- 密码；
- 私钥；
- 环境变量中的敏感值。

响应体中的敏感字段需要按字段名、配置规则和已有脱敏策略处理。

## 8. Oracle 推断流程

### 8.1 输入

Oracle 推断器接收：

- endpoint 当前资产；
- 用例测试点和请求快照；
- 原始断言或空断言；
- 实际执行响应；
- 执行错误；
- 历史同类用例和审批事实；
- 当前接口版本。

### 8.2 输出

推断器不直接修改正式资产，只生成 `OracleProposal`：

```json
{
  "case_id": "apitc-xxx",
  "test_point_key": "body.required.start_date.missing",
  "current_oracle_status": "needs_confirmation",
  "proposed_status": "confirmed",
  "proposed_assertions": [
    {
      "type": "status_code",
      "path": "",
      "expected": 400
    }
  ],
  "asset_updates": [],
  "reasoning": "实际响应稳定返回 HTTP 400，响应体包含字段校验错误信息。",
  "evidence_run_ids": ["apirun-xxx"],
  "confidence": 0.96,
  "risk_level": "medium"
}
```

### 8.3 建议生成规则

1. 单次异常响应只生成建议，不自动固化。
2. 状态码建议必须来自实际响应或已确认事实，不能只来自常见 REST 约定。
3. 业务错误码建议必须来自稳定响应字段，不能从错误文案臆造。
4. 多次执行结果一致时，提高建议置信度，但仍需要人工审批。
5. 同一测试点出现多个响应结果时，建议拆分条件或标记为业务依赖不稳定。
6. 网络错误、超时、5xx 基础设施错误不得直接用于更新业务 Oracle。
7. 建议必须列出证据运行记录和变更前后差异。

## 9. 人工审批流程

### 9.1 审批页面

审批页需要展示：

- 测试点和用例标题；
- 当前 `oracle_status`；
- 当前请求和断言；
- 实际响应；
- AI 建议的断言变化；
- 推断依据和置信度；
- 关联执行记录；
- 接口资产是否会被同步修改；
- 更新前后 Diff。

### 9.2 审批动作

#### 通过

- 创建新的用例版本；
- 将新版本 `oracle_status` 设为 `confirmed`；
- 更新正式接口自动化用例；
- 按审批范围更新接口资产响应或约束；
- 保留原版本和审批记录。

#### 驳回

- 保留当前用例和执行证据；
- 不修改正式断言和接口资产；
- 记录驳回原因；
- 可将用例保持为 `inferred` 或 `needs_confirmation`。

#### 仅更新用例

- 更新测试用例断言；
- 不修改 OpenAPI 接口资产；
- 适用于仅用于测试的预期，不足以成为公共接口契约的场景。

#### 更新接口资产并同步用例

- 创建新接口资产版本；
- 将已审批的响应或约束写回接口资产；
- 重新计算受影响测试点；
- 只更新受影响用例，其他用例保持原版本。

## 10. 数据模型变更

### 10.1 `api_test_cases`

新增字段：

```text
test_point_key TEXT NOT NULL DEFAULT ''
oracle_status TEXT NOT NULL DEFAULT 'confirmed'
```

约束：

- `test_point_key` 在同一生成批次和 endpoint 内唯一；
- `oracle_status` 只能是 `confirmed`、`inferred`、`needs_confirmation`；
- 旧数据默认迁移为 `confirmed`，并通过历史规则标记迁移来源。

### 10.2 `api_test_case_versions`

如果当前版本表不存在，需要新增版本表，保存：

- 用例 ID；
- 版本号；
- 请求快照；
- 断言快照；
- `oracle_status`；
- 生成来源；
- 变更原因；
- 创建人和创建时间。

### 10.3 `api_oracle_proposals`

建议字段：

```text
id
project_id
endpoint_id
case_id
case_version
test_point_key
status
current_snapshot_json
proposed_snapshot_json
asset_updates_json
reasoning
confidence
risk_level
evidence_run_ids_json
review_comment
reviewed_by
reviewed_at
created_at
updated_at
```

### 10.4 接口资产版本

接口资产更新必须保留版本。审批通过后，不能直接覆盖原始 OpenAPI 导入快照，应区分：

- 原始文档事实；
- 已审批运行事实；
- 当前生成视图。

## 11. API 契约

### 11.1 查询用例 Oracle 状态

```http
GET /projects/{project_id}/api-test-cases/{case_id}/oracle
```

返回当前 Oracle 状态、断言来源、最近执行结果和待审批建议。

### 11.2 生成 Oracle 建议

```http
POST /projects/{project_id}/api-test-cases/{case_id}/oracle-proposals
```

仅基于已有执行记录生成建议，不直接修改正式数据。

### 11.3 查询审批建议

```http
GET /projects/{project_id}/oracle-proposals
```

支持按 `pending`、endpoint、用例、风险等级和 `oracle_status` 筛选。

### 11.4 审批建议

```http
POST /projects/{project_id}/oracle-proposals/{proposal_id}/approve
POST /projects/{project_id}/oracle-proposals/{proposal_id}/reject
```

审批请求必须携带：

- 审批意见；
- 更新范围：`case_only` 或 `case_and_endpoint_asset`；
- 可选的人工修正断言。

### 11.5 重新生成受影响用例

```http
POST /projects/{project_id}/api-test-cases/{case_id}/reconcile
```

用于审批后重新应用接口资产事实，不能重新随机生成不相关用例。

## 12. 生成器重构边界

### 12.1 确定性模块

新增或抽取 `ApiTestPointPlanner`，职责包括：

- 解析 endpoint；
- 生成 `test_point_key`；
- 计算适用测试点；
- 定义请求变化；
- 定义初始 Oracle 状态；
- 做测试点完整性校验。

该模块不得依赖 LLM。

### 12.2 LLM 模块

现有生成 Agent 改为接收测试点计划，输出每个测试点的内容，不再输出自由数量的 cases。

如果 LLM 缺失测试点、重复测试点或修改测试点 key，后端必须拒绝该批次或进入可修复重试，不得静默落库。

### 12.3 执行模块

执行器增加 `assertion_mode` 和 `observation_mode`：

- `assertion_mode` 执行断言并生成 `passed/failed`；
- `observation_mode` 保存实际响应，但不覆盖 pytest 生成的 `passed/failed` 状态。

### 12.4 推断模块

新增独立 Oracle 推断服务，不能嵌入执行器，也不能直接写入接口资产。

## 13. 兼容策略

1. 旧接口自动化用例没有 `oracle_status` 时默认迁移为 `confirmed`。
2. 旧用例没有 `test_point_key` 时生成稳定兼容 key：

```text
legacy.<case_id>
```

3. 旧执行器不认识 `needs_confirmation` 时，后端适配层将其转换为观察执行模式。
4. 旧接口自动化脚本保持可执行，不强制一次性重生成全部项目资产。
5. 审批前不修改已有用例和接口资产。
6. 回写接口资产时生成新版本，旧 OpenAPI 原始快照只读保留。

## 14. 验收标准

### 14.1 生成完整性

- 对 `/openapi/v1/agent/analysis/`，规划器能够稳定识别最小成功、required 字段分别缺失、日期格式、日期关系、请求体缺失、鉴权空值等测试点。
- 最小请求与完整请求字段集合相同时，不生成重复成功用例。
- 同一输入重复生成时，`test_point_key` 集合一致。
- 模型输出少于规划测试点时，任务失败或进入补齐流程，不能成功落库为不完整批次。

### 14.2 执行完整性

- `confirmed` 和 `inferred` 用例可以正常执行并产生断言结果。
- `needs_confirmation` 用例可以正常发送请求并产生 `observed` 结果。
- `needs_confirmation` 不会因为缺少可靠断言被判定为失败。
- 请求体不发送和空对象可以被执行器区分。

### 14.3 推断和审批

- 执行结果可以生成 Oracle 建议，但不会直接修改正式用例。
- 审批通过后生成新版本，原版本仍可查看和回滚。
- `case_only` 审批不会修改接口资产。
- `case_and_endpoint_asset` 审批会创建接口资产新版本，并只影响关联测试点。
- 驳回后正式断言和接口资产不发生变化。

### 14.4 安全和审计

- 生成日志、执行快照、推断建议和审批记录均可追溯到项目、接口、用例、版本和执行记录。
- 敏感 Header、Token、Cookie 和密码不进入持久化证据。
- 所有资产回写均有变更前后 Diff。

## 15. 分阶段实施建议

### Phase 1：生成稳定性

- 实现 `test_point_key` 和确定性规划器；
- 改造 LLM 输入为测试点计划；
- 增加覆盖完整性校验和重复检测；
- 增加 `oracle_status` 字段。

### Phase 2：观察执行

- 支持 `needs_confirmation` 的 observation mode；
- 保存实际响应和脱敏执行证据；
- 增加 `observed` 执行结果。

### Phase 3：Oracle 建议

- 增加推断服务和建议记录；
- 根据多次执行结果生成稳定性、置信度和风险等级。

### Phase 4：人工审批和资产回写

- 增加审批页面和 API；
- 支持仅更新用例、更新用例并回写接口资产；
- 增加版本、Diff 和回滚。

### Phase 5：历史事实沉淀

- 将已审批响应映射和字段规则加入生成事实库；
- 后续生成时优先使用已审批事实；
- 用回归测试验证接口用例数量和测试点集合不再回退。

## 16. 最终实现决策（2026-07-17）

- 测试点数量由纯规则规划器根据 OpenAPI 字段、请求体、日期关系和可执行鉴权 Header 确定，LLM 只能补全每个测试点的请求与说明，不能删减、合并或新增 key。
- `oracle_status` 保持单字段三态：`confirmed`、`inferred`、`needs_confirmation`；三种状态均可执行，不再设置生成或执行门禁。
- `inferred` 执行当前推断断言并保存脱敏观察，`needs_confirmation` 发送真实请求并保存观察证据；存在观察证据且 pytest 无失败时，运行状态仍为 `passed`。
- 生成的 pytest + requests 项目通过 `API_OBSERVATION_RESULT_PATH` 写入观察结果，使用跨进程文件锁、锁内合并和原子替换，且对响应 Header 与 Body 进行敏感信息脱敏。
- 运行完成后，系统自动为 `inferred` 和 `needs_confirmation` 用例创建待审批 Oracle 建议；同一 `run_id + case_id` 只允许一条建议，推断失败只进入运行摘要，不改变测试运行状态。
- 审批支持 `case_only` 与 `case_and_endpoint_asset`。审批通过会创建用例版本、更新当前用例断言并将状态改为 `confirmed`；后者另外写入独立的 endpoint Oracle fact，不覆盖原始 OpenAPI。
- 后续生成会按 `endpoint_id + test_point_key` 读取已审批事实，将对应计划点提升为 `confirmed` 并携带审批断言；服务端完整性校验拒绝模型改写审批状态或断言。
- 观察证据、建议、审批记录、用例版本和 endpoint fact 分层保存，形成可追溯且可继续校准的闭环。
