"""
需求分析架构 v2.0 - 完善的三块核心架构

基于业界最佳实践（BABOK、IREB、IEEE 830）
"""

from typing import Literal
from pydantic import BaseModel, Field


# ============================================================================
# 1️⃣ 需求理解 (Requirement Understanding)
# ============================================================================

class BusinessObject(BaseModel):
    """业务对象"""
    name: str
    description: str = ""
    fields: list[str] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list, description="与其他对象的关系")


class BusinessRule(BaseModel):
    """业务规则"""
    rule_id: str
    rule_type: Literal["validation", "calculation", "workflow", "permission", "constraint"]
    description: str
    condition: str = ""
    example: str = ""


class StateFlow(BaseModel):
    """状态流转"""
    object_name: str
    states: list[str]
    transitions: list["StateTransition"] = Field(default_factory=list)


class StateTransition(BaseModel):
    """状态转换"""
    from_state: str
    to_state: str
    trigger: str
    condition: str = ""


class Dependency(BaseModel):
    """依赖关系"""
    source_module: str
    target_module: str
    dependency_type: Literal["data", "api", "service", "event"]
    description: str


class Risk(BaseModel):
    """风险"""
    risk_id: str
    category: Literal["technical", "business", "resource", "schedule", "external"]
    description: str
    impact: Literal["high", "medium", "low"]
    likelihood: Literal["high", "medium", "low"]
    mitigation: str = ""


class Assumption(BaseModel):
    """假设"""
    assumption_id: str
    description: str
    validation_needed: str
    risk_if_invalid: str


class RequirementModule(BaseModel):
    """需求模块"""
    module_key: str
    module_name: str
    summary: str
    capabilities: list[str] = Field(default_factory=list, description="功能点列表")
    business_objects: list[BusinessObject] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    state_flows: list[StateFlow] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="依赖的其他模块")


class RequirementUnderstandingOutput(BaseModel):
    """需求理解输出"""
    modules: list[RequirementModule] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    understanding_summary: str = Field(description="需求理解总结")


# ============================================================================
# 2️⃣ 质量评估 (Quality Assessment)
# ============================================================================

class CompletenessAssessment(BaseModel):
    """完整性评估"""
    score: int = Field(ge=0, le=100, description="完整性分数 0-100")

    functional_gaps: list[str] = Field(
        default_factory=list,
        description="功能完整性缺口：缺失的规则、字段、边界、异常场景"
    )

    nfr_gaps: list["NFRGap"] = Field(
        default_factory=list,
        description="非功能需求缺口"
    )

    missing_details: list[str] = Field(
        default_factory=list,
        description="缺失的细节：TBD、待定义项"
    )


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


class ClarityAssessment(BaseModel):
    """清晰度评估"""
    score: int = Field(ge=0, le=100, description="清晰度分数 0-100")

    fuzzy_terms: list["FuzzyTerm"] = Field(
        default_factory=list,
        description="模糊词列表"
    )

    ambiguous_statements: list["AmbiguousStatement"] = Field(
        default_factory=list,
        description="歧义表述"
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


class TestabilityAssessment(BaseModel):
    """可测试性评估"""
    score: int = Field(ge=0, le=100, description="可测试性分数 0-100")

    acceptance_criteria_gaps: list["AcceptanceCriteriaGap"] = Field(
        default_factory=list,
        description="验收标准缺口"
    )

    test_coverage_gaps: list["TestCoverageGap"] = Field(
        default_factory=list,
        description="测试覆盖缺口"
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


class ConsistencyAssessment(BaseModel):
    """一致性评估"""
    score: int = Field(ge=0, le=100, description="一致性分数 0-100")

    conflicts: list["Conflict"] = Field(
        default_factory=list,
        description="冲突列表"
    )

    terminology_issues: list["TerminologyIssue"] = Field(
        default_factory=list,
        description="术语不一致"
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


class QualityScores(BaseModel):
    """质量分数"""
    completeness: int = Field(ge=0, le=100)
    clarity: int = Field(ge=0, le=100)
    testability: int = Field(ge=0, le=100)
    consistency: int = Field(ge=0, le=100)
    overall: int = Field(ge=0, le=100, description="加权总分")


class QualityDecision(BaseModel):
    """质量决策"""
    result: Literal["approved", "conditional", "rejected"]
    rationale: str
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="阻塞问题：必须解决才能通过"
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="建议的下一步行动"
    )


class QualityAssessmentOutput(BaseModel):
    """质量评估输出"""
    scores: QualityScores
    decision: QualityDecision

    completeness: CompletenessAssessment
    clarity: ClarityAssessment
    testability: TestabilityAssessment
    consistency: ConsistencyAssessment

    assessment_summary: str = Field(description="质量评估总结")


# ============================================================================
# 3️⃣ 待澄清内容 (Clarification Items)
# ============================================================================

class ClarificationOption(BaseModel):
    """澄清选项"""
    option_id: str
    label: str = Field(description="选项标签，简短描述")
    answer_markdown: str = Field(
        description="答案内容（可直接写入需求文档的Markdown格式）"
    )
    rationale: str = Field(default="", description="选择此项的理由")
    confidence: Literal["high", "medium", "low"] = "medium"
    source: str = Field(
        default="",
        description="答案来源：辅助文档名称或推理依据"
    )


class EvidenceReference(BaseModel):
    """证据引用"""
    mapping_id: str = Field(description="辅助文档ID")
    filename: str
    excerpt: str = Field(description="相关摘录")
    section_hint: str = Field(default="", description="章节提示")
    confidence: Literal["high", "medium", "low"] = "medium"


class ClarificationItem(BaseModel):
    """待澄清项"""
    item_id: str

    # 问题来源
    source: Literal[
        "understanding",    # 来自需求理解阶段
        "completeness",     # 来自完整性检查
        "clarity",          # 来自清晰度检查
        "testability",      # 来自可测试性检查
        "consistency",      # 来自一致性检查
    ]

    # 关联信息
    module_key: str
    module_name: str

    # 问题描述
    question: str = Field(
        description="直接面向人工确认的问题。必须把需要确认的字段直接问出来。"
    )
    impact: str = Field(
        description="不确认会造成的下游设计、开发、测试、日志或状态处理影响"
    )
    severity: Literal["blocker", "major", "minor"] = "major"

    # 当前状态
    current_text: str = Field(
        default="",
        description="原需求文本（如果有）"
    )
    suggested_fix: str = Field(
        default="",
        description="建议修正后的文本（可直接替换current_text）"
    )

    # 建议选项
    recommended_options: list[ClarificationOption] = Field(
        default_factory=list,
        max_length=2,
        description="建议的选项（最多2个）"
    )

    # 辅助文档证据
    evidence: list[EvidenceReference] = Field(
        default_factory=list,
        description="从辅助文档找到的相关证据"
    )

    # 自动解答状态
    resolution_status: Literal[
        "auto_resolved",     # 自动解决（高可信度答案）
        "has_suggestions",   # 有建议选项
        "needs_manual",      # 需要人工确认
    ] = "needs_manual"


class ClarificationSummary(BaseModel):
    """澄清内容汇总"""
    total: int
    auto_resolved: int
    has_suggestions: int
    needs_manual: int
    by_severity: dict[str, int] = Field(
        default_factory=lambda: {"blocker": 0, "major": 0, "minor": 0}
    )
    by_source: dict[str, int] = Field(
        default_factory=lambda: {
            "understanding": 0,
            "completeness": 0,
            "clarity": 0,
            "testability": 0,
            "consistency": 0,
        }
    )


class ClarificationOutput(BaseModel):
    """待澄清内容输出"""
    items: list[ClarificationItem] = Field(
        description="按优先级排序的待澄清项"
    )
    summary: ClarificationSummary
    clarification_summary_text: str = Field(
        description="待澄清内容总结文本"
    )


# ============================================================================
# 最终输出
# ============================================================================

class RequirementAnalysisResultV2(BaseModel):
    """需求分析结果 v2.0"""

    # 分析状态
    status: Literal["completed", "needs_clarification", "blocked"]

    # 三块核心输出
    understanding: RequirementUnderstandingOutput
    quality_assessment: QualityAssessmentOutput
    clarification: ClarificationOutput

    # 综合报告
    analysis_report_markdown: str = Field(
        description="完整的分析报告（Markdown格式）"
    )

    preliminary_requirement_markdown: str = Field(
        default="",
        description="初步需求文档（可选：应用建议修正后的版本）"
    )

    # 元数据
    metadata: dict = Field(
        default_factory=dict,
        description="元数据：分析时间、版本、配置等"
    )


# ============================================================================
# 输入
# ============================================================================

class AuxiliaryDocument(BaseModel):
    """辅助文档"""
    mapping_id: str
    filename: str
    document_type: Literal[
        "specification",   # 规格说明
        "policy",          # 政策文档
        "standard",        # 标准
        "reference",       # 参考资料
        "template",        # 模板
        "example",         # 示例
        "other",
    ] = "other"
    markdown_content: str


class RequirementAnalysisInputV2(BaseModel):
    """需求分析输入 v2.0"""

    # 项目信息
    project_id: str
    document_id: str
    document_name: str
    run_id: str = ""

    # 主需求文档
    primary_mapping_id: str
    primary_filename: str
    primary_markdown_content: str

    # 辅助文档
    auxiliary_documents: list[AuxiliaryDocument] = Field(default_factory=list)

    # 配置
    config: dict = Field(
        default_factory=dict,
        description="分析配置：质量阈值、权重、是否生成修正文档等"
    )


__all__ = [
    # 输入
    "RequirementAnalysisInputV2",
    "AuxiliaryDocument",

    # 1️⃣ 需求理解
    "RequirementUnderstandingOutput",
    "RequirementModule",
    "BusinessObject",
    "BusinessRule",
    "StateFlow",
    "StateTransition",
    "Dependency",
    "Risk",
    "Assumption",

    # 2️⃣ 质量评估
    "QualityAssessmentOutput",
    "QualityScores",
    "QualityDecision",
    "CompletenessAssessment",
    "NFRGap",
    "ClarityAssessment",
    "FuzzyTerm",
    "AmbiguousStatement",
    "TestabilityAssessment",
    "AcceptanceCriteriaGap",
    "TestCoverageGap",
    "ConsistencyAssessment",
    "Conflict",
    "TerminologyIssue",

    # 3️⃣ 待澄清内容
    "ClarificationOutput",
    "ClarificationItem",
    "ClarificationOption",
    "EvidenceReference",
    "ClarificationSummary",

    # 最终输出
    "RequirementAnalysisResultV2",
]
