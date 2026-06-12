from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.services import requirement_exploration_service

router = APIRouter()


@router.post(
    "/projects/{project_id}/requirements/{document_id}/analysis-runs/{run_id}/exploration-plan/generate",
    summary="从需求分析结果生成探索计划",
)
def generate_exploration_plan_from_requirement(
    project_id: str,
    document_id: str,
    run_id: str,
    actor: Annotated[dict, Depends(current_user)],
):
    """
    基于需求分析的最终需求文档，生成探索计划。

    生成的计划包含：
    - 业务模块和功能点
    - 能力类型分类（query_filter/crud/content_display等）
    - UI元素定位信息（CSS选择器）
    - 需求点之间的依赖关系
    - 探索步骤和要点

    生成的计划可以导入到探索模块使用。
    """
    return requirement_exploration_service.generate_exploration_plan_from_requirement(
        project_id=project_id,
        document_id=document_id,
        run_id=run_id,
        actor=actor,
    )


@router.get(
    "/projects/{project_id}/requirements/{document_id}/analysis-runs/{run_id}/exploration-plan",
    summary="获取已生成的探索计划",
)
def get_exploration_plan_from_requirement(
    project_id: str,
    document_id: str,
    run_id: str,
    actor: Annotated[dict, Depends(current_user)],
):
    """
    获取已生成的探索计划。

    如果计划不存在，返回404错误。
    """
    return requirement_exploration_service.get_exploration_plan_from_requirement(
        project_id=project_id,
        document_id=document_id,
        run_id=run_id,
        actor=actor,
    )
