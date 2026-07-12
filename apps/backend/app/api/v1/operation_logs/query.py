"""全局操作日志查询与详情端点。

端点：
- ``GET /operation-logs`` —— 分页列出日志（admin）
- ``GET /operation-logs/{log_id}`` —— 日志详情
- ``GET /operation-logs/export`` —— CSV 导出
- ``GET /operation-logs/filter-options`` —— 过滤下拉项
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.dependencies.auth import current_user, require_admin
from app.schemas.operation_log import OperationLogQuery
from app.services import operation_log_service

router = APIRouter(prefix="/operation-logs", tags=["operation-logs"])


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


@router.get("/filter-options")
def list_filter_options(project_id: str | None = None, actor=Depends(current_user)) -> dict:
    return operation_log_service.list_filter_options(actor, project_id=project_id)


@router.get("/{log_id}")
def get_log(log_id: str, actor=Depends(current_user)) -> dict:
    return operation_log_service.get_log(log_id, actor)
