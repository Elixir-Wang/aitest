from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.performance_test import (
    PerformanceRequestPreviewIn,
    PerformanceRequestPreviewOut,
    PerformanceSseRulePreviewIn,
    PerformanceScriptConfigurationIn,
    PerformanceScriptOut,
    PerformanceTestCreateIn,
    PerformanceTestOut,
    PerformanceTestUpdateIn,
)
from app.services.performance_testing import script_service, service


router = APIRouter(prefix="/projects/{project_id}/performance-tests", tags=["performance-tests"])


@router.post("/request-preview", response_model=PerformanceRequestPreviewOut)
def preview_performance_request(
    project_id: str,
    payload: PerformanceRequestPreviewIn,
    actor=Depends(current_user),
) -> dict:
    return service.preview_performance_request(project_id, payload, actor)


@router.post("/sse-rule-preview")
def preview_sse_rule(
    project_id: str,
    payload: PerformanceSseRulePreviewIn,
    actor=Depends(current_user),
) -> dict:
    return service.preview_sse_rules(project_id, payload, actor)


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


@router.post("/{test_id}/scripts/generate", response_model=PerformanceScriptOut)
def generate_performance_script(project_id: str, test_id: str, actor=Depends(require_admin)) -> dict:
    return script_service.generate_script(project_id, test_id, actor)


@router.get("/{test_id}/script", response_model=PerformanceScriptOut)
def get_current_performance_script(project_id: str, test_id: str, actor=Depends(current_user)) -> dict:
    return script_service.get_current_script(project_id, test_id, actor)


@router.patch("/{test_id}/scripts/{script_id}/configuration", response_model=PerformanceScriptOut)
def update_performance_script_configuration(
    project_id: str,
    test_id: str,
    script_id: str,
    payload: PerformanceScriptConfigurationIn,
    actor=Depends(require_admin),
) -> dict:
    return script_service.update_script_configuration(project_id, test_id, script_id, payload, actor)


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
def delete_performance_test(project_id: str, test_id: str, actor=Depends(current_user)) -> None:
    service.delete_performance_test(project_id, test_id, actor)
