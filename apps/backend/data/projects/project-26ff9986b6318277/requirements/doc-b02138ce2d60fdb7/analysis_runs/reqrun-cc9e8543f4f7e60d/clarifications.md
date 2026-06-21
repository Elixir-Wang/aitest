# 待澄清问题

| 优先级 | 模块/对象 | 澄清问题 | 影响 |
|-------|----------|---------|------|
| P0 | 核心架构 | llm-gateway-g 与 llm-gateway-g-sdk 之间的边界如何划分？即哪些能力放在 Web 服务层、哪些能力放在 SDK 层？例如鉴权、限流、协议转换、参数透传、protocol_options 解析等是否两侧都实现，还是只在 SDK 实现、Web 服务仅做透传？ | 影响整体代码组织、复用程度、后续维护成本，以及 SDK 是否能脱离 Web 服务独立运行。 |
| P0 | API Key 管理 | api_keys 表与 source_model_api_key 表的关系是什么？api_keys 似乎存储原始来源 key，source_model_api_key 存储业务方 key 到 provider key 的映射，但二者如何联动（是否 source_api_key 必须先存在于 api_keys 表中）？source_api_key 的生成/发放流程是什么，由谁在什么场景下创建？ | 决定 API Key 申请、发放、吊销流程，影响业务方接入步骤和权限管控粒度。 |
| P0 | OpenAI 协议支持范围 | llm-gateway-g 需要支持 OpenAI 协议的哪些接口？是仅支持 /v1/chat/completions，还是同时需要支持 /v1/completions、/v1/embeddings、/v1/images/generations、/v1/audio/*、/v1/finetune/*、/v1/files 等？是否需要支持 Function Calling、Tool Use、Vision、Streaming、JSON Mode 等高级特性？ | 决定 SDK 需要实现的协议适配范围，影响工作量和后续业务方接入兼容性。 |
| P0 | 切流方案 | params_config.UseLLMGatewaySDK 的切流粒度具体如何工作？是以 llm_code 还是 target_model 为 key？切流期间是否同时调用新旧链路做对比验证？回滚机制是什么？切流后旧链路 agent-chat-model-g 是否同步下线？ | 影响上线策略、回滚能力、对线上业务的影响范围，是上线前的关键决策点。 |
| P1 | 自动初始化流程 | 自动初始化流程具体包括哪些步骤？是在服务启动时从数据库加载配置到内存缓存，还是包含表数据初始化、SDK 注册、心跳上报等？初始化失败的兜底策略是什么？配置变更后的热更新机制是怎样的？ | 决定服务启动依赖、运行期配置更新方式、故障恢复能力。 |
| P1 | 模型配置管理 | 模型配置管理提供哪些操作能力？是否包含 CRUD、启停、版本管理、灰度发布、配置导入导出？管理入口是管理后台 Web 页面、API 接口，还是仅直接操作数据库？谁有权限进行配置变更？ | 决定运维管理界面的开发范围和权限体系设计。 |
| P1 | protocol_options 字段 | llm_model_config.protocol_options 字段（JSON 类型）的结构定义是什么？包含哪些参数？用于解决不同厂商协议差异（Azure/OpenAI/Anthropic/国产模型等）的哪些问题？interface_protocol 枚举值有哪些？ | 影响 SDK 对不同 LLM 厂商的适配实现方式，是协议兼容层的核心数据结构。 |
| P1 | 代理与网络 | proxy_config 的使用场景是什么？是用于出公网代理（如 Azure OpenAI 区域访问），还是用于内网模型代理？是否支持多级代理？是否所有模型都需要代理，还是仅特定厂商需要？ | 影响网络架构设计和代理选型。 |
| P1 | 鉴权与权限 | 调用 llm-gateway-g 时，调用方如何鉴权？是使用 source_api_key（类似 OpenAI 的 Bearer Token），还是其他方式？是否区分调用方身份？是否需要支持调用方级别的模型白名单、配额控制？ | 决定鉴权中间件设计和 API 安全模型。 |
| P1 | 错误处理与降级 | 当上游 LLM 厂商接口超时、限流、返回错误时，网关层的处理策略是什么？是否支持多模型 failover（如主模型失败自动切换备用模型）？是否支持重试机制？最大重试次数和退避策略是什么？ | 决定网关的可用性和稳定性，影响业务方的容错设计。 |
| P1 | Function Calling | Function Calling 在不同厂商之间协议差异较大（如 OpenAI tools 字段 vs Anthropic tool_use vs 国产模型自有格式），网关如何做统一抽象？是否对业务方屏蔽差异？tool 描述的 schema 是否需要做厂商间的映射转换？ | 影响 Cybertron Agent 等依赖 Function Calling 的业务方的接入难度和兼容性。 |
| P2 | 性能与可观测性 | 网关层是否有明确的性能指标要求（QPS、P99 延迟、并发数）？是否需要记录请求日志、调用链路追踪（TraceID）、调用耗时统计？日志和监控指标采集方案是什么？ | 影响可观测性建设和后续问题排查能力。 |
| P2 | 数据一致性 | llm_model_config 中的 api_key 字段与 source_model_api_key 中的 provider_api_key 都存储了密钥，二者更新时的同步策略是什么？以哪个为准？是否存在一份密钥变更需要同步到另一份的场景？ | 影响密钥轮换流程和数据一致性保障。 |
| P2 | SDK 集成方式 | llm-gateway-g-sdk 的集成方式是 go get 引入，还是作为独立子模块/独立服务引入？SDK 内部是否需要持久化连接（连接池）？SDK 是否需要与服务注册中心、配置中心集成以实现动态刷新？ | 影响业务方升级 SDK 的成本和 SDK 自身的可维护性。 |
| P2 | 数据生命周期 | 5 张表中 create_name、update_name、user_name 等操作人字段是否需要对接用户系统（如 LDAP/OA）实现下拉选择？creat_time 等时间字段的精度和时区要求是什么？是否需要审计日志记录配置变更历史？ | 影响审计能力和问题追溯。 |
| P3 | TODO 扩展项优先级 | TODO 中的 4 项（API_KEY 限流管控、模型 QPS 管控、Token 消耗计量、模型管理）在本期是否有部分要提前实现？或者本期仅做架构打底，所有管控能力后续迭代？ | 决定本期交付范围和后续迭代节奏。 |
| P3 | 部署与多环境 | llm-gateway-g 和 llm-gateway-g-sdk 是否需要支持多环境部署（开发/测试/预发/生产）？是否需要支持多租户/多集群？跨环境配置如何隔离？ | 影响部署架构和配置管理方案。 |
