"""质量评估相关 Schemas."""

from typing import Literal
from pydantic import BaseModel, Field


class NFRGap(BaseModel):
    """非功能需求缺口"""
    category: Literal[
        "performance",      # 性能（响应时间、吞吐量、并发）
        "security",         # 安全（认证、授权、加密、审计）
        "availability",     # 可用性（SLA、容错、恢复）
        "scalability",      # 可扩展性（用户增长、数据量）
        "compatibility",    # 兼容性（浏览器、设备、API版本）
        "compliance",       # 合规（GDPR、HIPAA、行业标准）
        "usability",        # 可用性（易用性、无障碍）
        "maintainability",  # 可维护性（可读性、可扩展性）
    ]
    description: str
    impact: str
    severity: Literal["blocker", "major", "minor"] = "major"
    suggested_requirement: str = Field(
        default="",
        description="建议补充的需求内容"
    )
    evidence_text: str = Field(
        default="",
        description="触发该缺口判断的主需求原文。没有原文依据时不得生成 NFRGap。"
    )
    evidence_reason: str = Field(
        default="",
        description="说明为什么这段原文需要补充该非功能指标。"
    )


class CompletenessAssessment(BaseModel):
    """完整性评估"""

    functional_gaps: list[str] = Field(
        default_factory=list,
        description="功能完整性缺口：缺失的规则、字段、边界、异常场景"
    )

    nfr_gaps: list[NFRGap] = Field(
        default_factory=list,
        description="非功能需求缺口"
    )

    missing_details: list[str] = Field(
        default_factory=list,
        description="缺失的细节：TBD、待定义项"
    )


class FuzzyTerm(BaseModel):
    """模糊词"""
    term: str = Field(description="模糊词，如：快速、用户友好、安全")
    location: str = Field(description="出现位置（模块、章节）")
    current_text: str = Field(description="当前文本")
    issue: str = Field(description="问题说明")
    suggested_fix: str = Field(description="建议修改为（具体、可度量）")


class AmbiguousStatement(BaseModel):
    """歧义表述"""
    statement: str
    possible_interpretations: list[str] = Field(
        min_length=2,
        description="可能的多种解读"
    )
    suggested_clarification: str


class ClarityAssessment(BaseModel):
    """清晰度评估"""

    fuzzy_terms: list[FuzzyTerm] = Field(
        default_factory=list,
        description="模糊词列表"
    )

    ambiguous_statements: list[AmbiguousStatement] = Field(
        default_factory=list,
        description="歧义表述"
    )


class AcceptanceCriteriaGap(BaseModel):
    """验收标准缺口"""
    module_key: str
    capability: str = Field(description="功能点")
    issue: Literal[
        "missing_criteria",        # 缺少验收标准
        "missing_precondition",    # 缺少前置条件
        "missing_expected_result", # 缺少预期结果
        "not_observable",          # 结果不可观察
        "not_measurable",          # 结果不可度量
    ]
    current_text: str = ""
    suggested_criteria: str = Field(
        description="建议的验收标准（Given-When-Then格式）"
    )


class TestCoverageGap(BaseModel):
    """测试覆盖缺口"""
    module_key: str
    gap_type: Literal[
        "boundary_value",    # 边界值未定义
        "exception_path",    # 异常路径未覆盖
        "error_message",     # 错误提示未定义
        "permission",        # 权限测试点缺失
        "concurrency",       # 并发场景未考虑
        "data_dependency",   # 数据依赖未说明
    ]
    description: str
    impact: str


class TestabilityAssessment(BaseModel):
    """可测试性评估"""

    acceptance_criteria_gaps: list[AcceptanceCriteriaGap] = Field(
        default_factory=list,
        description="验收标准缺口"
    )

    test_coverage_gaps: list[TestCoverageGap] = Field(
        default_factory=list,
        description="测试覆盖缺口"
    )


class Conflict(BaseModel):
    """冲突"""
    conflict_id: str
    conflict_type: Literal[
        "rule_contradiction",    # 规则矛盾
        "state_conflict",        # 状态冲突
        "priority_conflict",     # 优先级冲突
        "permission_conflict",   # 权限冲突
        "data_conflict",         # 数据定义冲突
    ]
    description: str
    evidence_1: str = Field(description="证据1：第一个需求的原文")
    evidence_2: str = Field(description="证据2：第二个需求的原文")
    impact: str
    severity: Literal["blocker", "major", "minor"] = "major"


class TerminologyIssue(BaseModel):
    """术语不一致"""
    concept: str = Field(description="概念名称")
    variations: list[str] = Field(
        min_length=2,
        description="不同的叫法"
    )
    suggested_standard_term: str


class ConsistencyAssessment(BaseModel):
    """一致性评估"""

    conflicts: list[Conflict] = Field(
        default_factory=list,
        description="冲突列表"
    )

    terminology_issues: list[TerminologyIssue] = Field(
        default_factory=list,
        description="术语不一致"
    )


class QualityIssueSummary(BaseModel):
    """质量问题统计"""

    # 按维度统计问题数量
    completeness_issues: int = Field(
        description="完整性问题数（functional_gaps + nfr_gaps + missing_details）"
    )
    clarity_issues: int = Field(
        description="清晰度问题数（fuzzy_terms + ambiguous_statements）"
    )
    testability_issues: int = Field(
        description="可测试性问题数（acceptance_criteria_gaps + test_coverage_gaps）"
    )
    consistency_issues: int = Field(
        description="一致性问题数（conflicts + terminology_issues）"
    )

    total_issues: int = Field(
        description="问题总数"
    )

    # 按严重程度统计（从各维度的问题中提取）
    by_severity: dict[str, int] = Field(
        default_factory=lambda: {"blocker": 0, "major": 0, "minor": 0},
        description="按严重程度统计"
    )

    # 关键指标
    has_blocker: bool = Field(
        description="是否存在阻塞问题"
    )

    can_proceed: bool = Field(
        description="是否可以继续（blocker=0）"
    )


class QualityDecision(BaseModel):
    """质量决策"""
    result: Literal["approved", "conditional", "rejected"]
    rationale: str
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="阻塞问题摘要（完整问题在各维度详情中）"
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="建议的下一步行动"
    )


class QualityAssessmentOutput(BaseModel):
    """质量评估输出（无评分版）"""
    summary: QualityIssueSummary
    decision: QualityDecision

    completeness: CompletenessAssessment
    clarity: ClarityAssessment
    testability: TestabilityAssessment
    consistency: ConsistencyAssessment

    assessment_summary: str = Field(description="质量评估总结")


class QualityIssueFlat(BaseModel):
    """扁平的质量问题格式（LLM直接生成这个）"""
    issue_id: str = Field(description="问题ID，如 COMP-001, CLAR-001")

    # 分类维度
    dimension: Literal[
        "completeness",
        "clarity",
        "testability",
        "consistency",
        "implementability",
        "adversarial",
    ]
    category: str = Field(
        description="具体类别：nfr_gap, fuzzy_term, conflict, missing_detail, functional_gap, "
                    "ambiguous, missing_acceptance, boundary_undefined, exception_missing, "
                    "error_message, permission, concurrency, terminology, implementation_risk, "
                    "adversarial_scenario, requirement_gap"
    )
    severity: Literal["blocker", "major", "minor"]

    # 问题描述
    title: str = Field(description="问题标题")
    description: str = Field(description="问题详细描述")
    location: str = Field(description="出现位置（模块、章节）")
    current_text: str = Field(default="", description="当前原文（如有）")

    # 分析和建议
    issue_reason: str = Field(description="为什么是问题")
    suggested_fix: str = Field(description="建议修改方案")
    impact: str = Field(description="对测试/开发的影响")

    # 可选：维度特定信息（用于后处理转换）
    extra: dict = Field(
        default_factory=dict,
        description="维度特定的额外信息，如 {'nfr_category': 'performance', 'term': '快速'}"
    )


class QualityAssessmentSimple(BaseModel):
    """简化的质量评估输出（LLM生成这个，然后转换为QualityAssessmentOutput）"""

    issues: list[QualityIssueFlat] = Field(
        default_factory=list,
        description="所有识别的问题"
    )

    assessment_summary: str = Field(
        description="质量评估总结"
    )


__all__ = [
    "NFRGap",
    "CompletenessAssessment",
    "FuzzyTerm",
    "AmbiguousStatement",
    "ClarityAssessment",
    "AcceptanceCriteriaGap",
    "TestCoverageGap",
    "TestabilityAssessment",
    "Conflict",
    "TerminologyIssue",
    "ConsistencyAssessment",
    "QualityIssueSummary",
    "QualityDecision",
    "QualityAssessmentOutput",
    "QualityIssueFlat",
    "QualityAssessmentSimple",
]
