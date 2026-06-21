# 待澄清问题

| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |
|-------|----------|---------|--------|--------|------|
| P0 | 网关认证 | 业务方调用 `llm-gateway-g` 时，如何进行身份认证？ | 调用方在请求头携带 `source_api_key`，网关通过 `source_model_api_key` 表验证并映射到对应 `provider_api_key` | 调用方在请求头携带 `api_key`，网关通过 `api_keys` 表验证合法性 | 影响网关安全设计、API Key 发放流程以及多业务方接入实现 |
| P0 | source_model_api_key 映射 | `source_model_api_key` 表中 `source_api_key` 与 `provider_api_key` 的映射逻辑是什么？ | 一个 source_api_key 可映射多个 llm_code，每个 llm_code 对应一个 provider_api_key（即按模型隔离） | 一个 source_api_key 绑定一个 provider_api_key，请求时根据请求模型自动匹配 provider_api_key | 影响网关路由逻辑、API Key 分配粒度以及多业务方计费/隔离能力 |
| P0 | 切流策略 | Cybertron 中 `UseLLMGatewaySDK` 的逐渐切流具体规则是什么？ | 白名单机制：列表中的模型走网关/SDK，其他模型保持原逻辑；逐步将模型加入列表 | 灰度比例机制：按流量比例切流（如 10%、50%、100%），通过配置项动态调整 | 影响上线策略、回滚方案以及灰度验证流程 |
| P0 | OpenAI 协议支持范围 | `llm-gateway-g` 需要兼容的 OpenAI 协议接口范围是什么？ | 仅支持 chat/completions 接口（含 FunctionCall） | 支持 chat/completions、embeddings、images/generations 等多个接口 | 影响接口实现范围、SDK 封装范围以及多模态支持能力 |
| P0 | 自动初始化流程 | 自动初始化流程具体执行什么操作？ | 服务启动时从数据库加载模型配置、API Key、代理配置到内存缓存，并刷新配置变更 | 服务启动时检查并初始化数据库表、默认配置项、客户端连接池等 | 影响服务启动逻辑、配置热更新能力以及数据一致性保障 |
| P0 | 代理选择 | 模型配置中 `proxy_id` 为空时如何处理？代理是否按请求动态选择？ | proxy_id 为空表示直连，不使用代理；代理由模型配置静态绑定 | 支持代理动态选择（如按 region、模型类型等策略），proxy_id 为空时走默认代理 | 影响网络访问能力、跨境访问合规性以及代理池管理复杂度 |
| P1 | llm_code 生成 | `llm_model_config.llm_code`（char(6)）的编码规则是什么？ | 系统自动生成（如基于模型名称哈希或递增序列），保证全局唯一 | 管理员手工录入 6 位编码，作为模型的简写标识 | 影响模型识别效率、API Key 映射索引以及人工维护成本 |
| P1 | 错误处理 | LLM 调用失败时的错误处理和重试策略是什么？ | 网关层不做重试，直接将 Provider 错误透传给调用方 | 网关层对可恢复错误（如超时、限流）进行有限次数重试，并支持 fallback 到备用模型 | 影响服务可用性、用户体验以及下游 Provider 压力 |
| P1 | protocol_options | `llm_model_config.protocol_options`（JSON）字段存储哪些协议扩展选项？ | 存储不同 Provider 的私有参数（如 temperature、top_p、extra_headers 等透传参数） | 存储协议转换规则（如响应格式映射、流式输出配置等） | 影响多模型适配能力、字段扩展灵活性以及数据规范性 |
| P1 | FunctionCall 透传 | FunctionCall 调用通过网关时，是否需要特殊处理（如 tools 参数转换、响应解析等）？ | 网关透明转发 tools/tool_choice 等参数，仅做协议层转换，不做语义处理 | 网关做统一适配，将不同 Provider 的 FunctionCall 协议统一为 OpenAI 格式 | 影响 FunctionCall 兼容性、协议适配复杂度以及多模型一致体验 |
| P1 | 流式输出 | 网关是否需要支持流式输出（SSE/Streaming）？ | 支持流式输出（Server-Sent Events），透传 Provider 的流式响应 | 仅支持非流式输出，统一返回完整结果 | 影响对话场景体验、网关性能以及实现复杂度 |
| P1 | API Key 安全 | `api_keys` 和 `provider_api_key` 在数据库中是否加密存储？ | 明文存储（当前表结构为 text/varchar） | 加密存储（如 AES），网关层解密后使用 | 影响数据安全合规性、数据库泄露风险等级 |
| P1 | 配置管理界面 | 模型配置管理界面是否包含在本期需求中？ | 本期需求包含 Web 管理界面（CRUD 模型、API Key、代理、分类等） | 本期需求不包含管理界面，仅通过数据库手工维护，后续再做 | 影响本期交付范围、开发工作量以及上线后运维方式 |
| P2 | TODO 功能 | TODO 列出的功能（API_KEY 限流、QPS 管控、Token 计量、模型管理）是否在本次需求中实现？ | 本次需求不实现，仅在 TODO 中预留接口和数据结构 | 本次需求部分实现（如预留限流框架，但阈值由后续版本配置） | 影响本次需求边界、接口预留设计以及后续迭代计划 |
| P2 | 日志与监控 | 网关调用 LLM 时是否记录请求/响应日志？是否对接监控/告警系统？ | 记录调用日志（请求 ID、模型、耗时、Token 数、状态码等），不接入监控告警 | 记录完整审计日志，并对接 Prometheus/告警系统等 | 影响问题排查效率、运营观测能力以及告警及时性 |
| P2 | 分类管理 | `llm_info_classify`（LLM 供应商/分类）的分类体系如何定义？由谁维护？ | 预置固定分类（如 OpenAI、Azure、Qwen、文心一言等），管理员仅维护图标和名称 | 管理员自由维护分类，用于模型分组和权限管控 | 影响分类管理界面、权限控制粒度以及模型组织方式 |
