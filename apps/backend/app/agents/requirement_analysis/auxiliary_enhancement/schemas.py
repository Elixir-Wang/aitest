from typing import Literal

from pydantic import BaseModel, Field

from app.agents.requirement_analysis.primary_analysis.schemas import (
    RequirementAppliedSupplement,
    RequirementClarificationOption,
    RequirementEvidenceReference,
    RequirementUnresolvedFinding,
)


class RequirementAuxiliaryDocument(BaseModel):
    mapping_id: str
    filename: str
    markdown_content: str


class RequirementEnhancementQuestion(BaseModel):
    id: str
    module_key: str = ""
    module_name: str = ""
    question: str
    impact: str = ""
    severity: Literal["blocker", "major", "minor"] = "major"
    primary_excerpt: str = ""


class RequirementAuxiliaryArticleForEnhancement(BaseModel):
    mapping_id: str
    filename: str
    markdown_content: str


class RequirementAuxiliaryEnhancementInput(BaseModel):
    project_id: str
    document_id: str
    analysis_id: str
    primary_mapping_id: str = ""
    primary_filename: str = ""
    questions: list[RequirementEnhancementQuestion] = Field(default_factory=list)
    auxiliary_articles: list[RequirementAuxiliaryArticleForEnhancement] = Field(default_factory=list)


class RequirementResolvedQuestionOptions(BaseModel):
    question_id: str
    recommended_options: list[RequirementClarificationOption] = Field(default_factory=list, max_length=2)
    evidence: list[RequirementEvidenceReference] = Field(default_factory=list)
    resolution: Literal["answered", "weak_evidence", "conflict", "not_found"]
    reason: str = ""


class RequirementAuxiliaryCoverage(BaseModel):
    question_id: str
    matched_article_count: int = 0
    coverage: Literal["answered", "partial", "conflict", "none"]
    filenames: list[str] = Field(default_factory=list)


class RequirementAuxiliaryEnhancementOutput(BaseModel):
    enhancement_summary: str
    applied_supplements: list[RequirementAppliedSupplement] = Field(default_factory=list)
    resolved_question_options: list[RequirementResolvedQuestionOptions] = Field(default_factory=list)
    new_conflicts: list[RequirementUnresolvedFinding] = Field(default_factory=list)
    unchanged_question_ids: list[str] = Field(default_factory=list)
    auxiliary_coverage: list[RequirementAuxiliaryCoverage] = Field(default_factory=list)


__all__ = [
    "RequirementAuxiliaryArticleForEnhancement",
    "RequirementAuxiliaryCoverage",
    "RequirementAuxiliaryDocument",
    "RequirementAuxiliaryEnhancementInput",
    "RequirementAuxiliaryEnhancementOutput",
    "RequirementEnhancementQuestion",
    "RequirementResolvedQuestionOptions",
]
