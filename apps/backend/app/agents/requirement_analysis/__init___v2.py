"""
需求分析模块 v2.0
"""

from .schemas_v2 import (
    # 输入
    RequirementAnalysisInputV2,
    AuxiliaryDocument,

    # 输出
    RequirementAnalysisResultV2,

    # 需求理解
    RequirementUnderstandingOutput,
    RequirementModule,
    BusinessObject,
    BusinessRule,
    StateFlow,
    StateTransition,
    Dependency,
    Risk,
    Assumption,

    # 质量评估
    QualityAssessmentOutput,
    QualityScores,
    QualityDecision,
    CompletenessAssessment,
    NFRGap,
    ClarityAssessment,
    FuzzyTerm,
    AmbiguousStatement,
    TestabilityAssessment,
    AcceptanceCriteriaGap,
    TestCoverageGap,
    ConsistencyAssessment,
    Conflict,
    TerminologyIssue,

    # 待澄清内容
    ClarificationOutput,
    ClarificationItem,
    ClarificationOption,
    EvidenceReference,
    ClarificationSummary,
)

from .agent_v2 import (
    run_requirement_analysis_v2,
    run_understanding_agent,
    run_quality_assessment_agent,
    run_clarification_agent,
)

from .service_v2 import (
    RequirementAnalysisServiceV2,
    analyze_requirement_v2,
    DEFAULT_CONFIG,
)

from .router_v2 import router as router_v2

__version__ = "2.0.0"

__all__ = [
    # 版本
    "__version__",

    # Schema
    "RequirementAnalysisInputV2",
    "AuxiliaryDocument",
    "RequirementAnalysisResultV2",
    "RequirementUnderstandingOutput",
    "RequirementModule",
    "QualityAssessmentOutput",
    "QualityScores",
    "QualityDecision",
    "ClarificationOutput",
    "ClarificationItem",
    "NFRGap",
    "FuzzyTerm",

    # Agent
    "run_requirement_analysis_v2",
    "run_understanding_agent",
    "run_quality_assessment_agent",
    "run_clarification_agent",

    # Service
    "RequirementAnalysisServiceV2",
    "analyze_requirement_v2",
    "DEFAULT_CONFIG",

    # Router
    "router_v2",
]
