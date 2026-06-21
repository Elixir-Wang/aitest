from pydantic import BaseModel, ConfigDict, Field


class ExplorationRunOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    environment_id: str
    environment_name: str
    environment_site_url: str = ""
    requirement_doc_id: str = ""
    requirement_doc_title: str = ""
    title: str
    status: str
    scope: str
    forbidden_paths: str
    login_strategy: str
    captcha_strategy: str = "none"
    reuse_auth_state: bool = False
    has_login_credentials: bool = False
    goal: str
    notes: str = ""
    max_pages: int = 50
    max_actions: int = 1000
    timeout_minutes: int = 120
    artifact_root: str = ""
    result_summary: str = ""
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
    available_actions: list[str]


class ExplorationRunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str | None = None
    environment_id: str = Field(min_length=1)
    requirement_doc_id: str = ""
    title: str = Field(min_length=1)
    scope: str = ""
    forbidden_paths: str = ""
    login_strategy: str = "skip_login"
    goal: str = ""
    notes: str = ""
    max_pages: int = 50
    max_actions: int = 1000
    timeout_minutes: int = 120


class ExplorationRunUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment_id: str | None = Field(default=None, min_length=1)
    requirement_doc_id: str | None = None
    title: str | None = Field(default=None, min_length=1)
    scope: str | None = None
    forbidden_paths: str | None = None
    login_strategy: str | None = None
    goal: str | None = None
    notes: str | None = None
    max_pages: int | None = None
    max_actions: int | None = None
    timeout_minutes: int | None = None


class ExplorationGoalOptimizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=4000)


class ExplorationGoalOptimizeOut(BaseModel):
    optimized_goal: str


class ExplorationStepOut(BaseModel):
    id: str
    type: str
    title: str
    detail: str = ""
    status: str = "completed"
    occurred_at: str | None = None
    artifact_path: str = ""
    source: str = ""


class ExplorationPageOut(BaseModel):
    id: str
    module_key: str
    title: str
    url: str
    entry_path: str
    structure_summary: str
    yaml_path: str = ""
    status: str = "completed"
    blocker_reason: str = ""
    recent_event: str = ""
    steps: list[ExplorationStepOut] = []


class ExplorationElementOut(BaseModel):
    id: str
    page_id: str | None = None
    module_key: str
    element_name: str
    element_type: str
    recommended_locator: str
    fallback_locator: str
    stability_note: str
    source_ref: str
    primary_selector: dict = Field(default_factory=dict)
    fallback_selector: dict = Field(default_factory=dict)


class ExplorationBlockerOut(BaseModel):
    id: str
    module_key: str
    page_ref: str
    reason_type: str
    reason: str
    evidence_path: str
    impact_scope: str
    suggested_action: str
    is_blocking: bool


class ExplorationModuleOut(BaseModel):
    id: str
    module_key: str
    module_name: str
    entry_path: str
    planned_page_count: int
    explored_page_count: int
    blocked_page_count: int
    action_count: int
    field_count: int
    state_transition_count: int
    completion_status: str
    completion_summary: str
    pages: list[ExplorationPageOut]
    elements: list[ExplorationElementOut]
    blockers: list[ExplorationBlockerOut]


class ExplorationRunDetailOut(BaseModel):
    run: ExplorationRunOut
    artifact_schema_version: int = 0
    unsupported_artifact: bool = False
    unsupported_reason: str = ""
    modules: list[ExplorationModuleOut]


class ExplorationReportOut(BaseModel):
    run_id: str
    version_no: int | None = None
    title: str
    markdown_content: str = ""
    change_summary: str = ""
    created_at: str | None = None
    artifact_schema_version: int = 0
    unsupported_artifact: bool = False
    unsupported_reason: str = ""


class ExplorationLogItemOut(BaseModel):
    id: str
    timestamp: str = ""
    event: str = "raw"
    event_label: str = "原始日志"
    category: str = "raw"
    level: str = "info"
    page_id: str = ""
    page_title: str = ""
    url: str = ""
    action_name: str = ""
    result: str = ""
    source_label: str = ""
    target_label: str = ""
    artifact_path: str = ""
    summary: str = ""
    raw: str = ""
    payload: dict = Field(default_factory=dict)


class ExplorationLogOut(BaseModel):
    run_id: str
    log_content: str = ""
    log_path: str = ""
    updated_at: str | None = None
    items: list[ExplorationLogItemOut] = []
    total: int = 0
    page: int = 1
    page_size: int = 10
