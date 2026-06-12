"""
报告生成工具

用于生成需求分析报告（Markdown 格式）
"""

from app.agents.requirement_analysis.schemas_v2 import (
    RequirementUnderstandingOutput,
    QualityAssessmentOutput,
    ClarificationOutput,
)


def generate_analysis_report(
    understanding: RequirementUnderstandingOutput,
    quality: QualityAssessmentOutput,
    clarification: ClarificationOutput,
) -> str:
    """
    生成需求分析报告（Markdown 格式）

    Args:
        understanding: 需求理解结果
        quality: 质量评估结果
        clarification: 待澄清内容结果

    Returns:
        Markdown 格式的报告
    """

    # 1. 执行摘要
    summary_section = _generate_summary(quality, clarification)

    # 2. 需求理解
    understanding_section = _generate_understanding_section(understanding)

    # 3. 质量评估
    quality_section = _generate_quality_section(quality)

    # 4. 待澄清内容
    clarification_section = _generate_clarification_section(clarification)

    # 5. 下一步建议
    next_steps_section = _generate_next_steps(quality)

    # 组合报告
    report = f"""# 需求分析报告

{summary_section}

---

{understanding_section}

---

{quality_section}

---

{clarification_section}

---

{next_steps_section}

---

**报告生成时间**: {_get_timestamp()}
"""

    return report.strip()


def _generate_summary(
    quality: QualityAssessmentOutput,
    clarification: ClarificationOutput,
) -> str:
    """生成执行摘要"""

    decision_emoji = {
        "approved": "✅",
        "conditional": "⚠️",
        "rejected": "❌",
    }

    emoji = decision_emoji.get(quality.decision.result, "")

    return f"""## 执行摘要

- **质量评分**: {quality.scores.overall}/100
- **决策结果**: {emoji} {quality.decision.result.upper()}
- **待澄清问题**: {clarification.summary.total} 个
  - 需人工确认: {clarification.summary.needs_manual} 个
  - 有建议选项: {clarification.summary.has_suggestions} 个
  - 自动解决: {clarification.summary.auto_resolved} 个

### 决策理由

{quality.decision.rationale}"""


def _generate_understanding_section(
    understanding: RequirementUnderstandingOutput,
) -> str:
    """生成需求理解部分"""

    # 模块列表
    modules_text = "\n".join([
        f"- **{m.module_name}** (`{m.module_key}`): {m.summary}"
        for m in understanding.modules
    ])

    if not modules_text:
        modules_text = "（未识别到模块）"

    # 风险列表
    risks_text = "\n".join([
        f"- [{r.category}] {r.description} (影响: {r.impact}, 可能性: {r.likelihood})"
        for r in understanding.risks[:5]  # 只显示前5个
    ])

    if not risks_text:
        risks_text = "（未识别到风险）"

    # 假设列表
    assumptions_text = "\n".join([
        f"- {a.description}"
        for a in understanding.assumptions[:5]  # 只显示前5个
    ])

    if not assumptions_text:
        assumptions_text = "（未识别到假设）"

    return f"""## 1. 需求理解

{understanding.understanding_summary}

### 识别的模块

{modules_text}

### 主要风险

{risks_text}

### 关键假设

{assumptions_text}"""


def _generate_quality_section(
    quality: QualityAssessmentOutput,
) -> str:
    """生成质量评估部分"""

    # 质量分数表格
    scores_table = f"""| 维度 | 分数 |
|------|------|
| 完整性 | {quality.scores.completeness}/100 |
| 清晰度 | {quality.scores.clarity}/100 |
| 可测试性 | {quality.scores.testability}/100 |
| 一致性 | {quality.scores.consistency}/100 |
| **总分** | **{quality.scores.overall}/100** |"""

    # 阻塞问题
    blocking_issues_text = "\n".join([
        f"- {issue}"
        for issue in quality.decision.blocking_issues
    ])

    if not blocking_issues_text:
        blocking_issues_text = "无"

    # NFR 缺口
    nfr_gaps_text = "\n".join([
        f"- [{gap.category}] {gap.description} (严重程度: {gap.severity})"
        for gap in quality.completeness.nfr_gaps[:5]  # 只显示前5个
    ])

    if not nfr_gaps_text:
        nfr_gaps_text = "无"

    # 模糊词
    fuzzy_terms_text = "\n".join([
        f"- **\"{term.term}\"** (位置: {term.location})\n  - 当前: {term.current_text}\n  - 建议: {term.suggested_fix}"
        for term in quality.clarity.fuzzy_terms[:5]  # 只显示前5个
    ])

    if not fuzzy_terms_text:
        fuzzy_terms_text = "无"

    # 冲突
    conflicts_text = "\n".join([
        f"- [{conflict.conflict_type}] {conflict.description} (严重程度: {conflict.severity})"
        for conflict in quality.consistency.conflicts[:5]  # 只显示前5个
    ])

    if not conflicts_text:
        conflicts_text = "无"

    # 建议行动
    actions_text = "\n".join([
        f"{i+1}. {action}"
        for i, action in enumerate(quality.decision.recommended_actions)
    ])

    if not actions_text:
        actions_text = "无"

    return f"""## 2. 质量评估

### 质量分数

{scores_table}

### 阻塞问题

{blocking_issues_text}

### 非功能需求缺口

{nfr_gaps_text}

### 模糊词（需要明确）

{fuzzy_terms_text}

### 冲突（需要解决）

{conflicts_text}

### 建议行动

{actions_text}"""


def _generate_clarification_section(
    clarification: ClarificationOutput,
) -> str:
    """生成待澄清内容部分"""

    # 统计信息
    summary = clarification.summary

    stats_text = f"""### 统计信息

- **总问题数**: {summary.total}
- **按解答状态**:
  - 自动解决: {summary.auto_resolved}
  - 有建议: {summary.has_suggestions}
  - 需人工: {summary.needs_manual}
- **按严重程度**:
  - Blocker: {summary.by_severity.get('blocker', 0)}
  - Major: {summary.by_severity.get('major', 0)}
  - Minor: {summary.by_severity.get('minor', 0)}"""

    # 优先级问题列表（显示前10个）
    items_text = ""
    for i, item in enumerate(clarification.items[:10], 1):
        severity_emoji = {
            "blocker": "🔴",
            "major": "🟡",
            "minor": "🟢",
        }
        status_emoji = {
            "auto_resolved": "✅",
            "has_suggestions": "💡",
            "needs_manual": "❓",
        }

        emoji = severity_emoji.get(item.severity, "")
        status = status_emoji.get(item.resolution_status, "")

        items_text += f"\n#### [{i}] {emoji} {item.question}\n\n"
        items_text += f"- **严重程度**: {item.severity}\n"
        items_text += f"- **状态**: {status} {item.resolution_status}\n"
        items_text += f"- **影响**: {item.impact}\n"

        if item.current_text:
            items_text += f"- **当前文本**: {item.current_text}\n"

        if item.suggested_fix:
            items_text += f"- **建议修正**: {item.suggested_fix}\n"

        if item.recommended_options:
            items_text += f"- **建议选项**:\n"
            for opt in item.recommended_options:
                conf_emoji = {"high": "🟢", "medium": "🟡", "low": "🟠"}.get(opt.confidence, "")
                items_text += f"  - {conf_emoji} {opt.label}"
                if opt.source:
                    items_text += f" (来源: {opt.source})"
                items_text += "\n"

        items_text += "\n"

    if not items_text:
        items_text = "（无待澄清问题）"

    return f"""## 3. 待澄清内容

{clarification.clarification_summary_text}

{stats_text}

### 优先级问题列表 (Top 10)

{items_text}"""


def _generate_next_steps(
    quality: QualityAssessmentOutput,
) -> str:
    """生成下一步建议"""

    result = quality.decision.result

    if result == "approved":
        recommendation = "✅ 需求质量已达标，可以进入设计阶段。"
    elif result == "conditional":
        recommendation = "⚠️ 需解决阻塞问题后，可以进入设计阶段。"
    else:
        recommendation = "❌ 需求质量不达标，建议大幅返工后重新评审。"

    return f"""## 4. 下一步建议

{recommendation}

### 具体行动

{chr(10).join(f"{i+1}. {action}" for i, action in enumerate(quality.decision.recommended_actions))}"""


def _get_timestamp() -> str:
    """获取当前时间戳"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


__all__ = ["generate_analysis_report"]
