from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UiAutomationGenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_case_id: str = Field(min_length=1)
    environment_id: str = Field(min_length=1)
    exploration_run_id: str = ""


class UiAutomationRevisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Literal["missing_business_step_mapping"] = "missing_business_step_mapping"
    instruction: str = Field(default="", max_length=2000)
    environment_id: str = ""
    exploration_run_id: str = ""
    run_after_revision: bool = False

    @field_validator("instruction")
    @classmethod
    def normalize_instruction(cls, value: str) -> str:
        return value.strip()


class UiAutomationGenerationRunOut(BaseModel):
    id: str
    project_id: str
    test_case_id: str
    environment_id: str
    exploration_run_id: str = ""
    target_asset_id: str | None = None
    base_generation_run_id: str | None = None
    generation_mode: str = "create"
    reason_code: str = ""
    instruction: str = ""
    run_after_revision: bool = False
    revision_strategy: str = ""
    task_id: str = ""
    status: str
    suite_path: str = ""
    changed_files: list[str] = Field(default_factory=list)
    error_message: str = ""
    created_by: str
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


class UiAutomationAssetOut(BaseModel):
    id: str
    project_id: str
    test_case_id: str
    source_version: int
    generation_run_id: str
    status: str
    pytest_node_id: str
    suite_path: str
    test_file_path: str
    data_file_path: str
    plan_file_path: str
    source_hash: str
    created_by: str
    created_at: str = ""
    updated_at: str = ""


class UiAutomationAssetDetailOut(UiAutomationAssetOut):
    source_title: str = ""
    latest_generation_run: UiAutomationGenerationRunOut | None = None
    latest_execution_run: dict | None = None
    locator_summary: dict = Field(default_factory=dict)


class UiAutomationExecutionCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: str = Field(min_length=1)


class UiAutomationExecutionRunOut(BaseModel):
    id: str
    project_id: str
    asset_id: str
    environment_id: str
    status: str
    run_dir: str = ""
    result: dict = Field(default_factory=dict)
    stdout_path: str = ""
    stderr_path: str = ""
    screenshot_paths: list[str] = Field(default_factory=list)
    error_message: str = ""
    created_by: str
    started_at: str | None = None
    finished_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


class UiAutomationRunLogsOut(BaseModel):
    stdout: str = ""
    stderr: str = ""


class UiAutomationLiveViewOut(BaseModel):
    status: str
    message: str = ""
    stream_path: str = ""
    width: int = 1440
    height: int = 900


class UiAutomationStepArtifactOut(BaseModel):
    artifact_id: str
    kind: str = "screenshot"
    mime_type: str = "application/octet-stream"
    step_id: str = ""


class UiAutomationStepResultOut(BaseModel):
    step_id: str
    title: str = ""
    visible: bool = True
    operation_ids: list[str] = Field(default_factory=list)
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
    error: dict | None = None
    artifacts: list[UiAutomationStepArtifactOut] = Field(default_factory=list)


class UiAutomationIterationResultOut(BaseModel):
    iteration_id: str
    pytest_node_id: str = ""
    index: int = 0
    parameters: dict = Field(default_factory=dict)
    attempt: int = 1
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
    current_step_id: str = ""
    failed_step_id: str = ""
    error: dict | None = None
    steps: list[UiAutomationStepResultOut] = Field(default_factory=list)


class UiAutomationRunDetailOut(BaseModel):
    schema_version: str = "ui-run-detail/v1"
    detail_available: bool = False
    run_id: str
    run_status: str = ""
    incomplete: bool = False
    last_sequence: int = 0
    summary: dict = Field(default_factory=dict)
    iterations: list[UiAutomationIterationResultOut] = Field(default_factory=list)


class UiAutomationRunEventsOut(BaseModel):
    items: list[dict] = Field(default_factory=list)
    next_cursor: int = 0
    has_more: bool = False
