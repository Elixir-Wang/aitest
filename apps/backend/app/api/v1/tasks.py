from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import current_user
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/running")
def list_running_tasks(project_id: str | None = Query(default=None), actor=Depends(current_user)) -> list[dict]:
    return task_service.list_running_tasks(actor, project_id=project_id)


@router.get("")
def list_tasks(
    project_id: str | None = Query(default=None),
    status_group: str | None = Query(default=None),
    module: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    actor=Depends(current_user),
) -> dict:
    return task_service.list_tasks(
        actor,
        project_id=project_id,
        status_group=status_group,
        module=module,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )

