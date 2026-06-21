# 待澄清问题

| 优先级 | 模块/对象 | 澄清问题 | 选项 A | 选项 B | 影响 |
|-------|----------|---------|--------|--------|------|
| P0 | API Key 管理 | 业务方调用 llm-gateway-g 网关时，如何通过 api_key 识别调用方身份并完成鉴权？ | 调用方在请求头携带 api_key，网关用 api_key + source 定位 source_model_api_key，再映射到底层 provider_api_key | 调用方在请求体中传入 api_key 与 source，网关通过查询 source_model_api_key 表鉴权 | 影响网关鉴权流程设计、SDK 接口形态以及对外暴露的协议细节 |
| P0 | 模型配置 | llm_model_config 中 interface_protocol 字段支持的取值有哪些？不同协议下请求/响应的转换逻辑由谁负责？ | 由 llm-gateway-g 网关层统一适配：无论底层协议如何，对外一律返回 OpenAI 兼容协议 | 由 llm-gateway-g-sdk 在调用侧适配：SDK 根据 protocol 自行转换后再调用底层 | 影响网关与 SDK 的职责边界，以及协议适配层的位置和复杂度 |
| P0 | 自动初始化 | 自动初始化流程的具体步骤是什么？初始化失败时网关如何处理（启动失败/降级/重试）？ | 启动时从配置中心拉取模型列表入库，失败则启动失败并告警 | 启动时仅加载内存配置，失败则按空配置启动并在后台异步重试加载 | 影响网关启动可靠性、首次调用延迟以及运维排障方式 |
| P0 | API Key 管理 | api_keys 与 source_model_api_key 两张表的区别与使用场景是什么？ | api_keys 记录调用方在网关层的统一凭证；source_model_api_key 记录调用方凭证与底层厂商凭证的映射关系，用于实际转发 | api_keys 是历史遗留表，新逻辑统一使用 source_model_api_key；api_keys 仅做兼容保留 | 影响鉴权链路设计以及存量数据迁移方案 |
| P1 | 模型配置 | llm_model_config.api_key 字段（text 类型）与 source_model_api_key.provider_api_key 的职责如何划分？ | llm_model_config.api_key 作为该模型默认底层凭证；source_model_api_key 中的 provider_api_key 用于按调用方覆盖 | llm_model_config.api_key 仅作展示用，实际调用一律走 source_model_api_key 中的 provider_api_key | 影响密钥管理、调用优先级以及安全审计方式 |
| P1 | 代理配置 | proxy_config 的 proxy_url 使用场景是什么？是否所有 LLM 调用都强制走代理？ | 仅当 llm_model_config.proxy_id 非空时走代理，否则直接访问 end_point | 所有调用统一走代理，proxy_id 仅用于选择不同代理出口 | 影响网络拓扑以及底层 LLM 端点的可达性 |
| P1 | 切流/灰度 | Cybertron 通过 params_config.UseLLMGatewaySDK 按模型切流，未在列表中的模型调用网关时如何处理？ | 未命中列表的模型仍走旧链路（agent-chat-model-g），网关不接收此类请求 | 网关兼容所有模型，未在 UseLLMGatewaySDK 列表中的模型调用时网关自动兜底 | 影响灰度切流策略、回滚方案以及网关的兼容边界 |
| P1 | 限流与计量 | TODO 中提及的 API_KEY 限流、模型 QPS 管控、Token 消耗计量在本次需求中的优先级与实现深度？ | 本次仅预留扩展点（接口/埋点），不实现真正的限流与计量逻辑 | 本次需实现基础限流与计量，关键指标落库可查询 | 影响本期开发范围、性能开销以及与后续迭代的衔接 |
| P1 | FunctionCall | Cybertron Agent 的 FunctionCall 调用，网关是否需要解析/校验 tool_call 字段？还是仅做透传？ | 网关仅做协议透传，FunctionCall 的解析与校验由业务方（Agent）负责 | 网关在协议层做 FunctionCall 字段标准化（如统一 tool 命名空间） | 影响网关在 FunctionCall 场景下的兼容性与责任范围 |
| P1 | 异常处理 | 底层 LLM 调用失败（超时/429/5xx）时，网关的默认行为是什么？是否进行重试或失败透传？ | 网关不做自动重试，直接将底层错误按 OpenAI 错误格式透传给业务方 | 网关对可重试错误（429/5xx）按策略重试 N 次，最终失败再透传 | 影响用户体验、调用成功率以及下游 LLM 厂商的压力 |
| P2 | 协议扩展 | protocol_options（json 字段）的结构与支持项有哪些？本次需求是否需要定义 schema？ | protocol_options 为预留扩展字段，本期不约束 schema，按需透传 | 本期需定义 protocol_options 的标准 schema（温度、top_p、最大长度等） | 影响后续模型参数配置的统一性与可维护性 |
| P2 | 数据生命周期 | api_key、provider_api_key 等敏感字段在数据库中是否需要加密存储？ | 明文存储，依赖数据库访问控制保障安全（与现状一致） | 使用 KMS/应用层加密存储，密钥由配置中心下发 | 影响安全合规等级以及运维/排障方式 |
| P2 | 日志与监控 | 本期是否需要记录 LLM 调用的请求/响应日志与监控指标（成功率、延迟等）？ | 本期仅记录关键链路日志（鉴权、转发结果），不接入监控指标 | 本期需输出 Prometheus 指标（QPS/P99/错误率），便于后续切流观察 | 影响上线后切流判断与故障定位效率 |
| P3 | 模型管理 | TODO 中的「模型管理」是指后台 CRUD 页面，还是仅指配置接口？本期是否需要后台界面？ | 本期不做后台页面，仅提供配置数据初始化与 API | 本期需提供简易后台页面用于模型/API Key/代理的增删改查 | 影响交付物形态与运维操作成本 |
