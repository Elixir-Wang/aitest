# 待澄清问题

| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |
|-------|----------|---------|--------|--------|------|
| P0 | 模型调用路由 | 网关收到业务方请求后，如何确定路由到哪个 LLM 模型配置？模型选择/路由的完整逻辑是什么？ | 业务方在请求中通过 model 字段指定目标模型，网关通过 source_model_api_key 找到对应的 llm_code，再通过 llm_model_config 路由到目标端点 | 网关根据 source_api_key + 模型名称直接查找 llm_model_config，跳过 source_model_api_key 的映射层 | 影响核心调用流程的设计和实现，阻塞开发主线 |
| P0 | 协议适配 | interface_protocol 字段支持哪些协议值？不同协议之间的转换（适配）逻辑在哪里实现？ | interface_protocol 枚举值包括 openai、azure-openai、anthropic、custom 等，网关在 llm-gateway-g 内部完成协议转换 | interface_protocol 仅作标识，实际协议转换由各 LLM 厂商 SDK 在 llm-gateway-g-sdk 中分别实现 | 影响协议适配层的设计，是网关的核心能力之一 |
| P0 | SDK 设计 | llm-gateway-g-sdk 的初始化方式是什么？业务方如何获取配置和初始化客户端？ | SDK 提供 Init(config) 方法，配置项包括 API Key、端点地址等，业务方在服务启动时显式调用 | SDK 自动从环境变量或配置中心（如 params_config）加载配置，业务方无需显式初始化 | 影响 SDK 的使用方式和业务方接入成本 |
| P0 | API 鉴权 | api_keys 和 source_model_api_key 两张表的鉴权流程是什么？业务方调用时如何验证身份？ | 业务方在请求头携带 api_key，网关先查 api_keys 表验证有效性，再查 source_model_api_key 找到对应的 provider_api_key 替换后调用 LLM | api_keys 表仅记录 API Key 存在性，source_model_api_key 表同时承担鉴权和映射职责 | 影响安全性和调用链路设计 |
| P0 | 测试范围 | FunctionCall 调用的具体测试场景是什么？是否需要支持工具调用的完整链路（工具注册、调用、结果回传）？ | FunctionCall 仅验证 LLM 返回工具调用请求，业务方自行处理工具执行和结果回传 | 网关需要透传完整的工具调用链路，包括工具 schema 传递、调用结果回传给 LLM | 影响 FunctionCall 功能的实现范围和测试用例设计 |
| P1 | 异常处理 | 当 LLM 厂商接口调用失败（如超时、限流、返回 5xx）时，网关如何处理？是否支持重试和降级？ | 网关返回原始错误信息给业务方，不做自动重试，由业务方决定重试策略 | 网关内置重试机制（如最多 3 次，指数退避），重试失败后返回错误，支持配置开关 | 影响系统的稳定性和业务方的容错实现 |
| P1 | 流式响应 | 网关是否支持流式响应（SSE/Streaming）？OpenAI 协议的流式调用如何处理？ | 网关完整支持 OpenAI 流式协议（SSE），业务方可通过 stream=true 参数启用 | 本期仅支持非流式调用，流式响应在后续版本支持 | 影响对话类应用（如 Cybertron Agent）的用户体验和功能完整性 |
| P1 | 超时配置 | LLM 调用的超时时间如何配置？不同模型是否可以设置不同的超时时间？ | 网关使用统一默认超时（如 60 秒），所有模型共用，不支持按模型差异化配置 | 支持在 llm_model_config 中通过 protocol_options 配置每个模型的超时时间 | 影响长文本生成场景的可用性和系统稳定性 |
| P1 | 配置热更新 | llm_model_config 等配置变更后，是否需要重启服务才能生效？是否支持热加载？ | 配置变更后需要重启 llm-gateway-g 服务才能生效，SDK 端需要重启业务服务 | 网关层支持配置热加载（定时轮询或事件通知），SDK 端在调用时实时查询最新配置 | 影响运维效率和配置变更的响应速度 |
| P1 | 切流策略 | params_config 的 UseLLMGatewaySDK 切流是按模型粒度还是按请求粒度？切流期间如何处理同时存在新旧两套调用链路的兼容？ | 切流按模型粒度，列表内的模型走网关，列表外的走原 agent-chat-model-g，两套链路并存直至全部切完 | 切流按请求粒度（如灰度比例），同一模型部分请求走网关，部分走原链路 | 影响灰度发布的策略和上线风险控制 |
| P1 | 代理配置 | proxy_config 表的代理使用场景是什么？哪些模型调用需要走代理？ | 代理用于访问外网 LLM 厂商（如 OpenAI），通过 llm_model_config.proxy_id 关联；公司内部模型不走代理 | 所有模型都可通过 proxy_id 配置代理，具体是否走代理由配置决定 | 影响网络架构设计，特别是访问外网模型的连通性方案 |
| P1 | 日志与监控 | 网关调用 LLM 时是否需要记录请求/响应日志？是否需要对接公司内的监控/告警系统？ | 网关记录请求和响应日志（脱敏后的 API Key），对接公司内的日志平台和监控系统 | 本期仅记录关键调用信息（模型、耗时、状态码），不记录完整请求/响应内容 | 影响问题排查效率和系统可观测性 |
| P2 | 数据迁移 | 上线时如何将 agent-chat-model-g 中已有的模型配置迁移到新网关的 llm_model_config 表？是否需要数据迁移脚本？ | 提供一次性数据迁移脚本，从 agent-chat-model-g 导出配置后导入到 llm_model_config | 需要手动重新在 llm_model_config 表中录入配置，迁移工作由运维完成 | 影响上线步骤和过渡期配置准确性 |
| P2 | 并发安全 | 当 API Key、模型配置等信息发生变更时，正在进行的请求如何处理？是否存在并发读写冲突问题？ | 配置变更不影响已发起的请求，正在进行的请求使用变更前的配置完成调用 | 配置变更立即生效，可能导致部分正在进行的请求因配置不一致而出错 | 影响配置变更期间的请求正确性 |
| P2 | 接口协议兼容性 | 对外提供的 OpenAI 兼容协议覆盖哪些接口？是否包括 /v1/chat/completions、/v1/embeddings、/v1/models 等？ | 本期仅实现 /v1/chat/completions 接口（对话），其他接口在后续版本支持 | 完整实现 OpenAI 所有常用接口（chat/completions、embeddings、models、images 等） | 影响业务方接入范围和兼容性 |
| P2 | API Key 加密 | llm_model_config.api_key 和 source_model_api_key.provider_api_key 字段存储的是明文还是密文？数据库层面是否加密？ | 数据库存储明文 API Key，通过应用层控制访问权限，依赖数据库安全策略 | API Key 在存储前加密（如 AES），应用层解密后使用 | 影响敏感数据安全和数据库泄露风险 |
| P3 | 扩展性 | protocol_options（json 字段）当前规划支持哪些扩展参数？是否需要定义 JSON Schema 约束？ | protocol_options 为自由扩展字段，不做格式约束，由各协议自行定义 | 需要为 protocol_options 定义 JSON Schema，约束可配置的参数范围 | 影响后续扩展新协议时的配置规范和兼容性 |
