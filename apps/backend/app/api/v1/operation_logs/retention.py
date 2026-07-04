"""操作日志保留策略与清理端点。

端点：
- ``GET /operation-logs/retention-policy`` —— 查询保留策略（admin）
- ``PUT /operation-logs/retention-policy`` —— 更新保留策略（admin）
- ``POST /operation-logs/cleanup`` —— 手动触发清理（admin）
"""

from fastapi import APIRouter, Depends

from app.dependencies.auth import require_admin
from app.schemas.operation_log import OperationLogCleanupRequest, OperationLogRetentionPolicyUpdate
from app.services import operation_log_service

router = APIRouter(prefix="/operation-logs", tags=["operation-logs"])


@router.get("/retention-policy")
def get_retention_policy(actor=Depends(require_admin)) -> dict:
    return operation_log_service.get_retention_policy(actor)


@router.put("/retention-policy")
def update_retention_policy(
    payload: OperationLogRetentionPolicyUpdate,
    actor=Depends(require_admin),
) -> dict:
    return operation_log_service.update_retention_policy(payload, actor)


@router.post("/cleanup")
def cleanup_logs(payload: OperationLogCleanupRequest, actor=Depends(require_admin)) -> dict:
    return operation_log_service.cleanup_logs(payload, actor)