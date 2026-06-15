"""
深度分析数据模型

定义业务分析、领域建模、风险识别的输出模型
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ============================================================================
# 业务分析模型
# ============================================================================

class PainPoint(BaseModel):
    """业务痛点"""
    description: str = Field(description="痛点描述")
    reason: str = Field(description="为什么是痛点（根本原因）")
    impact: str = Field(description="对用户的影响")


class CoreValue(BaseModel):
    """核心价值"""
    value: str = Field(description="价值描述")
    differentiation: str = Field(description="与竞品的差异化")
    priority: Literal["high", "medium", "low"] = Field(description="价值优先级")


class CriticalFlow(BaseModel):
    """关键流程"""
    name: str = Field(description="流程名称")
    description: str = Field(description="流程描述")
    steps: list[str] = Field(description="关键步骤")
    decision_points: list[str] = Field(description="决策点（分叉口）")
    why_critical: str = Field(description="为什么这个流程关键")


class DecisionPoint(BaseModel):
    """决策点"""
    point: str = Field(description="决策点描述")
    options: list[str] = Field(description="可能的选项")
    criteria: str = Field(description="决策依据")
    test_concern: str = Field(description="测试关注点")


class BusinessInsight(BaseModel):
    """业务洞察结果"""
    domain: str = Field(description="业务领域（如：智能体平台、工作流引擎）")
    pain_points: list[PainPoint] = Field(description="业务痛点")
    core_values: list[CoreValue] = Field(description="核心价值")
    critical_flows: list[CriticalFlow] = Field(description="关键流程")
    decision_points: list[DecisionPoint] = Field(description="决策点")
    summary: str = Field(description="业务理解总结")


# ============================================================================
# 领域建模模型
# ============================================================================

class CoreConcept(BaseModel):
    """核心概念"""
    name: str = Field(description="概念名称")
    essence: str = Field(description="概念本质（为什么需要这个概念）")
    examples: list[str] = Field(description="具体示例")


class DomainEntity(BaseModel):
    """领域实体"""
    name: str = Field(description="实体名称")
    essence: str = Field(description="实体本质（存在意义）")
    lifecycle: str = Field(description="生命周期描述")
    key_attributes: list[str] = Field(description="关键属性（不是全部字段，只列核心的）")
    relationships: list[str] = Field(description="关系描述（如：订单 belongs_to 用户）")
    why_exists: str = Field(description="为什么需要这个实体")


class Invariant(BaseModel):
    """不变性约束"""
    constraint: str = Field(description="约束描述")
    why_important: str = Field(description="为什么这个约束重要")
    violation_consequence: str = Field(description="违反约束的后果")
    how_to_test: str = Field(description="如何测试验证")


class StateMachine(BaseModel):
    """状态机"""
    entity_name: str = Field(description="实体名称")
    states: list[str] = Field(description="所有状态")
    transitions: list[dict] = Field(description="状态转换（from, to, trigger, condition）")
    critical_transitions: list[str] = Field(description="最容易出问题的转换")
    mermaid_diagram: str = Field(description="Mermaid状态图代码")


class DomainModel(BaseModel):
    """领域模型结果"""
    core_concepts: list[CoreConcept] = Field(description="核心概念")
    entities: list[DomainEntity] = Field(description="领域实体")
    invariants: list[Invariant] = Field(description="不变性约束")
    state_machines: list[StateMachine] = Field(description="状态机")
    summary: str = Field(description="领域模型总结")


# ============================================================================
# 风险识别模型
# ============================================================================

class ComplexScenario(BaseModel):
    """复杂场景"""
    scenario: str = Field(description="场景描述")
    why_complex: str = Field(description="为什么复杂")
    complexity_source: Literal[
        "state_machine",      # 状态机复杂
        "concurrency",        # 并发
        "async",              # 异步
        "external_dependency", # 外部依赖
        "business_rule"       # 业务规则复杂
    ] = Field(description="复杂度来源")
    impact: Literal["high", "medium", "low"] = Field(description="影响程度")


class RiskRootCause(BaseModel):
    """风险根因"""
    risk_description: str = Field(description="风险描述（具体的、有场景的）")
    root_cause: str = Field(description="根本原因（为什么会出问题）")
    trigger_condition: str = Field(description="触发条件（什么情况下会发生）")
    consequence: str = Field(description="后果")
    likelihood: Literal["high", "medium", "low"] = Field(description="发生概率")


class BoundaryCondition(BaseModel):
    """边界条件"""
    boundary: str = Field(description="边界描述")
    behavior_at_boundary: str = Field(description="边界处的行为")
    beyond_boundary: str = Field(description="超出边界会怎样")
    test_cases: list[str] = Field(description="边界测试用例")


class TestStrategy(BaseModel):
    """测试策略"""
    risk_id: str = Field(description="关联的风险")
    strategy: str = Field(description="测试策略")
    test_scenarios: list[str] = Field(description="测试场景")
    assertion_points: list[str] = Field(description="断言点")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(description="优先级")


class RiskProfile(BaseModel):
    """风险画像结果"""
    complex_scenarios: list[ComplexScenario] = Field(description="复杂场景")
    root_causes: list[RiskRootCause] = Field(description="风险根因")
    boundary_conditions: list[BoundaryCondition] = Field(description="边界条件")
    test_strategies: list[TestStrategy] = Field(description="测试策略")
    summary: str = Field(description="风险总结")


# ============================================================================
# 最终输出模型
# ============================================================================

class DeepUnderstandingResult(BaseModel):
    """深度理解结果"""
    business_insight: BusinessInsight = Field(description="业务洞察")
    domain_model: DomainModel = Field(description="领域模型")
    risk_profile: RiskProfile = Field(description="风险画像")
    explanation_markdown: str = Field(description="讲解式文档（面向测试人员）")
    generated_at: str = Field(description="生成时间")


# ============================================================================
# 测试场景模型（QA视角）
# ============================================================================

class FeatureSpec(BaseModel):
    """功能点规格"""
    feature_name: str = Field(description="功能点名称")
    preconditions: list[str] = Field(description="前置条件")
    inputs: list[str] = Field(description="输入项")
    outputs: list[str] = Field(description="输出项")
    normal_path: str = Field(description="正常路径描述")
    exception_paths: list[str] = Field(description="异常路径列表")
    boundary_conditions: list[str] = Field(description="边界条件列表")


class TestScenario(BaseModel):
    """测试场景（Given-When-Then）"""
    scenario_id: str = Field(description="场景ID，如TC-001")
    title: str = Field(description="场景标题")
    given: str = Field(description="前置条件（Given）")
    when: str = Field(description="执行操作（When）")
    then: str = Field(description="预期结果（Then）")
    test_type: Literal["functional", "negative", "boundary", "concurrency"] = Field(
        description="测试类型"
    )
    priority: Literal["P0", "P1", "P2", "P3"] = Field(description="优先级")
    assertion_points: list[str] = Field(description="断言点列表")
    test_data: Optional[dict] = Field(default=None, description="测试数据示例")


class DataFlowEdge(BaseModel):
    """数据流转边"""
    from_node: str = Field(description="起点节点")
    to_node: str = Field(description="终点节点")
    data: str = Field(description="流转的数据")
    validation: Optional[str] = Field(default=None, description="数据校验规则")
    risk: Optional[str] = Field(default=None, description="风险说明")


class RiskHotspot(BaseModel):
    """风险热点"""
    area: str = Field(description="风险区域")
    risk: str = Field(description="风险描述")
    complexity: Literal[
        "concurrency",
        "state_machine",
        "async",
        "external_dependency",
        "business_rule"
    ] = Field(description="复杂度来源")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(description="优先级")
    test_strategy: str = Field(description="测试策略")


class TestScenarioInsight(BaseModel):
    """测试场景洞察（QA导向的需求理解）"""
    features: list[FeatureSpec] = Field(description="功能点清单")
    test_scenarios: list[TestScenario] = Field(description="测试场景清单")
    data_flow: list[DataFlowEdge] = Field(description="数据流转")
    data_flow_mermaid: str = Field(description="Mermaid数据流图")
    risk_hotspots: list[RiskHotspot] = Field(description="风险热点")
    summary: str = Field(description="测试场景总结")


class TestabilityIssue(BaseModel):
    """可测试性问题"""
    feature_name: str = Field(description="功能点名称")
    issue_type: Literal[
        "vague_description",
        "missing_assertion",
        "unclear_precondition",
        "missing_exception",
        "incomplete_state_machine"
    ] = Field(description="问题类型")
    description: str = Field(description="问题描述")
    suggestion: str = Field(description="改进建议")


class TestabilityAssessment(BaseModel):
    """可测试性评估"""
    score: int = Field(description="可测试性评分 0-100")
    testable_features: list[str] = Field(description="可测试功能列表")
    untestable_features: list[TestabilityIssue] = Field(description="不可测试功能列表")
    blocking_issues: list[str] = Field(description="阻塞项列表")
    allow_knowledge_generation: bool = Field(description="是否允许进入知识库生成")
    summary: str = Field(description="评估总结")


class CoverageAnalysis(BaseModel):
    """测试覆盖度分析"""
    total_features: int = Field(description="总功能点数")
    testable_features: int = Field(description="可测试功能点数")
    untestable_features: int = Field(description="不可测试功能点数")
    coverage_percentage: float = Field(description="覆盖率百分比")
    gaps: list[str] = Field(description="需求不清的地方")


class TestItem(BaseModel):
    """测试项"""
    id: str = Field(description="测试项ID")
    feature: str = Field(description="功能点")
    scenario: str = Field(description="测试场景")
    priority: Literal["P0", "P1", "P2", "P3"] = Field(description="优先级")
    test_type: str = Field(description="测试类型")
    given_when_then: str = Field(description="Given-When-Then描述")
    assertion_points: list[str] = Field(description="断言点")
    test_data: Optional[dict] = Field(default=None, description="测试数据")
    risk_level: Literal["high", "medium", "low"] = Field(description="风险等级")


class QARequirementView(BaseModel):
    """QA需求视图（面向测试人员的统一视图）"""
    test_checklist: list[TestItem] = Field(description="测试清单（按优先级排序）")
    risk_hotspots: list[RiskHotspot] = Field(description="风险热点")
    data_flow_diagram: str = Field(description="Mermaid数据流图")
    feature_map_diagram: Optional[str] = Field(default=None, description="Mermaid功能地图")
    state_machines: list[str] = Field(description="Mermaid状态图列表")
    coverage_analysis: CoverageAnalysis = Field(description="测试覆盖度分析")
    testability_assessment: TestabilityAssessment = Field(description="可测试性评估")
    summary: str = Field(description="QA视图总结")


# ============================================================================
# 快速理解模型（Quick Understanding）
# ============================================================================

class SmartSummary(BaseModel):
    """智能摘要"""
    core_function: str = Field(description="核心功能（一句话）")
    main_changes: list[str] = Field(description="主要变更点（3-5条）")
    affected_modules: list[str] = Field(description="影响的模块")
    key_risks: list[str] = Field(description="关键风险（3条以内）")
    estimated_complexity: Literal["low", "medium", "high"] = Field(description="复杂度估计")


class FAQItem(BaseModel):
    """FAQ条目"""
    question: str = Field(description="问题")
    answer: str = Field(description="答案")
    category: Literal[
        "功能", "数据", "流程", "边界", "异常", "性能", "依赖", "其他"
    ] = Field(description="问题分类")


class QuickUnderstandingView(BaseModel):
    """快速理解视图（3-5分钟快速扫描）"""
    summary: SmartSummary = Field(description="智能摘要")
    feature_map_diagram: str = Field(description="功能地图（Mermaid mindmap）")
    core_flow_diagram: str = Field(description="核心流程图（Mermaid flowchart）")
    faq: list[FAQItem] = Field(description="快速FAQ（10个问题）")


class AllDiagrams(BaseModel):
    """所有可视化图表"""
    feature_map: str = Field(description="功能地图（Mermaid mindmap）")
    core_flow: str = Field(description="核心流程图（Mermaid flowchart）")
    data_flow: str = Field(description="数据流图（Mermaid graph）")
    state_machines: list[str] = Field(description="状态机图列表（Mermaid stateDiagram）")


class ComprehensiveQAView(BaseModel):
    """综合QA视图（最终输出）"""
    # 第1部分：快速理解
    quick_understanding: QuickUnderstandingView = Field(description="快速理解视图")

    # 第2部分：测试场景
    test_scenarios: TestScenarioInsight = Field(description="测试场景洞察")

    # 第3部分：可测试性评估
    testability: TestabilityAssessment = Field(description="可测试性评估")

    # 第4部分：综合视图
    test_checklist: list[TestItem] = Field(description="测试清单（按优先级排序）")
    coverage_analysis: CoverageAnalysis = Field(description="测试覆盖度分析")
    all_diagrams: AllDiagrams = Field(description="所有可视化图表")
    summary: str = Field(description="综合总结")


__all__ = [
    # 业务分析
    "PainPoint",
    "CoreValue",
    "CriticalFlow",
    "DecisionPoint",
    "BusinessInsight",

    # 领域建模
    "CoreConcept",
    "DomainEntity",
    "Invariant",
    "StateMachine",
    "DomainModel",

    # 风险识别
    "ComplexScenario",
    "RiskRootCause",
    "BoundaryCondition",
    "TestStrategy",
    "RiskProfile",

    # 最终结果
    "DeepUnderstandingResult",

    # 测试场景（QA视角）
    "FeatureSpec",
    "TestScenario",
    "DataFlowEdge",
    "RiskHotspot",
    "TestScenarioInsight",
    "TestabilityIssue",
    "TestabilityAssessment",
    "CoverageAnalysis",
    "TestItem",
    "QARequirementView",

    # 快速理解
    "SmartSummary",
    "FAQItem",
    "QuickUnderstandingView",
    "AllDiagrams",
    "ComprehensiveQAView",
]
