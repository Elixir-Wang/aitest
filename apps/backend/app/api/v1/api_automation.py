from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request

from app.core.exceptions import api_error
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
    ApiOracleProposalCreateIn,
    ApiOracleProposalRejectIn,
    ApiOracleProposalReviewIn,
    ApiRepairApprovalIn,
    ApiRepairRejectIn,
    ApiRepairRollbackIn,
    ApiRepairSessionCreateIn,
    ApiRunCreateIn,
    ApiScenarioAiPlanAcceptedOut,
    ApiScenarioAiPlanApplyIn,
    ApiScenarioAiPlanIn,
    ApiScenarioAiPlanOut,
    ApiScenarioExecuteIn,
    ApiScenarioIn,
    ApiScenarioPublishIn,
    ApiScenarioStepIn,
    ApiScenarioStepsReplaceIn,
    ApiScenarioVersionSaveIn,
    ApiScriptGenerateIn,
    ApiScriptUpdateIn,
    ApiTestCaseSetIn,
    ApiTestCaseSetOut,
    ApiTestCaseOut,
    OpenAPIImportIn,
    parse_api_endpoint_debug_form,
)
from app.services.api_automation import self_healing, service


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
async def debug_api_endpoint(
    project_id: str,
    endpoint_id: str,
    request: Request,
    actor=Depends(current_user),
) -> dict:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    files = {}
    try:
        if content_type == "multipart/form-data":
            payload, files = parse_api_endpoint_debug_form(await request.form())
        else:
            payload = ApiEndpointDebugIn.model_validate(await request.json())
    except (ValueError, TypeError) as exc:
        raise api_error(422, "API_DEBUG_PAYLOAD_INVALID", str(exc) or "调试请求参数格式不正确。") from exc

    try:
        return service.debug_project_endpoint(project_id, endpoint_id, payload, actor, files=files)
    finally:
        for _, file_object, _, _ in files.values():
            file_object.close()


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
    actor=Depends(current_user),
) -> list[dict]:
    return service.list_api_test_cases(project_id, actor, endpoint_id=endpoint_id)


@router.get("/api-test-cases/{case_id}", response_model=ApiTestCaseOut)
def get_api_test_case(project_id: str, case_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_test_case(project_id, case_id, actor)


@router.delete("/api-test-cases/{case_id}", status_code=204)
def delete_api_test_case(project_id: str, case_id: str, actor=Depends(require_admin)) -> None:
    service.delete_api_test_case(project_id, case_id, actor)


@router.post("/api-test-cases/{case_id}/oracle-proposals")
def create_oracle_proposal(
    project_id: str,
    case_id: str,
    payload: ApiOracleProposalCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return service.create_oracle_proposal(project_id, case_id, payload.run_id, actor)


@router.get("/oracle-proposals")
def list_oracle_proposals(
    project_id: str,
    status: str = Query(default=""),
    actor=Depends(current_user),
) -> list[dict]:
    return service.list_oracle_proposals(project_id, actor, status=status)


@router.post("/oracle-proposals/{proposal_id}/approve")
def approve_oracle_proposal(
    project_id: str,
    proposal_id: str,
    payload: ApiOracleProposalReviewIn,
    actor=Depends(require_admin),
) -> dict:
    return service.approve_oracle_proposal(
        project_id,
        proposal_id,
        scope=payload.scope,
        review_comment=payload.review_comment,
        assertions=payload.assertions,
        actor=actor,
    )


@router.post("/oracle-proposals/{proposal_id}/reject")
def reject_oracle_proposal(
    project_id: str,
    proposal_id: str,
    payload: ApiOracleProposalRejectIn,
    actor=Depends(require_admin),
) -> dict:
    return service.reject_oracle_proposal(
        project_id,
        proposal_id,
        review_comment=payload.review_comment,
        actor=actor,
    )


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


@router.get("/api-automation/generation-runs/{run_id}", response_model=ApiGenerationRunOut)
def get_api_automation_generation_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_generation_run(project_id, run_id, actor)


@router.post(
    "/api-automation/generation-runs/{run_id}/retry-failed",
    response_model=ApiGenerationRunOut,
)
def retry_failed_api_generation_items(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    run = service.retry_failed_generation_items(project_id, run_id, actor)
    background_tasks.add_task(service.execute_generation_run, run_id)
    return run


@router.post("/api-automation/scripts/generate", status_code=202)
def generate_api_scripts(
    project_id: str,
    payload: ApiScriptGenerateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    run = service.create_script_generation_run(
        project_id,
        payload.endpoint_ids,
        actor,
        force=payload.force,
        api_environment_id=payload.api_environment_id,
    )
    background_tasks.add_task(service.execute_script_generation_run, run["id"])
    return run


@router.get("/api-automation/scripts/generation-runs/{run_id}")
def get_api_script_generation_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_script_generation_run(project_id, run_id, actor)


@router.get("/api-scripts")
def list_api_scripts(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_project_scripts(project_id, actor)


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


@router.delete("/api-scripts/{script_id}", status_code=204)
def delete_api_script(project_id: str, script_id: str, actor=Depends(require_admin)) -> None:
    service.delete_api_script(project_id, script_id, actor)


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


@router.get("/api-runs")
def list_api_runs(
    project_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str = Query(default=""),
    environment_id: str = Query(default=""),
    keyword: str = Query(default=""),
    actor=Depends(current_user),
) -> dict:
    return service.list_api_runs(
        project_id,
        actor,
        page=page,
        page_size=page_size,
        status=status,
        environment_id=environment_id,
        keyword=keyword,
    )


@router.get("/api-runs/{run_id}")
def get_api_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_run(project_id, run_id, actor)


@router.delete("/api-runs/{run_id}", status_code=204)
def delete_api_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> None:
    service.delete_api_run(project_id, run_id, actor)


@router.get("/api-runs/{run_id}/logs")
def get_api_run_logs(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_run_logs(project_id, run_id, actor)


@router.get("/api-runs/{run_id}/report")
def get_api_run_report(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_run_report(project_id, run_id, actor)


@router.get("/api-runs/{run_id}/scenario-result")
def get_api_scenario_run_result(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_scenario_run_result(project_id, run_id, actor)


@router.post("/api-runs/{run_id}/repair-session")
def create_api_repair_session(
    project_id: str,
    run_id: str,
    payload: ApiRepairSessionCreateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = self_healing.create_repair_session(project_id, run_id, payload.user_context, actor)
    if created["status"] == "queued":
        background_tasks.add_task(self_healing.execute_repair_attempt, created["attempt_id"])
    return created


@router.get("/api-repair-sessions/{session_id}")
def get_api_repair_session(project_id: str, session_id: str, actor=Depends(current_user)) -> dict:
    return self_healing.get_repair_session(project_id, session_id, actor)


@router.post("/api-repair-sessions/{session_id}/attempts")
def create_api_repair_attempt(
    project_id: str,
    session_id: str,
    payload: ApiRepairSessionCreateIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = self_healing.create_next_repair_attempt(project_id, session_id, payload.user_context, actor)
    background_tasks.add_task(self_healing.execute_repair_attempt, created["attempt_id"])
    return created


@router.get("/api-repair-attempts/{attempt_id}")
def get_api_repair_attempt(project_id: str, attempt_id: str, actor=Depends(current_user)) -> dict:
    return self_healing.get_repair_attempt(project_id, attempt_id, actor)


@router.get("/api-repair-attempts/{attempt_id}/diff")
def get_api_repair_diff(project_id: str, attempt_id: str, actor=Depends(current_user)) -> dict:
    return {"diff": self_healing.get_repair_diff(project_id, attempt_id, actor)}


@router.get("/api-repair-attempts/{attempt_id}/logs")
def get_api_repair_logs(project_id: str, attempt_id: str, actor=Depends(current_user)) -> dict:
    return self_healing.get_repair_logs(project_id, attempt_id, actor)


@router.get("/api-repair-attempts/{attempt_id}/report")
def get_api_repair_report(project_id: str, attempt_id: str, actor=Depends(current_user)) -> dict:
    return self_healing.get_repair_report(project_id, attempt_id, actor)


@router.post("/api-repair-attempts/{attempt_id}/approve")
def approve_api_repair_attempt(
    project_id: str,
    attempt_id: str,
    payload: ApiRepairApprovalIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    result = self_healing.approve_repair_attempt(project_id, attempt_id, payload.comment, actor)
    background_tasks.add_task(self_healing.execute_candidate_repair, attempt_id)
    return result


@router.post("/api-repair-attempts/{attempt_id}/apply")
def apply_api_repair_attempt(
    project_id: str,
    attempt_id: str,
    payload: ApiRepairApprovalIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    result = self_healing.apply_repair_attempt(project_id, attempt_id, payload.comment, actor)
    background_tasks.add_task(service.execute_api_run, result["run_id"])
    return result


@router.post("/api-repair-attempts/{attempt_id}/discard")
def discard_api_repair_attempt(
    project_id: str,
    attempt_id: str,
    payload: ApiRepairRejectIn,
    actor=Depends(require_admin),
) -> dict:
    return self_healing.discard_repair_attempt(project_id, attempt_id, payload.comment, actor)


@router.post("/api-repair-attempts/{attempt_id}/reject")
def reject_api_repair_attempt(
    project_id: str,
    attempt_id: str,
    payload: ApiRepairRejectIn,
    actor=Depends(require_admin),
) -> dict:
    return self_healing.reject_repair_attempt(project_id, attempt_id, payload.comment, actor)


@router.post("/api-repair-sessions/{session_id}/rollback")
def rollback_api_repair_session(
    project_id: str,
    session_id: str,
    payload: ApiRepairRollbackIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    result = self_healing.rollback_repair_session(project_id, session_id, payload.revision, payload.reason, actor)
    background_tasks.add_task(service.execute_api_run, result["run_id"])
    return result


@router.get("/api-scenarios")
def list_api_scenarios(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return service.list_api_scenarios(project_id, actor)


@router.post("/api-scenarios/ai-plan", response_model=ApiScenarioAiPlanAcceptedOut, status_code=202)
def create_api_scenario_ai_plan(
    project_id: str,
    payload: ApiScenarioAiPlanIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    accepted = service.enqueue_api_scenario_ai_plan(project_id, payload, actor)
    if accepted.pop("created"):
        background_tasks.add_task(
            service.create_api_scenario_ai_plan,
            project_id,
            payload,
            actor,
            existing_plan_id=accepted["plan_id"],
        )
    return accepted


@router.get("/api-scenarios/ai-plans/{plan_id}", response_model=ApiScenarioAiPlanOut | ApiScenarioAiPlanAcceptedOut)
def get_api_scenario_ai_plan(project_id: str, plan_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_scenario_ai_plan(project_id, plan_id, actor)


@router.post("/api-scenarios/ai-plans/{plan_id}/apply")
def apply_api_scenario_ai_plan(
    project_id: str,
    plan_id: str,
    payload: ApiScenarioAiPlanApplyIn,
    actor=Depends(require_admin),
) -> dict:
    return service.apply_api_scenario_ai_plan(project_id, plan_id, payload, actor)


@router.post("/api-scenarios")
def create_api_scenario(project_id: str, payload: ApiScenarioIn, actor=Depends(require_admin)) -> dict:
    return service.create_api_scenario(project_id, payload, actor)


@router.get("/api-scenarios/{scenario_id}")
def get_api_scenario(project_id: str, scenario_id: str, actor=Depends(current_user)) -> dict:
    return service.get_api_scenario(project_id, scenario_id, actor)


@router.put("/api-scenarios/{scenario_id}/version")
def save_api_scenario_version(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioVersionSaveIn,
    actor=Depends(require_admin),
) -> dict:
    return service.save_api_scenario_version(project_id, scenario_id, payload, actor)


@router.patch("/api-scenarios/{scenario_id}")
def update_api_scenario(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioIn,
    actor=Depends(require_admin),
) -> dict:
    return service.update_api_scenario(project_id, scenario_id, payload, actor)


@router.delete("/api-scenarios/{scenario_id}", status_code=204)
def delete_api_scenario(project_id: str, scenario_id: str, actor=Depends(require_admin)) -> None:
    service.delete_api_scenario(project_id, scenario_id, actor)


@router.put("/api-scenarios/{scenario_id}/steps")
def replace_api_scenario_steps(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioStepsReplaceIn,
    actor=Depends(require_admin),
) -> dict:
    return service.replace_api_scenario_steps(project_id, scenario_id, payload, actor)


@router.post("/api-scenarios/{scenario_id}/validate")
def validate_api_scenario(project_id: str, scenario_id: str, actor=Depends(current_user)) -> dict:
    return service.validate_api_scenario(project_id, scenario_id, actor)


@router.post("/api-scenarios/{scenario_id}/publish")
def publish_api_scenario(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioPublishIn | None = None,
    actor=Depends(require_admin),
) -> dict:
    return service.publish_api_scenario(
        project_id,
        scenario_id,
        actor,
        confirm_asset_changes=payload.confirm_asset_changes if payload else False,
    )


@router.get("/api-scenarios/{scenario_id}/revisions")
def list_api_scenario_revisions(
    project_id: str,
    scenario_id: str,
    actor=Depends(current_user),
) -> list[dict]:
    return service.list_api_scenario_revisions(project_id, scenario_id, actor)


@router.post("/api-scenarios/{scenario_id}/revisions/{revision}/restore")
def restore_api_scenario_revision(
    project_id: str,
    scenario_id: str,
    revision: int,
    actor=Depends(require_admin),
) -> dict:
    return service.restore_api_scenario_revision(project_id, scenario_id, revision, actor)


@router.post("/api-scenarios/{scenario_id}/execute")
def execute_api_scenario(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioExecuteIn,
    background_tasks: BackgroundTasks,
    actor=Depends(require_admin),
) -> dict:
    created = service.create_api_scenario_run(
        project_id,
        scenario_id,
        payload.api_environment_id,
        actor,
        source=payload.source,
    )
    background_tasks.add_task(service.execute_api_run, created["id"])
    return created


@router.post("/api-scenarios/{scenario_id}/steps")
def create_api_scenario_step(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioStepIn,
    actor=Depends(require_admin),
) -> dict:
    return service.create_api_scenario_step(project_id, scenario_id, payload, actor)



