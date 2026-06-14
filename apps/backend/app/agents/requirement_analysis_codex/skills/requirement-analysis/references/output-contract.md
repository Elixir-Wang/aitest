# 输出契约

生成 `RequirementAnalysisOutput` 产物时使用本契约。

## 必需文件

- 写入 `output/analysis.json`。
- 写入 `output/analysis.md`。
- 写入 `output/clarification.md`。
- 写入 `output/quality.md`。
- 将 `analysis.json.analysis_report_markdown` 设置为 `output/analysis.md` 的完整正文。
- 将 `analysis.json.clarification_report_markdown` 设置为 `output/clarification.md` 的完整正文。
- 将 `analysis.json.quality_assurance_report_markdown` 设置为 `output/quality.md` 的完整正文。

## 运行时映射

| 视图 | 运行时去向 |
| --- | --- |
| 需求分析 | `output/analysis.md`, `analysis_report_markdown` |
| 待澄清 | `output/clarification.md`, `clarification_report_markdown`, `clarification_questions`, `conflicts` |
| 质量保证 | `output/quality.md`, `quality_assurance_report_markdown`, `coverage_audit`, `quality_gate` |

前端 `质量保证` 子 tab 直接展示 `quality_assurance_report_markdown`，不要依赖额外 UI 卡片、质量表格或仪表盘结构承载关键信息。

## 状态值

`status` 只能使用：

- `completed`
- `needs_clarification`
- `blocked`

不要输出 `CONDITIONAL_PASS`、`APPROVED`、`FAILED`、`REJECTED` 等评审结论。

## 质量门禁值

`quality_gate.result` 只能使用：

- `passed`
- `warning`
- `blocked`

`quality_gate.testability_score` 必须是 0 到 100 的整数。

## 必填 JSON 字段

必须填充：

- `status`
- `analysis_summary`
- `preliminary_requirement_markdown`
- `analysis_report_markdown`
- `clarification_report_markdown`
- `quality_assurance_report_markdown`
- `applied_supplements`
- `maturity_assessment`
- `key_gaps`
- `assumptions`
- `modules`
- `clarification_questions`
- `conflicts`
- `coverage_audit`
- `quality_gate`
- `next_actions`

仅分析主需求时，`applied_supplements` 必须是空数组。

## 字段规则

- 调用方允许回退到原始主需求时，`preliminary_requirement_markdown` 可以为空。
- `clarification_questions` 放未解决问题，不放已确认需求的解释。
- `conflicts` 放来源冲突、范围外证据、弱证据或来源归属不清。
- `coverage_audit` 必须是数组。不要输出 `{covered, partial, missing}` 字典。
- `recommended_options` 最多包含两个选项。
- `recommended_options.answer_markdown` 必须能直接插入初步需求。

## Markdown 报告规则

`output/analysis.md` 是需求分析报告，应包含：

1. 分析摘要
2. 需求成熟度
3. 已确认范围和模块
4. Mermaid 理解图，至少包含业务流程图；来源支持时补充状态流转图、模块关系图或角色交互图
5. 按类别整理的关键缺口
6. 测试覆盖影响摘要
7. 质量门禁摘要
8. 下一步建议

不得包含：

- 标题为 `待确认问题`、`待人工确认`、`澄清问题` 或 `待澄清内容` 的章节
- 从 `clarification_questions` 复制的问题清单
- 从 `conflicts` 复制的冲突清单
- 冗长通用的评审模板

`output/quality.md` 是质量保证报告，应是一份完整 Markdown 文件。质量门禁、可测试性评分、覆盖审计和下一步建议必须在 Markdown 正文中表达清楚。
