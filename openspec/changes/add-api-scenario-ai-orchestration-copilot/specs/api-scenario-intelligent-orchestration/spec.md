# API Scenario Intelligent Orchestration Specification

## ADDED Requirements

### Requirement: Tool-driven endpoint asset retrieval

系统 SHALL 让接口场景编排智能体通过受控工具检索当前项目接口资产，并按需读取候选接口详情，而不是将全量接口详情一次性拼接到模型提示词。

#### Scenario: Business goal requires endpoint discovery

- **GIVEN** 用户提交业务目标且未指定 endpoint ID
- **WHEN** 系统开始生成接口场景计划
- **THEN** 智能体 SHALL 先调用接口搜索工具获得当前项目候选接口
- **AND** SHALL 只对实际候选调用接口详情工具
- **AND** SHALL NOT 查询用户不可见项目的接口资产

#### Scenario: User restricts endpoint scope

- **GIVEN** 用户选择了 endpoint ID 或标签范围
- **WHEN** 智能体检索接口资产
- **THEN** 工具 SHALL 将结果限制在指定范围和当前项目交集内
- **AND** 超出范围的 endpoint ID SHALL NOT 进入计划

#### Scenario: Model invents an endpoint

- **WHEN** 模型输出不存在、跨项目或未被检索工具返回的 endpoint ID
- **THEN** 服务端 SHALL 将计划标记为无效
- **AND** SHALL NOT 将模型生成的 URL 转换为可执行接口

### Requirement: Normalized endpoint input and output slots

系统 SHALL 将接口资产中的请求参数、请求体和响应 Schema 转换为统一的输入槽位和输出槽位，供依赖分析、参数补全和校验复用。

#### Scenario: Endpoint declares structured request fields

- **GIVEN** 接口资产声明 Path、Query、Header、Cookie、JSON、Form 或 Multipart 字段
- **WHEN** 系统构建编排资产视图
- **THEN** 每个字段 SHALL 具有稳定 slot ID、location、path、类型、必填状态和敏感标记
- **AND** Body 内部路径 SHALL 使用统一 JSON Pointer 表示

#### Scenario: Endpoint declares response schema

- **GIVEN** 接口资产声明成功响应 Schema
- **WHEN** 系统构建输出槽位
- **THEN** 系统 SHALL 生成带状态码、来源、JSONPath 或 Header 名称、字段名和类型的输出槽位
- **AND** SHALL 保留资产版本或内容指纹

#### Scenario: Response schema is unavailable

- **GIVEN** 接口资产缺少结构化响应 Schema
- **WHEN** 系统存在经过脱敏的示例响应或稳定历史结构
- **THEN** 系统 MAY 生成低置信度输出候选
- **AND** 自动绑定前 SHALL 要求达到配置的置信度阈值

### Requirement: Deterministic dependency candidate analysis

系统 SHALL 使用确定性规则为前序输出和后续请求输入生成带评分和理由的依赖候选，AI 只能在候选范围内选择或声明无法确定。

#### Scenario: Exact compatible field match

- **GIVEN** 前序接口输出 `order_id` 字符串
- **AND** 后续接口要求 `order_id` 字符串
- **WHEN** 系统分析接口依赖
- **THEN** 系统 SHALL 生成高置信度依赖候选
- **AND** 候选 SHALL 包含生产者槽位、消费者槽位、评分和匹配理由

#### Scenario: Multiple outputs match one input

- **GIVEN** 多个上游输出均可匹配同一必填输入
- **WHEN** 候选评分无法唯一确定来源
- **THEN** 系统 SHALL 创建未解决项
- **AND** SHALL NOT 静默选择任意来源

#### Scenario: Output and input types conflict

- **GIVEN** 上游输出类型与目标输入类型不兼容
- **WHEN** 系统分析依赖
- **THEN** 系统 SHALL 降低或拒绝该依赖候选
- **AND** 未注册转换器 SHALL NOT 被当作自动解决方案

### Requirement: Strongly typed scenario plan contract

系统 SHALL 使用版本化强类型 `ScenarioPlan` 契约约束步骤、边、参数目标、参数来源、提取器、断言和控制配置。

#### Scenario: Model returns a valid plan

- **WHEN** 模型完成规划
- **THEN** 输出 SHALL 通过当前 `ScenarioPlan` JSON Schema
- **AND** 每个参数来源 SHALL 使用明确的判别类型
- **AND** 每个绑定目标 SHALL 使用结构化 location 和 path

#### Scenario: Model returns legacy string binding

- **WHEN** 新计划包含字符串形式的来源，例如 `step_login.token`
- **THEN** Schema 校验 SHALL 拒绝该输出
- **AND** 系统 SHALL NOT 将字符串猜测转换为可执行绑定

#### Scenario: Historical scenario contains legacy binding

- **GIVEN** 已保存历史场景包含可确定迁移的旧绑定格式
- **WHEN** 系统读取该场景
- **THEN** 兼容层 SHALL 将其迁移为强类型来源
- **AND** 无法无歧义迁移的绑定 SHALL 返回明确校验错误

### Requirement: Unified parameter source model

系统 SHALL 支持 literal、user_input、environment、secret、scenario、step_output 和 generated 七类参数来源，并在前端和运行结果中保持来源可追溯。

#### Scenario: Parameter comes from user input

- **GIVEN** 场景定义了必填用户输入 `question`
- **WHEN** 请求字段绑定到该输入
- **THEN** 绑定来源 SHALL 为 `user_input`
- **AND** 执行前缺少该输入 SHALL 阻止运行

#### Scenario: Parameter comes from environment

- **GIVEN** 目标环境声明普通变量 `message_source`
- **WHEN** 计划将请求字段绑定到该变量
- **THEN** 绑定来源 SHALL 为 `environment`
- **AND** Plan SHALL 保存变量 key 而不是变量值

#### Scenario: Parameter comes from a secret

- **GIVEN** 请求需要 Token、Cookie、密码或密钥
- **WHEN** 系统生成参数来源
- **THEN** 来源 SHALL 为 `secret`
- **AND** Plan、Prompt、日志和普通运行快照 SHALL NOT 保存真实值

#### Scenario: Parameter uses a generated value

- **WHEN** 场景需要唯一 ID 或时间值
- **THEN** 系统 SHALL 只允许注册的确定性生成器类型
- **AND** SHALL NOT 接受代码表达式作为生成器

### Requirement: Previous response extraction and downstream binding

系统 SHALL 能够将前序步骤响应字段提取为命名变量，并将该变量绑定到后续接口的请求字段。

#### Scenario: JSON response feeds multipart request

- **GIVEN** 步骤 A 的 JSON 响应在 `$.data.segment_code` 返回字符串
- **AND** 步骤 B 的 Multipart 请求要求 `/segment_code`
- **WHEN** 系统编译依赖
- **THEN** 步骤 A SHALL 包含名为 `segment_code` 的 JSON 提取器
- **AND** 步骤 B SHALL 包含引用步骤 A 输出的 `step_output` 绑定
- **AND** 绑定目标 SHALL 为 Multipart `/segment_code`

#### Scenario: Header response feeds later header

- **GIVEN** 前序步骤从响应 Header 提取相关 ID
- **WHEN** 后续请求 Header 绑定该输出
- **THEN** 系统 SHALL 保留 Header 来源和目标名称
- **AND** Header 名称匹配 SHALL 大小写不敏感

#### Scenario: SSE event feeds later request

- **GIVEN** 前序步骤返回 SSE Event JSON
- **WHEN** 场景需要提取事件中的 `dialog_id`
- **THEN** 提取器 SHALL 声明 SSE event、JSONPath、类型和结束策略
- **AND** 不支持 SSE 的执行器 SHALL 在应用前返回兼容性错误

#### Scenario: Step references a later output

- **WHEN** 某绑定引用拓扑下游步骤输出
- **THEN** 服务端 SHALL 将计划标记为无效
- **AND** 错误 SHALL 包含当前步骤 ID 和绑定字段路径

### Requirement: Structured cURL ingestion

系统 SHALL 在服务端结构化解析用户提供的 cURL，并在进入模型前完成接口匹配、参数分类和敏感信息处理。

#### Scenario: cURL matches an imported endpoint

- **GIVEN** cURL 的方法和规范化路径匹配当前项目接口资产
- **WHEN** 系统解析 cURL
- **THEN** 系统 SHALL 将其映射到 endpoint ID
- **AND** Plan SHALL NOT 保存 cURL 中的完整可执行 URL

#### Scenario: cURL contains credentials

- **GIVEN** cURL 包含 Authorization、Cookie、Token、Key 或密码
- **WHEN** 系统构建模型上下文
- **THEN** 敏感值 SHALL 替换为 secret key 引用或待确认项
- **AND** 原始敏感值 SHALL NOT 发送给模型

#### Scenario: Sensitive value has no environment destination

- **GIVEN** cURL 包含尚未配置到环境的敏感值
- **WHEN** 系统完成解析
- **THEN** 系统 SHALL 提示用户选择已有 Secret key 或确认保存到环境
- **AND** 未经确认 SHALL NOT 修改环境配置

### Requirement: Environment schema projection

系统 SHALL 向编排智能体提供不含真实值的环境 Schema 投影，并在运行时由服务端解析环境和密钥。

#### Scenario: Agent inspects an environment

- **WHEN** 智能体调用环境 Schema 工具
- **THEN** 工具 SHALL 返回环境 ID、名称、鉴权类型、变量 key、类型和是否已配置
- **AND** SHALL NOT 返回 base URL 原文、变量值、默认 Header 值或 Secret 值

#### Scenario: Environment key is missing

- **GIVEN** 计划引用环境变量或 Secret key
- **WHEN** 所选环境没有对应配置
- **THEN** 计划 SHALL 保持可预览
- **AND** 应用或运行 SHALL 被阻止，直到用户修复配置或参数来源

#### Scenario: Protected authentication header is overridden

- **WHEN** AI 计划或用户普通步骤尝试覆盖受保护鉴权 Header
- **THEN** 服务端 SHALL 拒绝该覆盖
- **AND** 真实鉴权值 SHALL 只在请求发送前由运行时注入

### Requirement: Setup, main, verify and cleanup orchestration

系统 SHALL 为场景步骤标记 setup、main、verify 或 cleanup 阶段，并在依赖顺序和执行结果中保留该阶段。

#### Scenario: Goal requires authentication and business action

- **GIVEN** 业务操作依赖显式登录接口且不能由环境鉴权处理
- **WHEN** 系统生成计划
- **THEN** 登录步骤 SHALL 位于 setup 阶段
- **AND** 业务请求 SHALL 位于 main 阶段
- **AND** 登录输出 SHALL 通过强类型绑定传递

#### Scenario: Goal requires result verification

- **WHEN** 业务目标声明期望状态或结果
- **THEN** 系统 SHALL 在 main 步骤断言或独立 verify 步骤中表达该预期
- **AND** SHALL NOT 仅以 HTTP 请求成功替代明确业务结果

#### Scenario: Cleanup is required

- **GIVEN** 用户启用 `require_cleanup`
- **AND** 主流程创建或修改测试数据
- **WHEN** 系统生成计划
- **THEN** 系统 SHALL 规划 cleanup 步骤或产生无法清理的阻塞项
- **AND** cleanup 步骤 SHALL 显示其写操作风险和失败策略

### Requirement: Deterministic plan compilation

系统 SHALL 使用不调用模型的 Plan Compiler 将 AI 语义计划转换为现有场景步骤草稿。

#### Scenario: Same inputs are compiled repeatedly

- **GIVEN** ScenarioPlan、资产版本、环境 Schema 和 Compiler 版本相同
- **WHEN** 系统重复编译计划
- **THEN** 规范化步骤、绑定、提取器、断言和指纹 SHALL 相同

#### Scenario: Basic assertion is missing

- **GIVEN** AI 为 API 请求步骤未提供成功断言
- **WHEN** 接口资产声明明确成功状态码
- **THEN** Compiler SHALL 添加受支持的基础状态码断言
- **AND** SHALL 记录该断言由 Compiler 补全

#### Scenario: Required input has no source

- **WHEN** 编译后仍有必填输入没有来源
- **THEN** Compiler SHALL 创建字段级未解决项
- **AND** 计划 SHALL NOT 被标记为可应用

### Requirement: Unified server-side validation

系统 SHALL 在计划生成、计划编辑、应用、发布和运行前复用同一套服务端验证规则。

#### Scenario: Plan contains invalid binding

- **WHEN** 参数目标不存在、来源不存在、类型不兼容或引用不可达
- **THEN** 验证结果 SHALL 包含稳定错误码、step ID 和 field path
- **AND** 前端 SHALL 能定位到对应步骤和字段

#### Scenario: Write operation is not allowed

- **GIVEN** 计划包含 POST、PUT、PATCH、DELETE 或资产标记的写操作
- **AND** 用户未允许写操作
- **WHEN** 系统验证计划
- **THEN** 计划 SHALL 标记为无效
- **AND** 应用按钮 SHALL 保持禁用

#### Scenario: Asset changes after plan generation

- **GIVEN** Plan 保存的资产指纹与当前接口资产不一致
- **WHEN** 用户应用 Plan
- **THEN** 系统 SHALL 返回冲突
- **AND** SHALL 要求重新编译、确认资产差异或重新规划

### Requirement: Asynchronous generation and recoverable plan state

系统 SHALL 将 AI 场景计划生成建模为可持久化异步任务，并允许页面刷新或断开后恢复进度和结果。

#### Scenario: User starts plan generation

- **WHEN** 用户提交编排请求
- **THEN** 创建接口 SHALL 快速返回 run ID
- **AND** 任务 SHALL 记录 parsing、retrieval、dependency、planning、compiling 和 validating 阶段

#### Scenario: User refreshes during generation

- **GIVEN** 生成任务仍在运行
- **WHEN** 用户刷新或重新打开场景编辑器
- **THEN** 前端 SHALL 通过 run ID 恢复当前阶段和进度
- **AND** SHALL NOT 重复创建模型请求

#### Scenario: Completed preview is reopened

- **GIVEN** Plan 状态为 preview 或 invalid 且未过期
- **WHEN** 用户重新打开 AI 编排入口
- **THEN** 前端 SHALL 能读取并恢复 Plan、校验结果和未解决项

#### Scenario: Model generation fails

- **WHEN** 模型超时、工具失败或结构化输出重试耗尽
- **THEN** 任务 SHALL 标记为 failed 并保存脱敏错误
- **AND** 当前场景草稿 SHALL 保持不变

### Requirement: Explicit plan review and application

系统 SHALL 在用户明确确认前将 AI 结果保持为独立预览，不得自动修改、发布或执行场景。

#### Scenario: Valid plan is previewed

- **WHEN** Plan 通过服务端验证
- **THEN** 前端 SHALL 展示步骤、阶段、接口资产、数据依赖、参数来源、断言和风险
- **AND** 当前场景步骤 SHALL 保持不变

#### Scenario: User applies a valid plan

- **GIVEN** Plan 有效且场景修订号、草稿指纹、资产指纹和环境 Schema 指纹一致
- **WHEN** 用户确认应用
- **THEN** 系统 SHALL 复用现有步骤替换逻辑写入场景草稿
- **AND** 场景 SHALL 保持 draft
- **AND** SHALL NOT 自动发布或执行

#### Scenario: User edits unresolved values

- **GIVEN** Plan 因缺少参数来源而无效
- **WHEN** 用户补充输入或切换参数来源并重新校验
- **THEN** 系统 SHALL 在不重新调用模型的情况下重新编译和验证

### Requirement: Deterministic executable code generation

系统 SHALL 从已验证场景快照确定性生成可执行代码，代码生成不得再次调用编排模型。

#### Scenario: Applied scenario generates code

- **GIVEN** 场景草稿已经应用并通过验证
- **WHEN** 系统生成场景代码
- **THEN** Renderer SHALL 只消费场景快照和版本化模板
- **AND** 产物 SHALL 绑定 scenario ID、revision、plan ID、asset hash、environment schema hash 和 renderer version

#### Scenario: Generated code is validated

- **WHEN** Renderer 完成文件生成
- **THEN** 系统 SHALL 执行安全路径检查、Python 编译、pytest collect 和敏感明文扫描
- **AND** 任一检查失败 SHALL 将代码产物标记为 invalid
- **AND** 场景草稿 SHALL 保持可编辑且不被覆盖

#### Scenario: Scenario changes after generation

- **GIVEN** 场景修订、接口资产或 Renderer 版本发生变化
- **WHEN** 系统读取旧代码产物
- **THEN** 旧产物 SHALL 标记为 stale
- **AND** 运行入口 SHALL NOT 静默执行 stale 产物

### Requirement: Parameter provenance presentation

系统 SHALL 在编排预览和场景编辑器中展示每个参数的来源，并在依赖边上展示变量映射。

#### Scenario: Downstream parameter comes from prior output

- **WHEN** 后续请求字段使用 `step_output`
- **THEN** 前端 SHALL 在对应连线上展示输出变量和目标字段
- **AND** 参数面板 SHALL 展示前序步骤名称、变量名和提取路径

#### Scenario: Parameter comes from secret

- **WHEN** 参数来源为 `secret`
- **THEN** 前端 SHALL 显示 Secret key 和已配置状态
- **AND** SHALL NOT 显示真实值或可恢复掩码

#### Scenario: Validation error targets a parameter

- **WHEN** 服务端返回带 step ID 和 field path 的校验错误
- **THEN** 前端 SHALL 高亮对应节点和参数控件
- **AND** SHALL 显示可操作的修复说明

### Requirement: Auditability and sensitive-data governance

系统 SHALL 记录计划和代码生命周期所需审计信息，并保证模型上下文、持久化数据、日志和产物不包含未授权敏感明文。

#### Scenario: Plan generation completes

- **WHEN** Plan 生成完成
- **THEN** 审计记录 SHALL 包含创建人、模型、提示版本、Compiler 版本、资产指纹、环境 Schema 指纹和工具调用摘要
- **AND** SHALL NOT 包含 Secret 值、完整 Cookie 或 Authorization

#### Scenario: Sensitive content reaches a persistence boundary

- **WHEN** Prompt、Plan、日志、运行快照或代码产物包含疑似敏感明文
- **THEN** 敏感信息扫描 SHALL 阻止或脱敏该写入
- **AND** 系统 SHALL 记录不包含原文的安全事件

#### Scenario: Plan is applied or discarded

- **WHEN** 用户应用、放弃或替代 Plan
- **THEN** 系统 SHALL 记录操作人、Plan 版本、场景修订号和结果
- **AND** Plan 状态 SHALL 单向转换，不得重复应用
