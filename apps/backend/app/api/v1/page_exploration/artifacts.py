"""探索产物（artifacts）列表 / 内容 / 报告端点。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import current_user
from app.services.page_exploration import page_exploration_service

router = APIRouter()


@router.get("/runs/{run_id}/artifacts", response_model=dict)
def get_exploration_artifacts(run_id: str, actor=Depends(current_user)) -> dict:
    """获取探索报告"""
    try:
        return page_exploration_service.get_exploration_report(actor, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/{artifact_id}/content", response_model=dict)
def get_artifact_content(artifact_id: str, actor=Depends(current_user)) -> dict:
    """获取产物内容"""
    try:
        content = page_exploration_service.get_artifact_content(actor, artifact_id)
        return {"content": content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts", response_model=list[dict])
def list_all_artifacts(
    project_id: str | None = Query(default=None, description="项目ID（可选）"),
    run_id: str | None = Query(default=None, description="探索任务ID（可选）"),
    actor=Depends(current_user),
) -> list[dict]:
    """列出所有探索产物"""
    try:
        return page_exploration_service.list_all_artifacts(actor, project_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))