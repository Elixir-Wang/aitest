---
name: requirement-analysis
description: 用于分析主需求文档并生成三类需求分析产物：需求分析报告、待澄清报告、质量保证报告。适用于评审主需求来源、抽取模块和规则、识别不明确点、冲突、可测试性缺口、覆盖风险、质量门禁结果，或生成兼容 RequirementAnalysisOutput 的 AI 测试系统产物。
---

# 需求分析

只 

## 工作流

1. 阅读输入需求和元数据。
2. 抽取已确认的需求事实，必须能追溯到主需求文本：
   - 业务背景和目标
   - 范围和非范围边界
   - 用户、角色、权限
   - 模块、能力、业务对象、字段
   - 业务规则、校验规则、状态流转、集成关系
   - 非功能约束和验收信号
3. 使用清单识别缺口和风险：
   - [requirement-checklist.md](references/requirement-checklist.md)
   - [testability-checklist.md](references/testability-checklist.md)
4. 将发现拆成三个输出视图：
   - 需求分析报告：已确认分析、摘要、成熟度、范围、模块、业务规则、Mermaid 理解图、分组缺口。
   - 待澄清报告：必须由人工回答或裁决的问题。
   - 质量保证报告：以 Markdown 报告说明可测试性、覆盖审计、质量门禁和验证风险。
5. 按 [output-contract.md](references/output-contract.md) 生成运行时产物。

## 输出边界

三个视图必须各司其职：

- 已确认的需求理解、业务流程、状态流转、模块关系和角色交互进入需求分析报告。
- 可由人工答复的不确定点进入待澄清问题或冲突。
- 验证策略、覆盖缺口和质量门禁结果进入质量保证报告及对应 JSON 字段。

不要在需求分析报告里重复待澄清问题，也不要设置“待确认问题”“待人工确认”“澄清问题”“待澄清内容”等章节。除非来源已明确确认，否则不要把质量风险改写成业务需求。

## 三份文档

必须同时生成三份 Markdown：

- `output/analysis.md`：需求分析报告，面向阅读和评审。
- `output/clarification.md`：待澄清报告，同时作为可点击待澄清结构的解析来源。
- `output/quality.md`：质量保证报告，只作为 Markdown 报告展示，不要求前端额外拆成卡片、表格或仪表盘。

`analysis.json` 中的 `analysis_report_markdown`、`clarification_report_markdown`、`quality_assurance_report_markdown` 必须分别等于三份 Markdown 的正文。

## 引用选择

只按当前任务加载必要引用：

- 需要运行时 JSON 和 Markdown 规则时，读 [output-contract.md](references/output-contract.md)。
- 需要需求分析报告结构时，读 [analysis-report.md](references/analysis-report.md)。
- 需要待澄清问题和冲突规则时，读 [clarification-report.md](references/clarification-report.md)。
- 需要质量门禁和覆盖审计规则时，读 [quality-assurance-report.md](references/quality-assurance-report.md)。
- 需要需求质量检查项时，读 [requirement-checklist.md](references/requirement-checklist.md)。
- 需要可测试性检查项时，读 [testability-checklist.md](references/testability-checklist.md)。
- 需要输出模板时，读 [report-templates.md](references/report-templates.md)。
- 需要前后对比例子时，读 [examples.md](references/examples.md)。

不要只凭 `SKILL.md` 直接生成产物；至少读取 `output-contract.md`，并根据要生成的报告读取对应 reference。

## 防护规则

- 只有来源无法确定答案时，才提出直接问题。
- 每个待澄清问题必须包含影响和严重级别。
- 每个推荐选项必须能直接写入初步需求。
- 待澄清报告必须使用 `## CQ-001` 或 `## CF-001` 开头的可解析格式。
- 质量保证报告可以包含质量门禁、评分、覆盖审计和测试建议，但它本身就是最终展示内容。
- 只有缺失或冲突点阻断有意义的下游分析时，才使用 `blocked`。
- 分析可以继续但质量或可测试性仍需关注时，使用 `warning`。
- 没有未解决的重要澄清项或质量问题时，才使用 `passed`。
