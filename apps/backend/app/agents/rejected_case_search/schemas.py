from typing import Literal

from pydantic import BaseModel, Field

from app.services.rejected_case_knowledge.schemas import RejectedCaseKnowledgeDocument


class SearchTestPoint(BaseModel):
    point_key: str
    title: str
    module: str = ""
    category: str = ""
    priority: str = ""
    description: str = ""
    verification_points: list[str] = Field(default_factory=list)


class RejectedCaseReference(BaseModel):
    record_id: str
    source_file_id: str
    source_file_name: str
    source_requirement_id: str
    source_requirement_version: str = ""
    matched_test_point_keys: list[str] = Field(default_factory=list)
    title: str
    module: str = ""
    reason_type: str
    reason: str
    handling: Literal["block_duplicate", "generate_with_correction", "warning_only"]
    correction: str = ""
    relevance: Literal["high", "medium"]


class RejectedCaseSearchInput(BaseModel):
    project_id: str
    project_name: str
    requirement_id: str
    requirement_name: str
    requirement_version_id: str
    requirement_version_no: int
    requirement_content: str
    generation_scope: str = ""
    test_points: list[SearchTestPoint] = Field(default_factory=list)
    source_documents: list[RejectedCaseKnowledgeDocument] = Field(default_factory=list)


class RejectedCaseSearchResult(BaseModel):
    matches: list[RejectedCaseReference] = Field(default_factory=list, max_length=20)
