# 需求理解

## 1. 需求背景
当前模型网关服务 `agent-chat-model-g` 与业务存在较大耦合和绑定，不适合作为统一的网关层使用。为了解决该问题，需要将核心的与大模型 LLM 交互功能提取出来，沉淀为通用能力，供其他业务方复用。

## 2. 目标与价值
1. 解耦 LLM 交互能力与业务逻辑，沉淀通用网关能力。\n2. 提供统一接入 LLM 的网关层，支持三方及公司内大模型。\n3. 为 Go 语言服务提供 SDK 方式直接调用 LLM，减少 HTTP 通信带来的性能损耗。\n4. 支持以 OpenAI 通信协议对外提供服务。

## 3. 用户角色与使用场景
| 用户/调用方 | 使用场景 | 用户目标 |\n|---------|---------|---------|\n| 业务方服务（Go） | 通过 `llm-gateway-g-sdk` 直接调用 LLM | 减少 HTTP 通信损耗，调用各种大模型 |\n| 业务方服务（非 Go / 外部） | 通过 `llm-gateway-g` 的 OpenAI 协议调用 LLM | 统一协议接入多种大模型 |\n| Cybertron Agent | 对话使用模型网关调用 LLM（含 FunctionCall） | 验证模型网关能力 |\n| Go 版本对话流服务 | 使用 SDK 调用 LLM | 验证 SDK 能力 |\n| 模型配置管理员 | 配置模型、API Key、代理等 | 维护模型配置信息 |

## 4. 功能范围
**包含范围：**\n\n1. 提供 `llm-gateway-g` Web 服务，支持 OpenAI 通信协议。\n2. 提供 `llm-gateway-g-sdk`（Go SDK）核心调用能力。\n3. 模型配置管理（数据库表 `llm_model_config`）。\n4. 模型供应商/分类管理（数据库表 `llm_info_classify`）。\n5. 代理配置管理（数据库表 `proxy_config`）。\n6. API Key 管理（数据库表 `api_keys`）。\n7. 来源 API Key 与模型 Provider Key 的映射管理（数据库表 `source_model_api_key`）。\n8. 自动初始化流程。\n9. Cybertron Agent 对话（含 FunctionCall）调用模型网关验证。\n10. Go 版本对话流使用 SDK 调用 LLM 验证。\n11. Cybertron 中按模型逐渐切流配置（通过 `params_config` 中 `UseLLMGatewaySDK` 配置项）。\n\n**不包含范围（TODO 后续扩展）：**\n\n1. API_KEY 限流、管控。\n2. 模型 QPS 调用管控。\n3. Token 消耗计量。\n4. 模型管理功能。

## 5. 业务流程
### 自动初始化流程\n\n原文提供了自动初始化流程图（图片链接），核心是服务启动时自动加载/初始化相关配置。\n\n### 模型配置管理\n\n原文提供了模型配置管理流程（图片链接），涉及模型配置的新增/修改/查询等管理操作。\n\n```mermaid\ngraph TD\n    A[服务启动] --> B[自动初始化流程]\n    B --> C[加载模型配置 llm_model_config]\n    B --> D[加载 API Key 映射 source_model_api_key]\n    B --> E[加载代理配置 proxy_config]\n    C --> F[提供 LLM 调用能力]\n    D --> F\n    E --> F\n    F --> G[业务方通过 HTTP/SDK 调用]\n    G --> H[网关转发至对应 LLM Provider]\n```

## 6. 状态流转
| 对象 | 状态/字段 | 说明 |\n|-----|---------|------|\n| `llm_model_config` | `is_delete` | 0=有效，1=已删除（软删除） |\n| `api_keys` | `is_delete` | 0=有效，1=已删除（软删除） |\n| `proxy_config` | `is_delete` | 0=有效，1=已删除（软删除） |\n| `llm_info_classify` | `is_delete` | 0=有效，1=已删除（软删除） |\n| `source_model_api_key` | `is_delete` | 0=有效，1=已删除（软删除） |\n\n各表均采用 `is_delete` 软删除模式。模型配置通过 `params_config` 中 `UseLLMGatewaySDK` 配置项按模型逐渐切流，状态从直接调用切换为走网关/SDK。

## 7. 业务规则
| 规则类型 | 规则描述 |\n|---------|---------|\n| 唯一性约束 | `api_keys.api_key` 唯一 |\n| 唯一性约束 | `llm_model_config.llm_code` 唯一（char(6)） |\n| 索引 | `api_keys(source, is_delete)` 联合索引 |\n| 索引 | `llm_model_config(llm_name)`、`llm_model_config(target_model)`、`llm_model_config(is_delete)` |\n| 索引 | `source_model_api_key(source_api_key, llm_code)`、`source_model_api_key(source_api_key, is_delete)` |\n| 软删除 | 所有表均使用 `is_delete` 字段进行软删除 |\n| 切流规则 | 通过 `params_config` 中 `UseLLMGatewaySDK` 配置项，按模型逐个切换至网关/SDK 模式 |\n| API Key 映射 | `source_model_api_key` 表通过 `source_api_key + llm_code` 唯一定位 `provider_api_key` |\n| 模型关联 | `llm_model_config.proxy_id` 关联 `proxy_config.id` |\n| 模型关联 | `llm_model_config.classify_id` 关联 `llm_info_classify.id` |\n| 协议配置 | `llm_model_config.interface_protocol` 标识调用协议类型 |\n| 额外配置 | `llm_model_config.protocol_options` 存储 JSON 格式的协议扩展选项 |

## 8. 页面与交互
### 模型配置管理\n\n原文提供了模型配置管理界面（图片链接），用于管理模型配置信息。\n\n具体页面/交互细节原文未说明。\n\n涉及的核心操作（根据数据库表结构推断）：\n\n1. 维护模型供应商/分类（`llm_info_classify`）。\n2. 维护代理配置（`proxy_config`）。\n3. 维护模型配置（`llm_model_config`），包括 `llm_code`、`llm_name`、`target_model`、`end_point`、`api_key`、`interface_protocol`、`api_version`、`proxy_id`、`classify_id`、`protocol_options` 等。\n4. 维护 API Key 映射（`source_model_api_key`）。\n5. 维护 API Key（`api_keys`）。\n\n原文未说明是否有独立的 Web 管理后台、是否复用现有后台、权限控制等。

## 9. 数据与系统交互
### 数据库表\n\n| 表名 | 用途 | 核心字段 |\n|-----|------|---------|\n| `api_keys` | API Key 管理 | `api_key`（唯一）、`source`、`is_delete` |\n| `llm_info_classify` | LLM 供应商/分类 | `classify_name`、`user_name`、`icon`、`is_delete` |\n| `llm_model_config` | 模型配置 | `llm_code`（char(6) 唯一）、`llm_name`、`target_model`、`end_point`、`api_key`、`interface_protocol`、`api_version`、`proxy_id`、`classify_id`、`protocol_options`（JSON） |\n| `proxy_config` | 代理配置 | `proxy_name`、`proxy_url`、`creat_username`、`update_username`、`is_delete` |\n| `source_model_api_key` | 来源 API Key 与模型 Provider Key 映射 | `source_api_key` + `llm_code` 联合索引、`provider_api_key`、`api_version` |\n\n### 数据库连接（测试环境）\n\n- 实例：`10.100.123.143:3306`\n- 账号：`u_cybertron_llm_gateway`\n- 库名：`llm_gateway`\n\n### Cybertron 相关配置\n\n通过 `params_config` 中 `UseLLMGatewaySDK` 配置项控制切流模型，例如：\n\n```\nUseLLMGatewaySDK=[\"azure-gpt-4-jp\",\"Qwen2-72B-Instruct-AWQ\"]\n```\n\n### 系统交互\n\n1. `llm-gateway-g` 接收业务方 OpenAI 协议请求，查询模型配置，转发至对应 LLM Provider。\n2. `llm-gateway-g-sdk` 由 Go 服务直接引用，绕过 HTTP 调用 LLM。\n3. 支持 `proxy_config` 配置代理转发。\n4. 通过 `source_model_api_key` 实现多租户/多业务方的 API Key 隔离与映射。
