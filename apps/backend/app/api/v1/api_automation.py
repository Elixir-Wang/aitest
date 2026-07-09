from fastapi import APIRouter, BackgroundTasks, Depends, Query

from app.dependencies.auth import current_user, require_admin
from app.schemas.api_automation import (
    ApiAutomationGenerateIn,
    ApiDocumentOut,
    ApiEndpointDebugIn,
    ApiEndpointDebugOut,
    ApiEndpointIn,
    ApiEndpointOut,
    ApiEndpointUpdateIn,
    ApiEnvironmentIn,
    ApiEnvironmentOut,
    ApiGenerationRunOut,
    ApiRunCreateIn,
    ApiScenarioIn,
    ApiScenarioStepIn,
    ApiScriptGenerateIn,
    ApiScriptUpdateIn,
    ApiTestCaseSetIn,
    ApiTestCaseSetOut,
    ApiTestCaseOut,
    OpenAPIImportIn,
)
from app.services.api_automation import service


router = APIRouter(prefix="/projects/{project_id}", tags=["api-automation"])


@router.post("/api-documents/import", response_model=ApiDocumentOut)
def import_openapi_document(project_id: str, payload: OpenAPIImportIn, actor=Depends(require_admin)) -> dict:
    if payload.source_type == "url":
        return service.import_openapi_url(project_id, url=payload.url, actor=actor, name=payload.name)
    raw_content = payload.content
    return service.import_openapi_text(
        project_id,
        source_type=payload.source_type,
        raw_content=raw_content,
        actor=actor,
        name=payload.name,
        source_url=payload.url,
    )


@router.get("/api-endpoints", response_model=list[ApiEndpointOut])
def list_api_endpoints(
    project_id: str,
    method: str = Query(default=""),
    tag: str = Query(default=""),
    search: str = Query(default=""),
    actor=Depends(current_user),
) -> list[dict]:
    return service.list_project_endpoints(project_id, actor, method=method, tag=tag, search=search)


@router.post("/api-endpoints", response_model=ApiEndpointOut)
def create_api_endpoint(project_id: str, payload: ApiEndpointIn, actor=Depends(require_admin)) -> dict:
    return service.create_project_endpoint(project_id, payload, actor)


@router.get("/api-endpoints/{endpoint_id}", response_model=ApiEndpointOut)
def get_api_endpoint(project_id: str, endpoint_id: str, actor=Depends(current_user)) -> dict:
    return service.get_project_endpoint(project_id, endpoint_id, actor)


@router.post("/api-endpoints/{endpoint_id}/debug", response_model=ApiEndpointDebugOut)
def debug_api_endpoint(
    project_id: str,
    endpoint_id: str,
    payload: ApiEndpointDebugIn,
    actor=Depends(current_user),
) -> dict:
    return service.debug_project_endpoint(project_id, endpoint_id, payload, actor)


@router.patch("/api-endpoints/{endpoint_id}", response_model=ApiEndpointOut)
def update_api_endpoint(
    project_id: str,
    endpoint_id: str,
    payload: ApiEndpointUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return service.update_project_endpoint(project_id, endpoint_id, payload, actor)


@router.delete("/api-endpoints/{endpoint_id}", status_code=204)
def delete_api_endpoint(project_id: str, endpoint_id: str, actor=Depends(require_admin)) -> None:
    service.delete_project_endpoint(project_id, endpoint_id, actor)


@router.get("/api-environments", response_model=list[ApiEnvironmentOut])
def list_api_environments(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_api_environments(project_id, actor)


@router.post("/api-environments", response_model=ApiEnvironmentOut)
def create_api_environment(project_id: str, payload: ApiEnvironmentIn, actor=Depends(require_admin)) -> dict:
    return service.create_api_environment(project_id, payload, actor)


@router.patch("/api-environments/{environment_id}", response_model=ApiEnvironmentOut)
def update_api_environment(
    project_id: str,
    environment_id: str,
    payload: ApiEnvironmentIn,
    actor=Depends(require_admin),
) -> dict:
    return service.update_api_environment(project_id, environment_id, payload, actor)


@router.delete("/api-environments/{environment_id}", status_code=204)
def delete_api_environment(project_id: str, environment_id: str, actor=Depends(require_admin)) -> None:
    service.delete_api_environment(project_id, environment_id, actor)


@router.post("/api-test-cases/generate", response_model=ApiGenerationRunOut)
def generate_api_test_cases(
    project_id: str,
    payload: ApiAutomationGenerateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_generation_run(project_id, payload, actor)
    background_tasks.add_task(service.execute_generation_run, created["id"])
    return created


@router.get("/api-test-cases", response_model=list[ApiTestCaseOut])
def list_api_test_cases(
    project_id: str,
    endpoint_id: str = Query(default=""),
    status: str = Query(default=""),
    actor=Depends(current_user),
) -> list[dict]:
    return service.list_api_test_cases(project_id, actor, endpoint_id=endpoint_id, status=status)


@router.get("/api-test-cases/{case_id}", response_model=ApiTestCaseOut)
def get_api_test_case(project_id: str, case_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_test_case(project_id, case_id, actor)


@router.delete("/api-test-cases/{case_id}", status_code=204)
def delete_api_test_case(project_id: str, case_id: str, actor=Depends(require_admin)) -> None:
    service.delete_api_test_case(project_id, case_id, actor)


@router.get("/api-automation/generation-runs", response_model=list[ApiGenerationRunOut])
def list_api_automation_generation_runs(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_generation_runs(project_id, actor)


@router.get("/api-case-sets", response_model=list[ApiTestCaseSetOut])
def list_api_test_case_sets(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_api_test_case_sets(project_id, actor)


@router.post("/api-case-sets", response_model=ApiTestCaseSetOut)
def create_api_test_case_set(project_id: str, payload: ApiTestCaseSetIn, actor=Depends(require_admin)) -> dict:
    return service.create_api_test_case_set(project_id, payload, actor)


@router.patch("/api-case-sets/{set_id}", response_model=ApiTestCaseSetOut)
def update_api_test_case_set(
    project_id: str,
    set_id: str,
    payload: ApiTestCaseSetIn,
    actor=Depends(require_admin),
) -> dict:
    return service.update_api_test_case_set(project_id, set_id, payload, actor)


@router.get("/api-automation/generation-runs/{run_id}")
def get_api_automation_generation_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_generation_run(project_id, run_id, actor)


@router.post("/api-automation/scripts/generate")
def generate_api_scripts(project_id: str, payload: ApiScriptGenerateIn, actor=Depends(require_admin)) -> dict:
    return service.generate_scripts_from_api_test_cases(project_id, payload.api_test_case_ids, actor)


@router.get("/api-scripts/{script_id}")
def get_api_script(project_id: str, script_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_script(project_id, script_id, actor)


@router.patch("/api-scripts/{script_id}")
def update_api_script(
    project_id: str,
    script_id: str,
    payload: ApiScriptUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return service.update_api_script(project_id, script_id, content=payload.content, notes=payload.notes, actor=actor)


@router.post("/api-runs")
def create_api_run(
    project_id: str,
    payload: ApiRunCreateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_api_run(project_id, payload, actor)
    background_tasks.add_task(service.execute_api_run, created["id"])
    return created


@router.get("/api-runs/{run_id}")
def get_api_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_run(project_id, run_id, actor)


@router.get("/api-runs/{run_id}/logs")
def get_api_run_logs(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_run_logs(project_id, run_id, actor)


@router.get("/api-runs/{run_id}/report")
def get_api_run_report(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_run_report(project_id, run_id, actor)


@router.get("/api-scenarios")
def list_api_scenarios(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_api_scenarios(project_id, actor)


@router.post("/api-scenarios")
def create_api_scenario(project_id: str, payload: ApiScenarioIn, actor=Depends(require_admin)) -> dict:
    return service.create_api_scenario(project_id, payload, actor)


@router.get("/api-scenarios/{scenario_id}")
def get_api_scenario(project_id: str, scenario_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_scenario(project_id, scenario_id, actor)


@router.post("/api-scenarios/{scenario_id}/steps")
def create_api_scenario_step(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioStepIn,
    actor=Depends(require_admin),
) -> dict:
    return service.create_api_scenario_step(project_id, scenario_id, payload, actor)
