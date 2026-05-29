from __future__ import annotations

from pydantic import BaseModel, Field


class ExplorationRunOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    environment_id: str
    environment_name: str
    environment_site_url: str = ""
    title: str
    status: str
    scope: str
    forbidden_paths: str
    login_strategy: str
    description: str
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
    project_id: str | None = None
    environment_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    scope: str = ""
    forbidden_paths: str = ""
    login_strategy: str = "reuse_state"
    description: str = ""
    max_pages: int = 50
    max_actions: int = 1000
    timeout_minutes: int = 120


class ExplorationRunUpdateIn(BaseModel):
    environment_id: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1)
    scope: str | None = None
    forbidden_paths: str | None = None
    login_strategy: str | None = None
    description: str | None = None
    max_pages: int | None = None
    max_actions: int | None = None
    timeout_minutes: int | None = None


class ExplorationPageOut(BaseModel):
    id: str
    module_key: str
    title: str
    url: str
    entry_path: str
    structure_summary: str
    yaml_path: str = ""
    page_type: str = "unknown"
    status: str = "explored"
    blocker_reason: str = ""
    recent_event: str = ""


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
    modules: list[ExplorationModuleOut]


class ExplorationReportOut(BaseModel):
    run_id: str
    version_no: int | None = None
    title: str
    markdown_content: str = ""
    change_summary: str = ""
    created_at: str | None = None


class ExplorationLogOut(BaseModel):
    run_id: str
    log_content: str = ""
    log_path: str = ""
    updated_at: str | None = None
