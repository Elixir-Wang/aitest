"""探索产物（artifacts）列表 / 内容 / 报告端点。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies.auth import current_user
from app.core.db import connect
from app.repositories import project_repo
from app.services.page_exploration import page_exploration_service
from app.services.page_exploration.replay import OperationsStore, ReplayError, ReplayRunService, ReplayService
from app.services.page_exploration.replay.models import ReplayOperation
from app.api.v1.page_exploration.schemas import ReplayOperationRequest, SaveReplayOperationRequest

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


@router.get("/projects/{project_id}/operations", response_model=dict)
def list_project_operations(project_id: str, actor=Depends(current_user)) -> dict:
    """List project-level operations without binding them to an environment."""
    _ensure_project_access(actor, project_id)
    try:
        return OperationsStore().read(project_id).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{project_id}/operations/{operation_key}", response_model=dict)
def save_project_operation(
    project_id: str,
    operation_key: str,
    request: SaveReplayOperationRequest,
    actor=Depends(current_user),
) -> dict:
    """Create or replace one environment-agnostic project operation."""
    _ensure_project_access(actor, project_id, write=True, admin=True)
    try:
        operation = ReplayOperation.model_validate({**request.operation, "key": operation_key})
        ReplayService().validate_operation(project_id, operation)
        artifact = OperationsStore().upsert(project_id, operation)
        return artifact.model_dump(mode="json")
    except (ReplayError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/replay", response_model=dict)
def replay_project_operation(
    project_id: str,
    request: ReplayOperationRequest,
    actor=Depends(current_user),
) -> dict:
    """Execute a project-level operation in any environment owned by that project."""
    _ensure_project_access(actor, project_id, write=True)
    try:
        return ReplayRunService().start(
            project_id=project_id,
            environment_id=request.environment_id,
            operation_key=request.operation_key,
            parameters=request.parameters,
        )
    except ReplayError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{project_id}/replay-runs/{run_id}", response_model=dict)
def get_replay_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _ensure_project_access(actor, project_id)
    try:
        return ReplayRunService().get(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/replay-runs/{run_id}/stop", response_model=dict)
def stop_replay_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _ensure_project_access(actor, project_id, write=True)
    try:
        return ReplayRunService().stop(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects/{project_id}/replay-runs/{run_id}/retry", response_model=dict)
def retry_replay_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _ensure_project_access(actor, project_id, write=True)
    try:
        return ReplayRunService().retry(project_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
