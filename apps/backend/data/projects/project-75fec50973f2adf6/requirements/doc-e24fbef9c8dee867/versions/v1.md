# 需求理解

## 1. 需求背景
当前 `agent-chat-model-g` 服务与业务有较大的耦合和绑定，不适合作为统一的网关层使用。为了支持多个业务方统一接入大模型能力，需要将核心的与大模型 LLM 交互的功能提取出来，形成独立的通用网关层和 SDK，避免业务代码与 LLM 通信协议强耦合，同时减少 HTTP 调用带来的性能损耗。

当前痛点：
1. `agent-chat-model-g` 与业务耦合严重，无法作为通用基础设施复用
2. 多个业务方各自接入 LLM，存在重复开发
3. Go 服务通过 HTTP 调用 LLM 网关存在额外性能损耗

项目交付两个核心组件：
- **llm-gateway-g**：Web 服务应用，提供 OpenAI 兼容协议供其他业务方调用
- **llm-gateway-g-sdk**：Go SDK，供 Go 相关服务直接调用，减少 HTTP 交互性能损耗

## 2. 目标与价值
**业务目标**：
1. 将 LLM 交互能力从 `agent-chat-model-g` 中剥离，形成可复用的通用基础设施
2. 通过统一网关屏蔽不同 LLM 厂商（Azure、Qwen 等）的协议差异
3. 为 Go 服务提供 SDK 直连能力，减少 HTTP 调用带来的性能损耗

**技术目标**：
1. 提供 OpenAI 兼容的统一接入协议
2. 支持多种 LLM 接口协议（通过 `interface_protocol` 字段区分）
3. 支持代理配置（`proxy_config`）解决网络访问问题
4. 支持 API Key 映射机制（`source_model_api_key`）实现上游 Key 与下游 Key 的解耦

**业务价值**：
1. 统一管控所有 LLM 调用入口
2. 降低新业务接入 LLM 的成本
3. 为后续限流、计量、模型管理等能力提供基础

原文未说明具体的可衡量指标（如 QPS 目标、延迟目标、可用性目标）。

## 3. 用户角色与使用场景
| 用户角色 | 使用场景 | 用户目标 | 已知约束 |
|---------|---------|---------|---------|
| Cybertron Agent | 对话场景使用 LLM（包括 FunctionCall） | 通过网关调用 LLM 能力 | 需要支持 FunctionCall |
| Go 版本对话流服务 | 使用 llm-gateway-g-sdk 调用 LLM | 减少 HTTP 性能损耗 | 仅限 Go 语言服务 |
| 业务方（未来） | 通过 OpenAI 兼容协议调用 LLM | 屏蔽厂商差异，统一接入 | 需要 source_api_key 进行身份认证 |
| 平台管理员 | 管理模型配置、分类、代理、API Key | 维护网关正常运行 | 原文未明确管理员角色和权限 |
| LLM 厂商（三方/公司内） | 作为上游提供模型能力 | 被网关调用 | 通过 end_point 和 api_key 区分 |

原文未说明：
- 是否存在终端用户（最终调用方应用的最终用户）
- 管理员的具体权限模型和操作入口

## 4. 功能范围
**包含的功能**：
1. `llm-gateway-g` Web 服务：
   - 提供 OpenAI 兼容协议的 LLM 调用接口
   - 模型配置管理（增删改查）
   - LLM 分类管理（`llm_info_classify`）
   - 代理配置管理（`proxy_config`）
   - API Key 管理（`api_keys`、`source_model_api_key`）
2. `llm-gateway-g-sdk` Go SDK：
   - 核心 LLM 调用能力封装
   - 支持 FunctionCall
3. 自动初始化流程
4. 通过 `params_config` 中的 `UseLLMGatewaySDK` 配置控制 SDK 调用范围（按模型逐步切流）

**不包含的功能（TODO 扩展）**：
1. API_KEY 限流管控
2. 模型 QPS 调用管控
3. Token 消耗计量
4. 模型管理（具体范围未明确）

**与现有功能的关系**：
- 现有 `agent-chat-model-g` 服务的核心能力下沉到网关
- Cybertron Agent 和 Go 对话流是首批接入方，按模型逐步切流

## 5. 业务流程
**自动初始化流程**（基于流程图描述）：
1. 服务启动时加载配置
2. 读取 `params_config` 中的 `UseLLMGatewaySDK` 配置
3. 判断目标模型是否在 SDK 切流名单中
4. 是 → 使用 SDK 直接调用 LLM
5. 否 → 通过 HTTP 调用 llm-gateway-g

**模型调用主流程**：
1. 业务方携带 `source_api_key` 调用 llm-gateway-g（或通过 SDK 调用）
2. 网关根据 `source_api_key` + `llm_code` 在 `source_model_api_key` 中查找对应的 `provider_api_key`
3. 根据 `llm_code` 在 `llm_model_config` 中加载目标模型配置（end_point、interface_protocol、proxy_id、classify_id 等）
4. 若 `proxy_id` 非空，加载 `proxy_config` 配置代理
5. 网关将请求转换为目标 LLM 的协议格式
6. 调用上游 LLM 并返回结果

原文未说明：
- 自动初始化流程中具体的初始化步骤和异常处理
- 模型配置修改后的生效机制（实时生效还是重启生效）
- FunctionCall 的特殊处理流程

## 6. 状态流转
**llm_model_config 状态**：
原文未明确说明配置的状态字段（如启用/禁用、测试中/已发布等），仅通过 `is_delete` 字段实现软删除。

**source_model_api_key 状态**：
原文未明确说明 Key 的状态机，仅通过 `is_delete` 实现软删除。

**模型调用任务状态**：
原文未提供异步任务的状态流转信息。

**配置版本管理**：
原文未说明模型配置修改是否有版本控制、审批流程。

**核心状态对象识别**：
| 状态对象 | 已识别状态 | 缺失状态 |
|---------|-----------|---------|
| llm_model_config | 有效（is_delete=0）、已删除（is_delete=1） | 启用/禁用、测试/生产、灰度发布等 |
| source_model_api_key | 有效、已删除 | 启用/禁用、过期、配额耗尽等 |
| api_keys | 有效、已删除 | 启用/禁用、过期等 |
| 调用请求 | 原文未定义 | 待补充：执行中、成功、失败、超时等 |

## 7. 业务规则
**校验规则**：

| 规则类型 | 触发条件 | 判断逻辑 | 处理结果 |
|---------|---------|---------|---------|
| 唯一性 | 插入 api_keys | api_key 唯一 | 冲突时返回错误 |
| 唯一性 | llm_model_config | llm_code 唯一（uniq_index_llm_code） | 冲突时返回错误 |
| 必填校验 | llm_model_config | api_key、end_point、interface_protocol、llm_code、llm_name、target_model、create_name、update_name 非空 | 缺失时返回错误 |
| 必填校验 | proxy_config | proxy_name、proxy_url、creat_username、update_username 非空 | 缺失时返回错误 |
| 必填校验 | source_model_api_key | source_api_key、llm_code、provider_api_key 非空 | 缺失时返回错误 |
| 软删除 | 所有表 | 通过 is_delete 标记 | 删除时设置 is_delete=1 |

**映射规则**：
1. 通过 `source_api_key` + `llm_code` 在 `source_model_api_key` 表中查找对应的 `provider_api_key`
2. 通过 `llm_code` 在 `llm_model_config` 中查找模型配置
3. 通过 `proxy_id` 在 `proxy_config` 中查找代理配置

**协议规则**：
1. `interface_protocol` 字段决定使用哪种协议调用上游 LLM
2. `api_version` 字段用于指定协议版本（可空）
3. `protocol_options` JSON 字段存储协议相关配置（用途未明确）

**权限规则**：
原文未明确说明管理员的权限模型和操作审计要求。

**切流规则**：
通过 `params_config` 的 `UseLLMGatewaySDK` 数组控制 SDK 接入的模型范围，例如 `["azure-gpt-4-jp","Qwen2-72B-Instruct-AWQ"]`。

原文未说明：
- api_key 的格式校验规则（长度、字符集）
- proxy_url 的格式校验
- llm_code 的生成规则（char(6) 但未说明编码方式）
- 调用频率、并发数的限制

## 8. 页面与交互
**模型配置管理页面**：
原文仅提及"模型配置管理"标题，未给出具体的页面设计。

从数据库结构推测，至少需要以下管理页面：
1. **LLM 模型配置列表页**：展示模型编码、名称、目标模型、接口协议、创建人、更新时间
2. **LLM 模型配置编辑页**：编辑 llm_code、llm_name、target_model、end_point、api_key、interface_protocol、api_version、proxy_id、classify_id、protocol_options
3. **LLM 分类管理页**：管理 classify_name、icon
4. **代理配置管理页**：管理 proxy_name、proxy_url
5. **API Key 管理页**：管理 source_api_key 与 provider_api_key 的映射关系

原文未说明：
- 是否提供 Web UI 还是仅提供 API
- 页面布局、交互细节
- 操作反馈提示
- 列表分页、搜索、筛选能力
- 是否需要审计日志页面

## 9. 数据与系统交互
**核心数据表**：

**1. api_keys（API Key 表）**
- 用途：存储上游 LLM 的 API Key
- 关键字段：id、api_key（唯一）、source（来源/厂商）、creat_time、is_delete
- 索引：uniq(api_key)、idx(source, is_delete)

**2. llm_info_classify（LLM 分类表）**
- 用途：LLM 厂商/分类管理
- 关键字段：id、classify_name、user_name（管理员）、icon、create_time、update_time、is_delete

**3. llm_model_config（LLM 模型配置表）**
- 用途：核心模型配置
- 关键字段：
  - llm_code（char(6)，唯一索引）
  - llm_name（模型名称）
  - target_model（目标模型标识）
  - end_point（上游 LLM 端点）
  - api_key（上游 API Key）
  - interface_protocol（接口协议）
  - api_version（API 版本，可空）
  - proxy_id（代理 ID，关联 proxy_config）
  - classify_id（分类 ID，关联 llm_info_classify）
  - protocol_options（JSON，协议配置）
  - create_name、update_name、create_time、update_time、is_delete

**4. proxy_config（代理配置表）**
- 用途：网络代理配置
- 关键字段：proxy_name、proxy_url（最长 1024）、creat_username、update_username

**5. source_model_api_key（API Key 映射表）**
- 用途：业务方 source_api_key 与上游 provider_api_key 的映射
- 关键字段：source_api_key、llm_code、provider_api_key、api_version
- 索引：idx(source_api_key, llm_code)、idx(source_api_key, is_delete)

**测试环境数据库**：
- 实例：10.100.123.143:3306
- 库名：llm_gateway
- 账号：u_cybertron_llm_gateway

**系统交互**：
- 上游：对接多个 LLM 厂商（Azure、Qwen 等）
- 下游：服务 Cybertron Agent、Go 对话流服务等业务方
- 配置中心：通过 `params_config` 控制 SDK 切流

原文未说明：
- API 接口定义（REST/WebSocket/gRPC）
- 调用日志、监控指标的存储方案
- 缓存策略（是否缓存模型配置）
