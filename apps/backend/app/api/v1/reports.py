from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import current_user
from app.schemas.report_center import ReportCenterItemOut
from app.services import report_center_service


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportCenterItemOut])
def list_reports(
    report_type: str = Query(default="performance"),
    project_id: str = Query(default="all"),
    actor=Depends(current_user),
) -> list[dict]:
    return report_center_service.list_reports(report_type, project_id, actor)
