"""需求分析模块导出"""

from app.agents.requirement_analysis.agent import requirement_analysis_agent
from app.agents.requirement_analysis.schemas import (
    # 新的
    ClarificationItem,
    RequirementAnalysisResult,
    RequirementInput,
    RequirementUnderstanding,
    # 旧的（向后兼容）
    AuxiliaryRequirementDocument,
    RequirementAnalysisAgentInput,
    RequirementAnalysisAgentOutput,
    RequirementAnalysisRunInput,
    RequirementAnalysisRunOutput,
    RequirementClarificationItem,
)
from app.agents.requirement_analysis.service import (
    analyze_requirement,
    analyze_requirement_legacy,
    build_requirement_analysis_output_json,
    next_analysis_id,
    run_requirement_analysis,
)

__all__ = [
    # Agent
    "requirement_analysis_agent",
    # 新的 Schemas
    "RequirementInput",
    "RequirementUnderstanding",
    "ClarificationItem",
    "RequirementAnalysisResult",
    # 旧的 Schemas（向后兼容）
    "AuxiliaryRequirementDocument",
    "RequirementAnalysisAgentInput",
    "RequirementAnalysisAgentOutput",
    "RequirementAnalysisRunInput",
    "RequirementAnalysisRunOutput",
    "RequirementClarificationItem",
    # Service
    "analyze_requirement",
    "analyze_requirement_legacy",
    "run_requirement_analysis",
    "build_requirement_analysis_output_json",
    "next_analysis_id",
]
