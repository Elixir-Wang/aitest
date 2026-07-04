"""项目级 / 任务级 探索页面（pages）产物端点。"""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies.auth import current_user
from app.services.exploration import page_exploration_service

router = APIRouter()


@router.get("/runs/{run_id}/pages", response_model=list[dict])
def list_run_pages(run_id: str, actor=Depends(current_user)) -> list[dict]:
    """列出探索任务的页面"""
    try:
        return page_exploration_service.list_run_pages(actor, run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pages", response_model=list[dict])
def list_project_pages(project_id: str, actor=Depends(current_user)) -> list[dict]:
    """列出项目级探索页面产物"""
    try:
        return page_exploration_service.list_project_pages(actor, project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/pages/{page_id}/yaml", response_model=dict)
def get_project_page_yaml(project_id: str, page_id: str, actor=Depends(current_user)) -> dict:
    """获取项目级页面 YAML 产物内容"""
    try:
        return page_exploration_service.get_project_page_yaml_content(actor, project_id, page_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))