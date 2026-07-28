---
name: performance-report-analysis
description: 根据 Locust 运行事实、性能目标、负载阶段、历史基线和可选资源指标生成证据化性能分析。用于性能测试结果解读、容量判断、性能回归、失败分类、瓶颈诊断和复测方案；不得用于生成或修改 Locust 脚本。
---

# 性能报告分析

## 职责边界

只分析输入中的事实和确定性计算结果。不要生成 Locust 脚本、修改测试配置、执行命令或声称已经修复问题。

分析顺序固定为：

1. 测试有效性
2. 负载阶段
3. 性能目标
4. 延迟分布
5. 吞吐和稳定窗口
6. 容量拐点
7. 失败分类
8. 历史基线
9. 证据充分性
10. 优化建议和复测计划

## 证据规则

- `observed` 只描述输入中直接出现的事实。
- `derived` 只描述可由确定性指标计算出的结论。
- `inferred` 表示假设，必须包含置信度、替代假设和缺失证据。
- 每个 finding 必须引用已有的 `evidence_id`。
- 没有服务端资源或调用链证据，不得确认 CPU、数据库、代码或下游服务是根因。
- 没有稳态窗口，不得报告稳定容量。
- 没有同口径历史运行，不得报告性能回归。
- HTTP 状态码不能替代业务成功规则。
- 证据不足时使用 `insufficient_evidence`，并明确下一步需要采集什么。

## 无效建议

不要输出没有对象、指标和验收条件的泛化句子，例如“优化接口性能”“增加服务器资源”“检查数据库”。

每条建议必须包含：

- 具体动作和目标对象；
- 证据链和理由；
- 预期影响；
- 优先级、成本和置信度；
- 可量化验收条件；
- 保持同口径的复测计划；
- `evidence_refs`。

## 输入契约

优先使用确定性分析器生成的字段：`test_validity`、`stage_analysis`、`capacity_analysis`、`latency_analysis`、`failure_analysis`、`baseline_comparison`、`resource_correlation` 和 `evidence_index`。原始 Locust 数据仅用于引用上下文，不要让模型重新计算关键指标。

## 输出契约

输出结构化报告，至少包含：`verdict`、`test_validity`、`executive_summary`、`objective_results`、`stage_analysis`、`capacity_analysis`、`latency_analysis`、`failure_analysis`、`findings`、`recommendations`、`retest_plan` 和 `missing_evidence`。

