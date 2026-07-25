# API Endpoint Debug Request Body Specification

## ADDED Requirements

### Requirement: Request body editor selection

系统 SHALL 根据接口资产中声明的请求体 Content-Type 选择对应的调试编辑器，而不是将所有请求体统一展示为 JSON 文本框。

#### Scenario: JSON request body

- **WHEN** 当前接口请求体 Content-Type 为 `application/json`
- **THEN** 系统 SHALL 展示 JSON 文本编辑器
- **AND** 发送目标请求时 SHALL 使用 JSON 编码

#### Scenario: Multipart request body

- **WHEN** 当前接口请求体 Content-Type 为 `multipart/form-data`
- **THEN** 系统 SHALL 展示 Schema 驱动的字段表单
- **AND** binary 字段 SHALL 展示文件选择控件

#### Scenario: URL-encoded request body

- **WHEN** 当前接口请求体 Content-Type 为 `application/x-www-form-urlencoded`
- **THEN** 系统 SHALL 展示 Schema 驱动的字段表单
- **AND** 发送目标请求时 SHALL 使用表单编码

#### Scenario: Unsupported or missing content type

- **WHEN** 请求体 Content-Type 缺失或不属于已支持的结构化类型
- **THEN** 系统 SHALL 降级展示原始文本编辑器
- **AND** SHALL NOT 阻止用户继续调试接口

### Requirement: Complete Schema field presentation

系统 SHALL 展示请求体 Schema `properties` 中的全部字段，不得因为 Schema 存在 `required` 数组而隐藏可选字段。

#### Scenario: Required and optional fields coexist

- **GIVEN** 请求体 Schema 同时包含必填字段和可选字段
- **WHEN** 用户打开接口调试弹窗
- **THEN** 系统 SHALL 展示全部字段
- **AND** 仅 `schema.required` 中的字段 SHALL 标记为必填

#### Scenario: Field metadata is available

- **GIVEN** 字段 Schema 包含类型、格式、描述、示例、默认值或约束
- **WHEN** 系统展示该字段
- **THEN** 系统 SHALL 展示或应用对应的结构化元数据

### Requirement: Schema-driven field controls

系统 SHALL 根据字段 Schema 类型选择输入控件，并在发送前将用户输入转换为对应的数据类型。

#### Scenario: Binary string field

- **GIVEN** 字段 Schema 为 `type: string` 且 `format: binary`
- **WHEN** 系统展示字段
- **THEN** 系统 SHALL 展示文件选择控件
- **AND** SHALL NOT 将该字段展示为普通字符串输入框

#### Scenario: Numeric and boolean fields

- **WHEN** 用户填写数字或布尔字段
- **THEN** 系统 SHALL 将输入转换为对应类型
- **AND** 转换失败时 SHALL 阻止发送并展示字段错误

#### Scenario: Object or array field

- **WHEN** Schema 字段类型为对象或数组
- **THEN** 系统 SHALL 提供局部 JSON 编辑能力
- **AND** 非法 JSON SHALL 阻止发送

### Requirement: Standards-based validation

系统 SHALL 依据结构化 OpenAPI Schema 执行客户端校验，不得仅根据自然语言描述猜测业务规则。

#### Scenario: Required field is empty

- **GIVEN** 字段存在于 `schema.required`
- **WHEN** 用户未提供有效值并点击发送
- **THEN** 系统 SHALL 阻止发送
- **AND** SHALL 在对应字段附近展示必填错误

#### Scenario: Description mentions conditional requirement

- **GIVEN** 字段描述包含“某条件下必填”等自然语言
- **AND** Schema 未通过标准结构表达该条件
- **WHEN** 用户发送请求
- **THEN** 系统 SHALL 保留描述提示
- **AND** SHALL NOT 自动创建硬性校验规则

### Requirement: Multipart debug transport

系统 SHALL 支持通过平台后端代理发送包含普通字段和真实文件内容的 multipart 请求。

#### Scenario: Multipart request contains fields and file

- **GIVEN** 用户填写普通表单字段并选择文件
- **WHEN** 用户发送调试请求
- **THEN** 平台后端 SHALL 使用 `data` 发送普通字段
- **AND** SHALL 使用 `files` 发送文件字段
- **AND** 目标服务 SHALL 接收到标准 multipart 请求

#### Scenario: Multipart content type boundary

- **WHEN** 平台后端发送 multipart 请求
- **THEN** 系统 SHALL 让 HTTP 客户端自动生成 Content-Type boundary
- **AND** SHALL NOT 使用不含有效 boundary 的手工 multipart Content-Type

#### Scenario: Optional empty field

- **GIVEN** 可选字段为空
- **WHEN** 系统构造 multipart 或 urlencoded 请求
- **THEN** 系统 SHALL 默认不发送该字段

### Requirement: Debug transport compatibility

系统 SHALL 保持现有非文件调试请求的行为兼容。

#### Scenario: Existing JSON debug request

- **GIVEN** 接口请求体为 JSON 且不包含文件
- **WHEN** 用户发送调试请求
- **THEN** 系统 SHALL 继续通过现有 JSON 调试协议发送
- **AND** Path、Query、Header、环境认证和响应展示行为 SHALL 保持不变

#### Scenario: File-bearing internal request

- **GIVEN** 调试请求包含浏览器 File 对象
- **WHEN** 前端调用平台调试接口
- **THEN** 前端 SHALL 使用 FormData 传输调试元数据和文件
- **AND** 后端 SHALL 将其恢复为统一调试请求模型

### Requirement: File safety and observability

系统 SHALL 限制调试文件大小，并避免在响应或日志中泄露文件内容和敏感认证信息。

#### Scenario: Request summary contains file

- **WHEN** 调试结果返回请求摘要
- **THEN** 摘要 SHALL 仅包含文件字段名、文件名、MIME 类型和大小
- **AND** SHALL NOT 包含文件二进制内容

#### Scenario: File exceeds configured limit

- **WHEN** 单文件或单次请求总文件大小超过配置限制
- **THEN** 平台后端 SHALL 在请求目标服务前拒绝该请求
- **AND** SHALL 返回稳定、可识别的参数错误

#### Scenario: Sensitive headers are present

- **WHEN** 请求包含认证 Header 或 Token
- **THEN** 调试结果和日志 SHALL 继续对敏感值进行脱敏
