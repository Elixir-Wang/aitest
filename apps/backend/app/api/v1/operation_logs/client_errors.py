"""客户端错误上报端点。

端点：
- ``POST /operation-logs/client-errors`` —— 前端把浏览器/前端错误回传到服务端持久化
"""

from fastapi import APIRouter, Depends, Request

from app.dependencies.auth import current_user
from app.schemas.operation_log import ClientErrorReport
from app.services import operation_log_service

router = APIRouter(prefix="/operation-logs", tags=["operation-logs"])


@router.post("/client-errors")
def report_client_error(
    payload: ClientErrorReport,
    request: Request,
    actor=Depends(current_user),
) -> dict:
    client_host = request.client.host if request.client else ""
    return operation_log_service.record_client_error(
        payload,
        actor,
        ip_address=client_host,
        user_agent=request.headers.get("user-agent", ""),
    )