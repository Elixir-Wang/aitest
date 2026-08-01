import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agents.api_automation.orchestration.schemas import (
    ScenarioAssertion,
    ScenarioBinding,
    ScenarioExtractor,
    ScenarioPlanInput,
    normalize_legacy_assertion,
    normalize_legacy_binding,
    normalize_legacy_extractor,
)


AuthType = Literal["none", "account_password", "cybertron_agent"]
GenerationStatus = Literal["queued", "running", "completed", "failed", "cancelled", "interrupted"]
ScriptStatus = Literal["draft", "ready", "needs_input", "failed"]
RunStatus = Literal["queued", "running", "passed", "failed", "cancelled", "interrupted"]


class _StrippedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class OpenAPIImportIn(_StrippedModel):
    source_type: Literal["url", "file"]
    url: str = ""
    content: str = ""
    name: str = ""


class ApiDocumentOut(BaseModel):
    id: str
    project_id: str
    name: str
    source_type: str
    source_url: str
    file_path: str
    version: str
    status: str
    endpoint_count: int
    error_message: str
    created_at: str


class ApiEndpointIn(_StrippedModel):
    method: str = Field(min_length=1)
    path: str = Field(min_length=1)
    summary: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    request_body: dict[str, Any] = Field(default_factory=dict)
    responses: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)

    @field_validator("method")
    @classmethod
    def _normalize_method(cls, value: str) -> str:
        return value.upper()


class ApiEndpointUpdateIn(_StrippedModel):
    method: str | None = None
    path: str | None = None
    summary: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    parameters: list[dict[str, Any]] | None = None
    request_body: dict[str, Any] | None = None
    responses: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None
    source: dict[str, Any] | None = None


class ApiEndpointOut(BaseModel):
    id: str
    project_id: str
    document_id: str | None
    method: str
    path: str
    normalized_path: str
    summary: str
    description: str
    tags: list[str]
    parameters: list[dict[str, Any]]
    request_body: dict[str, Any]
    responses: dict[str, Any]
    auth: dict[str, Any]
    source: dict[str, Any]
    created_at: str
    updated_at: str


class ApiEndpointDebugIn(_StrippedModel):
    api_environment_id: str | None = None
    path_params: dict[str, Any] = Field(default_factory=dict)
    query_params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None


MAX_API_DEBUG_FILE_BYTES = 20 * 1024 * 1024
MAX_API_DEBUG_TOTAL_FILE_BYTES = 50 * 1024 * 1024


def parse_api_endpoint_debug_form(form: Any) -> tuple[ApiEndpointDebugIn, dict[str, tuple[str, Any, str, int]]]:
    raw_payload = form.get("payload")
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        raise ValueError("缺少调试请求 payload。")
    try:
        payload = ApiEndpointDebugIn.model_validate(json.loads(raw_payload))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("调试请求 payload 格式不正确。") from exc

    files: dict[str, tuple[str, Any, str, int]] = {}
    total_size = 0
    for key, item in form.multi_items():
        if not isinstance(key, str) or not key.startswith("file::"):
            continue
        field_name = key.removeprefix("file::").strip()
        filename = str(getattr(item, "filename", "") or "").strip()
        file_object = getattr(item, "file", None)
        if not field_name or not filename or file_object is None:
            raise ValueError("调试文件字段格式不正确。")
        if field_name in files:
            raise ValueError(f"文件字段 {field_name} 只允许上传一个文件。")
        size = int(getattr(item, "size", 0) or 0)
        if size > MAX_API_DEBUG_FILE_BYTES:
            raise ValueError(f"文件 {filename} 超过 20 MB 限制。")
        total_size += size
        if total_size > MAX_API_DEBUG_TOTAL_FILE_BYTES:
            raise ValueError("单次调试请求的文件总大小超过 50 MB 限制。")
        files[field_name] = (
            filename,
            file_object,
            str(getattr(item, "content_type", "") or "application/octet-stream"),
            size,
        )
    return payload, files


class ApiEndpointDebugOut(BaseModel):
    request: dict[str, Any]
    status_code: int
    elapsed_ms: int
    headers: dict[str, str]
    body_text: str
    body_json: Any = None
    error_message: str = ""


class ApiEnvironmentIn(_StrippedModel):
    name: str = Field(min_length=1)
    api_base_url: str = Field(min_length=1)
    linked_ui_environment_id: str | None = None
    username: str = ""
    password: str = ""
    auth_type: AuthType = "none"
    auth_config: dict[str, Any] = Field(default_factory=dict)
    variables: dict[str, Any] = Field(default_factory=dict)
    default_headers: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, ge=1, le=600)
    verify_ssl: bool = True
    auth_state_ttl_seconds: int = Field(default=86400, ge=0)
    description: str = ""


class ApiEnvironmentOut(BaseModel):
    id: str
    project_id: str
    name: str
    api_base_url: str
    username: str
    auth_type: str
    auth_config: dict[str, Any]
    variables: dict[str, Any]
    default_headers: dict[str, Any]
    timeout_seconds: int
    verify_ssl: bool
    auth_state_ttl_seconds: int
    description: str
    created_at: str
    updated_at: str


class ApiAutomationGenerateIn(_StrippedModel):
    endpoint_ids: list[str] = Field(default_factory=list, max_length=100)
    test_case_ids: list[str] = Field(default_factory=list)
    api_environment_id: str | None = None
    generation_goal: str = ""
    include_security_cases: bool = False
    generate_code: bool = True


class ApiGenerationAttemptOut(BaseModel):
    id: str
    attempt_no: int
    status: str
    generated_case_count: int
    error_message: str
    started_at: str
    finished_at: str | None = None


class ApiGenerationItemOut(BaseModel):
    id: str
    endpoint_id: str
    method: str
    path: str
    status: str
    attempt_count: int
    generated_case_count: int
    error_message: str
    started_at: str | None = None
    finished_at: str | None = None
    attempts: list[ApiGenerationAttemptOut] = Field(default_factory=list)


class ApiGenerationRunOut(BaseModel):
    id: str
    project_id: str
    api_environment_id: str | None
    task_id: str
    status: str
    endpoint_ids: list[str]
    source_test_case_ids: list[str]
    generation_goal: str
    options: dict[str, Any]
    result_summary: dict[str, Any]
    error_message: str
    total_count: int
    completed_count: int
    success_count: int
    failed_count: int
    generated_case_count: int
    items: list[ApiGenerationItemOut]
    created_at: str
    finished_at: str | None = None


class ApiTestCaseOut(BaseModel):
    id: str
    project_id: str
    endpoint_id: str | None
    title: str
    test_point_key: str
    oracle_status: Literal["confirmed", "inferred", "needs_confirmation"]
    test_description: str
    priority: str
    coverage: str
    preconditions: list[str]
    request: dict[str, Any]
    test_data: dict[str, Any]
    assertions: list[dict[str, Any]]
    notes: str
    created_at: str
    updated_at: str


class ApiTestCaseSetIn(_StrippedModel):
    name: str = Field(min_length=1)
    notes: str = ""


class ApiTestCaseSetOut(BaseModel):
    id: str
    project_id: str
    name: str
    notes: str
    status: str
    endpoint_count: int
    case_count: int
    latest_generation_run_id: str | None
    created_at: str
    updated_at: str


class ApiTestCaseUpdateIn(_StrippedModel):
    title: str | None = None
    priority: str | None = None
    coverage: str | None = None
    preconditions: list[str] | None = None
    request: dict[str, Any] | None = None
    test_data: dict[str, Any] | None = None
    expected: dict[str, Any] | None = None
    assertions: list[dict[str, Any]] | None = None
    variables: dict[str, Any] | None = None
    data_origin: dict[str, Any] | None = None
    notes: str | None = None


class ApiScriptUpdateIn(_StrippedModel):
    content: str = Field(min_length=1)
    notes: str = ""


class ApiScriptGenerateIn(_StrippedModel):
    endpoint_ids: list[str] = Field(min_length=1, max_length=100)
    force: bool = False
    api_environment_id: str | None = None


class ApiRunCreateIn(_StrippedModel):
    script_ids: list[str] = Field(min_length=1)
    api_environment_id: str | None = None


class ApiRepairSessionCreateIn(_StrippedModel):
    user_context: str = Field(default="", max_length=20_000)


class ApiRepairApprovalIn(_StrippedModel):
    comment: str = Field(default="", max_length=20_000)


class ApiRepairRejectIn(_StrippedModel):
    comment: str = Field(default="", max_length=20_000)


class ApiRepairRollbackIn(_StrippedModel):
    revision: int = Field(ge=0)
    reason: str = Field(default="", max_length=20_000)


class ApiRepairAttemptOut(BaseModel):
    id: str
    session_id: str
    attempt_number: int
    base_run_id: str
    base_revision: int
    status: str
    user_context: str
    diagnosis: dict[str, Any]
    validation: dict[str, Any]
    decision: str
    applied_run_id: str | None
    error_message: str
    created_at: str
    updated_at: str


class ApiRepairSessionOut(BaseModel):
    id: str
    project_id: str
    source_run_id: str
    current_run_id: str
    status: str
    current_revision: int
    created_by: str
    created_at: str
    updated_at: str
    attempts: list[ApiRepairAttemptOut] = Field(default_factory=list)


class ApiOracleProposalCreateIn(_StrippedModel):
    run_id: str = Field(min_length=1)


class ApiOracleProposalReviewIn(_StrippedModel):
    scope: Literal["case_only", "case_and_endpoint_asset"] = "case_only"
    review_comment: str = ""
    assertions: list[dict[str, Any]] | None = None


class ApiOracleProposalRejectIn(_StrippedModel):
    review_comment: str = ""


class ApiScenarioIn(_StrippedModel):
    name: str = Field(min_length=1)
    description: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)


class ApiScenarioStepIn(_StrippedModel):
    id: str | None = None
    step_type: Literal["api_request", "condition", "wait", "poll", "assign"] = "api_request"
    api_test_case_id: str | None = None
    endpoint_id: str | None = None
    step_order: int = Field(default=0, ge=0)
    name: str = ""
    request_overrides: dict[str, Any] = Field(default_factory=dict)
    bindings: list[ScenarioBinding] = Field(default_factory=list)
    extractors: list[ScenarioExtractor] = Field(default_factory=list)
    assertions: list[ScenarioAssertion] = Field(default_factory=list)
    control_config: dict[str, Any] = Field(default_factory=dict)
    on_failure: Literal["stop", "continue", "always_run"] = "stop"
    enabled: bool = True

    @field_validator("bindings", mode="before")
    @classmethod
    def _normalize_bindings(cls, value: object) -> object:
        return [normalize_legacy_binding(item) for item in value] if isinstance(value, list) else value

    @field_validator("extractors", mode="before")
    @classmethod
    def _normalize_extractors(cls, value: object) -> object:
        return [normalize_legacy_extractor(item) for item in value] if isinstance(value, list) else value

    @field_validator("assertions", mode="before")
    @classmethod
    def _normalize_assertions(cls, value: object) -> object:
        return [normalize_legacy_assertion(item) for item in value] if isinstance(value, list) else value


class ApiScenarioStepsReplaceIn(_StrippedModel):
    steps: list[ApiScenarioStepIn] = Field(default_factory=list, max_length=100)


class ApiScenarioVersionSaveIn(_StrippedModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    variables: dict[str, Any] = Field(default_factory=dict)
    steps: list[ApiScenarioStepIn] = Field(default_factory=list, max_length=100)


class ApiScenarioAiSourceScope(_StrippedModel):
    endpoint_ids: list[str] = Field(default_factory=list, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=30)


class ApiScenarioAiConstraints(_StrippedModel):
    environment_id: str | None = None
    require_cleanup: bool = False


class ApiScenarioAiPlanIn(_StrippedModel):
    goal: str = Field(min_length=1, max_length=4000)
    source_scope: ApiScenarioAiSourceScope = Field(default_factory=ApiScenarioAiSourceScope)
    constraints: ApiScenarioAiConstraints = Field(default_factory=ApiScenarioAiConstraints)
    scenario_id: str | None = None


class ApiScenarioAiPlanAcceptedOut(_StrippedModel):
    plan_id: str
    scenario_id: str | None = None
    lifecycle_status: Literal["generating", "completed", "failed", "expired"] = "generating"

class ApiScenarioAiPlanNode(_StrippedModel):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["api_request", "condition", "wait", "poll", "assign"]
    endpoint_id: str | None = None
    phase: Literal["setup", "main", "verify", "cleanup"] = "main"
    name: str = ""
    request_overrides: dict[str, Any] = Field(default_factory=dict)
    bindings: list[ScenarioBinding] = Field(default_factory=list)
    extractors: list[ScenarioExtractor] = Field(default_factory=list)
    assertions: list[ScenarioAssertion] = Field(default_factory=list)
    control_config: dict[str, Any] = Field(default_factory=dict)
    on_failure: Literal["stop", "continue", "always_run"] = "stop"
    enabled: bool = True


class ApiScenarioAiPlanEdge(_StrippedModel):
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)
    condition: str = "success"


class ApiScenarioAiPlanOut(_StrippedModel):
    plan_id: str
    plan_version: int = 2
    status: Literal["preview", "applied", "discarded", "expired"] = "preview"
    compiler_version: int = 1
    asset_fingerprint: str = ""
    environment_schema: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 2
    graph_version: int = 1
    scenario_name: str
    description: str = ""
    inputs: list[ScenarioPlanInput] = Field(default_factory=list)
    nodes: list[ApiScenarioAiPlanNode] = Field(default_factory=list)
    edges: list[ApiScenarioAiPlanEdge] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    validation: dict[str, Any] = Field(default_factory=dict)
    expected_revision: int | None = None
    expires_at: str


class ApiScenarioAiPlanApplyIn(_StrippedModel):
    scenario_id: str = Field(min_length=1)
    confirmation: Literal["overwrite_draft"]


class ApiScenarioPublishIn(_StrippedModel):
    confirm_asset_changes: bool = False


class ApiScenarioExecuteIn(_StrippedModel):
    api_environment_id: str
    source: Literal["published", "draft"] = "published"
