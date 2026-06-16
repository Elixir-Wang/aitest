"""
需求分析架构 v2.0 - 完善的三块核心架构

基于业界最佳实践（BABOK、IREB、IEEE 830）
"""

from typing import TYPE_CHECKING, Literal
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.agents.requirement_analysis.agents.questioning import QuestioningOutput


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
    evidence_text: str = Field(
        default="",
        description="触发该缺口判断的主需求原文。没有原文依据时不得生成 NFRGap。"
    )
    evidence_reason: str = Field(
        default="",
        description="说明为什么这段原文需要补充该非功能指标。"
    )


class ClarityAssessment(BaseModel):
    """清晰度评估"""

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


# ============================================================================
# 2️⃣.0 下游 Prompt 轻量上下文
# ============================================================================

class EvidenceSnippet(BaseModel):
    """供下游 Agent 使用的短证据片段"""

    source: Literal["primary", "auxiliary"]
    ref: str
    text: str
    filename: str = ""


class RequirementUnderstandingBrief(BaseModel):
    """
    需求理解摘要：供质量评估 Agent 使用，避免传完整理解 JSON

    Token 优化：
    - 完整版 RequirementUnderstandingOutput: ~15K tokens
    - 摘要版 RequirementUnderstandingBrief: ~2K tokens
    - 节省: 87%
    """

    business_goal: str = ""
    modules: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    p0_flows: list[str] = Field(default_factory=list)
    p1_flows: list[str] = Field(default_factory=list)
    state_objects: list[str] = Field(default_factory=list)
    external_dependencies: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)

    # 新增：Mermaid 文件路径引用（不传源码）
    mermaid_files: dict[str, str] = Field(
        default_factory=dict,
        description="Mermaid 文件路径映射：{state_Order: 'diagrams/Order_state_machine.mmd', domain_model: 'diagrams/domain_model.mmd'}"
    )

    # 新增：关键风险 ID（不传完整风险对象）
    high_risk_ids: list[str] = Field(
        default_factory=list,
        description="高风险 ID 列表（下游需要时按需读取）"
    )


class QualityIssueBrief(BaseModel):
    """质量问题摘要：供澄清 Agent 使用，避免传完整质量 JSON"""

    issue_id: str
    severity: Literal["blocker", "major", "minor"]
    dimension: str
    summary: str
    impact: str
    evidence_refs: list[str] = Field(default_factory=list)
    needs_human_decision: bool = True


class QualityAssessmentBrief(BaseModel):
    """质量评估摘要：供澄清 Agent 使用"""

    decision: Literal["approved", "conditional", "rejected"]
    blockers: list[str] = Field(default_factory=list)
    top_issues: list[QualityIssueBrief] = Field(default_factory=list)


class QuestioningBrief(BaseModel):
    """
    质疑分析摘要：供下游 Agent 使用

    Token 优化：仅传递关键统计和ID引用，不传完整内容
    - 完整版 QuestioningOutput: ~12K tokens
    - 摘要版 QuestioningBrief: ~1.5K tokens
    - 节省: 87.5%
    """

    # 风险统计
    high_risk_count: int = Field(default=0, description="🔴高风险数量")
    medium_risk_count: int = Field(default=0, description="🟡中风险数量")
    low_risk_count: int = Field(default=0, description="🟢低风险数量")
    total_risk_count: int = Field(default=0, description="总风险数量")

    # 熔断状态
    breaker_status: str = Field(default="pass", description="熔断状态：halt/review/pass")
    breaker_message: str = Field(default="", description="熔断提示信息")

    # 9宫格摘要（仅传统计，不传完整矩阵）
    nine_grid_summary: dict[str, int] = Field(
        default_factory=dict,
        description="9宫格统计：{WHAT: 3疑点, WHY: 0, WHO: 2, ...}"
    )
    total_nine_grid_issues: int = Field(default=0, description="9宫格总疑点数")

    # 关键疑点 ID（仅传 ID，不传完整内容）
    critical_question_ids: list[str] = Field(
        default_factory=list,
        description="关键疑点ID列表（下游需要时按需读取）"
    )

    # 反向场景统计
    adversarial_scenario_count: int = Field(default=0, description="反向破坏场景数量")
    adversarial_high_risk_count: int = Field(default=0, description="高风险反向场景数量")

    # 可执行性/可实现性统计
    executability_red_count: int = Field(default=0, description="🔴不可测试数量")
    executability_yellow_count: int = Field(default=0, description="🟡验证困难数量")
    implementability_red_count: int = Field(default=0, description="🔴不可实现数量")
    implementability_yellow_count: int = Field(default=0, description="🟡有风险数量")

    # 需求漏洞统计
    requirement_gap_count: int = Field(default=0, description="需求漏洞总数")
    critical_gap_count: int = Field(default=0, description="严重漏洞数量")

    # 建议行动
    recommended_action: str = Field(
        default="",
        description="建议行动（从 risk_breaker 提取）"
    )

    # 元数据
    generated_at: str = Field(default="", description="生成时间")


# ============================================================================
# 2️⃣.1 质量评估简化输出（V2 两阶段方案）
# ============================================================================

class QualityIssueFlat(BaseModel):
    """扁平的质量问题格式（LLM直接生成这个）"""
    issue_id: str = Field(description="问题ID，如 COMP-001, CLAR-001")

    # 分类维度
    dimension: Literal["completeness", "clarity", "testability", "consistency"]
    category: str = Field(
        description="具体类别：nfr_gap, fuzzy_term, conflict, missing_detail, functional_gap, "
                    "ambiguous, missing_acceptance, boundary_undefined, exception_missing, "
                    "error_message, permission, concurrency, terminology"
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


# ============================================================================
# 3️⃣ 待澄清内容 (Clarification Items) - 测试驱动架构
# ============================================================================

class TestSurface(BaseModel):
    """测试表面（测试关注的技术层面）"""
    surface_type: Literal[
        "api",                  # API 契约层
        "state_flow",           # 状态流转层
        "data_consistency",     # 数据一致性层
        "permission",           # 权限控制层
        "security",             # 安全层
        "audit_log",            # 审计日志层
        "async_task",           # 异步任务层
        "external_dependency",  # 外部依赖层
        "ui_feedback",          # 用户反馈层
        "migration",            # 数据迁移层
        "non_functional",       # 非功能需求层
    ]
    rationale: str = Field(
        default="",
        description="为什么这个澄清项影响该测试表面"
    )


class TestCase(BaseModel):
    """测试用例草案"""
    test_id: str = Field(description="测试用例ID，如 TC-001")
    scenario: str = Field(description="测试场景描述（Given-When-Then格式）")
    test_type: Literal[
        "positive",      # 正向测试（正常路径）
        "negative",      # 负向测试（异常路径）
        "boundary",      # 边界值测试
        "concurrency",   # 并发测试
        "security",      # 安全测试
        "performance",   # 性能测试
    ] = "positive"
    expected_result: str = Field(description="预期结果（可断言的）")
    assertion_points: list[str] = Field(
        default_factory=list,
        description="具体的断言点（如：响应状态码为200、字段X包含Y）"
    )
    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        default="P1",
        description="测试优先级（P0=冒烟，P1=核心，P2=重要，P3=边缘）"
    )


class ClarificationOption(BaseModel):
    """澄清选项（供人工选择的方案）"""
    option_id: str
    label: str = Field(description="选项简称，如：按幂等处理、拒绝重复操作")
    description: str = Field(
        description="完整的规则描述，可直接写入需求文档"
    )

    # 测试视角的优劣分析
    pros: list[str] = Field(
        default_factory=list,
        description="该选项的优势（测试角度）"
    )
    cons: list[str] = Field(
        default_factory=list,
        description="该选项的劣势或风险（测试角度）"
    )

    # 如果选择该选项，需要补充的测试用例
    additional_tests: list[str] = Field(
        default_factory=list,
        description="选择该选项后需要补充的测试场景"
    )

    # 证据和来源
    confidence: Literal["high", "medium", "low"] = "medium"
    source: str = Field(
        description="选项来源：辅助文档名称、测试最佳实践、业务经验"
    )
    evidence_excerpt: str = Field(
        default="",
        description="如果来自辅助文档，引用原文片段"
    )


class ClarificationItem(BaseModel):
    """待澄清项（测试驱动视角）"""

    # ========== 基础标识 ==========
    item_id: str = Field(description="唯一标识，如 CL-001")
    title: str = Field(description="简短标题，如：订单状态流转规则待确认")

    # ========== 问题分类 ==========
    issue_category: Literal[
        "contract_unclear",        # 契约不明确（输入输出、接口定义）
        "rule_missing",            # 规则缺失（业务规则、计算规则）
        "boundary_undefined",      # 边界未定义（边界值、极端情况）
        "exception_unhandled",     # 异常未处理（错误处理、失败场景）
        "state_ambiguous",         # 状态模糊（状态流转、终态判定）
        "concurrency_unclear",     # 并发不明确（幂等性、锁策略）
        "permission_undefined",    # 权限未定义（谁能做、什么不能做）
        "dependency_unclear",      # 依赖不清楚（外部依赖、数据依赖）
        "acceptance_missing",      # 验收标准缺失
        "conflict",                # 需求冲突
    ]

    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        default="P1",
        description="优先级（P0=阻塞交付，P1=高风险，P2=中风险，P3=低风险）"
    )

    # ========== 视觉化分级标记（新增）==========
    visual_marker: str = Field(
        default="",
        description="视觉化标记：🔴(P0高风险阻塞) / 🟡(P1/P2中风险) / 🟢(P3低风险)"
    )

    risk_level: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="风险等级：high(阻塞上线) / medium(影响范围/体验) / low(可观察可优化)"
    )

    # ========== 关联信息 ==========
    module_key: str = Field(description="关联的需求模块")
    module_name: str = Field(description="模块名称")
    source_stage: Literal[
        "understanding",    # 来自需求理解阶段
        "completeness",     # 来自完整性检查
        "clarity",          # 来自清晰度检查
        "testability",      # 来自可测试性检查
        "consistency",      # 来自一致性检查
    ]

    # ========== 测试驱动核心字段 ==========

    # 1. 决策点（需要确认什么）
    decision_point: str = Field(
        description="需要人工裁决的具体业务点，如：重复提交是否幂等、失败后是否回滚"
    )

    # 2. 问题描述（为什么需要澄清）
    why_clarify: str = Field(
        description="为什么这个点必须澄清，当前有什么不确定性或风险"
    )

    # 3. 测试影响（不澄清的后果）
    test_impact: str = Field(
        description="不澄清会导致哪些测试无法设计、无法断言、无法验收"
    )

    # 4. 风险场景（Given-When-Then）
    risk_scenario: str = Field(
        description="Given-When-Then 格式的风险触发场景"
    )

    # 5. 影响的测试表面
    affected_surfaces: list[TestSurface] = Field(
        default_factory=list,
        description="该澄清项影响哪些测试层面"
    )

    # 6. 测试用例草案
    test_cases: list[TestCase] = Field(
        default_factory=list,
        description="澄清后应设计的测试用例（3-5个代表性用例）"
    )

    # ========== 澄清选项 ==========
    options: list[ClarificationOption] = Field(
        default_factory=list,
        min_length=0,
        max_length=4,
        description="供人工选择的澄清方案（2-4个互斥选项）"
    )

    recommended_option_id: str = Field(
        default="",
        description="推荐的选项ID（如果有明确推荐）"
    )

    recommendation_rationale: str = Field(
        default="",
        description="推荐理由（基于测试风险、业务通用性等）"
    )

    # ========== 原需求上下文 ==========
    source_excerpt: str = Field(
        default="",
        description="主需求中的相关原文（可追溯）"
    )

    related_requirements: list[str] = Field(
        default_factory=list,
        description="相关的需求条目ID或描述"
    )

    # ========== 解答状态 ==========
    resolution_status: Literal[
        "auto_resolved",     # 从辅助文档找到高置信度答案
        "has_options",       # 有多个选项供选择
        "needs_input",       # 需要业务方输入
        "needs_research",    # 需要进一步调研
    ] = "needs_input"

    # 如果 auto_resolved，记录自动解答的内容
    auto_resolution: str = Field(
        default="",
        description="自动解答的内容（仅当 resolution_status=auto_resolved）"
    )
    auto_resolution_source: str = Field(
        default="",
        description="自动解答的来源（辅助文档名称 + 章节）"
    )

    # ========== 元数据 ==========
    tags: list[str] = Field(
        default_factory=list,
        description="标签，如：高并发、支付核心、数据迁移"
    )

    related_items: list[str] = Field(
        default_factory=list,
        description="关联的其他澄清项ID（如：CL-002 依赖 CL-001 的答案）"
    )


class ClarificationSummary(BaseModel):
    """澄清内容汇总"""

    # 总体统计
    total: int
    by_priority: dict[str, int] = Field(
        default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    )
    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="按 issue_category 分类统计"
    )
    by_resolution: dict[str, int] = Field(
        default_factory=lambda: {
            "auto_resolved": 0,
            "has_options": 0,
            "needs_input": 0,
            "needs_research": 0
        }
    )

    # 测试覆盖分析
    test_surfaces_coverage: dict[str, int] = Field(
        default_factory=dict,
        description="各测试表面被涉及的次数"
    )
    total_test_cases: int = Field(
        default=0,
        description="所有澄清项生成的测试用例总数"
    )

    # 风险评估
    blocking_count: int = Field(
        default=0,
        description="P0 阻塞项数量"
    )
    high_risk_count: int = Field(
        default=0,
        description="P1 高风险项数量"
    )

    # 推荐行动
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="建议的下一步行动（优先处理哪些项）"
    )


class ClarificationOutput(BaseModel):
    """待澄清内容输出（测试驱动版本）"""

    items: list[ClarificationItem] = Field(
        description="按优先级排序的待澄清项（P0 → P1 → P2 → P3）"
    )

    summary: ClarificationSummary

    # 整体评估
    overall_assessment: str = Field(
        description="整体评估：当前需求的可测试性和交付风险"
    )

    # 测试策略建议
    test_strategy_recommendations: list[str] = Field(
        default_factory=list,
        description="基于澄清项的测试策略建议（如：重点做并发测试、补充边界值测试）"
    )

    # 元数据
    generated_at: str = Field(description="生成时间戳")
    model_version: str = Field(default="test-driven")


# ============================================================================
# 最终输出
# ============================================================================

class RequirementAnalysisResultV2(BaseModel):
    """需求分析结果 v2.0"""

    # 分析状态
    status: Literal["completed", "needs_clarification", "blocked"]

    # 核心输出（新增 questioning）
    understanding: RequirementUnderstandingOutput
    questioning: "QuestioningOutput | None" = Field(default=None, description="质疑分析输出")
    quality_assessment: QualityAssessmentOutput
    clarification: ClarificationOutput

    # 综合报告
    analysis_report_markdown: str = Field(
        description="完整的分析报告（Markdown格式）"
    )

    enhanced_requirement_markdown: str = Field(
        default="",
        description="增强版需求文档：原始需求 + 辅助文档自动补充的内容（标记补充部分）"
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
    "EvidenceSnippet",
    "RequirementUnderstandingBrief",
    "QualityIssueBrief",
    "QualityAssessmentBrief",
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
