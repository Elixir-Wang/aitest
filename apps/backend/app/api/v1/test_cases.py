from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.dependencies.auth import current_user, require_admin
from app.schemas.test_case import (
    TestCaseReviewIn,
    TestCaseReviewOut,
    TestCaseSetCreateIn,
    TestCaseSetOut,
)
from app.services import test_case_service


router = APIRouter(prefix="/projects/{project_id}/test-case-sets", tags=["test-cases"])


@router.get("", response_model=list[TestCaseSetOut])
def list_project_test_case_sets(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return test_case_service.list_project_test_case_sets(project_id, actor)


@router.post("", response_model=TestCaseSetOut)
def create_project_test_case_set(
    project_id: str,
    payload: TestCaseSetCreateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = test_case_service.create_test_case_set(project_id, payload, actor)
    if created["generation_run"]:
        background_tasks.add_task(test_case_service.execute_test_case_generation_run, created["generation_run"]["id"])
    return created


@router.get("/{set_id}", response_model=TestCaseSetOut)
def get_project_test_case_set(project_id: str, set_id: str, actor=Depends(current_user)) -> dict:
    return test_case_service.get_test_case_set(project_id, set_id, actor)


@router.get("/{set_id}/export/xmind")
def export_project_test_case_set_xmind(project_id: str, set_id: str, actor=Depends(current_user)) -> Response:
    content, filename = test_case_service.export_test_case_set_xmind(project_id, set_id, actor)
    return Response(
        content=content,
        media_type="application/vnd.xmind.workbook",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.patch("/{set_id}/cases/{case_id}/review", response_model=TestCaseReviewOut)
def review_project_test_case(
    project_id: str,
    set_id: str,
    case_id: str,
    payload: TestCaseReviewIn,
    actor=Depends(require_admin),
) -> dict:
    return test_case_service.review_test_case(project_id, set_id, case_id, payload, actor)


@router.post("/{set_id}/regenerate", response_model=TestCaseSetOut)
def regenerate_project_test_case_set(
    project_id: str,
    set_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    regenerated = test_case_service.regenerate_test_case_set(project_id, set_id, actor)
    if regenerated["generation_run"]:
        background_tasks.add_task(
            test_case_service.execute_test_case_generation_run,
            regenerated["generation_run"]["id"],
        )
    return regenerated


@router.delete("/{set_id}", status_code=204)
def delete_project_test_case_set(project_id: str, set_id: str, actor=Depends(require_admin)) -> None:
    test_case_service.delete_test_case_set(project_id, set_id, actor)
