# 性能测试请求配置精简设计

**日期：** 2026-07-14  
**状态：** 已完成自检，待用户评审  
**范围：** 性能测试创建、请求预览、请求配置持久化与 Locust 脚本生成

## 1. 目标

1. 新增并稳定性能测试创建能力，性能测试请求配置不再依赖接口自动化测试用例作为数据来源。
2. 请求配置根据接口 Schema、示例、默认值、枚举和约束自动生成合理 Mock 值，用户可以继续编辑。
3. 没有实际内容的 Path、Query、Headers、Body 配置不显示。
4. cybertron-robot-key 和 cybertron-robot-token 按普通 Header 处理，正常显示和编辑，并删除对应提示。
5. 由于项目为新项目，直接删除无用字段和配置，不增加数据库迁移兼容层。

## 2. 非目标

- 不改变真实敏感 Header 的安全策略。
- 不新增独立 Mock 服务或随机数据平台。
- 不改变 Locust 运行、统计、报告和脚本审核流程。
- 不保留 请求数据来源旧入口、旧 API 参数或旧数据库配置。

## 3. 设计

### 3.1 数据模型与 API

彻底删除 source_api_test_case_id：

- 从性能测试创建、更新、预览请求模型删除。
- 从性能测试序列化输出和前端 TypeScript 类型删除。
- 删除后端服务中的来源用例查询、归属校验、接口匹配校验和请求合并逻辑。
- 删除仓储、种子数据和数据库表中的对应字段及相关索引/约束；新项目无需迁移旧数据。
- 删除来源用例相关错误码、测试夹具和前端接口用例加载逻辑。

请求预览接口只依赖项目和 ndpoint_id，返回接口定义生成的请求配置、成功规则和来源说明。

### 3.2 自动 Mock 规则

后端统一生成请求配置，避免前端与脚本生成器各自实现一套规则。递归处理参数 Schema 和请求体 Schema：

1. 优先使用 OpenAPI 参数或 Schema 的 xample。
2. 没有 example 时使用 default。
3. 没有 default 时，枚举取第一个合法值。
4. 按类型和约束生成值：
   - string：依据 ormat、长度限制和模式生成可读字符串；
   - integer/number：依据 minimum/maximum 生成范围内值；
   - oolean：生成 	rue；
   - rray：递归生成一个合法元素；
   - object：递归生成已声明属性；
   - 
ull：生成 
ull。
5. 对 required 字段生成值；可选字段仅在 OpenAPI 示例或默认配置明确存在时生成，避免请求配置膨胀。
6. 生成结果写入可编辑的请求配置；用户修改后，以用户修改值为准。

cybertron-robot-key 和 cybertron-robot-token 不属于敏感 Header，不进入敏感过滤列表、不生成警告、不被运行时特殊覆盖。

### 3.3 前端显示

请求配置按实际内容条件渲染：

- path_parameters 非空才显示 Path 配置。
- query_parameters 非空才显示 Query 配置。
- headers 非空才显示 Headers 配置。
- Body 不是空对象、空字符串或无内容时才显示 Request Body。
- 成功状态码始终显示，因为它属于成功规则而非请求数据。
- 请求配置仍使用 JSON 编辑器，自动 Mock 完成后允许直接修改。
- 删除请求数据来源字段、相关确认交互和接口用例选项。
- 删除两条 cybertron Header 敏感提示；其他真实敏感 Header 警告继续保留。

### 3.4 持久化与脚本生成

- 性能测试保存的 equest_config 只包含实际存在的请求部分，不保存来源用例字段。
- Locust 脚本计划和渲染器读取统一的请求配置，不再尝试回填来源用例数据。
- 运行时不对两个 cybertron Header 做专门注入或替换，保留用户配置的值。

## 4. 验证

后端：

- 预览请求仅传 ndpoint_id。
- Schema example/default/enum/类型约束的 Mock 优先级和递归生成有单元测试。
- cybertron Header 正常出现在请求配置且没有 warning。
- 来源用例字段、错误码和合并逻辑不再存在。
- 空配置不进入不必要的持久化字段。

前端：

- 创建页不出现请求数据来源。
- 空 Path/Query/Headers/Body 不渲染。
- 自动 Mock 值可编辑并能随表单保存。
- 两条 cybertron Header 不显示敏感提示。

回归：

- 运行性能测试相关后端测试。
- 运行性能测试前端契约测试。
- 执行前端类型检查/构建和后端格式检查（使用仓库已有命令）。
- git diff --check，不覆盖现有未提交改动。

## 5. 影响文件范围

重点修改：

- pps/frontend/src/components/ai-testing/performance-testing/performance-test-form.tsx
- pps/frontend/src/lib/api-client.ts
- pps/backend/app/schemas/performance_test.py
- pps/backend/app/services/performance_testing/service.py
- pps/backend/app/services/performance_testing/plan_builder.py
- pps/backend/app/services/performance_testing/run_service.py
- 性能测试数据库 Schema、仓储、种子和相关测试

不修改性能测试执行器、Locust 统计、报告和与本需求无关的接口自动化功能。
