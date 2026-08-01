"""探索产物（artifacts）列表 / 内容 / 报告端点。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.page_exploration_loop.services.checkpoint import load_checkpoint
from app.core import settings
from app.dependencies.auth import current_user
from app.core.db import connect
from app.repositories import project_repo
from app.services.page_exploration import page_exploration_service
from app.services.page_exploration.coverage_registry import build_coverage_view, load_coverage

router = APIRouter()


def _ensure_project_access(actor: dict, project_id: str, *, write: bool = False, admin: bool = False) -> None:
    def actor_value(key: str, default=""):
        try:
            return actor[key]
        except (KeyError, TypeError, IndexError):
            return default

    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在。")
    role = str(actor_value("role"))
    if admin and role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可维护项目自动化操作。")
    if write and role == "guest":
        raise HTTPException(status_code=403, detail="游客不能执行 UI 自动化。")
    scope = str(actor_value("project_scope"))
    if role != "admin" and scope != "全部项目" and scope != str(project["name"]):
        raise HTTPException(status_code=403, detail="无权访问该项目。")


@router.get("/projects/{project_id}/coverage", response_model=dict)
def get_project_exploration_coverage(
    project_id: str,
    run_id: str | None = Query(default=None),
    actor=Depends(current_user),
) -> dict:
    _ensure_project_access(actor, project_id)
    root = settings.PROJECT_FILE_STORAGE_ROOT
    checkpoint = None
    if run_id:
        state = load_checkpoint(root / project_id / "page_exploration" / "runs" / run_id)
        checkpoint = state.to_dict() if state is not None else None
    return build_coverage_view(load_coverage(root, project_id), checkpoint=checkpoint)


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


@router.delete("/projects/{project_id}/artifacts", response_model=dict)
def clear_project_artifacts(project_id: str, actor=Depends(current_user)) -> dict:
    """清空项目级探索产物。"""
    try:
        return page_exploration_service.clear_project_artifacts(actor, project_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
