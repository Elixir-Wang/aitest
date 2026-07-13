from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.performance_test import (
    PerformanceRequestPreviewIn,
    PerformanceRequestPreviewOut,
    PerformanceTestCreateIn,
    PerformanceTestOut,
    PerformanceTestUpdateIn,
)
from app.services.performance_testing import service


router = APIRouter(prefix="/projects/{project_id}/performance-tests", tags=["performance-tests"])


@router.post("/request-preview", response_model=PerformanceRequestPreviewOut)
def preview_performance_request(
    project_id: str,
    payload: PerformanceRequestPreviewIn,
    actor=Depends(current_user),
) -> dict:
    return service.preview_performance_request(project_id, payload, actor)


@router.post("", response_model=PerformanceTestOut)
def create_performance_test(
    project_id: str,
    payload: PerformanceTestCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return service.create_performance_test(project_id, payload, actor)


@router.get("", response_model=list[PerformanceTestOut])
def list_performance_tests(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_performance_tests(project_id, actor)


@router.get("/{test_id}", response_model=PerformanceTestOut)
def get_performance_test(project_id: str, test_id: str, actor=Depends(current_user)) -> dict:
    return service.get_performance_test(project_id, test_id, actor)


@router.patch("/{test_id}", response_model=PerformanceTestOut)
def update_performance_test(
    project_id: str,
    test_id: str,
    payload: PerformanceTestUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return service.update_performance_test(project_id, test_id, payload, actor)


@router.delete("/{test_id}", status_code=204)
def delete_performance_test(project_id: str, test_id: str, actor=Depends(require_admin)) -> None:
    service.delete_performance_test(project_id, test_id, actor)
