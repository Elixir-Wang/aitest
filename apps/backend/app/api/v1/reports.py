from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import current_user, require_admin
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


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: str,
    report_type: str = Query(default="performance"),
    actor=Depends(require_admin),
) -> None:
    report_center_service.delete_report(report_type, report_id, actor)


@router.get("/api/{report_id}")
def get_api_report(report_id: str, actor=Depends(current_user)) -> dict:
    return report_center_service.get_api_report(report_id, actor)
