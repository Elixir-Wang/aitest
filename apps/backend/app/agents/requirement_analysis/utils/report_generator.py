"""
需求分析报告生成工具。

v3 LangGraph 输出按前端三 Tab 拆分：
- 需求分析：仅展示需求理解和 Mermaid 理解图。
- 质量保障：仅展示质量评估与验证风险。
- 待澄清：仅展示需要人工确认或裁决的事项。
"""

import re
from hashlib import sha1

from app.agents.requirement_analysis.schemas import (
    ClarificationOutput,
    QualityAssessmentOutput,
    RequirementModule,
    RequirementUnderstandingOutput,
)


def generate_analysis_report(
    understanding: RequirementUnderstandingOutput,
) -> str:
    """生成需求分析 Tab 的需求理解报告。"""
    return f"""# 需求分析报告

## 分析摘要

{_markdown_text(understanding.understanding_summary) or "（未生成分析摘要）"}

{_generate_modules_section(understanding)}

{_generate_business_objects_section(understanding)}

{_generate_business_rules_section(understanding)}

{_generate_state_flows_section(understanding)}

{_generate_dependencies_section(understanding)}

{_generate_risks_and_assumptions_section(understanding)}

{_generate_mermaid_section(understanding)}
""".strip()


def generate_quality_assurance_report(
    quality: QualityAssessmentOutput,
    clarification: ClarificationOutput | None = None,
) -> str:
    """生成质量保障 Tab 的质量评估报告。"""
    clarification_summary = ""
    if clarification is not None:
        summary = clarification.summary
        clarification_summary = f"""

## 覆盖风险摘要

- **待处理澄清项**: {summary.total}
- **需人工确认**: {summary.needs_manual}
- **有建议选项**: {summary.has_suggestions}
- **自动解决**: {summary.auto_resolved}
""".rstrip()

    return f"""# 质量保障报告

## 质量摘要

{_markdown_text(quality.assessment_summary)}

## 质量分数

{_generate_quality_scores_table(quality)}

## 质量决策

- **结果**: {quality.decision.result}
- **理由**: {_markdown_text(quality.decision.rationale)}

## 完整性评估

- **分数**: {quality.completeness.score}/100
- **功能缺口**:
{_bullet_list(quality.completeness.functional_gaps)}
- **缺失细节**:
{_bullet_list(quality.completeness.missing_details)}
- **非功能需求缺口**:
{_generate_nfr_gaps(quality)}

## 清晰度评估

- **分数**: {quality.clarity.score}/100
- **模糊词**:
{_generate_fuzzy_terms(quality)}
- **歧义表述**:
{_generate_ambiguous_statements(quality)}

## 可测试性评估

- **分数**: {quality.testability.score}/100
- **验收标准缺口**:
{_generate_acceptance_gaps(quality)}
- **测试覆盖缺口**:
{_generate_test_coverage_gaps(quality)}

## 一致性评估

- **分数**: {quality.consistency.score}/100
- **冲突**:
{_generate_conflicts(quality)}
- **术语不一致**:
{_generate_terminology_issues(quality)}

## 阻塞问题

{_bullet_list(quality.decision.blocking_issues)}

## 建议行动

{_numbered_list(quality.decision.recommended_actions)}
{clarification_summary}
""".strip()


def generate_clarification_report(
    clarification: ClarificationOutput,
) -> str:
    """生成待澄清 Tab 的 Markdown 报告。"""
    summary = clarification.summary
    return f"""# 待澄清内容

## 澄清摘要

{clarification.clarification_summary_text}

## 待澄清项统计

- **总数**: {summary.total}
- **需人工确认**: {summary.needs_manual}
- **有建议选项**: {summary.has_suggestions}
- **自动解决**: {summary.auto_resolved}
- **按来源维度**: {_format_count_map(summary.by_source)}
- **按严重级别**: {_format_count_map(summary.by_severity)}

## 待澄清项

{_generate_clarification_items(clarification)}
""".strip()


def _generate_modules_section(understanding: RequirementUnderstandingOutput) -> str:
    modules = []
    for module in understanding.modules:
        capabilities = _inline_list(module.capabilities)
        modules.append(
            f"- **{_markdown_text(module.module_name)}** (`{module.module_key}`): {_markdown_text(module.summary)}"
            f"\n  - 能力: {capabilities}"
        )
    return f"""## 模块与能力

{chr(10).join(modules) if modules else "（未识别到模块）"}"""


def _generate_business_objects_section(understanding: RequirementUnderstandingOutput) -> str:
    rows = []
    for module in understanding.modules:
        for obj in module.business_objects:
            rows.append(
                f"- **{_markdown_text(obj.name)}**（{_markdown_text(module.module_name)}）: {_markdown_text(obj.description) or '（无描述）'}"
                f"\n  - 字段: {_inline_list(obj.fields)}"
                f"\n  - 关系: {_inline_list(obj.relationships)}"
            )
    return f"""## 业务对象与字段

{chr(10).join(rows) if rows else "（未识别到业务对象）"}"""


def _generate_business_rules_section(understanding: RequirementUnderstandingOutput) -> str:
    rows = []
    for module in understanding.modules:
        for rule in module.business_rules:
            detail = f"- **{rule.rule_id}** [{rule.rule_type}]（{_markdown_text(module.module_name)}）: {_markdown_text(rule.description)}"
            if rule.condition:
                detail += f"\n  - 条件: {_markdown_text(rule.condition)}"
            if rule.example:
                detail += f"\n  - 示例: {_markdown_text(rule.example)}"
            rows.append(detail)
    return f"""## 业务规则

{chr(10).join(rows) if rows else "（未识别到业务规则）"}"""


def _generate_state_flows_section(understanding: RequirementUnderstandingOutput) -> str:
    rows = []
    for module in understanding.modules:
        for flow in module.state_flows:
            transitions = [
                f"{_markdown_text(transition.from_state)} -> {_markdown_text(transition.to_state)}（{_markdown_text(transition.trigger)}）"
                for transition in flow.transitions
            ]
            rows.append(
                f"- **{_markdown_text(flow.object_name)}**（{_markdown_text(module.module_name)}）"
                f"\n  - 状态: {_inline_list(flow.states)}"
                f"\n  - 流转: {_inline_list(transitions)}"
            )
    return f"""## 状态流转

{chr(10).join(rows) if rows else "当前主需求未明确描述状态流转。"}"""


def _generate_dependencies_section(understanding: RequirementUnderstandingOutput) -> str:
    dependencies = [
        f"- **{_markdown_text(dep.source_module)}** -> **{_markdown_text(dep.target_module)}** [{_markdown_text(dep.dependency_type)}]: {_markdown_text(dep.description)}"
        for dep in understanding.dependencies
    ]
    module_dependencies = []
    module_by_key = {module.module_key: module.module_name for module in understanding.modules}
    for module in understanding.modules:
        for dependency in module.dependencies:
            dependency_name = module_by_key.get(dependency, dependency)
            module_dependencies.append(
                f"- **{_markdown_text(module.module_name)}** -> **{_markdown_text(dependency_name)}**"
            )
    rows = dependencies + module_dependencies
    return f"""## 依赖与集成点

{chr(10).join(rows) if rows else "（未识别到依赖或集成点）"}"""


def _generate_risks_and_assumptions_section(understanding: RequirementUnderstandingOutput) -> str:
    risks = [
        f"- **{risk.risk_id}** [{risk.category}] {_markdown_text(risk.description)}"
        f"\n  - 影响: {_markdown_text(risk.impact)}；可能性: {_markdown_text(risk.likelihood)}"
        f"\n  - 缓解: {_markdown_text(risk.mitigation) or '（未说明）'}"
        for risk in understanding.risks
    ]
    assumptions = [
        f"- **{assumption.assumption_id}** {_markdown_text(assumption.description)}"
        f"\n  - 需验证: {_markdown_text(assumption.validation_needed)}"
        f"\n  - 不成立风险: {_markdown_text(assumption.risk_if_invalid)}"
        for assumption in understanding.assumptions
    ]
    return f"""## 风险与假设

### 风险

{chr(10).join(risks) if risks else "（未识别到风险）"}

### 假设

{chr(10).join(assumptions) if assumptions else "（未识别到假设）"}"""


def _generate_mermaid_section(understanding: RequirementUnderstandingOutput) -> str:
    return f"""## Mermaid 理解图

### 模块关系图

{_generate_module_mermaid(understanding)}

### 业务流程图

{_generate_capability_mermaid(understanding)}

{_generate_state_mermaid_blocks(understanding)}"""


def _generate_module_mermaid(understanding: RequirementUnderstandingOutput) -> str:
    modules = understanding.modules
    if not modules:
        return "（未识别到模块，无法生成模块关系图。）"

    lines = ["```mermaid", "flowchart LR"]
    module_by_key = {module.module_key: module for module in modules}
    used_edges = False

    for module in modules:
        source_id = _node_id("module", module.module_key)
        lines.append(f'  {source_id}["{_escape_mermaid_label(module.module_name)}"]')

    for dep in understanding.dependencies:
        source_id = _node_id("module", dep.source_module)
        target_id = _node_id("module", dep.target_module)
        lines.append(
            f'  {source_id} -->|"{_escape_mermaid_label(dep.dependency_type)}"| {target_id}'
        )
        used_edges = True

    for module in modules:
        source_id = _node_id("module", module.module_key)
        for dependency in module.dependencies:
            if dependency not in module_by_key:
                continue
            target_id = _node_id("module", dependency)
            lines.append(f"  {source_id} --> {target_id}")
            used_edges = True

    if not used_edges:
        root_id = "scope_root"
        lines.append(f'  {root_id}["需求范围"]')
        for module in modules:
            lines.append(f"  {root_id} --> {_node_id('module', module.module_key)}")

    lines.append("```")
    return "\n".join(lines)


def _generate_capability_mermaid(understanding: RequirementUnderstandingOutput) -> str:
    capabilities: list[tuple[RequirementModule, str]] = []
    for module in understanding.modules:
        for capability in module.capabilities:
            capabilities.append((module, capability))

    if not capabilities:
        return "（未识别到模块能力，无法生成业务流程图。）"

    lines = ["```mermaid", "flowchart TD", '  start["开始"]']
    previous_id = "start"
    for index, (module, capability) in enumerate(capabilities[:20], 1):
        node_id = _node_id("cap", module.module_key, str(index))
        label = f"{module.module_name}: {capability}"
        lines.append(f'  {node_id}["{_escape_mermaid_label(label)}"]')
        lines.append(f"  {previous_id} --> {node_id}")
        previous_id = node_id
    lines.append('  done["结束"]')
    lines.append(f"  {previous_id} --> done")
    lines.append("```")
    return "\n".join(lines)


def _generate_state_mermaid_blocks(understanding: RequirementUnderstandingOutput) -> str:
    blocks = []
    for module in understanding.modules:
        for flow in module.state_flows:
            if not flow.states:
                continue
            state_ids = {
                state: _node_id("state", flow.object_name, state)
                for state in flow.states
            }
            lines = [
                f"### 状态流转图：{flow.object_name}",
                "",
                "```mermaid",
                "stateDiagram-v2",
            ]
            for state, state_id in state_ids.items():
                lines.append(f'  state "{_escape_mermaid_label(state)}" as {state_id}')
            if flow.transitions:
                for transition in flow.transitions:
                    from_state = state_ids.get(
                        transition.from_state,
                        _node_id("state", flow.object_name, transition.from_state),
                    )
                    to_state = state_ids.get(
                        transition.to_state,
                        _node_id("state", flow.object_name, transition.to_state),
                    )
                    trigger = _escape_mermaid_label(transition.trigger)
                    if trigger:
                        lines.append(f"  {from_state} --> {to_state}: {trigger}")
                    else:
                        lines.append(f"  {from_state} --> {to_state}")
            else:
                lines.append(f"  [*] --> {state_ids[flow.states[0]]}")
            lines.append("```")
            blocks.append("\n".join(lines))

    if not blocks:
        return "### 状态流转图\n\n当前主需求未明确描述状态流转。"
    return "\n\n".join(blocks)


def _generate_quality_scores_table(quality: QualityAssessmentOutput) -> str:
    return f"""| 维度 | 分数 |
|------|------|
| 完整性 | {quality.scores.completeness}/100 |
| 清晰度 | {quality.scores.clarity}/100 |
| 可测试性 | {quality.scores.testability}/100 |
| 一致性 | {quality.scores.consistency}/100 |
| **总分** | **{quality.scores.overall}/100** |"""


def _generate_nfr_gaps(quality: QualityAssessmentOutput) -> str:
    gaps = [
        f"- [{gap.category}] {_markdown_text(gap.description)}；影响: {_markdown_text(gap.impact)}；严重程度: {gap.severity}"
        + (f"；建议需求: {_markdown_text(gap.suggested_requirement)}" if gap.suggested_requirement else "")
        for gap in quality.completeness.nfr_gaps
    ]
    return "\n".join(gaps) if gaps else "  - 无"


def _generate_fuzzy_terms(quality: QualityAssessmentOutput) -> str:
    terms = [
        f'- **"{_markdown_text(term.term)}"**（{_markdown_text(term.location)}）: {_markdown_text(term.issue)}'
        f"\n  - 当前: {_markdown_text(term.current_text)}"
        f"\n  - 建议: {_markdown_text(term.suggested_fix)}"
        for term in quality.clarity.fuzzy_terms
    ]
    return "\n".join(terms) if terms else "  - 无"


def _generate_ambiguous_statements(quality: QualityAssessmentOutput) -> str:
    statements = [
        f"- {_markdown_text(item.statement)}"
        f"\n  - 可能解读: {_inline_list(item.possible_interpretations)}"
        f"\n  - 建议澄清: {_markdown_text(item.suggested_clarification)}"
        for item in quality.clarity.ambiguous_statements
    ]
    return "\n".join(statements) if statements else "  - 无"


def _generate_acceptance_gaps(quality: QualityAssessmentOutput) -> str:
    gaps = [
        f"- **{gap.module_key} / {_markdown_text(gap.capability)}** [{_markdown_text(gap.issue)}]"
        f"\n  - 当前: {_markdown_text(gap.current_text) or '（未说明）'}"
        f"\n  - 建议: {_markdown_text(gap.suggested_criteria)}"
        for gap in quality.testability.acceptance_criteria_gaps
    ]
    return "\n".join(gaps) if gaps else "  - 无"


def _generate_test_coverage_gaps(quality: QualityAssessmentOutput) -> str:
    gaps = [
        f"- **{gap.module_key}** [{gap.gap_type}] {_markdown_text(gap.description)}；影响: {_markdown_text(gap.impact)}"
        for gap in quality.testability.test_coverage_gaps
    ]
    return "\n".join(gaps) if gaps else "  - 无"


def _generate_conflicts(quality: QualityAssessmentOutput) -> str:
    conflicts = [
        f"- **{conflict.conflict_id}** [{conflict.conflict_type}] {_markdown_text(conflict.description)}"
        f"\n  - 证据1: {_markdown_text(conflict.evidence_1)}"
        f"\n  - 证据2: {_markdown_text(conflict.evidence_2)}"
        f"\n  - 影响: {_markdown_text(conflict.impact)}；严重程度: {conflict.severity}"
        for conflict in quality.consistency.conflicts
    ]
    return "\n".join(conflicts) if conflicts else "  - 无"


def _generate_terminology_issues(quality: QualityAssessmentOutput) -> str:
    issues = [
        f"- **{issue.concept}**: {_inline_list(issue.variations)}"
        f"\n  - 建议统一为: {_markdown_text(issue.suggested_standard_term)}"
        for issue in quality.consistency.terminology_issues
    ]
    return "\n".join(issues) if issues else "  - 无"


def _generate_clarification_items(clarification: ClarificationOutput) -> str:
    if not clarification.items:
        return "（无待澄清项）"

    groups = [
        ("blocker", "阻塞项"),
        ("risk", "风险项"),
        ("acceptance", "验收项"),
    ]
    rows = []
    for bucket, label in groups:
        bucket_items = [
            item for item in clarification.items
            if getattr(item, "clarification_bucket", "risk") == bucket
        ]
        rows.append(f"### {label}")
        if not bucket_items:
            rows.append("（无）")
            continue
        for index, item in enumerate(bucket_items, 1):
            rows.append(_generate_clarification_item_detail(item, index))
    return "\n\n".join(rows)


def _generate_clarification_item_detail(item, index: int) -> str:
    row = f"""#### {index}. {item.title or item.question}

- **问题**: {item.question}
- **分类**: {_clarification_bucket_label(getattr(item, "clarification_bucket", "risk"))}
- **类型**: {item.issue_type}
- **来源维度**: {item.source}
- **模块**: {item.module_name or item.module_key}
- **严重级别**: {item.severity}
- **处理状态**: {item.resolution_status}
- **影响**: {item.impact}
"""
    if getattr(item, "decision_point", ""):
        row += f"- **裁决点**: {item.decision_point}\n"
    if getattr(item, "source_excerpt", "") or item.current_text:
        row += f"- **来源文本**: {getattr(item, 'source_excerpt', '') or item.current_text}\n"
    if getattr(item, "current_gap", ""):
        row += f"- **当前缺口**: {item.current_gap}\n"
    if getattr(item, "test_impact", ""):
        row += f"- **测试影响**: {item.test_impact}\n"
    if getattr(item, "risk_scenario", ""):
        row += f"- **风险场景**:\n{_indent_block(item.risk_scenario)}\n"
    affected_surfaces = getattr(item, "affected_surfaces", []) or []
    if affected_surfaces:
        row += f"- **影响范围**: {_inline_list([_surface_label(surface) for surface in affected_surfaces])}\n"
    if getattr(item, "recommended_decision", ""):
        row += f"- **推荐判断**: {item.recommended_decision}\n"
    if getattr(item, "human_question", ""):
        row += f"- **需要确认**: {item.human_question}\n"
    if getattr(item, "draft_acceptance_tests", []):
        row += "- **验收用例草案**:\n"
        for test in item.draft_acceptance_tests:
            row += f"  - {_markdown_text(test)}\n"
    if item.suggested_fix:
        row += f"- **建议修正**: {item.suggested_fix}\n"

    decision_options = getattr(item, "decision_options", []) or []
    if decision_options:
        row += "- **可选裁决**:\n"
        for option in decision_options[:3]:
            row += _format_option_line(option)
    elif item.recommended_options:
        row += "- **推荐选项**:\n"
        for option in item.recommended_options[:2]:
            row += _format_option_line(option)

    if item.evidence:
        row += "- **辅助文档证据**:\n"
        for evidence in item.evidence:
            row += (
                f"  - {evidence.filename}"
                f"（可信度: {evidence.confidence}）: {evidence.excerpt}"
            )
            if evidence.section_hint:
                row += f"；位置: {evidence.section_hint}"
            row += "\n"
    return row.strip()


def _format_option_line(option) -> str:
    row = (
        f"  - **{option.label}**（可信度: {option.confidence}）: "
        f"{option.answer_markdown}"
    )
    if option.rationale:
        row += f"；理由: {option.rationale}"
    if option.source:
        row += f"；来源: {option.source}"
    return row + "\n"


def _clarification_bucket_label(bucket: str) -> str:
    labels = {
        "blocker": "阻塞项",
        "risk": "风险项",
        "acceptance": "验收项",
    }
    return labels.get(bucket, bucket)


def _surface_label(surface: str) -> str:
    labels = {
        "api": "接口契约",
        "state_flow": "状态流转",
        "data_consistency": "数据一致性",
        "permission": "权限",
        "security": "安全",
        "audit_log": "审计日志",
        "regression": "回归",
        "migration": "迁移",
        "ui_feedback": "用户反馈",
        "async_task": "异步任务",
        "external_dependency": "外部依赖",
        "non_functional": "非功能",
    }
    return labels.get(surface, surface)


def _indent_block(text: str) -> str:
    return "\n".join(f"  {line}" if line.strip() else "" for line in _markdown_text(text).splitlines())


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {_markdown_text(item)}" for item in items) if items else "- 无"


def _numbered_list(items: list[str]) -> str:
    return "\n".join(f"{index}. {_markdown_text(item)}" for index, item in enumerate(items, 1)) if items else "无"


def _inline_list(items: list[str]) -> str:
    return "、".join(_markdown_text(item).replace("\n", " ") for item in items if item) or "（未说明）"


def _markdown_text(value: object) -> str:
    text = str(value or "")
    if "\\" not in text:
        return text
    return (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
    )


def _format_count_map(value: dict[str, int]) -> str:
    return "、".join(f"{key}: {count}" for key, count in value.items()) or "无"


def _escape_mermaid_label(value: str) -> str:
    return str(value or "").replace('"', "'").replace("\n", " ").strip()


def _node_id(*parts: str) -> str:
    raw = "_".join(str(part or "node") for part in parts)
    safe = re.sub(r"[^0-9a-zA-Z_]", "_", raw)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        safe = "node"
    if safe[0].isdigit():
        safe = f"n_{safe}"
    digest = sha1(raw.encode("utf-8")).hexdigest()[:8]
    return f"{safe}_{digest}"


__all__ = [
    "generate_analysis_report",
    "generate_quality_assurance_report",
    "generate_clarification_report",
]
