from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.test_case import (
    TestCaseGenerationRequest,
    TestCaseGenerationResponse,
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


@router.post("/generate", response_model=TestCaseGenerationResponse)
async def generate_test_cases(
    project_id: str,
    payload: TestCaseGenerationRequest,
    actor=Depends(require_admin),
) -> dict:
    """根据最终需求文档生成测试用例集"""
    return await test_case_service.generate_test_cases_from_requirement(project_id, payload, actor)


@router.get("/{set_id}", response_model=TestCaseSetOut)
def get_project_test_case_set(project_id: str, set_id: str, actor=Depends(current_user)) -> dict:
    return test_case_service.get_test_case_set(project_id, set_id, actor)


@router.delete("/{set_id}", status_code=204)
def delete_project_test_case_set(project_id: str, set_id: str, actor=Depends(require_admin)) -> None:
    test_case_service.delete_test_case_set(project_id, set_id, actor)
