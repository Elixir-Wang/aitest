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
