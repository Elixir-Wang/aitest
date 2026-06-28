from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies.auth import current_user, require_admin
from app.schemas.project import ProjectCreateIn, ProjectOut, ProjectUpdateIn
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


class ExplorationGoalOptimizeRequest(BaseModel):
    """探索目标优化请求"""
    goal: str = Field(..., description="原始探索目标")


class ExplorationGoalOptimizeResponse(BaseModel):
    """探索目标优化响应"""
    optimized_goal: str = Field(..., description="优化后的探索目标")


@router.get("", response_model=list[ProjectOut])
def list_projects(actor=Depends(current_user)) -> list[dict]:
    return project_service.list_projects(actor)


@router.post("", response_model=ProjectOut)
def create_project(payload: ProjectCreateIn, actor=Depends(require_admin)) -> dict:
    return project_service.create_project(payload, actor)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, payload: ProjectUpdateIn, actor=Depends(require_admin)) -> dict:
    return project_service.update_project(project_id, payload, actor)


@router.delete("/{project_id}")
def delete_project(project_id: str, actor=Depends(require_admin)) -> dict:
    return project_service.delete_project(project_id, actor)


@router.post("/{project_id}/exploration-goal/optimize", response_model=ExplorationGoalOptimizeResponse)
def optimize_exploration_goal(
    project_id: str,
    payload: ExplorationGoalOptimizeRequest,
    actor=Depends(current_user)
) -> dict:
    """优化探索目标

    使用AI优化和改进用户输入的探索目标，使其更清晰、具体和可执行。

    Args:
        project_id: 项目ID
        payload: 包含原始探索目标的请求
        actor: 当前用户

    Returns:
        优化后的探索目标
    """
    return project_service.optimize_exploration_goal(project_id, payload.goal, actor)

