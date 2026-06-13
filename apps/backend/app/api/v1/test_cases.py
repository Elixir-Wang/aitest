from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.test_case import TestCaseSetCreateIn, TestCaseSetOut
from app.services import test_case_service


router = APIRouter(prefix="/projects/{project_id}/test-case-sets", tags=["test-cases"])


@router.get("", response_model=list[TestCaseSetOut])
def list_project_test_case_sets(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return test_case_service.list_project_test_case_sets(project_id, actor)


@router.post("", response_model=TestCaseSetOut)
def create_project_test_case_set(
    project_id: str,
    payload: TestCaseSetCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return test_case_service.create_test_case_set(project_id, payload, actor)


@router.get("/{set_id}", response_model=TestCaseSetOut)
def get_project_test_case_set(project_id: str, set_id: str, actor=Depends(current_user)) -> dict:
    return test_case_service.get_test_case_set(project_id, set_id, actor)
