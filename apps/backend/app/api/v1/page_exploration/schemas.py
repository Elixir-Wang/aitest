"""Request/Response 模型集中定义，避免子路由重复声明。"""

from typing import Literal

from pydantic import BaseModel, Field


class CreateExplorationRunRequest(BaseModel):
    """创建探索任务请求"""

    project_id: str = Field(..., description="项目ID")
    environment_id: str = Field(..., description="环境ID")
    title: str = Field(..., description="任务标题")
    exploration_mode: Literal["goal", "autonomous", "loop"] = Field(..., description="探索方式")
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
    exploration_mode: Literal["goal", "autonomous", "loop"] | None = Field(None, description="探索方式")
    scope: str | None = Field(None, description="探索范围")
    forbidden_paths: str | None = Field(None, description="禁止路径")
    goal: str | None = Field(None, description="探索目标")
    notes: str | None = Field(None, description="备注")
    max_pages: int | None = Field(None, ge=1, le=500, description="最大页面数")
    max_actions: int | None = Field(None, ge=1, le=10000, description="最大操作数")
    timeout_minutes: int | None = Field(None, ge=1, le=1440, description="超时时间（分钟）")


class ExplorationRunDetailResponse(BaseModel):
    """探索任务详情响应"""

    run: dict
    artifact_schema_version: int
    unsupported_artifact: bool
    unsupported_reason: str
    modules: list[dict]
    timeline_events: list[dict] = Field(default_factory=list)
