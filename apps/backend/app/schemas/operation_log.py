from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LogType = Literal["audit", "config", "task", "agent"]
LogSource = Literal["web", "api", "agent", "runner", "system"]
LogResult = Literal["success", "failed", "partial_success", "cancelled"]


class OperationLogCreate(BaseModel):
    log_type: LogType = "audit"
    module: str
    action: str
    object_type: str
    object_id: str | None = None
    object_name: str = ""
    project_id: str | None = None
    actor_id: str = "system"
    actor_name: str = "系统"
    source: LogSource = "system"
    result: LogResult = "success"
    failure_reason: str = ""
    summary: str = ""
    before: dict | list | str | None = None
    after: dict | list | str | None = None
    task_id: str | None = None
    artifact_path: list[str] = Field(default_factory=list)
    request_id: str = ""
    ip_address: str = ""
    user_agent: str = ""


class OperationLogQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    project_id: str | None = None
    log_type: str | None = None
    module: str | None = None
    action: str | None = None
    object_type: str | None = None
    actor_id: str | None = None
    result: str | None = None
    keyword: str | None = None
    start_time: str | None = None
    end_time: str | None = None


class OperationLogListItem(BaseModel):
    id: str
    log_type: str
    module: str
    action: str
    object_type: str
    object_id: str | None
    object_name: str
    project_id: str | None
    actor_id: str
    actor_name: str
    source: str
    result: str
    failure_reason: str
    summary: str
    task_id: str | None
    created_at: str


class OperationLogDetail(OperationLogListItem):
    before: dict | list | str | None
    after: dict | list | str | None
    artifact_path: list[str]
    request_id: str
    ip_address: str
    user_agent: str


class OperationLogListOut(BaseModel):
    items: list[OperationLogListItem]
    total: int
    page: int
    page_size: int


class OperationLogFilterOptionsOut(BaseModel):
    modules: list[str]
    actions: list[str]
    results: list[str]
    log_types: list[str]


class OperationLogRetentionPolicyOut(BaseModel):
    id: str
    retention_days: int
    max_rows: int
    protect_high_risk: bool
    updated_by: str
    updated_at: str


class OperationLogRetentionPolicyUpdate(BaseModel):
    retention_days: int = Field(ge=1, le=3650)
    max_rows: int = Field(ge=100, le=10_000_000)
    protect_high_risk: bool = True


class OperationLogCleanupRequest(BaseModel):
    before_time: str | None = None
    log_type: str | None = None
    project_id: str | None = None
    dry_run: bool = True


class OperationLogCleanupResult(BaseModel):
    matched_count: int
    deleted_count: int
    dry_run: bool


class ClientErrorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=1000)
    code: str = Field(default="", max_length=80)
    status: int | None = Field(default=None, ge=0, le=599)
    trace_id: str = Field(default="", max_length=80)
    method: str = Field(default="", max_length=12)
    path: str = Field(default="", max_length=500)
    page_url: str = Field(default="", max_length=1000)
    action_label: str = Field(default="", max_length=120)
    occurred_at: str = Field(default="", max_length=80)


class ClientErrorReportOut(BaseModel):
    log_id: str | None
    trace_id: str
