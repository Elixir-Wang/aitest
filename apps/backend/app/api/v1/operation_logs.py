from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import current_user, require_admin
from app.schemas.operation_log import OperationLogCleanupRequest, OperationLogRetentionPolicyUpdate
from app.services import operation_log_service

router = APIRouter(prefix="/operation-logs", tags=["operation-logs"])
project_router = APIRouter(prefix="/projects/{project_id}/operation-logs", tags=["operation-logs"])


@router.get("")
def list_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    project_id: str | None = None,
    log_type: str | None = None,
    module: str | None = None,
    action: str | None = None,
    object_type: str | None = None,
    actor_id: str | None = None,
    result: str | None = None,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    actor=Depends(require_admin),
) -> dict:
    from app.schemas.operation_log import OperationLogQuery

    return operation_log_service.list_logs(
        OperationLogQuery(
            page=page,
            page_size=page_size,
            project_id=project_id,
            log_type=log_type,
            module=module,
            action=action,
            object_type=object_type,
            actor_id=actor_id,
            result=result,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
        ),
        actor,
    )


@router.get("/retention-policy")
def get_retention_policy(actor=Depends(require_admin)) -> dict:
    return operation_log_service.get_retention_policy(actor)


@router.put("/retention-policy")
def update_retention_policy(payload: OperationLogRetentionPolicyUpdate, actor=Depends(require_admin)) -> dict:
    return operation_log_service.update_retention_policy(payload, actor)


@router.post("/cleanup")
def cleanup_logs(payload: OperationLogCleanupRequest, actor=Depends(require_admin)) -> dict:
    return operation_log_service.cleanup_logs(payload, actor)


@router.get("/export")
def export_logs(actor=Depends(require_admin)) -> dict:
    return {"status": "pending", "message": "日志导出将在前端页面接入后补充文件生成。"}


@router.get("/{log_id}")
def get_log(log_id: str, actor=Depends(current_user)) -> dict:
    return operation_log_service.get_log(log_id, actor)


@project_router.get("")
def list_project_logs(
    project_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    log_type: str | None = None,
    module: str | None = None,
    action: str | None = None,
    object_type: str | None = None,
    actor_id: str | None = None,
    result: str | None = None,
    keyword: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    actor=Depends(current_user),
) -> dict:
    from app.schemas.operation_log import OperationLogQuery

    return operation_log_service.list_project_logs(
        project_id,
        OperationLogQuery(
            page=page,
            page_size=page_size,
            log_type=log_type,
            module=module,
            action=action,
            object_type=object_type,
            actor_id=actor_id,
            result=result,
            keyword=keyword,
            start_time=start_time,
            end_time=end_time,
        ),
        actor,
    )
