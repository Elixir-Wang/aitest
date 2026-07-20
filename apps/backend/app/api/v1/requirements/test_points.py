from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.test_point import TestPointOverviewOut, TestPointOut, TestPointUpdateIn
from app.services import test_point_service


router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("/{document_id}/test-points", response_model=TestPointOverviewOut)
def get_test_points(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return test_point_service.get_overview(project_id, document_id, actor)


@router.post("/{document_id}/test-points/generate", response_model=dict)
def generate_test_points(
    project_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    run = test_point_service.enqueue_generation(project_id, document_id, actor, require_admin=True)
    if run and run["status"] == "queued":
        background_tasks.add_task(test_point_service.execute_generation_run, run["id"])
    return run


@router.patch("/{document_id}/test-points/{point_id}", response_model=TestPointOut)
def update_test_point(
    project_id: str,
    document_id: str,
    point_id: str,
    payload: TestPointUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return test_point_service.update_point(project_id, document_id, point_id, payload, actor)
