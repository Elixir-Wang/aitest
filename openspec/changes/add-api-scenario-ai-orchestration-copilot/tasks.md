# Tasks

## 1. 统一场景 DSL 和强类型契约

- [ ] 定义 `ScenarioPlan`、`ScenarioPlanStep`、`ScenarioPlanEdge`、阶段、状态和校验结果的 Pydantic Schema。
- [ ] 定义 `ParameterTarget`，覆盖 path、query、header、cookie、json_body、form、multipart 和 raw_body。
- [ ] 定义 `ValueSource` 判别联合，覆盖 literal、user_input、environment、secret、scenario、step_output 和 generated。
- [ ] 定义 JSON Body、Header、Cookie、文本正则和 SSE Event JSON 提取器 Schema。
- [ ] 定义状态码、Header、JSONPath、Schema、SSE Event 和文本断言 Schema。
- [ ] 定义 wait、poll、condition 和 assign 的强类型控制配置。
- [ ] 将 `ApiScenarioStepIn` 和前端 TypeScript 类型迁移到统一强类型契约，同时兼容读取历史松散 JSON。
- [ ] 增加契约版本和迁移器，禁止新计划写入旧字符串形式的绑定来源。

## 2. 接口资产分析和检索工具

- [ ] 实现接口资产标准化器，从 OpenAPI 参数、请求体和响应中生成输入槽位、输出槽位和类型信息。
- [ ] 为 Path、Query、Header、Cookie、JSON、Form、Multipart 和 SSE 响应建立统一字段路径表示。
- [ ] 实现确定性依赖候选分析，综合 OpenAPI Link、字段名、类型、路径参数、描述、示例和业务标签评分。
- [ ] 保存资产指纹和依赖候选版本，接口资产变化时使旧计划失效或进入待确认状态。
- [ ] 为编排智能体提供 `search_endpoints`、`get_endpoint_detail`、`get_dependency_candidates` 和 `get_existing_scenario` 工具。
- [ ] 工具查询必须限制当前项目、返回数量、单字段长度和总 token 大小。
- [ ] 智能体只能通过工具获取接口详情，不允许将前 100 个完整接口直接拼接进初始提示词。

## 3. 用户输入、环境和敏感信息隔离

- [ ] 定义计划输入参数 Schema，支持字符串、数字、布尔、对象、数组、文件引用和枚举。
- [ ] 实现 cURL 结构化解析，将 URL、Path、Query、Header、Cookie、JSON、Form 和 Multipart 转换为候选输入。
- [ ] 在 cURL 和自然语言进入模型前检测 Authorization、Cookie、Token、Key、密码和自定义敏感 Header。
- [ ] 敏感值只转换为 `secret` 引用或待确认项，不得进入 Prompt、Plan JSON、审计日志或前端普通文本状态。
- [ ] 实现环境 Schema 投影，仅向模型暴露环境 ID、名称、变量键、类型、是否已配置和鉴权类型。
- [ ] 实现运行时环境解析器，在执行阶段读取真实 base URL、普通变量、默认 Header、鉴权配置和密钥。
- [ ] 定义请求参数合并顺序和受保护鉴权字段，禁止 AI 或普通步骤覆盖受保护密钥。
- [ ] 用户要求将新敏感值保存到环境时，必须经过单独确认和现有加密存储流程。

## 4. 智能规划和计划编译

- [ ] 将 `api_scenario_orchestration_agent` 改为工具驱动的资产检索和规划智能体。
- [ ] 提示词明确要求先检索候选接口、再读取必要详情、再建立数据依赖，禁止猜测 endpoint ID 和字段路径。
- [ ] 智能体输出仅包含强类型语义计划，不包含真实 URL、密钥、脚本或任意代码。
- [ ] 实现 Plan Compiler，将智能体输出规范化为现有 `ApiScenarioStepIn` 草稿。
- [ ] 编译器自动补全环境变量引用、用户输入引用、稳定步骤 ID、默认状态码断言和安全的字段默认值。
- [ ] 编译器根据依赖候选自动创建前序提取器和后续 `step_output` 绑定。
- [ ] 对无法唯一确定的字段产生 `unresolved_items`，不得自动选择低置信度依赖。
- [ ] 自动标记 setup、main、verify 和 cleanup 阶段，并在要求清理时规划补偿步骤。
- [ ] 对轮询接口生成受限 poll 配置，包括间隔、超时、最大次数和终止断言。

## 5. 服务端验证和安全边界

- [ ] 验证所有 endpoint ID 属于当前项目且资产版本与计划快照一致。
- [ ] 验证每个必填请求字段存在可解析来源，并检查来源与目标类型兼容。
- [ ] 验证 `step_output` 只能引用拓扑上游步骤和真实存在的提取变量。
- [ ] 验证变量名唯一、目标路径合法、JSONPath/SSE 路径受支持且无循环依赖。
- [ ] 验证写操作授权、cleanup 要求、受保护 Header、跨项目引用和任意 URL 注入。
- [ ] 验证每个关键请求步骤至少包含成功断言，verify 阶段包含业务结果断言。
- [ ] 将错误绑定到稳定的 step ID、edge ID 和字段路径，供前端精确定位。
- [ ] 生成、编辑、应用、发布和运行前均复用同一个验证服务。

## 6. 异步生成、持久化和 API

- [ ] 将同步 AI 生成改为异步 generation run，创建接口快速返回 run ID。
- [ ] 增加生成状态、阶段、进度、错误、模型、提示版本和工具调用摘要字段。
- [ ] 增加 Plan 详情读取接口，使页面刷新后可以恢复 preview、invalid、applied、discarded 和 expired 状态。
- [ ] 增加 Plan 编辑和重新校验接口，允许用户补充未解决参数而不重新调用模型。
- [ ] 增加局部重新规划接口，并限制可修改步骤范围和资产范围。
- [ ] 增加 Plan 放弃接口和过期清理任务。
- [ ] 应用接口校验场景修订号、草稿指纹、资产指纹、环境 Schema 指纹和 Plan 状态。
- [ ] 应用成功后继续复用现有步骤替换逻辑，结果保持 draft，不自动发布或执行。

## 7. 确定性代码生成和执行兼容

- [ ] 定义场景 Renderer 输入契约，以已验证场景快照为唯一事实源。
- [ ] 复用现有 pytest requests 项目基础结构，新增场景级确定性 Renderer。
- [ ] Renderer 支持用户输入、环境变量、Secret 引用、前序输出绑定、条件、等待、轮询和清理阶段。
- [ ] 代码产物绑定 scenario ID、scenario revision、plan ID、asset hash、environment schema hash 和 renderer version。
- [ ] 场景或资产变化时将旧代码标记为 stale，并在运行前阻止使用不匹配产物。
- [ ] 生成后执行格式检查、Python 编译、pytest collect 和可选 Dry Run。
- [ ] Renderer 失败不得回写或破坏已确认场景草稿。
- [ ] 运行结果按稳定 step ID 返回输入来源摘要、提取变量、断言和跳过原因，敏感值保持脱敏。

## 8. 前端智能编排体验

- [ ] 在 AI 编排入口提供业务目标、环境、接口范围、用户输入、写操作、cleanup 和步骤上限设置。
- [ ] cURL 粘贴后展示结构化解析结果和敏感字段处理建议，不回显完整密钥。
- [ ] 展示资产检索、依赖分析、计划编译和服务端校验的异步进度。
- [ ] 预览节点顺序、阶段、接口资产、断言、假设、警告和未解决项。
- [ ] 在依赖边上展示前序输出变量到后续请求字段的映射。
- [ ] 每个参数显示来源徽标：用户输入、环境、Secret、固定值、场景变量、前序输出或系统生成。
- [ ] 支持补充缺失输入、切换参数来源、修改提取路径、重新校验和局部重新规划。
- [ ] 校验失败时禁用应用按钮，并定位到具体步骤和字段。
- [ ] 页面刷新后根据 run ID 或 plan ID 恢复计划预览和生成进度。
- [ ] 应用后展示画布、步骤和生成代码三个视图，并显示代码产物是否 current 或 stale。

## 9. 审计、可观测性和数据治理

- [ ] 记录 Plan 创建人、确认人、模型、提示版本、工具调用、资产指纹和环境 Schema 指纹。
- [ ] 记录依赖候选评分和最终选择理由，但不得记录真实密钥或完整敏感请求值。
- [ ] 记录生成耗时、工具调用次数、Schema 重试次数、校验错误类型和应用结果。
- [ ] 对 Prompt、Plan、日志、运行快照和代码产物增加敏感信息扫描测试。
- [ ] 为计划、生成任务和代码产物定义保留、过期和级联清理策略。

## 10. 测试和交付

- [ ] 增加强类型 Plan、ValueSource、ParameterTarget、Extractor 和 Assertion Schema 测试。
- [ ] 增加资产槽位提取和依赖候选评分单元测试。
- [ ] 增加 cURL 解析、敏感字段识别、环境投影和 Secret 隔离测试。
- [ ] 增加前序输出到 Path、Query、Header、JSON、Form、Multipart 和 SSE 字段绑定测试。
- [ ] 增加缺失输入、类型冲突、后向引用、循环依赖、写操作和 cleanup 校验测试。
- [ ] 增加异步任务、刷新恢复、过期、局部重新规划和场景修订冲突 API 测试。
- [ ] 增加 Plan 应用、确定性代码生成、pytest collect、Dry Run 和 stale 产物测试。
- [ ] 增加前端计划进度、依赖图、参数来源、错误定位、恢复和代码状态契约测试。
- [ ] 使用 Playwright 验证桌面和窄屏下输入、预览、画布、步骤和代码视图无重叠。
- [ ] 运行后端聚焦 pytest、前端类型检查、Biome、生产构建和 OpenSpec 严格校验。
- [ ] 更新接口自动化文档，说明智能体工具、参数来源、环境安全边界、计划确认和代码生成生命周期。
