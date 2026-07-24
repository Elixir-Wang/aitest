from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agents.manual_test_case_generation.schemas import ManualTestCaseAiGenerateIn, ManualTestCaseAiGenerateOut


GenerationScopeType = Literal["all", "specified"]
TestCaseReviewStatus = Literal["ready_for_review", "approved", "rejected"]


class TestCaseSetCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    requirement_doc_id: str = Field(min_length=1)
    generation_scope_type: GenerationScopeType = "all"
    generation_scope_text: str = ""
    notes: str = ""

    @field_validator("name", "requirement_doc_id", "generation_scope_text", "notes", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("generation_scope_text")
    @classmethod
    def _validate_scope_text(cls, value: str, info) -> str:
        if info.data.get("generation_scope_type") == "specified" and not value:
            raise ValueError("指定范围模式下必须填写生成范围。")
        return value


class TestCaseGenerationRunOut(BaseModel):
    id: str
    test_case_set_id: str
    task_id: str
    status: str
    input_snapshot: dict[str, Any]
    error_message: str
    created_at: str
    finished_at: str | None = None


class TestCaseReviewStatsOut(BaseModel):
    case_count: int
    approved_count: int
    rejected_count: int
    pending_count: int
    reviewed_count: int
    adoption_rate: float
    review_progress: float


class TestCaseStep(BaseModel):
    action: str = Field(min_length=1)
    expected_result: str = ""

    @field_validator("action", "expected_result", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ManualTestCaseStep(BaseModel):
    action: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)

    @field_validator("action", "expected_result", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ManualTestCaseCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    preconditions: str = ""
    steps: list[ManualTestCaseStep] = Field(min_length=1)
    notes: str = ""

    @field_validator("title", "preconditions", "notes", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


ManualTestCaseAiGenerateRequest = ManualTestCaseAiGenerateIn
ManualTestCaseAiGenerateResponse = ManualTestCaseAiGenerateOut


class ManualTestCaseOut(BaseModel):
    id: str
    project_id: str
    project_name: str = ""
    title: str
    preconditions: str
    steps: list[ManualTestCaseStep]
    notes: str
    created_by: str
    created_at: str
    updated_at: str


class TestCaseReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TestCaseReviewStatus
    review_feedback: str = Field(default="", max_length=1000)
    preconditions: str | None = None
    steps: list[TestCaseStep] | None = None
    expected_result: str | None = None

    @model_validator(mode="after")
    def _require_rejection_feedback(self):
        if self.status == "rejected" and not self.review_feedback:
            raise ValueError("不采纳原因不能为空。")
        return self

    @field_validator("review_feedback", "preconditions", "expected_result", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("steps")
    @classmethod
    def _validate_steps(cls, value: list[TestCaseStep] | None) -> list[TestCaseStep] | None:
        if value is None:
            return value
        steps = [step for step in value if step.action]
        if not steps:
            raise ValueError("测试步骤不能为空。")
        return steps

    @field_validator("steps", mode="before")
    @classmethod
    def _normalize_steps(cls, value: object) -> object:
        if value is None:
            return value
        if not isinstance(value, list):
            return value
        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"action": item, "expected_result": ""})
            else:
                normalized.append(item)
        return normalized


class TestCaseReviewOut(BaseModel):
    case: "TestCaseOut"
    review_stats: TestCaseReviewStatsOut
    knowledge_record: "RejectedCaseKnowledgeRecordOut | None" = None


class RejectedCaseKnowledgeRecordOut(BaseModel):
    record_id: str
    file_id: str
    file_name: str
    status: Literal["active", "inactive"]


class TestCaseOut(BaseModel):
    id: str
    test_case_set_id: str
    project_id: str
    title: str
    module: str
    priority: str
    preconditions: str
    steps: list[TestCaseStep]
    expected_result: str
    status: str
    review_feedback: str = ""
    reviewed_by: str = ""
    reviewed_at: str | None = None
    created_at: str
    updated_at: str


class TestCaseSetOut(BaseModel):
    id: str
    project_id: str
    project_name: str = ""
    name: str
    requirement_doc_id: str
    requirement_doc_title: str = ""
    generation_scope_type: GenerationScopeType
    generation_scope_text: str
    notes: str
    status: str
    status_label: str
    case_count: int
    created_by: str
    created_at: str
    updated_at: str
    generation_run: TestCaseGenerationRunOut | None = None
    review_stats: TestCaseReviewStatsOut
    cases: list[TestCaseOut] = Field(default_factory=list)
