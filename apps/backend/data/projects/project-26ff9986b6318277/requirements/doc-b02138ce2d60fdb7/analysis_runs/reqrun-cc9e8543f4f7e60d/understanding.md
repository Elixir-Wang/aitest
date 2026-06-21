# 需求理解

## 1. 需求背景
现有模型网关服务 agent-chat-model-g 与业务存在较大耦合和绑定，不适合作为统一的网关层使用。需要将核心的与大模型 LLM 交互功能提取出来，形成通用功能沉淀，构建可被多业务方复用的统一接入层。

## 2. 目标与价值
1. 构建 llm-gateway-g Web 服务，对外提供 OpenAI 通信协议，统一接入各类大模型（包括三方和公司内部模型）。2. 构建 llm-gateway-g-sdk（Go SDK），供 Go 相关服务直接调用 LLM 能力，减少通过 HTTP 与 llm-gateway-g 交互带来的性能损耗。3. 将 LLM 交互能力与业务解耦，形成可沉淀的通用网关层。

## 3. 用户角色与使用场景
1. 内部 Go 服务：通过 llm-gateway-g-sdk 直接调用 LLM，避免 HTTP 性能损耗。2. 内部非 Go 业务服务（或三方服务）：通过 llm-gateway-g 提供的 OpenAI 兼容协议调用 LLM。3. 运维/管理员：通过模型配置管理功能维护 LLM 模型、API Key、代理等配置（具体用户角色原文未说明）。4. 首批接入方：Cybertron Agent 对话（含 FunctionCall 调用）、Go 版本对话流。

## 4. 功能范围
包含范围：\n1. llm-gateway-g Web 服务，提供 OpenAI 通信协议调用各类大模型。\n2. llm-gateway-g-sdk Go SDK，供 Go 服务本地调用 LLM。\n3. 5 张数据库表（api_keys、llm_info_classify、llm_model_config、proxy_config、source_model_api_key）支撑模型配置管理。\n4. 自动初始化流程。\n5. 模型配置管理功能。\n6. Cybertron Agent 对话（含 FunctionCall）和 Go 版本对话流的 LLM 调用迁移。\n7. 切流配置 params_config.UseLLMGatewaySDK，按模型粒度逐步切流。\n\n不包含范围（明确为 TODO 后续扩展）：\n1. API_KEY 限流、管控。\n2. 模型 QPS 调用管控。\n3. Token 消耗计量。\n4. 模型管理（具体指代原文未说明）。

## 5. 业务流程
1. 自动初始化流程：原文仅提供流程图（图片不可访问），具体步骤原文未说明。\n2. 模型配置管理：原文仅提及该流程名称，具体配置管理操作流程原文未说明。\n3. 调用链路（基于表结构推断）：调用方传入 source_api_key → 通过 source_model_api_key 关联到 llm_code 和 provider_api_key → 通过 llm_model_config 读取 end_point、target_model、interface_protocol、api_version、protocol_options（必要时通过 proxy_config 设置代理）→ 调用对应大模型。\n4. 切流流程：通过 params_config.UseLLMGatewaySDK 列表控制哪些模型走网关，未列出的模型保持原调用方式，按模型逐个切流。

## 6. 状态流转
原文未说明核心对象的状态流转。从表结构可观察到的软删除设计：\n1. api_keys：通过 is_delete 标识删除状态。\n2. llm_info_classify：通过 is_delete 标识删除状态。\n3. llm_model_config：通过 is_delete 标识删除状态。\n4. proxy_config：通过 is_delete 标识删除状态。\n5. source_model_api_key：通过 is_delete 标识删除状态。\n6. LLM 模型的启用/禁用状态、API Key 的启用/禁用状态、调用请求的成功/失败/重试状态等原文均未说明。

## 7. 业务规则
1. llm_model_config.llm_code 为 char(6) 类型，业务侧通过该 code 引用模型。\n2. llm_code 在表上同时存在 uniq_index_llm_code 和 uniq_index_llm_name 两个唯一索引（后者实际基于 llm_code 字段），需注意唯一性约束。\n3. 切流规则：按模型粒度切换，通过 params_config.UseLLMGatewaySDK 列表控制，列表内模型走新网关，未列出的保持原调用方式。\n4. api_key 字段以 text 类型存储（llm_model_config.api_key、source_model_api_key.provider_api_key），可存储较长的密钥。\n5. llm_model_config.api_key 与 source_model_api_key.provider_api_key 的关系（是否为多对一/一对多）原文未说明。\n6. 权限校验、调用频率限制、Token 用量统计、失败重试等规则原文均未说明（部分已列为 TODO）。

## 8. 页面与交互
本文档为后端网关/SDK 设计，未涉及前端页面。仅提供架构设计图和自动初始化流程图（图片不可访问）。是否需要模型配置管理的管理后台页面、是否需要调用监控/统计可视化页面，原文均未说明。

## 9. 数据与系统交互
数据库：MySQL 实例 10.100.123.143:3306，库名 llm_gateway，账号 u_cybertron_llm_gateway。\n\n涉及 5 张表：\n1. api_keys：存储 API Key 与来源（source），字段包括 id、api_key（唯一）、source、creat_time、is_delete。\n2. llm_info_classify：LLM 厂商/分类信息，字段包括 id、classify_name、user_name、icon、create_time、update_time、is_delete。\n3. llm_model_config：模型配置主表，字段包括 id、llm_code（char(6)，唯一）、llm_name、target_model、end_point、api_key、interface_protocol、api_version、proxy_id、classify_id、create_name、update_name、create_time、update_time、is_delete、protocol_options（JSON）。\n4. proxy_config：代理配置，字段包括 id、proxy_name、proxy_url、creat_time、is_delete、creat_username、update_username。\n5. source_model_api_key：业务方 API Key 与模型 provider 密钥的映射，字段包括 id、source_api_key、llm_code、provider_api_key、create_time、update_time、is_delete、api_version。\n\n外部依赖：\n1. params_config 配置中心：存储 UseLLMGatewaySDK 切流列表。\n2. 各大模型厂商的 OpenAI 兼容接口（具体厂商列表原文未说明）。\n3. Cybertron Agent、Go 版本对话流等业务调用方。\n\n外部系统交互协议：OpenAI 兼容通信协议。
