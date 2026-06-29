# 需求理解

## 1. 需求背景
## 需求背景

当前 agent-chat-model-g 服务与业务有较大的耦合和绑定，不适合作为统一的网关层使用。

### 核心痛点
- 现有服务与业务逻辑强耦合，无法被其他业务方直接复用
- 调用 LLM 的能力散落在业务代码中，缺乏统一接入层
- 通过 HTTP 方式调用 LLM 能力存在性能损耗

### 解决方案
将核心的与大模型 LLM 交互功能提取出来，沉淀为通用能力，构建独立的模型网关层：
- llm-gateway-g：Web 服务应用，对外提供 OpenAI 通信协议
- llm-gateway-g-sdk：Go SDK，供 Go 相关服务直接调用，避免 HTTP 性能损耗

### 切流策略
通过 params_config 配置 UseLLMGatewaySDK 列表（测试环境包含 azure-gpt-4-jp 和 Qwen2-72B-Instruct-AWQ），按模型进行逐渐切流。

## 2. 目标与价值
## 目标与价值

### 业务目标
1. 能力沉淀：将 LLM 交互能力从业务服务中剥离，形成可复用的基础设施
2. 统一接入：提供统一的 OpenAI 兼容协议入口，支持三方和公司内模型
3. 性能优化：通过 Go SDK 减少 HTTP 通信开销

### 核心价值
- 降低接入成本：业务方无需关心不同 LLM 厂商的协议差异
- 灵活路由：支持通过配置动态选择不同的 LLM 模型
- 协议标准化：统一对外暴露 OpenAI 兼容协议

### 可衡量成果
- 成功将 agent-chat-model-g 中的 LLM 调用能力迁移至网关
- Cybertron Agent 对话流能正常通过网关调用 LLM（含 FunctionCall）
- Go 版本对话流通过 SDK 调用 LLM 功能正常

## 3. 用户角色与使用场景
## 用户角色与使用场景

| 用户角色 | 使用场景 | 用户目标 | 接入方式 |
|---------|---------|---------|---------|
| 业务方服务（Go） | 直接调用 LLM 进行对话/推理 | 减少 HTTP 性能损耗 | 集成 llm-gateway-g-sdk |
| 业务方服务（非 Go / 跨语言） | 通过 HTTP 调用 LLM | 使用 OpenAI 兼容协议接入 | 调用 llm-gateway-g Web 服务 |
| 模型配置管理员 | 配置可用的 LLM 模型、API Key、代理 | 管理系统支持的模型 | 原文未说明（推测通过数据库或管理后台） |
| Cybertron Agent | 对话场景调用 LLM（含 FunctionCall） | 验证网关功能 | SDK 或 HTTP |

## 4. 功能范围
## 功能范围

### 包含的功能
1. llm-gateway-g Web 服务：提供 OpenAI 兼容协议的 HTTP 接入
2. llm-gateway-g-sdk Go SDK：供 Go 服务直接调用
3. 模型配置管理：维护 llm_model_config 表配置（端点、API Key、协议等）
4. 分类管理：llm_info_classify 表维护 LLM 厂商/分类
5. 代理配置：proxy_config 表配置网络代理
6. API Key 映射：source_model_api_key 表实现调用方 API Key 到目标模型 API Key 的映射
7. API Key 管理：api_keys 表管理 API Key 与来源
8. 自动初始化流程：服务启动时的初始化逻辑
9. 切流支持：通过 params_config 的 UseLLMGatewaySDK 字段控制是否走网关

### 不包含的功能（明确列入 TODO）
1. API_KEY 限流与管控
2. 模型 QPS 调用管控
3. Token 消耗计量
4. 模型管理（管理后台）

## 5. 业务流程
## 业务流程

### 自动初始化流程
原文提供了流程图（图片未加载），推测流程：
1. 服务启动
2. 加载配置（从数据库或配置中心）
3. 初始化 LLM 客户端
4. 准备就绪

### 模型调用流程（基于表结构推导）
1. 业务方发起请求（携带 api_key 和 model 标识）
2. 网关层（SDK 或 HTTP）接收请求
3. 鉴权：验证 api_key 有效性
4. 查找映射：通过 source_api_key + llm_code 找到 provider_api_key
5. 查找配置：通过 llm_code 找到 end_point、interface_protocol 等
6. 协议适配：将业务方请求按 interface_protocol 转换为目标 LLM 格式
7. 调用 LLM：使用 provider_api_key 调用目标端点
8. 返回结果：将 LLM 响应转换回业务方协议格式

### 切流流程
1. 业务请求到达
2. 读取 params_config.UseLLMGatewaySDK 配置
3. 判断目标模型是否在切流列表中
4. 是 → 走 llm-gateway-g 或 SDK
5. 否 → 走原有 agent-chat-model-g 逻辑

## 6. 状态流转
## 状态流转

原文未明确定义状态机。从表结构看，仅使用 is_delete 软删除标识，未见其他状态字段。

| 对象 | 已知状态 | 说明 |
|-----|---------|------|
| API Key | 有效 / 已删除 | 通过 is_delete 区分 |
| 模型配置 | 有效 / 已删除 | 通过 is_delete 区分 |
| 代理配置 | 有效 / 已删除 | 通过 is_delete 区分 |
| 分类 | 有效 / 已删除 | 通过 is_delete 区分 |
| API Key 映射 | 有效 / 已删除 | 通过 is_delete 区分 |

## 7. 业务规则
## 业务规则

| 规则类型 | 对象 | 规则描述 | 依据 |
|---------|------|---------|------|
| 唯一性规则 | api_keys | api_key 字段唯一 | 唯一索引 idx_api_keys_api_key |
| 索引规则 | api_keys | source + is_delete 联合索引 | 索引 idx_api_keys_source_delete |
| 唯一性规则 | llm_model_config | llm_code 唯一 | 唯一索引 uniq_index_llm_code |
| 必填规则 | llm_model_config | llm_code、llm_name、target_model、end_point、api_key、interface_protocol、create_name、update_name 非空 | 字段定义为 NOT NULL |
| 长度规则 | llm_model_config | llm_code 固定 6 字符 | 字段类型 char(6) |
| 索引规则 | llm_model_config | llm_name、target_model 建索引 | 索引 idx_llm_name、idx_target_model |
| 软删除规则 | 所有表 | 通过 is_delete 标记删除，未物理删除 | 所有表均有 is_delete 字段 |
| 必填规则 | proxy_config | proxy_name、proxy_url、creat_username、update_username 非空 | 字段定义为 NOT NULL |
| 长度规则 | proxy_config | proxy_url 最长 1024 字符 | 字段类型 varchar(1024) |
| 索引规则 | source_model_api_key | source_api_key + llm_code 联合索引 | 索引 idx_source_api_key_llm_code |
| 协议标识规则 | llm_model_config | interface_protocol 标识目标 LLM 的协议类型 | 字段含义 |
| 扩展配置规则 | llm_model_config | protocol_options 以 JSON 存储协议特定参数 | 字段类型为 JSON |

## 8. 页面与交互
## 页面与交互

原文未说明。

本期功能为后端服务/中间件，需求文档未涉及任何页面 UI 设计。模型配置管理（TODO）也未给出 UI 设计。

## 9. 数据与系统交互
## 数据与系统交互

### 数据库表结构

#### 1. api_keys - API Key 表
- id：bigint，主键自增
- api_key：varchar(255)，API Key 值，唯一
- source：varchar(255)，来源标识
- creat_time：datetime(3)，创建时间
- is_delete：int，软删除标记

#### 2. llm_info_classify - LLM 厂商/分类表
- id：bigint unsigned，主键
- classify_name：varchar(255)，分类名称
- user_name：varchar(255)，用户名
- icon：varchar(255)，图标
- create_time、update_time：datetime(3)
- is_delete：bigint，软删除标记

#### 3. llm_model_config - 模型配置表
- id：bigint，主键
- llm_code：char(6)，模型编码，唯一
- llm_name：varchar(255)，模型名称
- target_model：varchar(255)，目标模型标识
- end_point：varchar(255)，端点 URL
- api_key：text，模型 API Key
- interface_protocol：varchar(255)，接口协议
- api_version：varchar(64)，API 版本
- proxy_id：bigint，关联代理配置
- classify_id：bigint，关联分类
- protocol_options：json，协议扩展参数
- create_name、update_name：varchar(255)，创建/更新人
- create_time、update_time：datetime(3)
- is_delete：int，软删除标记

#### 4. proxy_config - 代理配置表
- id：bigint，主键
- proxy_name：varchar(255)，代理名称
- proxy_url：varchar(1024)，代理 URL
- creat_time、update_username：创建时间/更新人
- creat_username、update_username：varchar(255)，创建/更新人
- is_delete：int，软删除标记

#### 5. source_model_api_key - 源 API Key 与模型映射表
- id：bigint，主键
- source_api_key：varchar(255)，源 API Key
- llm_code：char(6)，模型编码
- provider_api_key：text，目标厂商 API Key
- api_version：varchar(64)，API 版本
- create_time、update_time：datetime(3)
- is_delete：bigint，软删除标记

### 系统交互
- 三方 LLM 厂商：通过 end_point + api_key 调用外部大模型 API
- Cybertron Agent：作为业务方调用方，验证网关功能
- 公司内部 LLM：通过 end_point 接入内部模型服务

### API 能力
原文未提供具体的 API 接口设计，仅说明提供 OpenAI 兼容协议。

### 测试环境
- 数据库实例：10.100.123.143:3306
- 数据库账号：u_cybertron_llm_gateway
- 库名：llm_gateway
