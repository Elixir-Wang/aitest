"""项目级操作日志查询与导出端点（与全局 query 行为类似，但权限和 project_id 作用域不同）。

端点：
- ``GET /projects/{project_id}/operation-logs`` —— 项目内日志列表
- ``GET /projects/{project_id}/operation-logs/export`` —— CSV 导出
- ``GET /projects/{project_id}/operation-logs/filter-options`` —— 过滤下拉项
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.dependencies.auth import current_user
from app.schemas.operation_log import OperationLogQuery
from app.services import operation_log_service

router = APIRouter(prefix="/projects/{project_id}/operation-logs", tags=["operation-logs"])


@router.get("")
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


@router.get("/export")
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


@router.get("/filter-options")
def list_project_filter_options(project_id: str, actor=Depends(current_user)) -> dict:
    return operation_log_service.list_filter_options(actor, project_id=project_id)