from pydantic import BaseModel, Field, field_validator


class ManualTestCaseAiGenerateIn(BaseModel):
    description: str = Field(min_length=2, max_length=4000)
    include_exploration_artifacts: bool = True

    @field_validator("description", mode="before")
    @classmethod
    def _strip_description(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ExplorationElementContext(BaseModel):
    element_key: str = ""
    name: str = ""
    text: str = ""
    role: str = ""
    action_type: str = ""
    context_hint: str = ""


class ExplorationPageContext(BaseModel):
    page_id: str
    title: str = ""
    display_name: str = ""
    breadcrumb: list[str] = Field(default_factory=list)
    entry_path: str = ""
    structure_summary: str = ""
    elements: list[ExplorationElementContext] = Field(default_factory=list)


class ExplorationContext(BaseModel):
    pages: list[ExplorationPageContext] = Field(default_factory=list)
    source_count: int = 0
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class ManualTestCaseGenerationInput(BaseModel):
    description: str
    exploration_context: ExplorationContext | None = None


class ManualTestCaseGenerationStep(BaseModel):
    action: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)

    @field_validator("action", "expected_result", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ManualTestCaseGenerationResult(BaseModel):
    title: str = Field(min_length=1)
    preconditions: str = ""
    steps: list[ManualTestCaseGenerationStep] = Field(min_length=1)
    generation_notes: list[str] = Field(default_factory=list)

    @field_validator("title", "preconditions", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class ManualTestCaseAiSourceSummaryOut(BaseModel):
    description_used: bool = True
    exploration_artifacts_requested: bool
    exploration_artifacts_used: bool
    page_count: int = 0
    truncated: bool = False


class ManualTestCaseAiGenerateOut(ManualTestCaseGenerationResult):
    source_summary: ManualTestCaseAiSourceSummaryOut


__all__ = [
    "ExplorationContext",
    "ExplorationElementContext",
    "ExplorationPageContext",
    "ManualTestCaseAiGenerateIn",
    "ManualTestCaseAiGenerateOut",
    "ManualTestCaseAiSourceSummaryOut",
    "ManualTestCaseGenerationInput",
    "ManualTestCaseGenerationResult",
    "ManualTestCaseGenerationStep",
]
