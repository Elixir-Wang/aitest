"""Request/Response 模型集中定义，避免子路由重复声明。"""

from typing import Literal

from pydantic import BaseModel, Field


class CreateExplorationRunRequest(BaseModel):
    """创建探索任务请求"""

    project_id: str = Field(..., description="项目ID")
    environment_id: str = Field(..., description="环境ID")
    title: str = Field(..., description="任务标题")
    exploration_mode: Literal["goal", "autonomous"] = Field(..., description="探索方式")
    scope: str = Field(..., description="探索范围（起始URL）")
    goal: str = Field(default="", description="探索目标")
    forbidden_paths: str = Field(default="", description="禁止路径（每行一个）")
    max_pages: int = Field(default=50, ge=1, le=500, description="最大页面数")
    max_actions: int = Field(default=1000, ge=1, le=10000, description="最大操作数")
    timeout_minutes: int = Field(default=120, ge=1, le=1440, description="超时时间（分钟）")
    login_strategy: str = Field(default="skip_login", description="登录策略")
    requirement_doc_id: str = Field(default="", description="需求文档ID")
    notes: str = Field(default="", description="备注")


class UpdateExplorationRunRequest(BaseModel):
    """更新探索任务请求"""

    title: str | None = Field(None, description="任务标题")
    environment_id: str | None = Field(None, description="环境ID")
    requirement_doc_id: str | None = Field(None, description="需求文档ID")
    exploration_mode: Literal["goal", "autonomous"] | None = Field(None, description="探索方式")
    scope: str | None = Field(None, description="探索范围")
    forbidden_paths: str | None = Field(None, description="禁止路径")
    goal: str | None = Field(None, description="探索目标")
    notes: str | None = Field(None, description="备注")
    max_pages: int | None = Field(None, ge=1, le=500, description="最大页面数")
    max_actions: int | None = Field(None, ge=1, le=10000, description="最大操作数")
    timeout_minutes: int | None = Field(None, ge=1, le=1440, description="超时时间（分钟）")


class ExplorationRunResponse(BaseModel):
    """探索任务响应"""

    id: str
    project_id: str
    environment_id: str
    title: str
    status: str
    exploration_mode: str
    scope: str
    goal: str
    forbidden_paths: str
    max_pages: int
    max_actions: int
    timeout_minutes: int
    created_at: str
    created_by: str
    started_at: str | None = None
    finished_at: str | None = None
    result_summary: str = ""


class ExplorationRunDetailResponse(BaseModel):
    """探索任务详情响应"""

    run: dict
    artifact_schema_version: int
    unsupported_artifact: bool
    unsupported_reason: str
    modules: list[dict]
    timeline_events: list[dict] = Field(default_factory=list)


class ReplayOperationRequest(BaseModel):
    environment_id: str = Field(..., description="当前项目中任选的运行环境 ID")
    operation_key: str = Field(..., min_length=1, description="项目级永久操作 key")
    parameters: dict = Field(default_factory=dict, description="运行时参数")


class SaveReplayOperationRequest(BaseModel):
    operation: dict = Field(..., description="引用永久 element_key 的项目级操作")
