# Performance SSE Metrics Specification

## ADDED Requirements

### Requirement: Backward-compatible SSE transport configuration

系统 SHALL 支持性能测试以 `http` 或 `sse` 传输运行；未配置传输方式的现有测试 SHALL 按 `http` 解释并保持既有行为。

#### Scenario: Existing HTTP test is read or run

- **GIVEN** 一个历史性能测试不存在 `transport` 或 `sse` 配置
- **WHEN** 用户读取、生成脚本或运行该测试
- **THEN** 系统 SHALL 将其解释为 `transport=http`
- **AND** SHALL NOT 为其加入 SSE 请求头、流消费或 SSE 指标

#### Scenario: User selects SSE transport

- **GIVEN** 用户创建或编辑当前项目可见的性能测试
- **WHEN** 用户将 `transport` 设置为 `sse`
- **THEN** 系统 SHALL 校验 SSE 配置、流超时和所有指标规则
- **AND** 运行时 SHALL 以 `Accept: text/event-stream` 请求目标接口

### Requirement: Configurable SSE event metric matching

系统 SHALL 允许用户通过受限事件匹配规则定义从请求开始到首次匹配事件的时间指标，而不依赖供应商专用字段。

#### Scenario: JSON event field first matches a metric

- **GIVEN** SSE 指标规则指定 `data_json`、受支持路径和 `non_empty` 条件
- **WHEN** 流中第一个事件的目标字段满足条件
- **THEN** 系统 SHALL 以请求开始到该事件接收时刻的单调时钟差记录该指标
- **AND** SHALL 忽略该请求内随后再次命中的同一指标

#### Scenario: Event name does not match

- **GIVEN** 指标规则指定了 `event_name`
- **WHEN** 收到的 SSE 事件名称不同
- **THEN** 系统 SHALL 不执行该事件的字段匹配
- **AND** SHALL 继续消费后续事件

#### Scenario: Rule contains unsupported path or operator

- **WHEN** 用户提交不在受限 JSONPath 语法或允许操作符集合中的规则
- **THEN** 系统 SHALL 拒绝配置并返回字段级校验错误
- **AND** SHALL NOT 解释、编译或执行任意代码

### Requirement: Standards-compliant SSE framing

系统 SHALL 以 SSE 帧边界解析事件，而不是假设每一网络行都是独立 JSON。

#### Scenario: SSE frame has multiple data lines

- **GIVEN** 一个 SSE 帧包含多行 `data:`
- **WHEN** 解析器遇到帧结束空行
- **THEN** 系统 SHALL 以换行连接各数据行作为该事件的 `data_text`
- **AND** SHALL 在该完整事件上执行匹配规则

#### Scenario: Stream has comments and no event field

- **WHEN** 流中出现注释行或不含 `event:` 的数据帧
- **THEN** 系统 SHALL 忽略注释行
- **AND** SHALL 将无事件名帧作为空事件名的有效事件处理

### Requirement: SSE completion and missing metric semantics

系统 SHALL 区分流完成、超时、协议失败和指标未命中，并根据每条指标的缺失策略处理未命中情况。

#### Scenario: Optional tool-call metric is absent on a successful answer

- **GIVEN** `first_tool_call` 的 `missing_policy` 为 `record_null`
- **AND** 流成功完成但未出现工具调用事件
- **THEN** 系统 SHALL 将该请求的工具调用指标记录为缺失
- **AND** SHALL NOT 因此增加 HTTP 请求失败数

#### Scenario: Required metric is absent

- **GIVEN** 某指标的 `missing_policy` 为 `fail_request`
- **WHEN** 流在完成时该指标仍未命中
- **THEN** 系统 SHALL 将该请求标记为失败并记录稳定的缺失原因

#### Scenario: Configured completion rule is absent

- **GIVEN** SSE 配置包含结束规则
- **WHEN** 流以 EOF 关闭但未命中结束规则
- **THEN** 系统 SHALL 将该请求标记为失败，原因为 `sse_end_rule_not_matched`
- **AND** SHALL 保留已在该请求中采集的指标

### Requirement: Isolated SSE metric aggregation

系统 SHALL 将 SSE 事件指标独立于既有 Locust HTTP 聚合统计进行采集和展示。

#### Scenario: SSE metric is collected

- **GIVEN** 一个 SSE 请求命中首内容指标
- **WHEN** 运行结果被采集
- **THEN** 系统 SHALL 在该指标的独立汇总中记录样本量、缺失数、失败数、平均值和可信分位数
- **AND** SHALL NOT 将该指标作为额外请求写入 Locust HTTP 聚合 CSV

#### Scenario: SSE objective has no trustworthy samples

- **GIVEN** 某 SSE 指标目标已配置
- **AND** 该指标没有可信匹配样本或分位数不可计算
- **WHEN** 系统判定性能目标
- **THEN** 该目标 SHALL 为 `not_evaluated`
- **AND** SHALL NOT 将缺失指标当作零延迟或通过

### Requirement: SSE rule preview

系统 SHALL 提供受鉴权、非持久化的 SSE 样例规则预览能力。

#### Scenario: User validates a rule against a sample

- **GIVEN** 用户可访问当前项目
- **WHEN** 用户提交大小受限的 SSE 样本文本和规则
- **THEN** 系统 SHALL 返回解析事件摘要、每条规则首次命中的事件序号或无命中原因
- **AND** SHALL NOT 向目标服务发起请求
- **AND** SHALL NOT 持久化样例或未脱敏事件字段值

#### Scenario: Sample exceeds configured limit

- **WHEN** 用户提交超过大小或事件数上限的 SSE 样例
- **THEN** 系统 SHALL 拒绝请求并返回稳定的输入限制错误
- **AND** SHALL NOT 保存部分样例内容

### Requirement: SSE event data privacy and compatibility

系统 SHALL 限制 SSE 事件内容在运行、诊断和报告中的传播，并将规则版本纳入结果可比性判断。

#### Scenario: SSE run is diagnosed

- **WHEN** 系统为 SSE 性能运行构建分析证据或报告
- **THEN** 系统 SHALL 仅提供聚合时间指标、匹配/缺失计数和脱敏协议错误摘要
- **AND** SHALL NOT 提供完整 SSE 数据、文本增量、工具参数或认证信息

#### Scenario: Baseline uses different SSE rules

- **GIVEN** 当前运行与候选基线的 SSE 规则或指标口径不同
- **WHEN** 用户请求性能对比
- **THEN** 系统 SHALL 标记对应 SSE 指标不可比较并说明原因
- **AND** SHALL NOT 将两者的时间指标合并为同一趋势或差异结论

### Requirement: Evidence-based AI metric generation

系统 SHALL 允许管理员基于当前项目内单接口或接口场景目标步骤的一次真实 SSE 探测生成声明式指标候选，并 SHALL NOT 在没有有效样本时猜测或生成指标规则。

#### Scenario: Generate metrics from current unsaved request values

- **GIVEN** 管理员已选择当前项目内的接口和环境
- **AND** 性能测试表单包含尚未保存的 path、query、header 或 body 参数
- **WHEN** 管理员请求生成 SSE 指标
- **THEN** 系统 SHALL 使用当前表单参数执行一次流式请求
- **AND** SHALL 使用客户端单调时钟记录事件相对请求开始的接收偏移
- **AND** SHALL 基于捕获到的真实事件生成 `call_llm_start` 和 `first_answer` 候选指标

#### Scenario: Probe does not produce a valid SSE sample

- **WHEN** 探测请求失败、返回非成功状态、响应不是 `text/event-stream` 或没有有效事件
- **THEN** 系统 SHALL 返回稳定的探测失败错误
- **AND** SHALL NOT 调用模型生成无证据候选
- **AND** SHALL NOT 修改当前性能测试配置

#### Scenario: Scenario target requests AI metric generation

- **GIVEN** 当前性能测试目标是接口场景
- **AND** 用户已选择场景中的一个接口请求步骤作为 SSE 目标步骤
- **WHEN** 用户请求生成 SSE 指标
- **THEN** 系统 SHALL 按当前保存场景快照执行目标步骤之前的赋值、条件和 HTTP 请求步骤
- **AND** SHALL 将前置步骤输出按既有绑定语义传递给目标步骤
- **AND** SHALL 兼容场景已有的 JSON Pointer/JSONPath 输出提取，并保持 JSON、表单、multipart、Cookie 和 Header 请求编码
- **AND** SHALL 在目标步骤以流式方式捕获 SSE 样本并生成候选指标
- **AND** 正式 Locust 脚本 SHALL 只将该目标步骤作为 SSE 消费，其余步骤保持原传输行为

### Requirement: Constrained generation and deterministic replay

系统 SHALL 将 AI 输出限制为现有 `PerformanceSseConfig` 声明式契约，并 SHALL 在返回可应用候选前使用真实样本和运行时等价匹配语义完成确定性回放。

#### Scenario: AI candidate matches the captured sample

- **GIVEN** AI 候选通过 Schema、受限路径和操作符校验
- **AND** 必需指标及配置的结束规则均在真实样本上命中
- **WHEN** 服务端完成确定性回放
- **THEN** 系统 SHALL 返回已验证候选及 `generation_source=ai`
- **AND** SHALL 返回每条指标的命中数、首次事件序号和样本耗时
- **AND** SHALL NOT 让模型决定或改写样本耗时

#### Scenario: AI candidate is unavailable or invalid

- **WHEN** 模型不可用、输出不符合 Schema、缺少必需指标或真实样本回放失败
- **THEN** 系统 SHALL NOT 返回未验证的模型候选供用户直接应用
- **AND** SHALL 尝试使用真实样本事件结构生成确定性候选
- **AND** SHALL 返回 `generation_source=deterministic_fallback` 和明确 warning
- **AND** 确定性候选的有效性 SHALL 仍由相同回放结果决定

#### Scenario: User revalidates an edited candidate

- **GIVEN** 用户修改了候选指标路径、事件名或期望值
- **WHEN** 用户提交 `candidate_sse` 重新验证
- **THEN** 系统 SHALL 重新执行真实探测并回放用户候选
- **AND** SHALL 返回 `generation_source=user_validation` 和最新验证证据
- **AND** SHALL NOT 再次调用模型改写该用户候选

### Requirement: Explicit confirmation and stable script input

系统 SHALL 将生成结果视为候选配置，只有通过验证且经用户明确应用后才进入现有性能测试保存流程；Locust 脚本生成 SHALL 只读取已保存配置。

#### Scenario: User applies a verified candidate

- **GIVEN** 候选配置的 `validation.valid` 为 `true`
- **WHEN** 用户明确应用候选并保存性能测试
- **THEN** 系统 SHALL 将候选写入现有 `request_config.sse`
- **AND** 后续脚本生成 SHALL 复用该固定配置
- **AND** SHALL NOT 在脚本生成阶段再次调用模型

#### Scenario: User regenerates while a configuration exists

- **GIVEN** 表单中已有已确认的 SSE 指标配置
- **WHEN** 用户请求重新生成
- **THEN** 前端 SHALL 在执行探测前请求确认
- **AND** 新候选 SHALL NOT 自动覆盖当前配置
- **AND** 取消或验证失败 SHALL 保留当前配置

### Requirement: AI generation privacy and authorization

系统 SHALL 限制 AI 指标生成的调用者、项目引用、模型输入和响应内容，不得泄露认证信息或完整 SSE 业务内容。

#### Scenario: Build model input from captured events

- **GIVEN** 探测事件包含认证信息、业务标识或回答正文
- **WHEN** 系统构建 AI 输入
- **THEN** 系统 SHALL 只保留匹配所需的受控事件结构、枚举值、内容非空标记和接收偏移
- **AND** SHALL NOT 将认证信息、Cookie、Token、业务标识或完整回答正文发送给模型

#### Scenario: Generate metrics with inaccessible references

- **WHEN** 非管理员调用生成接口，或 endpoint/environment 不属于当前可见项目
- **THEN** 系统 SHALL 拒绝请求
- **AND** SHALL NOT 发起目标 SSE 请求
- **AND** SHALL NOT 调用模型

#### Scenario: Return a generation result

- **WHEN** 系统完成探测和候选验证
- **THEN** 响应 SHALL 只包含受控样本摘要、候选配置、验证证据、生成来源和警告
- **AND** SHALL NOT 持久化或返回完整 SSE 事件流
