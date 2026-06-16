"""
需求分析报告生成工具。

LangGraph 输出按前端三 Tab 拆分：
- 需求分析：仅展示需求理解和 Mermaid 理解图。
- 质量保障：仅展示质量评估与验证风险。
- 待澄清：仅展示需要人工确认或裁决的事项。
"""

import re
from hashlib import sha1

from app.agents.requirement_analysis.core.schemas import (
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
- **需人工确认**: {summary.by_resolution.get('needs_input', 0) + summary.by_resolution.get('needs_research', 0)}
- **有建议选项**: {summary.by_resolution.get('has_options', 0)}
- **自动解决**: {summary.by_resolution.get('auto_resolved', 0)}
""".rstrip()

    return f"""# 质量保障报告

## 质量摘要

{_markdown_text(quality.assessment_summary)}

## 质量问题统计

{_generate_quality_issue_summary(quality)}

## 质量决策

- **结果**: {quality.decision.result}
- **理由**: {_markdown_text(quality.decision.rationale)}

## 完整性评估

- **问题数**: {quality.summary.completeness_issues}
- **功能缺口**:
{_bullet_list(quality.completeness.functional_gaps)}
- **缺失细节**:
{_bullet_list(quality.completeness.missing_details)}
- **非功能需求缺口**:
{_generate_nfr_gaps(quality)}

## 清晰度评估

- **问题数**: {quality.summary.clarity_issues}
- **模糊词**:
{_generate_fuzzy_terms(quality)}
- **歧义表述**:
{_generate_ambiguous_statements(quality)}

## 可测试性评估

- **问题数**: {quality.summary.testability_issues}
- **验收标准缺口**:
{_generate_acceptance_gaps(quality)}
- **测试覆盖缺口**:
{_generate_test_coverage_gaps(quality)}

## 一致性评估

- **问题数**: {quality.summary.consistency_issues}
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

{clarification.overall_assessment}

## 待澄清项统计

- **总数**: {summary.total}
- **需人工确认**: {summary.by_resolution.get('needs_input', 0) + summary.by_resolution.get('needs_research', 0)}
- **有建议选项**: {summary.by_resolution.get('has_options', 0)}
- **自动解决**: {summary.by_resolution.get('auto_resolved', 0)}
- **按优先级**: {_format_count_map(summary.by_priority)}
- **按分类**: {_format_count_map(summary.by_category)}

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


def _generate_quality_issue_summary(quality: QualityAssessmentOutput) -> str:
    summary = quality.summary
    return f"""| 维度 | 问题数 |
|------|--------|
| 完整性 | {summary.completeness_issues} |
| 清晰度 | {summary.clarity_issues} |
| 可测试性 | {summary.testability_issues} |
| 一致性 | {summary.consistency_issues} |
| **总计** | **{summary.total_issues}** |
| **按严重程度** | blocker: {summary.by_severity.get('blocker', 0)}, major: {summary.by_severity.get('major', 0)}, minor: {summary.by_severity.get('minor', 0)} |
| **可继续** | **{'是' if summary.can_proceed else '否'}** |"""


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
        ("P0", "P0 阻塞项"),
        ("P1", "P1 高风险"),
        ("P2", "P2 中风险"),
        ("P3", "P3 低风险"),
    ]
    rows = []
    for priority, label in groups:
        bucket_items = [item for item in clarification.items if item.priority == priority]
        rows.append(f"### {label}")
        if not bucket_items:
            rows.append("（无）")
            continue
        for index, item in enumerate(bucket_items, 1):
            rows.append(_generate_clarification_item_detail(item, index))
    return "\n\n".join(rows)


def _generate_clarification_item_detail(item, index: int) -> str:
    from app.agents.requirement_analysis.utils.adapter import (
        ISSUE_CATEGORY_LABELS,
        RESOLUTION_STATUS_LABELS,
        SOURCE_STAGE_LABELS,
        surface_label,
    )

    affected_surfaces = [surface_label(surface) for surface in (item.affected_surfaces or [])]
    row = f"""#### {index}. {item.title}

- **裁决点**: {item.decision_point}
- **澄清原因**: {item.why_clarify}
- **优先级**: {item.priority}
- **分类**: {ISSUE_CATEGORY_LABELS.get(item.issue_category, item.issue_category)}
- **来源阶段**: {SOURCE_STAGE_LABELS.get(item.source_stage, item.source_stage)}
- **模块**: {item.module_name or item.module_key}
- **处理状态**: {RESOLUTION_STATUS_LABELS.get(item.resolution_status, item.resolution_status)}
- **测试影响**: {item.test_impact}
"""
    if item.source_excerpt:
        row += f"- **来源文本**: {item.source_excerpt}\n"
    if item.risk_scenario:
        row += f"- **风险场景**:\n{_indent_block(item.risk_scenario)}\n"
    if affected_surfaces:
        row += f"- **影响范围**: {_inline_list(affected_surfaces)}\n"
    if item.recommendation_rationale:
        row += f"- **推荐理由**: {item.recommendation_rationale}\n"
    if item.auto_resolution:
        row += f"- **自动解答**: {item.auto_resolution}\n"
    if item.auto_resolution_source:
        row += f"- **解答来源**: {item.auto_resolution_source}\n"
    if item.test_cases:
        row += "- **测试用例草案**:\n"
        for test_case in item.test_cases:
            row += f"  - **{test_case.test_id}** [{test_case.test_type}]: {test_case.scenario} → {test_case.expected_result}\n"
    if item.options:
        row += "- **可选方案**:\n"
        for option in item.options[:4]:
            row += _format_option_line(option)
    return row.strip()


def _format_option_line(option) -> str:
    description = getattr(option, "description", None) or getattr(option, "answer_markdown", "")
    row = f"  - **{option.label}**（可信度: {option.confidence}）: {description}"
    source = getattr(option, "source", "")
    if source:
        row += f"；来源: {source}"
    evidence_excerpt = getattr(option, "evidence_excerpt", "")
    if evidence_excerpt:
        row += f"；引用: {evidence_excerpt}"
    return row + "\n"


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
