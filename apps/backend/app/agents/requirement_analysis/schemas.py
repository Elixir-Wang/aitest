"""Requirement analysis package-level schemas."""

from typing import TYPE_CHECKING, Literal
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.agents.requirement_analysis.clarification.schemas import ClarificationOutput
    from app.agents.requirement_analysis.quality.schemas import QualityAssessmentOutput
    from app.agents.requirement_analysis.understanding.schemas import RequirementUnderstandingOutput


# ============================================================================
# 输入 Schemas
# ============================================================================

class AuxiliaryDocument(BaseModel):
    """辅助文档"""
    mapping_id: str
    filename: str
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


# ============================================================================
# 输出 Schemas
# ============================================================================

class RequirementAnalysisResultV2(BaseModel):
    """需求分析结果 v2.0"""

    # 分析状态
    status: Literal["completed", "needs_clarification", "blocked"]

    # 核心输出
    understanding: "RequirementUnderstandingOutput"
    questioning: None = Field(default=None, description="兼容字段：独立质疑智能体已下线")
    quality_assessment: "QualityAssessmentOutput"
    clarification: "ClarificationOutput"

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
# Brief Schemas (Token 优化)
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
    """质量问题摘要：供澄清 Agent 使用，避免传完整质量评估 JSON"""

    issue_id: str
    severity: Literal["blocker", "major", "minor"]
    dimension: str
    summary: str
    impact: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    needs_human_decision: bool = True


class QualityAssessmentBrief(BaseModel):
    """质量评估摘要：下游澄清 Agent 的输入契约"""

    decision: Literal["approved", "conditional", "rejected"]
    blockers: list[str] = Field(default_factory=list)
    top_issues: list[QualityIssueBrief] = Field(default_factory=list)
    assessment_summary: str = ""


__all__ = [
    # 输入
    "AuxiliaryDocument",
    "RequirementAnalysisInputV2",

    # 输出
    "RequirementAnalysisResultV2",

    # Brief（Token 优化）
    "EvidenceSnippet",
    "RequirementUnderstandingBrief",
    "QualityIssueBrief",
    "QualityAssessmentBrief",
]


def _rebuild_result_model() -> None:
    from app.agents.requirement_analysis.clarification.schemas import ClarificationOutput
    from app.agents.requirement_analysis.quality.schemas import QualityAssessmentOutput
    from app.agents.requirement_analysis.understanding.schemas import RequirementUnderstandingOutput

    RequirementAnalysisResultV2.model_rebuild(
        _types_namespace={
            "ClarificationOutput": ClarificationOutput,
            "QualityAssessmentOutput": QualityAssessmentOutput,
            "RequirementUnderstandingOutput": RequirementUnderstandingOutput,
        }
    )


_rebuild_result_model()
