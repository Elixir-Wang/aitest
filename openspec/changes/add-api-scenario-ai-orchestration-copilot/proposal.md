## Why

当前 AI 接口场景编排使用松散 JSON 和一次性接口上下文，无法稳定生成与执行器兼容的参数绑定，也可能让 cURL 凭据、环境值和敏感 Header 进入模型与计划持久化。需要将其升级为工具驱动、强类型、可恢复的智能编排能力，使 AI 能查看当前项目接口详情、分析前后置依赖并生成可校验的数据流，同时由服务端安全补全环境参数和确定性生成执行代码。

## What Changes

- 将编排智能体改为工具驱动检索，只按需搜索和读取当前项目接口资产详情。
- 从 OpenAPI 请求和响应 Schema 生成标准化输入槽位、输出槽位和确定性依赖候选。
- 引入版本化强类型 `ScenarioPlan`，约束步骤、阶段、边、参数目标、参数来源、提取器、断言和控制配置。
- 统一 literal、user_input、environment、secret、scenario、step_output 和 generated 七类参数来源。
- 自动将前序响应字段编译为提取变量，并绑定到后续 Path、Query、Header、Cookie、JSON、Form、Multipart 或 SSE 参数。
- 增加 cURL 结构化解析、敏感字段识别、环境 Schema 投影和运行时 Secret 注入。
- 引入不调用模型的 Plan Compiler 和统一 Validator，负责参数补全、类型检查、资产归属、写操作和执行器兼容校验。
- 将同步生成升级为可持久化异步任务，支持进度、刷新恢复、编辑、重新校验、局部重新规划、应用和放弃。
- 用户确认后才将有效 Plan 应用到场景草稿；不自动发布、不自动运行。
- 从已验证场景快照确定性生成场景执行代码，并绑定场景修订、资产指纹、环境 Schema 指纹和 Renderer 版本。
- 与 `add-api-scenario-ai-canvas` 共享同一场景 DSL；本变更负责智能规划和数据流，画布变更负责图编辑和 DAG 执行扩展。

## Capabilities

### New Capabilities

- `api-scenario-intelligent-orchestration`: 覆盖工具驱动接口资产检索、接口输入输出槽位、依赖候选、强类型场景计划、参数来源、环境和 Secret 隔离、前序输出绑定、异步计划生命周期、计划应用和确定性代码生成。

### Modified Capabilities

无。本仓库当前没有已归档的同名主规格；现有未归档 AI 画布变更保持独立，并通过共享 DSL 兼容。

## Impact

- 后端：`app/agents/api_automation/orchestration/`、接口资产解析和仓储、环境凭据服务、场景服务、场景验证器、pytest requests Renderer、任务和审计服务。
- 前端：接口场景编辑器、AI 编排弹窗、依赖图、参数来源编辑、生成进度恢复和代码视图。
- API：新增异步 Plan Run、Plan 读取/编辑/校验/重规划/应用/放弃接口；现有同步 AI Plan 接口进入兼容期。
- 数据：扩展 AI Plan 持久化，增加生成任务、Schema/Compiler/Renderer 版本、资产和环境指纹、代码产物状态。
- 安全：Prompt、Plan、日志、运行快照和代码产物增加敏感信息隔离和扫描边界。
- 测试：新增 Schema、依赖分析、cURL 脱敏、环境投影、变量绑定、异步恢复、代码生成和端到端前端测试。
