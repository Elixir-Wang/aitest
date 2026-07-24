from typing import Literal

from pydantic import BaseModel, Field


RejectedCaseStatus = Literal["active", "inactive"]
RejectedCaseHandling = Literal["block_duplicate", "generate_with_correction", "warning_only"]


class RejectedCaseStep(BaseModel):
    action: str
    expected_result: str = ""


class RejectedCaseRecord(BaseModel):
    record_id: str
    status: RejectedCaseStatus = "active"
    project_id: str
    project_name: str
    requirement_id: str
    requirement_name: str
    requirement_version_id: str = ""
    requirement_version_no: int | None = None
    generation_run_id: str
    test_case_set_id: str
    test_case_id: str
    title: str
    module: str = ""
    priority: str = ""
    preconditions: str = ""
    steps: list[RejectedCaseStep] = Field(default_factory=list)
    expected_result: str = ""
    reason_type: str = "其他"
    reason: str
    handling: RejectedCaseHandling = "warning_only"
    correction: str = ""
    reviewed_by: str = ""
    reviewed_at: str
    deactivated_at: str = ""


class RejectedCaseKnowledgeDocument(BaseModel):
    file_id: str
    file_name: str
    markdown_content: str
    records: list[RejectedCaseRecord] = Field(default_factory=list)
