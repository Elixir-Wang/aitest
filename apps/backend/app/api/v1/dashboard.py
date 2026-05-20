from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.auth import current_user
from app.schemas.dashboard import DashboardOut
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOut)
def dashboard_overview(
    project_id: str = Query(default="all"),
    days: int = Query(default=17, ge=1, le=90),
    actor=Depends(current_user),
) -> dict:
    return dashboard_service.dashboard_overview(project_id, days, actor)

