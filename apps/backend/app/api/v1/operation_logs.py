from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app.dependencies.auth import current_user, require_admin
from app.schemas.operation_log import ClientErrorReport, OperationLogCleanupRequest, OperationLogRetentionPolicyUpdate
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


@router.get("/filter-options")
def list_filter_options(project_id: str | None = None, actor=Depends(current_user)) -> dict:
    return operation_log_service.list_filter_options(actor, project_id=project_id)


@router.put("/retention-policy")
def update_retention_policy(payload: OperationLogRetentionPolicyUpdate, actor=Depends(require_admin)) -> dict:
    return operation_log_service.update_retention_policy(payload, actor)


@router.post("/cleanup")
def cleanup_logs(payload: OperationLogCleanupRequest, actor=Depends(require_admin)) -> dict:
    return operation_log_service.cleanup_logs(payload, actor)


@router.get("/export")
def export_logs(
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
) -> Response:
    from app.schemas.operation_log import OperationLogQuery

    content = operation_log_service.export_logs(
        OperationLogQuery(
            page=1,
            page_size=200,
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
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="operation-logs.csv"'},
    )


@router.post("/client-errors")
def report_client_error(payload: ClientErrorReport, request: Request, actor=Depends(current_user)) -> dict:
    client_host = request.client.host if request.client else ""
    return operation_log_service.record_client_error(
        payload,
        actor,
        ip_address=client_host,
        user_agent=request.headers.get("user-agent", ""),
    )


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


@project_router.get("/filter-options")
def list_project_filter_options(project_id: str, actor=Depends(current_user)) -> dict:
    return operation_log_service.list_filter_options(actor, project_id=project_id)


@project_router.get("/export")
def export_project_logs(
    project_id: str,
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
) -> Response:
    from app.schemas.operation_log import OperationLogQuery

    content = operation_log_service.export_logs(
        OperationLogQuery(
            page=1,
            page_size=200,
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
        project_id=project_id,
    )
    return Response(
        content="\ufeff" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-operation-logs.csv"'},
    )
