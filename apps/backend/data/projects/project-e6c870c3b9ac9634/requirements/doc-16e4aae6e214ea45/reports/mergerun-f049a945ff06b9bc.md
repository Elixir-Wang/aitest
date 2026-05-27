# 归并质量报告

## 结论

failed

## 输入信息

| 指标 | 值 |
| --- | --- |
| 合并运行 | mergerun-f049a945ff06b9bc |
| 来源文件数 | 4 |
| 来源片段数 | 0 |
| 合并摘要 | 需求归并智能体运行失败：1 validation error for RequirementClusterDecision decision   Input should be 'merge', 'duplicate', 'conflict', 'pending_clarification' or 'discard' [type=literal_error, input_value='deduplicate', input_type=str]     For further information visit https://errors.pydantic.dev/2.12/v/literal_error |
| 差异摘要 | 智能体运行失败，未生成合并需求稿。 |
| 影响模块 |  |

## 质量检查

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| 段落映射存在 | failed | 覆盖项 0 条 |
| 候选稿无源文档结构 | passed | 检查源文件名、docmap 和来源文档分组 |
| 明显冲突已隔离 | passed | 明显冲突 0 个 |
| 结构化 Markdown 保留 | failed | 合并候选稿疑似丢失结构化 Markdown：代码围栏保留不足（来源 49，候选稿 0）；Mermaid 流程图保留不足（来源 14，候选稿 0）；Markdown 表格行保留不足（来源 408，候选稿 0）。 |
| 摘要与映射统计一致 | passed | 一致 |

## 阻塞问题

- 需求归并智能体运行失败：1 validation error for RequirementClusterDecision
decision
  Input should be 'merge', 'duplicate', 'conflict', 'pending_clarification' or 'discard' [type=literal_error, input_value='deduplicate', input_type=str]
    For further information visit https://errors.pydantic.dev/2.12/v/literal_error
- 智能体未返回段落映射，无法证明来源内容已完整处理。
- 合并候选稿疑似丢失结构化 Markdown：代码围栏保留不足（来源 49，候选稿 0）；Mermaid 流程图保留不足（来源 14，候选稿 0）；Markdown 表格行保留不足（来源 408，候选稿 0）。

## 非阻塞问题

- 后续可接入需求分析，继续检查范围不清和验收缺失。
