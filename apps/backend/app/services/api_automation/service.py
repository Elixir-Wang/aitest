import secrets
from pathlib import Path
from sqlite3 import Row

import httpx

from app.agents.api_automation import service as api_generation_agent_service
from app.agents.api_automation.schemas import ApiAutomationGenerationInput
from app.core.environment_credentials import decrypt_api_environment_secret, encrypt_api_environment_secret
from app.core.security import hash_secret
from app.core import storage
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, project_repo
from app.schemas.api_automation import (
    ApiAutomationGenerateIn,
    ApiEndpointIn,
    ApiEndpointUpdateIn,
    ApiEnvironmentIn,
    ApiRunCreateIn,
    ApiScenarioIn,
    ApiScenarioStepIn,
)
from app.services.api_automation.openapi_parser import OpenAPIParseError, parse_openapi_document
from app.services.api_automation.runner import run_script_suite
from app.services.api_automation.script_generator import generate_pytest_suite


MAX_OPENAPI_BYTES = 2 * 1024 * 1024


def import_openapi_url(project_id: str, *, url: str, actor, name: str = "") -> dict:
    _require_admin(actor)
    if not url:
        raise api_error(400, "OPENAPI_URL_REQUIRED", "请填写 OpenAPI/Swagger URL。")
    try:
        response = httpx.get(url, timeout=15.0, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise api_error(400, "OPENAPI_URL_FETCH_FAILED", f"OpenAPI URL 获取失败：{exc}") from exc
    content = response.text
    if len(content.encode("utf-8")) > MAX_OPENAPI_BYTES:
        raise api_error(400, "OPENAPI_DOCUMENT_TOO_LARGE", "OpenAPI 文档超过大小限制。")
    return import_openapi_text(project_id, source_type="url", raw_content=content, actor=actor, name=name, source_url=url)


def import_openapi_text(
    project_id: str,
    *,
    source_type: str,
    raw_content: str,
    actor,
    name: str = "",
    source_url: str = "",
) -> dict:
    _require_admin(actor)
    document_id = f"apidoc-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        try:
            parsed = parse_openapi_document(raw_content, source_name=name or source_url)
        except OpenAPIParseError as exc:
            raise api_error(400, "OPENAPI_PARSE_FAILED", str(exc)) from exc

        stored_path = _store_openapi_document(project_id, document_id, raw_content, source_type)
        api_automation_repo.create_document(
            db,
            document_id=document_id,
            project_id=project_id,
            name=name or parsed["title"],
            source_type=source_type,
            source_url=source_url,
            file_path=stored_path,
            version=parsed["version"],
            endpoint_count=parsed["endpoint_count"],
            created_by=actor["id"],
        )
        for endpoint in parsed["endpoints"]:
            api_automation_repo.upsert_endpoint(
                db,
                endpoint_id=f"apiend-{secrets.token_hex(8)}",
                project_id=project_id,
                document_id=document_id,
                method=endpoint["method"],
                path=endpoint["path"],
                normalized_path=endpoint["normalized_path"],
                summary=endpoint["summary"],
                description=endpoint["description"],
                tags=endpoint["tags"],
                parameters=endpoint["parameters"],
                request_body=endpoint["request_body"],
                responses=endpoint["responses"],
                auth=endpoint["auth"],
                source=endpoint["source"],
                created_by=actor["id"],
            )
        document = api_automation_repo.find_document(db, document_id)
        if document is None:
            raise api_error(500, "OPENAPI_IMPORT_FAILED", "接口文档保存失败。")
        return _serialize_document(document)


def list_project_endpoints(
    project_id: str,
    actor,
    *,
    method: str = "",
    tag: str = "",
    search: str = "",
) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        rows = api_automation_repo.list_endpoints(db, project_id, method=method, tag=tag, search=search)
        return [_serialize_endpoint(row) for row in rows]


def get_project_endpoint(project_id: str, endpoint_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_endpoint(db, endpoint_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        return _serialize_endpoint(row)


def create_project_endpoint(project_id: str, payload: ApiEndpointIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint_id = api_automation_repo.upsert_endpoint(
            db,
            endpoint_id=f"apiend-{secrets.token_hex(8)}",
            project_id=project_id,
            document_id=None,
            method=payload.method,
            path=payload.path,
            normalized_path=payload.path,
            summary=payload.summary,
            description=payload.description,
            tags=payload.tags,
            parameters=payload.parameters,
            request_body=payload.request_body,
            responses=payload.responses,
            auth=payload.auth,
            source={**payload.source, "source_type": "manual"},
            created_by=actor["id"],
        )
        row = api_automation_repo.find_endpoint(db, endpoint_id)
        if not row:
            raise api_error(500, "API_ENDPOINT_CREATE_FAILED", "接口保存失败。")
        return _serialize_endpoint(row)


def update_project_endpoint(project_id: str, endpoint_id: str, payload: ApiEndpointUpdateIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_endpoint(db, endpoint_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        endpoint_data = _serialize_endpoint(existing)
        update_data = payload.model_dump(exclude_unset=True)
        endpoint_data.update({key: value for key, value in update_data.items() if value is not None})
        saved_id = api_automation_repo.upsert_endpoint(
            db,
            endpoint_id=endpoint_id,
            project_id=project_id,
            document_id=existing["document_id"],
            method=endpoint_data["method"],
            path=endpoint_data["path"],
            normalized_path=endpoint_data["path"],
            summary=endpoint_data["summary"],
            description=endpoint_data["description"],
            tags=endpoint_data["tags"],
            parameters=endpoint_data["parameters"],
            request_body=endpoint_data["request_body"],
            responses=endpoint_data["responses"],
            auth=endpoint_data["auth"],
            source=endpoint_data["source"],
            created_by=actor["id"],
        )
        row = api_automation_repo.find_endpoint(db, saved_id)
        if not row:
            raise api_error(500, "API_ENDPOINT_UPDATE_FAILED", "接口保存失败。")
        return _serialize_endpoint(row)


def delete_project_endpoint(project_id: str, endpoint_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_endpoint(db, endpoint_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        api_automation_repo.delete_endpoint(db, endpoint_id)


def create_api_environment(project_id: str, payload: ApiEnvironmentIn, actor) -> dict:
    _require_admin(actor)
    _validate_auth_config(payload.auth_type, payload.auth_config)
    auth_config = _prepare_auth_config_for_storage(payload.auth_type, payload.auth_config)
    password_encrypted = encrypt_api_environment_secret(payload.password)
    password_hash = hash_secret(payload.password) if payload.password else ""
    environment_id = f"apienv-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        try:
            api_automation_repo.create_api_environment(
                db,
                environment_id=environment_id,
                project_id=project_id,
                linked_ui_environment_id=payload.linked_ui_environment_id,
                name=payload.name,
                api_base_url=payload.api_base_url,
                username=payload.username,
                password_encrypted=password_encrypted,
                password_hash=password_hash,
                auth_type=payload.auth_type,
                auth_config=auth_config,
                variables=payload.variables,
                default_headers=payload.default_headers,
                timeout_seconds=payload.timeout_seconds,
                verify_ssl=payload.verify_ssl,
                auth_state_ttl_seconds=payload.auth_state_ttl_seconds,
                description=payload.description,
                created_by=actor["id"],
            )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise api_error(409, "API_ENVIRONMENT_CONFLICT", "接口环境名称已存在。") from exc
            raise
        row = api_automation_repo.find_api_environment(db, environment_id)
        if not row:
            raise api_error(500, "API_ENVIRONMENT_CREATE_FAILED", "接口环境保存失败。")
        return _serialize_api_environment(row)


def list_api_environments(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        rows = api_automation_repo.list_api_environments(db, project_id)
        return [_serialize_api_environment(row) for row in rows]


def update_api_environment(project_id: str, environment_id: str, payload: ApiEnvironmentIn, actor) -> dict:
    _require_admin(actor)
    _validate_auth_config(payload.auth_type, payload.auth_config)
    auth_config = _prepare_auth_config_for_storage(payload.auth_type, payload.auth_config)
    fields = {
        "linked_ui_environment_id": payload.linked_ui_environment_id,
        "name": payload.name,
        "api_base_url": payload.api_base_url,
        "username": payload.username,
        "auth_type": payload.auth_type,
        "auth_config": auth_config,
        "variables": payload.variables,
        "default_headers": payload.default_headers,
        "timeout_seconds": payload.timeout_seconds,
        "verify_ssl": payload.verify_ssl,
        "auth_state_ttl_seconds": payload.auth_state_ttl_seconds,
        "description": payload.description,
    }
    if payload.password:
        fields["password_encrypted"] = encrypt_api_environment_secret(payload.password)
        fields["password_hash"] = hash_secret(payload.password)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_api_environment(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        api_automation_repo.update_api_environment(db, environment_id, **fields)
        row = api_automation_repo.find_api_environment(db, environment_id)
        if not row:
            raise api_error(500, "API_ENVIRONMENT_UPDATE_FAILED", "接口环境保存失败。")
        return _serialize_api_environment(row)


def delete_api_environment(project_id: str, environment_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_api_environment(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        api_automation_repo.delete_api_environment(db, environment_id)


def create_generation_run(project_id: str, payload: ApiAutomationGenerateIn, actor) -> dict:
    _require_admin(actor)
    run_id = f"apigen-{secrets.token_hex(8)}"
    task_id = f"api_automation_generation:{run_id}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_endpoint_ids(db, project_id, payload.endpoint_ids)
        api_automation_repo.create_generation_run(
            db,
            run_id=run_id,
            task_id=task_id,
            project_id=project_id,
            api_environment_id=payload.api_environment_id,
            endpoint_ids=payload.endpoint_ids,
            source_test_case_ids=payload.test_case_ids,
            generation_goal=payload.generation_goal,
            options={
                "include_security_cases": payload.include_security_cases,
                "generate_code": payload.generate_code,
            },
            created_by=actor["id"],
        )
        row = api_automation_repo.find_generation_run(db, run_id)
        if not row:
            raise api_error(500, "API_GENERATION_RUN_CREATE_FAILED", "接口自动化生成任务创建失败。")
        return _serialize_generation_run(row)


def execute_generation_run(run_id: str) -> dict:
    with connect() as db:
        run = api_automation_repo.find_generation_run(db, run_id)
        if not run:
            raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
        api_automation_repo.update_generation_run(db, run_id, status="running")
        endpoints = [
            _serialize_endpoint(endpoint)
            for endpoint_id in api_automation_repo.loads_json(run["endpoint_ids_json"], [])
            if (endpoint := api_automation_repo.find_endpoint(db, endpoint_id)) is not None
        ]
        environment_summary = {}
        if run["api_environment_id"]:
            environment = api_automation_repo.find_api_environment(db, run["api_environment_id"])
            if environment:
                environment_summary = _serialize_api_environment(environment)

    try:
        result = api_generation_agent_service.generate_api_test_cases(
            ApiAutomationGenerationInput(
                project_id=run["project_id"],
                endpoints=endpoints,
                environment_summary=environment_summary,
                source_test_cases=[],
                generation_goal=run["generation_goal"],
                include_security_cases=bool(
                    api_automation_repo.loads_json(run["options_json"], {}).get("include_security_cases")
                ),
            )
        )
    except Exception as exc:
        with connect() as db:
            api_automation_repo.update_generation_run(
                db,
                run_id,
                status="failed",
                error_message=str(exc),
                finished=True,
            )
            failed = api_automation_repo.find_generation_run(db, run_id)
        return _serialize_generation_run(failed)

    ready_count = 0
    needs_input_count = 0
    with connect() as db:
        for generated_case in result.cases:
            status = generated_case.status
            if status == "ready":
                ready_count += 1
            if status == "needs_input":
                needs_input_count += 1
            api_automation_repo.create_api_test_case(
                db,
                case_id=f"apitc-{secrets.token_hex(8)}",
                project_id=run["project_id"],
                endpoint_id=generated_case.endpoint_id,
                source_test_case_id=None,
                generation_run_id=run_id,
                title=generated_case.title,
                priority=generated_case.priority,
                source=generated_case.source,
                status=status,
                tags=[],
                request=generated_case.request,
                expected=generated_case.expected,
                assertions=[
                    assertion.model_dump() if hasattr(assertion, "model_dump") else assertion
                    for assertion in generated_case.assertions
                ],
                variables=generated_case.variables,
                data_origin=generated_case.data_origin,
                data_file_path="",
                notes=generated_case.notes,
                created_by="system",
            )
        summary = {
            "summary": result.summary,
            "test_case_count": len(result.cases),
            "ready_count": ready_count,
            "needs_input_count": needs_input_count,
            "script_count": 0,
        }
        api_automation_repo.update_generation_run(
            db,
            run_id,
            status="completed",
            result_summary=summary,
            finished=True,
        )
        completed = api_automation_repo.find_generation_run(db, run_id)
        return _serialize_generation_run(completed)


def get_generation_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_generation_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
        result = _serialize_generation_run(row)
        result["test_cases"] = [_serialize_api_test_case(case) for case in api_automation_repo.list_api_test_cases(db, project_id)]
        return result


def generate_scripts_from_api_test_cases(project_id: str, api_test_case_ids: list[str], actor) -> dict:
    _require_admin(actor)
    if not api_test_case_ids:
        raise api_error(400, "API_TEST_CASE_REQUIRED", "请至少选择一条接口自动化用例。")
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        rows = []
        for case_id in api_test_case_ids:
            row = api_automation_repo.find_api_test_case(db, case_id)
            if not row or row["project_id"] != project_id:
                raise api_error(404, "API_TEST_CASE_NOT_FOUND", f"接口自动化用例不存在：{case_id}")
            if row["status"] != "ready":
                raise api_error(400, "API_TEST_CASE_NOT_READY", "只有 ready 状态的接口自动化用例可以生成脚本。")
            rows.append(row)
        cases = [_serialize_api_test_case(row) for row in rows]

    suite_id = f"apisuite-{secrets.token_hex(8)}"
    generated = generate_pytest_suite(
        project_id=project_id,
        suite_id=suite_id,
        cases=cases,
        output_root=storage.PROJECT_FILE_STORAGE_ROOT,
    )
    suite_path = storage.store_path(generated["suite_path"]) or str(generated["suite_path"])
    test_file_path = storage.store_path(generated["test_file_path"]) or str(generated["test_file_path"])
    data_file_path = storage.store_path(generated["data_file_path"]) or str(generated["data_file_path"])

    scripts = []
    with connect() as db:
        for row in rows:
            script_id = api_automation_repo.create_script(
                db,
                script_id=f"apiscript-{secrets.token_hex(8)}",
                project_id=project_id,
                endpoint_id=row["endpoint_id"],
                api_test_case_id=row["id"],
                test_case_id=row["source_test_case_id"],
                generation_run_id=row["generation_run_id"],
                name=generated["script_name"],
                status="ready",
                suite_path=suite_path,
                test_file_path=test_file_path,
                data_file_path=data_file_path,
                notes="",
                created_by=actor["id"],
            )
            script = api_automation_repo.find_script(db, script_id)
            scripts.append(_serialize_script(script))
    return {"suite_id": suite_id, "scripts": scripts}


def get_api_script(project_id: str, script_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_script(db, script_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
        script = _serialize_script(row)
    path = _resolve_generated_path(project_id, script["test_file_path"])
    script["content"] = path.read_text(encoding="utf-8")
    return script


def update_api_script(project_id: str, script_id: str, *, content: str, notes: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_script(db, script_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
        script = _serialize_script(row)
    path = _resolve_generated_path(project_id, script["test_file_path"])
    path.write_text(content, encoding="utf-8")
    with connect() as db:
        db.execute(
            """
            UPDATE api_test_scripts
            SET notes = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (notes, actor["id"], script_id),
        )
        updated = api_automation_repo.find_script(db, script_id)
        result = _serialize_script(updated)
    result["content"] = content
    return result


def create_api_run(project_id: str, payload: ApiRunCreateIn, actor) -> dict:
    _require_admin(actor)
    run_id = f"apirun-{secrets.token_hex(8)}"
    task_id = f"api_automation_run:{run_id}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        for script_id in payload.script_ids:
            script = api_automation_repo.find_script(db, script_id)
            if not script or script["project_id"] != project_id:
                raise api_error(404, "API_SCRIPT_NOT_FOUND", f"接口自动化脚本不存在：{script_id}")
        api_automation_repo.create_api_run(
            db,
            run_id=run_id,
            task_id=task_id,
            project_id=project_id,
            api_environment_id=payload.api_environment_id,
            script_ids=payload.script_ids,
            command_summary="uv run pytest tests --json-report",
            created_by=actor["id"],
        )
        row = api_automation_repo.find_api_run(db, run_id)
        return _serialize_api_run(row)


def execute_api_run(run_id: str) -> dict:
    with connect() as db:
        run = api_automation_repo.find_api_run(db, run_id)
        if not run:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        script_ids = api_automation_repo.loads_json(run["script_ids_json"], [])
        if not script_ids:
            raise api_error(400, "API_RUN_SCRIPT_REQUIRED", "运行记录缺少脚本。")
        script = api_automation_repo.find_script(db, script_ids[0])
        if not script:
            raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
        environment = _build_runtime_environment(db, run["api_environment_id"])
        api_automation_repo.update_api_run(db, run_id, status="running")

    suite_path = _resolve_generated_path(run["project_id"], script["suite_path"])
    run_dir = storage.PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "api_automation" / "runs" / run_id
    result = run_script_suite(
        run_id=run_id,
        project_id=run["project_id"],
        suite_path=suite_path,
        run_dir=run_dir,
        environment=environment,
        timeout=environment.get("timeout_seconds", 30),
    )
    with connect() as db:
        api_automation_repo.update_api_run(
            db,
            run_id,
            status=result["status"],
            stdout_path=storage.store_path(result["stdout_path"]) or result["stdout_path"],
            stderr_path=storage.store_path(result["stderr_path"]) or result["stderr_path"],
            json_report_path=storage.store_path(result["json_report_path"]) or result["json_report_path"],
            summary=result["summary"],
            error_message=result["error_message"],
            finished=True,
        )
        updated = api_automation_repo.find_api_run(db, run_id)
        return _serialize_api_run(updated)


def get_api_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_api_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        return _serialize_api_run(row)


def get_api_run_logs(project_id: str, run_id: str, actor) -> dict:
    run = get_api_run(project_id, run_id, actor)
    return {
        "stdout": _read_optional_text(run["stdout_path"]),
        "stderr": _read_optional_text(run["stderr_path"]),
    }


def get_api_run_report(project_id: str, run_id: str, actor) -> dict:
    run = get_api_run(project_id, run_id, actor)
    path = storage.resolve_stored_path(run["json_report_path"])
    if path is None or not path.exists():
        raise api_error(404, "API_RUN_REPORT_NOT_FOUND", "接口自动化 JSON 报告不存在。")
    return api_automation_repo.loads_json(path.read_text(encoding="utf-8"), {})


def create_api_scenario(project_id: str, payload: ApiScenarioIn, actor) -> dict:
    _require_admin(actor)
    scenario_id = f"apiscn-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        db.execute(
            """
            INSERT INTO api_scenarios (id, project_id, name, description, variables_json, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                project_id,
                payload.name,
                payload.description,
                api_automation_repo.dumps_json(payload.variables),
                actor["id"],
            ),
        )
        row = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        return _serialize_scenario(row, [])


def list_api_scenarios(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        rows = db.execute(
            "SELECT * FROM api_scenarios WHERE project_id = ? ORDER BY updated_at DESC, created_at DESC",
            (project_id,),
        ).fetchall()
        return [_serialize_scenario(row, []) for row in rows]


def get_api_scenario(project_id: str, scenario_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_SCENARIO_NOT_FOUND", "接口场景不存在。")
        steps = db.execute(
            "SELECT * FROM api_scenario_steps WHERE scenario_id = ? ORDER BY step_order ASC, created_at ASC",
            (scenario_id,),
        ).fetchall()
        return _serialize_scenario(row, [_serialize_scenario_step(step) for step in steps])


def create_api_scenario_step(project_id: str, scenario_id: str, payload: ApiScenarioStepIn, actor) -> dict:
    _require_admin(actor)
    step_id = f"apistep-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if not scenario or scenario["project_id"] != project_id:
            raise api_error(404, "API_SCENARIO_NOT_FOUND", "接口场景不存在。")
        if payload.endpoint_id:
            endpoint = api_automation_repo.find_endpoint(db, payload.endpoint_id)
            if not endpoint or endpoint["project_id"] != project_id:
                raise api_error(400, "API_ENDPOINT_INVALID", "接口不存在或不属于当前项目。")
        db.execute(
            """
            INSERT INTO api_scenario_steps (
              id, scenario_id, project_id, endpoint_id, step_order, name,
              request_overrides_json, extractors_json, assertions_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                step_id,
                scenario_id,
                project_id,
                payload.endpoint_id,
                payload.step_order,
                payload.name,
                api_automation_repo.dumps_json(payload.request_overrides),
                api_automation_repo.dumps_json(payload.extractors),
                api_automation_repo.dumps_json(payload.assertions),
            ),
        )
        row = db.execute("SELECT * FROM api_scenario_steps WHERE id = ?", (step_id,)).fetchone()
        return _serialize_scenario_step(row)


def recover_interrupted_api_automation_tasks() -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE api_generation_runs
            SET status = 'interrupted',
                error_message = '服务已重启，接口自动化生成任务已中断，请重新发起。',
                updated_at = CURRENT_TIMESTAMP,
                finished_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
            """
        )
        db.execute(
            """
            UPDATE api_automation_runs
            SET status = 'interrupted',
                error_message = '服务已重启，接口自动化执行任务已中断，请重新执行。',
                updated_at = CURRENT_TIMESTAMP,
                finished_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
            """
        )


def _store_openapi_document(project_id: str, document_id: str, raw_content: str, source_type: str) -> str:
    suffix = "json" if source_type == "url" or raw_content.lstrip().startswith("{") else "yaml"
    document_dir = storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "documents" / document_id
    document_dir.mkdir(parents=True, exist_ok=True)
    path = document_dir / f"openapi.{suffix}"
    path.write_text(raw_content, encoding="utf-8")
    return storage.store_path(path) or str(path)


def _serialize_document(row: Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "source_type": row["source_type"],
        "source_url": row["source_url"],
        "file_path": row["file_path"],
        "version": row["version"],
        "status": row["status"],
        "endpoint_count": row["endpoint_count"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
    }


def _serialize_endpoint(row: Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "document_id": row["document_id"],
        "method": row["method"],
        "path": row["path"],
        "normalized_path": row["normalized_path"],
        "summary": row["summary"],
        "description": row["description"],
        "tags": api_automation_repo.loads_json(row["tags_json"], []),
        "parameters": api_automation_repo.loads_json(row["parameters_json"], []),
        "request_body": api_automation_repo.loads_json(row["request_body_json"], {}),
        "responses": api_automation_repo.loads_json(row["responses_json"], {}),
        "auth": api_automation_repo.loads_json(row["auth_json"], {}),
        "source": api_automation_repo.loads_json(row["source_json"], {}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_api_environment(row: Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "api_base_url": row["api_base_url"],
        "username": row["username"],
        "auth_type": row["auth_type"],
        "auth_config": _mask_auth_config(api_automation_repo.loads_json(row["auth_config_json"], {})),
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
        "default_headers": api_automation_repo.loads_json(row["default_headers_json"], {}),
        "timeout_seconds": row["timeout_seconds"],
        "verify_ssl": bool(row["verify_ssl"]),
        "auth_state_ttl_seconds": row["auth_state_ttl_seconds"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_generation_run(row: Row | None) -> dict:
    if row is None:
        raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "api_environment_id": row["api_environment_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "endpoint_ids": api_automation_repo.loads_json(row["endpoint_ids_json"], []),
        "source_test_case_ids": api_automation_repo.loads_json(row["source_test_case_ids_json"], []),
        "generation_goal": row["generation_goal"],
        "options": api_automation_repo.loads_json(row["options_json"], {}),
        "result_summary": api_automation_repo.loads_json(row["result_summary_json"], {}),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _serialize_api_test_case(row: Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "endpoint_id": row["endpoint_id"],
        "title": row["title"],
        "priority": row["priority"],
        "source": row["source"],
        "status": row["status"],
        "tags": api_automation_repo.loads_json(row["tags_json"], []),
        "request": api_automation_repo.loads_json(row["request_json"], {}),
        "expected": api_automation_repo.loads_json(row["expected_json"], {}),
        "assertions": api_automation_repo.loads_json(row["assertions_json"], []),
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_script(row: Row | None) -> dict:
    if row is None:
        raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "endpoint_id": row["endpoint_id"],
        "api_test_case_id": row["api_test_case_id"],
        "test_case_id": row["test_case_id"],
        "generation_run_id": row["generation_run_id"],
        "name": row["name"],
        "status": row["status"],
        "suite_path": row["suite_path"],
        "test_file_path": row["test_file_path"],
        "data_file_path": row["data_file_path"],
        "language": row["language"],
        "framework": row["framework"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_api_run(row: Row | None) -> dict:
    if row is None:
        raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "api_environment_id": row["api_environment_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "script_ids": api_automation_repo.loads_json(row["script_ids_json"], []),
        "command_summary": row["command_summary"],
        "stdout_path": row["stdout_path"],
        "stderr_path": row["stderr_path"],
        "json_report_path": row["json_report_path"],
        "summary": api_automation_repo.loads_json(row["summary_json"], {}),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _serialize_scenario(row: Row, steps: list[dict]) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
        "steps": steps,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_scenario_step(row: Row) -> dict:
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "project_id": row["project_id"],
        "endpoint_id": row["endpoint_id"],
        "step_order": row["step_order"],
        "name": row["name"],
        "request_overrides": api_automation_repo.loads_json(row["request_overrides_json"], {}),
        "extractors": api_automation_repo.loads_json(row["extractors_json"], []),
        "assertions": api_automation_repo.loads_json(row["assertions_json"], []),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _resolve_generated_path(project_id: str, stored_path: str) -> Path:
    path = storage.resolve_stored_path(stored_path)
    if path is None:
        raise api_error(404, "API_SCRIPT_FILE_NOT_FOUND", "脚本文件不存在。")
    resolved = path.resolve()
    allowed_root = (storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "generated").resolve()
    if allowed_root not in resolved.parents and resolved != allowed_root:
        raise api_error(400, "API_SCRIPT_PATH_INVALID", "脚本路径不在允许的接口自动化目录下。")
    if not resolved.exists():
        raise api_error(404, "API_SCRIPT_FILE_NOT_FOUND", "脚本文件不存在。")
    return resolved


def _build_runtime_environment(db, api_environment_id: str | None) -> dict:
    if not api_environment_id:
        return {"api_base_url": "", "timeout_seconds": 30, "auth": {}, "headers": {}, "variables": {}}
    row = api_automation_repo.find_api_environment(db, api_environment_id)
    if not row:
        raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
    auth_config = api_automation_repo.loads_json(row["auth_config_json"], {})
    auth = {}
    if row["auth_type"] == "static_bearer" and auth_config.get("token_encrypted"):
        auth["bearer"] = decrypt_api_environment_secret(auth_config["token_encrypted"]) or ""
    return {
        "api_base_url": row["api_base_url"],
        "timeout_seconds": row["timeout_seconds"],
        "auth": auth,
        "headers": api_automation_repo.loads_json(row["default_headers_json"], {}),
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
    }


def _read_optional_text(stored_path: str) -> str:
    path = storage.resolve_stored_path(stored_path)
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _validate_auth_config(auth_type: str, auth_config: dict) -> None:
    if auth_type == "none":
        return
    if auth_type == "static_bearer" and not (auth_config.get("token") or auth_config.get("token_encrypted")):
        raise api_error(400, "API_AUTH_TOKEN_REQUIRED", "Bearer 鉴权必须填写 token。")
    if auth_type == "cookie" and not (auth_config.get("cookie_name") and (auth_config.get("cookie_value") or auth_config.get("cookie_value_encrypted"))):
        raise api_error(400, "API_AUTH_COOKIE_REQUIRED", "Cookie 鉴权必须填写 cookie 名称和值。")
    if auth_type == "static_headers" and not auth_config.get("headers"):
        raise api_error(400, "API_AUTH_HEADERS_REQUIRED", "静态 Header 鉴权必须填写 headers。")
    if auth_type == "login_request":
        required = ["method", "path", "extract", "inject"]
        missing = [key for key in required if not auth_config.get(key)]
        if missing:
            raise api_error(400, "API_AUTH_LOGIN_CONFIG_REQUIRED", f"登录鉴权缺少配置：{', '.join(missing)}。")


def _prepare_auth_config_for_storage(auth_type: str, auth_config: dict) -> dict:
    stored = dict(auth_config)
    if auth_type == "static_bearer" and stored.get("token"):
        stored["token_encrypted"] = encrypt_api_environment_secret(str(stored.pop("token")))
    if auth_type == "cookie" and stored.get("cookie_value"):
        stored["cookie_value_encrypted"] = encrypt_api_environment_secret(str(stored.pop("cookie_value")))
    if auth_type == "static_headers":
        headers = stored.get("headers")
        if isinstance(headers, dict):
            encrypted_headers = {}
            for key, value in headers.items():
                encrypted_headers[key] = encrypt_api_environment_secret(str(value))
            stored["headers_encrypted"] = encrypted_headers
            stored.pop("headers", None)
    return stored


def _mask_auth_config(auth_config: dict) -> dict:
    masked = dict(auth_config)
    if masked.pop("token_encrypted", ""):
        masked["token_saved"] = True
    if masked.pop("cookie_value_encrypted", ""):
        masked["cookie_value_saved"] = True
    if "headers_encrypted" in masked:
        masked["headers_saved"] = sorted(masked.pop("headers_encrypted").keys())
    return masked


def _require_visible_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return project
    if project["name"] == actor["project_scope"]:
        return project
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _require_admin(actor) -> None:
    if actor["role"] != "admin":
        raise api_error(403, "PERMISSION_DENIED", "仅管理员可维护接口自动化。")


def _require_endpoint_ids(db, project_id: str, endpoint_ids: list[str]) -> None:
    if not endpoint_ids:
        raise api_error(400, "API_ENDPOINT_REQUIRED", "请至少选择一个接口。")
    for endpoint_id in endpoint_ids:
        endpoint = api_automation_repo.find_endpoint(db, endpoint_id)
        if not endpoint or endpoint["project_id"] != project_id:
            raise api_error(400, "API_ENDPOINT_INVALID", f"接口不存在或不属于当前项目：{endpoint_id}")
