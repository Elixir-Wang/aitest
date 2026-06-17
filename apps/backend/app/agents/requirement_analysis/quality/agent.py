"""Requirement quality assessment child agent."""

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.quality.schemas import (
    QualityAssessmentOutput,
    QualityAssessmentSimple,
    QualityIssueFlat,
    QualityIssueSummary,
    QualityDecision,
    CompletenessAssessment,
    ClarityAssessment,
    TestabilityAssessment,
    ConsistencyAssessment,
    NFRGap,
    FuzzyTerm,
    AmbiguousStatement,
    AcceptanceCriteriaGap,
    TestCoverageGap,
    Conflict,
    TerminologyIssue,
)
from app.agents.requirement_analysis.understanding.schemas import RequirementUnderstandingOutput
from app.agents.requirement_analysis.schemas import RequirementUnderstandingBrief, EvidenceSnippet
from app.agents.requirement_analysis.utils.context import format_evidence_snippets

QUALITY_ASSESSMENT_SYSTEM_PROMPT = """
你是需求质量评估专家。

## 任务
识别需求文档中的所有质量问题，每个问题输出为一个 QualityIssueFlat 对象。

你同时承担“质疑式审查”职责。质疑不是独立输出，而是质量评估的方法：
- 对 P0/P1 功能从 WHAT、WHY、WHO、WHEN、WHERE、HOW、HOW_MUCH、WHAT_IF、WHY_NOT 角度检查是否明确。
- 从 malicious_input、concurrency、resource_exhaustion、dependency_failure、rollback_chaos、permission_drift、data_pollution 角度寻找反向破坏场景。
- 检查测试环境、测试数据、验证手段、Mock 依赖、自动化集成和环境限制是否可执行。
- 检查模型能力、依赖服务成熟度、性能边界、技术方案、新技术引入、第三方限制和数据兼容是否可实现。
- 检查 logical_flaw、missing_feature、rule_conflict、state_conflict、permission_breach、boundary_missing、exception_unhandled、concurrency_undefined、degradation_undefined、consistency_issue。

质疑式发现的问题必须归一为 QualityIssueFlat，不要生成独立质疑结果。

## 检查维度和类别

### 1. completeness（完整性）
- **functional_gap**: 功能定义不完整（缺少规则、字段、边界、异常处理）
- **nfr_gap**: 缺少非功能需求（必须有原文evidence）
  - 在extra中添加: {"nfr_category": "performance"} (可选值: performance, security, availability, scalability, compatibility, compliance, usability, maintainability)
- **missing_detail**: 缺少关键细节（字段长度、错误提示内容等）

### 2. clarity（清晰度）
- **fuzzy_term**: 不可量化的陈述（无法设计测试断言）
  - 在extra中添加: {"testability_impact": "无法设计性能测试"}
  - **检查规则**：
    - 时间/性能陈述必须有具体数值和单位（如"< 2秒"、"< 500ms"）
    - 数量陈述必须有边界值（如"最多100条"、"至少1个"）
    - 条件陈述必须有明确触发条件（如"当X=Y时"而非"必要时"）
    - 结果陈述必须有可观测的状态变化（如"状态变为已支付"而非"完成支付"）
  - **判断标准**：如果该陈述无法直接转化为测试断言（assert语句），则标记为fuzzy_term
  - 示例：
    - ❌ "系统应快速响应" → 无法写 assert，需澄清
    - ✅ "系统响应时间 < 2秒" → 可以写 assert response_time < 2000
    - ❌ "支持大量并发" → 无法写 assert，需澄清
    - ✅ "支持1000 QPS并发" → 可以写 assert qps >= 1000

- **ambiguous**: 歧义表述（一句话多种理解）
  - 在extra中添加: {"interpretations": ["理解1", "理解2", "理解3"]}

### 3. testability（可测试性）
- **missing_acceptance**: 缺少验收标准
  - 在extra中添加: {"module_key": "order_create", "capability": "用户创建订单"}
- **boundary_undefined**: 边界值未定义
- **exception_missing**: 异常路径未覆盖
- **error_message**: 错误提示未定义
- **permission**: 权限测试点缺失
- **concurrency**: 并发场景未考虑

### 4. consistency（一致性）
- **conflict**: 规则冲突、状态矛盾
  - 在extra中添加: {"conflict_type": "rule_contradiction", "evidence_1": "证据1", "evidence_2": "证据2"}
  - conflict_type可选值: rule_contradiction, state_conflict, priority_conflict, permission_conflict, data_conflict
- **terminology**: 术语不一致
  - 在extra中添加: {"concept": "智能体", "variations": ["智能体", "Agent", "助手"]}

### 5. implementability（可实现性）
- **implementation_risk**: 技术方案、模型能力、依赖成熟度、性能边界或数据兼容存在实现风险
  - 在extra中添加: {"questioning_dimension": "HOW", "risk_level": "high|medium|low"}

### 6. adversarial（反向破坏）
- **adversarial_scenario**: 通过反向破坏场景发现的需求漏洞
  - 在extra中添加: {"attack_vector": "concurrency", "expected_defense": "应有防御", "actual_consequence": "缺失防御的后果"}
- **requirement_gap**: 通过质疑矩阵发现的业务漏洞
  - 在extra中添加: {"questioning_dimension": "WHAT_IF", "gap_type": "exception_unhandled"}

## 严重程度
- **blocker**: 必须立即修复（严重冲突、核心流程无验收标准）
- **major**: 显著影响测试覆盖（边界值缺失、模糊词、重要NFR缺失）
- **minor**: 不影响核心测试（术语不统一、可选字段说明缺失）

## 输出格式
```json
{
  "issues": [
    {
      "issue_id": "COMP-001",
      "dimension": "completeness",
      "category": "nfr_gap",
      "severity": "major",
      "title": "智能体列表查询缺少响应时间要求",
      "description": "原文提到'用户可以查询智能体列表'，但未定义性能指标",
      "location": "智能体管理模块",
      "current_text": "用户可以在列表页查询智能体",
      "issue_reason": "查询接口需要性能指标才能设计性能测试",
      "suggested_fix": "列表查询需在2秒内返回结果（95%请求）",
      "impact": "无法设计性能测试、无法判定是否达标",
      "extra": {
        "nfr_category": "performance"
      }
    },
    {
      "issue_id": "CLAR-001",
      "dimension": "clarity",
      "category": "fuzzy_term",
      "severity": "major",
      "title": "模糊词：快速",
      "description": "'快速响应'无法度量",
      "location": "登录模块",
      "current_text": "用户登录后系统需要快速响应",
      "issue_reason": "无法度量具体的响应时间要求",
      "suggested_fix": "用户登录后系统需在2秒内返回结果",
      "impact": "无法设计性能测试用例",
      "extra": {
        "term": "快速"
      }
    }
  ],
  "assessment_summary": "识别出X个问题，其中blocker Y个，major Z个，minor W个。主要问题集中在..."
}
```

## 重要规则
1. **深度检查，不要遗漏**：宁可多识别问题，也不要漏掉
2. **每个问题必须有证据**：current_text必须来自原文
3. **NFR不要过度**：必须有明确原文场景才生成nfr_gap
4. **severity要准确**：blocker要慎重，只有真正阻塞的才标
5. **维度特定信息放在extra中**：便于后处理转换为详细结构
6. **质疑能力归入质量问题**：9宫格、反向破坏、可执行性、可实现性和风险熔断都必须体现为 quality issue 或 assessment_summary，不得输出独立质疑结果
""".strip()


def quality_assessment_agent(model):
    """Create the requirement quality assessment agent."""
    return create_agent(
        model=model,
        tools=[],
        system_prompt=QUALITY_ASSESSMENT_SYSTEM_PROMPT,
        response_format=ToolStrategy(QualityAssessmentSimple),
    )


# ============================================================================
# 转换函数：从简化输出转换为完整结构
# ============================================================================

def _extract_nfr_gaps(issues: list[QualityIssueFlat]) -> list[NFRGap]:
    """从扁平问题提取NFR缺口"""
    nfr_issues = [i for i in issues if i.category == "nfr_gap"]
    return [
        NFRGap(
            category=issue.extra.get("nfr_category", "performance"),
            description=issue.description,
            impact=issue.impact,
            severity=issue.severity,
            suggested_requirement=issue.suggested_fix,
            evidence_text=issue.current_text,
            evidence_reason=issue.issue_reason
        )
        for issue in nfr_issues
    ]


def _extract_fuzzy_terms(issues: list[QualityIssueFlat]) -> list[FuzzyTerm]:
    """从扁平问题提取模糊词"""
    fuzzy_issues = [i for i in issues if i.category == "fuzzy_term"]
    return [
        FuzzyTerm(
            term=issue.extra.get("term", issue.title.replace("模糊词：", "")),
            location=issue.location,
            current_text=issue.current_text,
            issue=issue.issue_reason,
            suggested_fix=issue.suggested_fix
        )
        for issue in fuzzy_issues
    ]


def _normalize_string_list(
    values: list[str] | None,
    *,
    min_items: int,
    fallbacks: list[str],
) -> list[str]:
    """合并 LLM 输出与兜底文案，去重并保证最少条目数。"""
    normalized: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if text and text not in normalized:
            normalized.append(text)

    for fallback in fallbacks:
        text = str(fallback or "").strip()
        if text and text not in normalized:
            normalized.append(text)

    if len(normalized) < min_items:
        return []
    return normalized


def _extract_ambiguous_statements(issues: list[QualityIssueFlat]) -> list[AmbiguousStatement]:
    """从扁平问题提取歧义表述"""
    ambiguous_issues = [i for i in issues if i.category == "ambiguous"]
    results: list[AmbiguousStatement] = []
    for issue in ambiguous_issues:
        interpretations = _normalize_string_list(
            issue.extra.get("interpretations"),
            min_items=2,
            fallbacks=[
                issue.issue_reason,
                issue.description,
                f"按建议理解：{issue.suggested_fix}" if issue.suggested_fix else "",
                f"字面理解：{issue.current_text}" if issue.current_text else "",
            ],
        )
        if len(interpretations) < 2:
            continue
        results.append(
            AmbiguousStatement(
                statement=issue.current_text,
                possible_interpretations=interpretations,
                suggested_clarification=issue.suggested_fix,
            )
        )
    return results


def _extract_acceptance_gaps(issues: list[QualityIssueFlat]) -> list[AcceptanceCriteriaGap]:
    """从扁平问题提取验收标准缺口"""
    acceptance_issues = [i for i in issues if i.category == "missing_acceptance"]
    return [
        AcceptanceCriteriaGap(
            module_key=issue.extra.get("module_key", "unknown"),
            capability=issue.extra.get("capability", issue.title),
            issue="missing_criteria",
            current_text=issue.current_text,
            suggested_criteria=issue.suggested_fix
        )
        for issue in acceptance_issues
    ]


def _extract_test_coverage_gaps(issues: list[QualityIssueFlat]) -> list[TestCoverageGap]:
    """从扁平问题提取测试覆盖缺口"""
    coverage_categories = [
        "boundary_undefined", "exception_missing", "error_message",
        "permission", "concurrency"
    ]
    coverage_issues = [i for i in issues if i.category in coverage_categories]

    # 映射category到gap_type
    category_to_gap_type = {
        "boundary_undefined": "boundary_value",
        "exception_missing": "exception_path",
        "error_message": "error_message",
        "permission": "permission",
        "concurrency": "concurrency"
    }

    return [
        TestCoverageGap(
            module_key=issue.extra.get("module_key", "unknown"),
            gap_type=category_to_gap_type.get(issue.category, "boundary_value"),
            description=issue.description,
            impact=issue.impact
        )
        for issue in coverage_issues
    ]


def _extract_conflicts(issues: list[QualityIssueFlat]) -> list[Conflict]:
    """从扁平问题提取冲突"""
    conflict_issues = [i for i in issues if i.category == "conflict"]
    return [
        Conflict(
            conflict_id=issue.issue_id,
            conflict_type=issue.extra.get("conflict_type", "rule_contradiction"),
            description=issue.description,
            evidence_1=issue.extra.get("evidence_1", issue.current_text),
            evidence_2=issue.extra.get("evidence_2", ""),
            impact=issue.impact,
            severity=issue.severity
        )
        for issue in conflict_issues
    ]


def _extract_terminology_issues(issues: list[QualityIssueFlat]) -> list[TerminologyIssue]:
    """从扁平问题提取术语不一致"""
    terminology_issues = [i for i in issues if i.category == "terminology"]
    results: list[TerminologyIssue] = []
    for issue in terminology_issues:
        variations = _normalize_string_list(
            issue.extra.get("variations"),
            min_items=2,
            fallbacks=[
                issue.extra.get("concept", ""),
                issue.title,
                issue.current_text,
                issue.suggested_fix,
            ],
        )
        if len(variations) < 2:
            continue
        results.append(
            TerminologyIssue(
                concept=issue.extra.get("concept", issue.title),
                variations=variations,
                suggested_standard_term=issue.suggested_fix,
            )
        )
    return results


def _calculate_summary(issues: list[QualityIssueFlat]) -> QualityIssueSummary:
    """根据问题列表自动计算统计信息"""
    completeness = sum(1 for i in issues if i.dimension == "completeness")
    clarity = sum(1 for i in issues if i.dimension == "clarity")
    testability = sum(1 for i in issues if i.dimension in {"testability", "implementability", "adversarial"})
    consistency = sum(1 for i in issues if i.dimension == "consistency")

    by_severity = {
        "blocker": sum(1 for i in issues if i.severity == "blocker"),
        "major": sum(1 for i in issues if i.severity == "major"),
        "minor": sum(1 for i in issues if i.severity == "minor"),
    }

    return QualityIssueSummary(
        completeness_issues=completeness,
        clarity_issues=clarity,
        testability_issues=testability,
        consistency_issues=consistency,
        total_issues=len(issues),
        by_severity=by_severity,
        has_blocker=by_severity["blocker"] > 0,
        can_proceed=by_severity["blocker"] == 0
    )


def _make_decision(summary: QualityIssueSummary, issues: list[QualityIssueFlat]) -> QualityDecision:
    """根据统计信息生成决策"""
    blocker_count = summary.by_severity.get("blocker", 0)
    major_count = summary.by_severity.get("major", 0)

    # 提取blocker问题摘要
    blocking_issues = [
        f"{issue.title} ({issue.location})"
        for issue in issues
        if issue.severity == "blocker"
    ]

    if blocker_count == 0 and major_count <= 3:
        return QualityDecision(
            result="approved",
            rationale=f"无阻塞问题，major问题{major_count}个（≤3），可以继续",
            blocking_issues=[],
            recommended_actions=["建议在澄清阶段处理minor问题"] if summary.total_issues > 0 else []
        )
    elif blocker_count == 0 and major_count > 3:
        return QualityDecision(
            result="conditional",
            rationale=f"存在{major_count}个重要问题，建议澄清后质量更好",
            blocking_issues=[],
            recommended_actions=[
                "优先处理major问题",
                "补充核心模块的验收标准",
                "定义关键字段的边界值"
            ]
        )
    else:
        return QualityDecision(
            result="rejected",
            rationale=f"存在{blocker_count}个阻塞问题，必须解决后才能继续",
            blocking_issues=blocking_issues,
            recommended_actions=[
                "立即解决所有blocker问题",
                "重点关注规则冲突和核心流程缺失"
            ]
        )


def convert_to_full_assessment(simple: QualityAssessmentSimple) -> QualityAssessmentOutput:
    """将简化输出转换为完整结构"""
    issues = simple.issues

    # 按维度分组并转换
    completeness_issues = [i for i in issues if i.dimension == "completeness"]
    clarity_issues = [i for i in issues if i.dimension == "clarity"]
    testability_issues = [i for i in issues if i.dimension in {"testability", "implementability", "adversarial"}]
    consistency_issues = [i for i in issues if i.dimension == "consistency"]

    completeness = CompletenessAssessment(
        functional_gaps=[
            i.description for i in completeness_issues
            if i.category == "functional_gap"
        ],
        nfr_gaps=_extract_nfr_gaps(completeness_issues),
        missing_details=[
            i.description for i in completeness_issues
            if i.category == "missing_detail"
        ]
    )

    clarity = ClarityAssessment(
        fuzzy_terms=_extract_fuzzy_terms(clarity_issues),
        ambiguous_statements=_extract_ambiguous_statements(clarity_issues)
    )

    testability = TestabilityAssessment(
        acceptance_criteria_gaps=_extract_acceptance_gaps(testability_issues),
        test_coverage_gaps=_extract_test_coverage_gaps(testability_issues)
    )

    consistency = ConsistencyAssessment(
        conflicts=_extract_conflicts(consistency_issues),
        terminology_issues=_extract_terminology_issues(consistency_issues)
    )

    # 计算统计和决策
    summary = _calculate_summary(issues)
    decision = _make_decision(summary, issues)

    return QualityAssessmentOutput(
        summary=summary,
        decision=decision,
        completeness=completeness,
        clarity=clarity,
        testability=testability,
        consistency=consistency,
        assessment_summary=simple.assessment_summary
    )


async def run_quality_assessment_agent(
    model,
    primary_markdown_content: str = "",
    understanding_result: RequirementUnderstandingOutput | None = None,
    *,
    requirement_evidence: list[EvidenceSnippet] | None = None,
    understanding_brief: RequirementUnderstandingBrief | None = None,
) -> QualityAssessmentOutput:
    """Run the requirement quality assessment agent."""

    # 阶段1：LLM生成简化输出
    agent = quality_assessment_agent(model)

    evidence_text = format_evidence_snippets(requirement_evidence or [])
    if not evidence_text.strip() or evidence_text == "（无证据片段）":
        evidence_text = primary_markdown_content

    if understanding_brief is None and understanding_result is not None:
        from app.agents.requirement_analysis.utils.context import build_understanding_brief

        understanding_brief = build_understanding_brief(understanding_result)

    understanding_text = (
        understanding_brief.model_dump_json(indent=2)
        if understanding_brief is not None
        else "（无理解摘要）"
    )

    user_content = f"""
# 需求证据片段

{evidence_text}

---

# 需求理解摘要

{understanding_text}

---

请识别所有质量问题。
""".strip()

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": user_content,
                }
            ]
        }
    )

    simple_output = result.get("structured_response")
    if simple_output is None:
        raise ValueError("质量评估智能体未返回结构化结果")

    # 阶段2：转换为完整结构
    full_output = convert_to_full_assessment(simple_output)

    return full_output


__all__ = [
    "QUALITY_ASSESSMENT_SYSTEM_PROMPT",
    "quality_assessment_agent",
    "run_quality_assessment_agent",
    "convert_to_full_assessment",
]

