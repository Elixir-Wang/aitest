import asyncio
import hashlib
import json
import secrets
import shutil
import threading
import time
from pathlib import Path
from sqlite3 import Row
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from app.agents.api_automation.case_generation import service as api_generation_agent_service
from app.agents.api_automation.case_generation.schemas import ApiAutomationGenerationInput
from app.agents.api_automation.pytest_requests.schemas import PytestRequestsGenerationInput
from app.agents.api_automation.pytest_requests.service import generate_pytest_requests_code
from app.core.environment_credentials import decrypt_api_environment_secret, encrypt_api_environment_secret
from app.core.security import hash_secret
from app.core import storage
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, environment_repo, project_repo
from app.repositories import test_case_repo
from app.schemas.api_automation import (
    ApiAutomationGenerateIn,
    ApiEndpointDebugIn,
    ApiEndpointIn,
    ApiEndpointUpdateIn,
    ApiEnvironmentIn,
    ApiRunCreateIn,
    ApiScenarioIn,
    ApiScenarioStepIn,
    ApiScenarioStepsReplaceIn,
    ApiTestCaseSetIn,
)
from app.services.api_automation.openapi_parser import OpenAPIParseError, parse_openapi_document
from app.services.api_automation.runner import collect_script_suite, run_script_suite
from app.services.api_automation.artifact_storage import (
    materialize_scenario_snapshot,
    materialize_generation_result,
    project_workspace_lock,
    relative_file_key,
    restore_endpoint_artifacts,
    snapshot_endpoint_artifacts,
)


MAX_OPENAPI_BYTES = 2 * 1024 * 1024
MAX_DEBUG_RESPONSE_CHARS = 200_000
API_GENERATION_CONCURRENCY = 5
_api_generation_slots = threading.BoundedSemaphore(API_GENERATION_CONCURRENCY)


def import_openapi_url(project_id: str, *, url: str, actor, name: str = "") -> dict:
    _require_admin(actor)
    if not url:
        raise api_error(400, "OPENAPI_URL_REQUIRED", "请填写 OpenAPI/Swagger URL。")
    try:
        response = requests.get(url, timeout=15.0, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException as exc:
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


def debug_project_endpoint(project_id: str, endpoint_id: str, payload: ApiEndpointDebugIn, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint_row = api_automation_repo.find_endpoint(db, endpoint_id)
        if not endpoint_row or endpoint_row["project_id"] != project_id:
            raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        endpoint = _serialize_endpoint(endpoint_row)
        environment = _build_debug_environment(db, project_id, payload.api_environment_id)

    request = _build_debug_request(endpoint, environment, payload)
    started = time.perf_counter()
    try:
        response = requests.request(
            method=request["method"],
            url=request["url"],
            params=request["query_params"],
            headers=request["headers"],
            json=request["json_body"],
            data=request["raw_body"],
            timeout=environment["timeout_seconds"],
            verify=environment["verify_ssl"],
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return {
            "request": _public_debug_request(request),
            "status_code": 0,
            "elapsed_ms": elapsed_ms,
            "headers": {},
            "body_text": "",
            "body_json": None,
            "error_message": str(exc),
        }

    elapsed_ms = round(response.elapsed.total_seconds() * 1000)
    body_text = response.text
    if len(body_text) > MAX_DEBUG_RESPONSE_CHARS:
        body_text = f"{body_text[:MAX_DEBUG_RESPONSE_CHARS]}\n... 响应内容已截断"
    try:
        body_json = response.json()
    except ValueError:
        body_json = None
    return {
        "request": _public_debug_request(request),
        "status_code": response.status_code,
        "elapsed_ms": elapsed_ms,
        "headers": dict(response.headers),
        "body_text": body_text,
        "body_json": body_json,
        "error_message": "",
    }


def create_api_environment(project_id: str, payload: ApiEnvironmentIn, actor) -> dict:
    _require_admin(actor)
    _validate_account_password_config(payload)
    _validate_auth_config(payload.auth_type, payload.auth_config)
    auth_config = _prepare_auth_config_for_storage(payload.auth_type, payload.auth_config)
    password_encrypted = encrypt_api_environment_secret(payload.password)
    password_hash = hash_secret(payload.password) if payload.password else ""
    environment_id = f"apienv-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _validate_linked_ui_environment(db, project_id, payload.linked_ui_environment_id)
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
    explicitly_set_fields = payload.model_fields_set
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_api_environment(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        _validate_linked_ui_environment(db, project_id, payload.linked_ui_environment_id)
        _validate_account_password_config(payload, existing)
        auth_config = _merge_auth_config_for_update(existing, payload)
        _validate_auth_config(payload.auth_type, auth_config)
        auth_config = _prepare_auth_config_for_storage(payload.auth_type, auth_config)
        fields = {
            "linked_ui_environment_id": payload.linked_ui_environment_id,
            "name": payload.name,
            "api_base_url": payload.api_base_url,
            "username": payload.username,
            "auth_type": payload.auth_type,
            "auth_config": auth_config,
            "default_headers": payload.default_headers,
            "auth_state_ttl_seconds": payload.auth_state_ttl_seconds,
            "description": payload.description,
        }
        if "timeout_seconds" in explicitly_set_fields:
            fields["timeout_seconds"] = payload.timeout_seconds
        if "variables" in explicitly_set_fields:
            fields["variables"] = payload.variables
        if "verify_ssl" in explicitly_set_fields:
            fields["verify_ssl"] = payload.verify_ssl
        if payload.password:
            fields["password_encrypted"] = encrypt_api_environment_secret(payload.password)
            fields["password_hash"] = hash_secret(payload.password)
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
        api_automation_repo.create_generation_items(db, run_id, payload.endpoint_ids)
        row = api_automation_repo.find_generation_run(db, run_id)
        if not row:
            raise api_error(500, "API_GENERATION_RUN_CREATE_FAILED", "接口自动化生成任务创建失败。")
        return _serialize_generation_run(db, row)


def list_generation_runs(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [
            _serialize_generation_run(db, row, include_attempts=False)
            for row in api_automation_repo.list_generation_runs(db, project_id)
        ]


def list_api_test_cases(project_id: str, actor, *, endpoint_id: str = "") -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        if endpoint_id:
            endpoint = api_automation_repo.find_endpoint(db, endpoint_id)
            if not endpoint or endpoint["project_id"] != project_id:
                raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        rows = api_automation_repo.list_api_test_cases(db, project_id, endpoint_id=endpoint_id)
        return [_serialize_api_test_case(row) for row in rows]


def get_api_test_case(project_id: str, case_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_api_test_case(db, case_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_TEST_CASE_NOT_FOUND", "接口自动化用例不存在。")
        return _serialize_api_test_case(row)


def delete_api_test_case(project_id: str, case_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_api_test_case(db, case_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_TEST_CASE_NOT_FOUND", "接口自动化用例不存在。")
        api_automation_repo.delete_api_test_case(db, case_id)


def create_api_test_case_set(project_id: str, payload: ApiTestCaseSetIn, actor) -> dict:
    _require_admin(actor)
    set_id = f"apicaseset-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        api_automation_repo.create_api_test_case_set(
            db,
            set_id=set_id,
            project_id=project_id,
            name=payload.name,
            notes=payload.notes,
            created_by=actor["id"],
        )
        row = api_automation_repo.find_api_test_case_set(db, set_id)
        return _serialize_api_test_case_set(row)


def list_api_test_case_sets(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [_serialize_api_test_case_set(row) for row in api_automation_repo.list_api_test_case_sets(db, project_id)]


def update_api_test_case_set(project_id: str, set_id: str, payload: ApiTestCaseSetIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_api_test_case_set(db, set_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_TEST_CASE_SET_NOT_FOUND", "接口集不存在。")
        api_automation_repo.update_api_test_case_set(db, set_id, name=payload.name, notes=payload.notes)
        row = api_automation_repo.find_api_test_case_set(db, set_id)
        return _serialize_api_test_case_set(row)


def execute_generation_run(run_id: str) -> dict:
    with connect() as db:
        run = api_automation_repo.find_generation_run(db, run_id)
        if not run:
            raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
        api_automation_repo.update_generation_run(db, run_id, status="running")
        item_ids = [
            item["id"]
            for item in api_automation_repo.list_generation_items(db, run_id)
            if item["status"] == "queued"
        ]

    asyncio.run(_execute_generation_items(run_id, item_ids))

    with connect() as db:
        items = api_automation_repo.list_generation_items(db, run_id)
        success_count = sum(item["status"] == "completed" for item in items)
        failed_count = sum(item["status"] == "failed" for item in items)
        total_count = len(items)
        status = "completed" if success_count == total_count else "failed" if failed_count == total_count else "partial_success"
        summary = {
            "summary": f"成功 {success_count}，失败 {failed_count}，共 {total_count}",
            "total_count": total_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "test_case_count": sum(item["generated_case_count"] for item in items),
            "script_count": 0,
        }
        api_automation_repo.update_generation_run(
            db,
            run_id,
            status=status,
            result_summary=summary,
            error_message="\n".join(item["error_message"] for item in items if item["error_message"]),
            finished=True,
        )
        completed = api_automation_repo.find_generation_run(db, run_id)
        return _serialize_generation_run(db, completed)


async def _execute_generation_items(run_id: str, item_ids: list[str]) -> None:
    await asyncio.gather(*(_execute_generation_item(run_id, item_id) for item_id in item_ids))


async def _execute_generation_item(run_id: str, item_id: str) -> None:
    attempt_id = f"apiattempt-{secrets.token_hex(8)}"
    with connect() as db:
        api_automation_repo.start_generation_item_attempt(db, item_id, attempt_id)
        input_data = _build_generation_item_input(db, run_id, item_id)

    await asyncio.to_thread(_api_generation_slots.acquire)
    try:
        result = await api_generation_agent_service.generate_api_test_cases(input_data)
    except Exception as exc:
        with connect() as db:
            api_automation_repo.finish_generation_item_attempt(
                db,
                item_id,
                attempt_id,
                status="failed",
                error_message=_generation_error_message(exc),
            )
        return
    finally:
        _api_generation_slots.release()

    try:
        with connect() as db:
            generated_case_count = _persist_generation_item_cases(db, run_id, item_id, attempt_id, result)
            api_automation_repo.finish_generation_item_attempt(
                db,
                item_id,
                attempt_id,
                status="completed",
                generated_case_count=generated_case_count,
            )
    except Exception as exc:
        with connect() as db:
            api_automation_repo.finish_generation_item_attempt(
                db,
                item_id,
                attempt_id,
                status="failed",
                error_message=_generation_error_message(exc),
            )


def _build_generation_item_input(db, run_id: str, item_id: str) -> ApiAutomationGenerationInput:
    run = api_automation_repo.find_generation_run(db, run_id)
    item = api_automation_repo.find_generation_item(db, item_id)
    if not run or not item:
        raise ValueError("接口自动化生成子任务不存在。")
    endpoint = api_automation_repo.find_endpoint(db, item["endpoint_id"])
    if not endpoint:
        raise ValueError("接口自动化生成子任务关联接口不存在。")
    source_test_cases = [
        _serialize_source_test_case(test_case)
        for test_case_id in api_automation_repo.loads_json(run["source_test_case_ids_json"], [])
        if (test_case := test_case_repo.find_case_by_id(db, test_case_id)) is not None
    ]
    environment_summary = {}
    if run["api_environment_id"]:
        environment = api_automation_repo.find_api_environment(db, run["api_environment_id"])
        if environment:
            environment_summary = _serialize_api_environment(environment)
    return ApiAutomationGenerationInput(
        project_id=run["project_id"],
        endpoints=[_serialize_endpoint(endpoint)],
        environment_summary=environment_summary,
        source_test_cases=source_test_cases,
        generation_goal=run["generation_goal"],
        include_security_cases=bool(
            api_automation_repo.loads_json(run["options_json"], {}).get("include_security_cases")
        ),
    )


def _persist_generation_item_cases(db, run_id: str, item_id: str, attempt_id: str, result) -> int:
    item = api_automation_repo.find_generation_item(db, item_id)
    endpoint = api_automation_repo.find_endpoint(db, item["endpoint_id"]) if item else None
    if not item or not endpoint:
        raise ValueError("接口自动化生成子任务关联接口不存在。")
    for generated_case in result.cases:
        request_method = str(generated_case.request.get("method") or "").upper()
        request_path = str(generated_case.request.get("path") or "")
        if (
            generated_case.endpoint_id != endpoint["id"]
            or request_method != str(endpoint["method"]).upper()
            or request_path != endpoint["path"]
        ):
            raise ValueError("生成用例与接口定义不一致。")
    for generated_case in result.cases:
        api_automation_repo.create_api_test_case(
            db,
            case_id=f"apitc-{secrets.token_hex(8)}",
            project_id=endpoint["project_id"],
            endpoint_id=generated_case.endpoint_id,
            source_test_case_id=None,
            generation_run_id=run_id,
            generation_item_id=item_id,
            generation_attempt_id=attempt_id,
            title=generated_case.title,
            test_description=generated_case.test_description,
            priority=generated_case.priority,
            coverage=generated_case.coverage,
            source=generated_case.source,
            preconditions=[],
            request=generated_case.request,
            test_data=generated_case.test_data,
            expected={},
            assertions=[assertion.model_dump() for assertion in generated_case.assertions],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by="system",
        )
    return len(result.cases)


def _generation_error_message(exc: Exception) -> str:
    message = str(exc)
    return "模型输出超出长度限制" if "finish_reason" in message and "length" in message else message


def get_generation_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_generation_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
        result = _serialize_generation_run(db, row)
        result["test_cases"] = [
            _serialize_api_test_case(case)
            for case in api_automation_repo.list_api_test_cases(db, project_id)
            if case["generation_run_id"] == run_id
        ]
        return result


def retry_failed_generation_items(project_id: str, run_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_generation_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
        items = api_automation_repo.list_generation_items(db, run_id)
        if any(item["status"] in {"queued", "running"} for item in items):
            raise api_error(409, "API_GENERATION_RUN_ACTIVE", "接口自动化生成任务仍在执行。")
        if not any(item["status"] == "failed" for item in items):
            raise api_error(409, "API_GENERATION_RUN_NO_FAILURES", "没有可重试的失败接口。")
        api_automation_repo.reset_failed_generation_items(db, run_id)
        api_automation_repo.update_generation_run(db, run_id, status="running", error_message="", finished=False)
        return _serialize_generation_run(db, api_automation_repo.find_generation_run(db, run_id))


def generate_project_scripts(project_id: str, endpoint_ids: list[str], actor, *, force: bool = False) -> dict:
    _require_admin(actor)
    if not endpoint_ids:
        raise api_error(400, "API_ENDPOINT_REQUIRED", "请至少选择一个接口。")
    endpoint_ids = list(dict.fromkeys(endpoint_ids))
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_endpoint_ids(db, project_id, endpoint_ids)
        endpoint_rows = {endpoint_id: api_automation_repo.find_endpoint(db, endpoint_id) for endpoint_id in endpoint_ids}
        case_rows_by_endpoint = {
            endpoint_id: api_automation_repo.list_api_test_cases(db, project_id, endpoint_id=endpoint_id)
            for endpoint_id in endpoint_ids
        }
        missing_cases = [endpoint_id for endpoint_id, rows in case_rows_by_endpoint.items() if not rows]
        if missing_cases:
            raise api_error(409, "API_ENDPOINT_CASES_REQUIRED", f"所选接口尚未生成用例：{', '.join(missing_cases)}")
        existing_by_endpoint = {
            endpoint_id: api_automation_repo.find_script_by_endpoint(db, project_id, endpoint_id)
            for endpoint_id in endpoint_ids
        }

    cases_by_endpoint = {
        endpoint_id: [_serialize_api_test_case(row) for row in rows]
        for endpoint_id, rows in case_rows_by_endpoint.items()
    }
    source_hashes = {
        endpoint_id: _script_source_hash(_serialize_endpoint(endpoint_rows[endpoint_id]), cases_by_endpoint[endpoint_id])
        for endpoint_id in endpoint_ids
    }
    changed_endpoint_ids = [
        endpoint_id
        for endpoint_id in endpoint_ids
        if force
        or existing_by_endpoint[endpoint_id] is None
        or existing_by_endpoint[endpoint_id]["source_hash"] != source_hashes[endpoint_id]
    ]

    suite_id = f"{project_id}-pytest-requests"
    artifacts_by_endpoint = {}
    if changed_endpoint_ids:
        with project_workspace_lock(project_id):
            snapshots = []
            for endpoint_id in changed_endpoint_ids:
                endpoint = _serialize_endpoint(endpoint_rows[endpoint_id])
                generated = generate_pytest_requests_code(
                    PytestRequestsGenerationInput(
                        endpoint={
                            "id": endpoint_id,
                            "method": endpoint["method"],
                            "path": endpoint["path"],
                            "summary": endpoint["summary"],
                        },
                        cases=cases_by_endpoint[endpoint_id],
                    )
                )
                snapshots.append(snapshot_endpoint_artifacts(project_id, generated))
                artifacts_by_endpoint[endpoint_id] = materialize_generation_result(project_id, generated)
            generated_suite_path = artifacts_by_endpoint[changed_endpoint_ids[0]]["suite_path"]
            try:
                collection = collect_script_suite(suite_path=generated_suite_path, timeout=120)
            except Exception as exc:
                for snapshot in reversed(snapshots):
                    restore_endpoint_artifacts(snapshot)
                raise api_error(
                    422,
                    "API_SCRIPT_COLLECTION_FAILED",
                    f"生成的 pytest 项目无法收集：{str(exc)[:2000]}",
                ) from exc
            if not collection["ok"]:
                for snapshot in reversed(snapshots):
                    restore_endpoint_artifacts(snapshot)
                error_output = (collection["stderr"] or collection["stdout"] or "pytest 收集失败。").strip()
                raise api_error(
                    422,
                    "API_SCRIPT_COLLECTION_FAILED",
                    f"生成的 pytest 项目无法收集：{error_output[:2000]}",
                )
        suite_path = storage.store_path(generated_suite_path) or str(generated_suite_path)
    else:
        suite_path = str(existing_by_endpoint[endpoint_ids[0]]["suite_path"])

    scripts = []
    changes = {"created": 0, "updated": 0, "unchanged": 0}
    with connect() as db:
        for endpoint_id in endpoint_ids:
            existing = existing_by_endpoint[endpoint_id]
            if endpoint_id not in artifacts_by_endpoint:
                serialized = _serialize_script(existing)
                serialized["change"] = "unchanged"
                scripts.append(serialized)
                changes["unchanged"] += 1
                continue

            artifact = artifacts_by_endpoint[endpoint_id]
            case_row = case_rows_by_endpoint[endpoint_id][0]
            script_id, change = api_automation_repo.upsert_script(
                db,
                script_id=f"apiscript-{secrets.token_hex(8)}",
                project_id=project_id,
                endpoint_id=endpoint_id,
                api_test_case_id=case_row["id"],
                test_case_id=case_row["source_test_case_id"],
                generation_run_id=case_row["generation_run_id"],
                name=artifact["script_name"],
                status="ready",
                suite_path=suite_path,
                test_file_path=storage.store_path(artifact["test_file_path"]) or str(artifact["test_file_path"]),
                data_file_path=storage.store_path(artifact["data_file_path"]) or str(artifact["data_file_path"]),
                source_hash=source_hashes[endpoint_id],
                case_count=len(case_rows_by_endpoint[endpoint_id]),
                created_by=actor["id"],
            )
            serialized = _serialize_script(api_automation_repo.find_script(db, script_id))
            serialized["change"] = change
            scripts.append(serialized)
            changes[change] += 1
    return {"suite_id": suite_id, "suite_path": suite_path, "summary": changes, "scripts": scripts}


def list_project_scripts(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [_serialize_script(row) for row in api_automation_repo.list_scripts(db, project_id)]


def get_api_script_files(project_id: str, script_id: str, actor) -> dict:
    script = get_api_script(project_id, script_id, actor)
    suite_path = _resolve_generated_path(project_id, script["suite_path"])
    files = []
    for kind, stored_path in (("test", script["test_file_path"]), ("data", script["data_file_path"])):
        path = _resolve_generated_path(project_id, stored_path)
        path.resolve().relative_to(suite_path.resolve())
        files.append(
            {
                "key": relative_file_key(suite_path, path),
                "name": path.name,
                "kind": kind,
                "language": "python" if kind == "test" else "json",
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return {"script_id": script_id, "files": files}


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
            SET notes = ?, manual_modified = 1, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (notes, actor["id"], script_id),
        )
        updated = api_automation_repo.find_script(db, script_id)
        result = _serialize_script(updated)
    result["content"] = content
    return result


def delete_api_script(project_id: str, script_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_script(db, script_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
        script = _serialize_script(row)
        api_automation_repo.delete_script(db, script_id)

    suite_path = _resolve_generated_path(project_id, script["suite_path"]).resolve()
    deleted_parents = []
    for stored_path in (script["test_file_path"], script["data_file_path"]):
        if not stored_path:
            continue
        path = _resolve_generated_path(project_id, stored_path).resolve()
        path.relative_to(suite_path)
        deleted_parents.append(path.parent)
        if path.exists() and path.is_file():
            path.unlink()
    if len(deleted_parents) == 2 and deleted_parents[0] == deleted_parents[1]:
        endpoint_dir = deleted_parents[0]
        endpoints_root = (suite_path / "endpoints").resolve()
        if endpoint_dir.parent == endpoints_root and endpoint_dir.exists() and not any(endpoint_dir.iterdir()):
            endpoint_dir.rmdir()


def create_api_run(project_id: str, payload: ApiRunCreateIn, actor) -> dict:
    _require_admin(actor)
    run_id = f"apirun-{secrets.token_hex(8)}"
    task_id = f"api_automation_run:{run_id}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scripts = []
        for script_id in payload.script_ids:
            script = api_automation_repo.find_script(db, script_id)
            if not script or script["project_id"] != project_id:
                raise api_error(404, "API_SCRIPT_NOT_FOUND", f"接口自动化脚本不存在：{script_id}")
            scripts.append(script)
        environment = None
        if payload.api_environment_id:
            environment = api_automation_repo.find_api_environment(db, payload.api_environment_id)
            if not environment or environment["project_id"] != project_id:
                raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        script_snapshots = []
        for script in scripts:
            endpoint = api_automation_repo.find_endpoint(db, script["endpoint_id"]) if script["endpoint_id"] else None
            script_snapshots.append(
                {
                    "id": script["id"],
                    "endpoint_id": script["endpoint_id"],
                    "name": script["name"],
                    "case_count": script["case_count"],
                    "method": endpoint["method"] if endpoint else "",
                    "path": endpoint["path"] if endpoint else "",
                    "endpoint_summary": endpoint["summary"] if endpoint else "",
                }
            )
        execution_snapshot = {
            "environment": {
                "id": environment["id"],
                "name": environment["name"],
                "api_base_url": environment["api_base_url"],
            }
            if environment
            else None,
            "scripts": script_snapshots,
            "script_count": len(script_snapshots),
            "endpoint_count": len({item["endpoint_id"] for item in script_snapshots if item["endpoint_id"]}),
            "case_count": sum(int(item["case_count"] or 0) for item in script_snapshots),
            "created_by_name": actor.get("nickname") or actor.get("username") or actor["id"],
        }
        api_automation_repo.create_api_run(
            db,
            run_id=run_id,
            task_id=task_id,
            project_id=project_id,
            api_environment_id=payload.api_environment_id,
            script_ids=payload.script_ids,
            execution_snapshot=execution_snapshot,
            command_summary="uv run pytest tests --json-report",
            created_by=actor["id"],
        )
        row = api_automation_repo.find_api_run(db, run_id)
        return _serialize_api_run(row, db)


def list_api_runs(
    project_id: str,
    actor,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    environment_id: str = "",
    keyword: str = "",
) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        rows, total = api_automation_repo.list_api_runs(
            db,
            project_id,
            page=page,
            page_size=page_size,
            status=status,
            environment_id=environment_id,
            keyword=keyword.strip(),
        )
        return {
            "items": [_serialize_api_run(row, db) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


def execute_api_run(run_id: str) -> dict:
    with connect() as db:
        run = api_automation_repo.find_api_run(db, run_id)
        if not run:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        script_ids = api_automation_repo.loads_json(run["script_ids_json"], [])
        target_type = run["target_type"] if "target_type" in run.keys() else "scripts"
        if target_type == "scenario":
            snapshot = api_automation_repo.loads_json(run["execution_snapshot_json"], {})
            suite_path = _resolve_generated_path(run["project_id"], snapshot.get("suite_path", ""))
            test_path = _resolve_generated_path(run["project_id"], snapshot.get("test_file_path", ""))
            test_paths = [str(test_path.relative_to(suite_path))]
            environment = _build_runtime_environment(db, run["api_environment_id"])
            api_automation_repo.update_api_run(db, run_id, status="running")
        else:
            if not script_ids:
                raise api_error(400, "API_RUN_SCRIPT_REQUIRED", "运行记录缺少脚本。")
            scripts = [api_automation_repo.find_script(db, script_id) for script_id in script_ids]
            if any(script is None for script in scripts):
                raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
            script = scripts[0]
            environment = _build_runtime_environment(db, run["api_environment_id"])
            api_automation_repo.update_api_run(db, run_id, status="running")
            suite_path = _resolve_generated_path(run["project_id"], script["suite_path"])
            test_paths = []
            for selected_script in scripts:
                selected_suite_path = _resolve_generated_path(run["project_id"], selected_script["suite_path"])
                if selected_suite_path != suite_path:
                    raise api_error(400, "API_RUN_SUITE_MISMATCH", "所选脚本不属于同一测试项目。")
                test_path = _resolve_generated_path(run["project_id"], selected_script["test_file_path"])
                test_paths.append(str(test_path.relative_to(suite_path)))
    run_dir = storage.PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "api_automation" / "runs" / run_id
    result = run_script_suite(
        run_id=run_id,
        project_id=run["project_id"],
        suite_path=suite_path,
        run_dir=run_dir,
        environment=environment,
        timeout=environment.get("timeout_seconds", 30),
        test_paths=test_paths,
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
        api_automation_repo.update_scripts_last_run(db, script_ids, result["status"])
        updated = api_automation_repo.find_api_run(db, run_id)
        return _serialize_api_run(updated, db)


def create_api_scenario_run(project_id: str, scenario_id: str, api_environment_id: str, actor) -> dict:
    _require_admin(actor)
    run_id = f"apirun-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        if scenario["status"] != "ready":
            raise api_error(409, "API_SCENARIO_NOT_READY", "请先校验并发布场景。")
        environment = api_automation_repo.find_api_environment(db, api_environment_id)
        if not environment or environment["project_id"] != project_id:
            raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        snapshot = api_automation_repo.loads_json(scenario["published_snapshot_json"], {})
        serialized_snapshot = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        snapshot_hash = hashlib.sha256(serialized_snapshot.encode("utf-8")).hexdigest()
        if snapshot_hash != scenario["published_hash"]:
            raise api_error(409, "API_SCENARIO_SNAPSHOT_INVALID", "场景发布快照校验失败，请重新发布。")
    with project_workspace_lock(project_id):
        artifacts = materialize_scenario_snapshot(project_id, snapshot)
        relative_test_path = str(artifacts["test_file_path"].relative_to(artifacts["suite_path"]))
        try:
            collection = collect_script_suite(
                suite_path=artifacts["suite_path"],
                timeout=120,
                test_paths=[relative_test_path],
            )
        except Exception as exc:
            raise api_error(422, "API_SCENARIO_COLLECTION_FAILED", f"场景脚本无法收集：{str(exc)[:2000]}") from exc
        if not collection["ok"]:
            error_output = (collection["stderr"] or collection["stdout"] or "pytest 收集失败。").strip()
            raise api_error(422, "API_SCENARIO_COLLECTION_FAILED", f"场景脚本无法收集：{error_output[:2000]}")
    execution_snapshot = {
        "target_type": "scenario",
        "scenario": {
            "id": scenario_id,
            "name": snapshot.get("name", scenario["name"]),
            "revision": snapshot.get("revision", scenario["revision"]),
            "step_count": len(snapshot.get("steps", [])),
            "published_hash": scenario["published_hash"],
        },
        "environment": {
            "id": environment["id"],
            "name": environment["name"],
            "api_base_url": environment["api_base_url"],
        },
        "suite_path": storage.store_path(artifacts["suite_path"]) or str(artifacts["suite_path"]),
        "test_file_path": storage.store_path(artifacts["test_file_path"]) or str(artifacts["test_file_path"]),
        "data_file_path": storage.store_path(artifacts["data_file_path"]) or str(artifacts["data_file_path"]),
        "created_by_name": actor.get("nickname") or actor.get("username") or actor["id"],
    }
    with connect() as db:
        api_automation_repo.create_api_run(
            db,
            run_id=run_id,
            task_id=f"api_automation_run:{run_id}",
            project_id=project_id,
            api_environment_id=api_environment_id,
            script_ids=[],
            target_type="scenario",
            target_ids=[scenario_id],
            execution_snapshot=execution_snapshot,
            command_summary=f"uv run pytest {relative_test_path} --json-report",
            created_by=actor["id"],
        )
        return _serialize_api_run(api_automation_repo.find_api_run(db, run_id), db)


def get_api_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_api_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        return _serialize_api_run(row, db)


def delete_api_run(project_id: str, run_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_api_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        if row["status"] in {"queued", "running"}:
            raise api_error(409, "API_RUN_ACTIVE", "排队中或执行中的运行记录不能删除。")

        runs_root = (storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "runs").resolve()
        run_dir = (runs_root / run_id).resolve()
        run_dir.relative_to(runs_root)
        if run_dir.exists():
            shutil.rmtree(run_dir)
        api_automation_repo.delete_api_run(db, run_id)


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


def update_api_scenario(project_id: str, scenario_id: str, payload: ApiScenarioIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        db.execute(
            """
            UPDATE api_scenarios
            SET name = ?, description = ?, variables_json = ?, status = 'draft',
                updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.name, payload.description, api_automation_repo.dumps_json(payload.variables), actor["id"], scenario_id),
        )
        steps = _list_scenario_step_rows(db, scenario_id)
        return _serialize_scenario(db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone(), [_serialize_scenario_step(step) for step in steps])


def delete_api_scenario(project_id: str, scenario_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_scenario(db, project_id, scenario_id)
        db.execute("DELETE FROM api_scenarios WHERE id = ?", (scenario_id,))


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


def replace_api_scenario_steps(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioStepsReplaceIn,
    actor,
) -> dict:
    _require_admin(actor)
    step_ids = [step.id for step in payload.steps if step.id]
    if len(step_ids) != len(set(step_ids)):
        raise api_error(400, "API_SCENARIO_STEP_ID_DUPLICATE", "场景步骤 ID 不能重复。")
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_scenario(db, project_id, scenario_id)
        prepared = [_prepare_scenario_step(db, project_id, step, index) for index, step in enumerate(payload.steps)]
        db.execute("DELETE FROM api_scenario_steps WHERE scenario_id = ?", (scenario_id,))
        for step in prepared:
            _insert_scenario_step(db, scenario_id, project_id, step)
        db.execute(
            "UPDATE api_scenarios SET status = 'draft', updated_by = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (actor["id"], scenario_id),
        )
        scenario = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        rows = _list_scenario_step_rows(db, scenario_id)
        return _serialize_scenario(scenario, [_serialize_scenario_step(row) for row in rows])


def create_api_scenario_step(project_id: str, scenario_id: str, payload: ApiScenarioStepIn, actor) -> dict:
    _require_admin(actor)
    step_id = f"apistep-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        if not scenario or scenario["project_id"] != project_id:
            raise api_error(404, "API_SCENARIO_NOT_FOUND", "接口场景不存在。")
        prepared = _prepare_scenario_step(db, project_id, payload, payload.step_order, step_id=step_id)
        _insert_scenario_step(db, scenario_id, project_id, prepared)
        db.execute("UPDATE api_scenarios SET status = 'draft', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (scenario_id,))
        row = db.execute("SELECT * FROM api_scenario_steps WHERE id = ?", (step_id,)).fetchone()
        return _serialize_scenario_step(row)


def validate_api_scenario(project_id: str, scenario_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        steps = [_serialize_scenario_step(row) for row in _list_scenario_step_rows(db, scenario_id)]
        return _validate_scenario_definition(db, scenario, steps)


def publish_api_scenario(project_id: str, scenario_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        steps = [_serialize_scenario_step(row) for row in _list_scenario_step_rows(db, scenario_id)]
        validation = _validate_scenario_definition(db, scenario, steps)
        if not validation["valid"]:
            raise api_error(409, "API_SCENARIO_INVALID", "；".join(validation["errors"]))
        snapshot = _build_scenario_snapshot(db, scenario, steps)
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        published_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        db.execute(
            """
            UPDATE api_scenarios
            SET status = 'ready', revision = revision + 1, published_snapshot_json = ?,
                published_hash = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (serialized, published_hash, actor["id"], scenario_id),
        )
        updated = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        return _serialize_scenario(updated, steps)


def recover_interrupted_api_automation_tasks() -> None:
    with connect() as db:
        active_runs = db.execute(
            "SELECT * FROM api_generation_runs WHERE status IN ('queued', 'running')"
        ).fetchall()
        recovery_error = "服务已重启，未完成接口生成已终止，失败接口可重试。"
        db.execute(
            """
            UPDATE api_generation_item_attempts
            SET status = 'failed', error_message = ?, finished_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
            """,
            (recovery_error,),
        )
        db.execute(
            """
            UPDATE api_generation_items
            SET status = 'failed', error_message = ?, finished_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
            """,
            (recovery_error,),
        )
        for run in active_runs:
            items = api_automation_repo.list_generation_items(db, run["id"])
            if not items:
                api_automation_repo.update_generation_run(
                    db, run["id"], status="interrupted", error_message=recovery_error, finished=True
                )
                continue
            counts = _generation_run_counts(items)
            status = "partial_success" if counts["success_count"] else "failed"
            api_automation_repo.update_generation_run(
                db,
                run["id"],
                status=status,
                result_summary={"summary": recovery_error, **counts},
                error_message=recovery_error,
                finished=True,
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


def _generation_run_counts(items: list[Row]) -> dict:
    return {
        "total_count": len(items),
        "completed_count": sum(item["status"] in {"completed", "failed"} for item in items),
        "success_count": sum(item["status"] == "completed" for item in items),
        "failed_count": sum(item["status"] == "failed" for item in items),
        "generated_case_count": sum(item["generated_case_count"] for item in items),
    }


def _serialize_generation_item(db, row: Row, *, include_attempts: bool = True) -> dict:
    attempts = api_automation_repo.list_generation_item_attempts(db, row["id"]) if include_attempts else []
    return {
        "id": row["id"],
        "endpoint_id": row["endpoint_id"],
        "method": row["method"],
        "path": row["path"],
        "status": row["status"],
        "attempt_count": row["attempt_count"],
        "generated_case_count": row["generated_case_count"],
        "error_message": row["error_message"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "attempts": [
            {
                "id": attempt["id"],
                "attempt_no": attempt["attempt_no"],
                "status": attempt["status"],
                "generated_case_count": attempt["generated_case_count"],
                "error_message": attempt["error_message"],
                "started_at": attempt["started_at"],
                "finished_at": attempt["finished_at"],
            }
            for attempt in attempts
        ],
    }


def _serialize_generation_run(db, row: Row | None, *, include_attempts: bool = True) -> dict:
    if row is None:
        raise api_error(404, "API_GENERATION_RUN_NOT_FOUND", "接口自动化生成任务不存在。")
    items = api_automation_repo.list_generation_items(db, row["id"])
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
        **_generation_run_counts(items),
        "items": [_serialize_generation_item(db, item, include_attempts=include_attempts) for item in items],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _serialize_api_test_case_set(row: Row | None) -> dict:
    if row is None:
        raise api_error(404, "API_TEST_CASE_SET_NOT_FOUND", "接口用例集不存在。")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "notes": row["notes"],
        "status": row["status"],
        "endpoint_count": row["endpoint_count"],
        "case_count": row["case_count"],
        "latest_generation_run_id": row["latest_generation_run_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_api_test_case(row: Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "endpoint_id": row["endpoint_id"],
        "title": row["title"],
        "test_description": row["test_description"],
        "priority": row["priority"],
        "coverage": row["coverage"],
        "preconditions": api_automation_repo.loads_json(row["preconditions_json"], []),
        "request": api_automation_repo.loads_json(row["request_json"], {}),
        "test_data": api_automation_repo.loads_json(row["test_data_json"], {}),
        "assertions": api_automation_repo.loads_json(row["assertions_json"], []),
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_source_test_case(row: Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "module": row["module"],
        "priority": row["priority"],
        "preconditions": row["preconditions"],
        "steps": api_automation_repo.loads_json(row["steps_json"], []),
        "expected_result": row["expected_result"],
        "status": row["status"],
        "review_feedback": row["review_feedback"],
    }


def _serialize_script(row: Row | None) -> dict:
    if row is None:
        raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
    keys = set(row.keys())
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
        "source_hash": row["source_hash"] if "source_hash" in keys else "",
        "case_count": row["case_count"] if "case_count" in keys else 0,
        "manual_modified": bool(row["manual_modified"]) if "manual_modified" in keys else False,
        "last_run_status": row["last_run_status"] if "last_run_status" in keys else "",
        "last_run_at": row["last_run_at"] if "last_run_at" in keys else None,
        "method": row["method"] if "method" in keys and row["method"] else "",
        "path": row["path"] if "path" in keys and row["path"] else "",
        "endpoint_summary": row["endpoint_summary"] if "endpoint_summary" in keys and row["endpoint_summary"] else "",
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _script_source_hash(endpoint: dict, cases: list[dict]) -> str:
    payload = {"generator_version": 1, "endpoint": endpoint, "cases": cases}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _serialize_api_run(row: Row | None, db=None) -> dict:
    if row is None:
        raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
    keys = set(row.keys())
    snapshot = api_automation_repo.loads_json(
        row["execution_snapshot_json"] if "execution_snapshot_json" in keys else "{}", {}
    )
    script_ids = api_automation_repo.loads_json(row["script_ids_json"], [])
    if db is not None and not snapshot.get("environment") and row["api_environment_id"]:
        environment = api_automation_repo.find_api_environment(db, row["api_environment_id"])
        if environment:
            snapshot["environment"] = {
                "id": environment["id"],
                "name": environment["name"],
                "api_base_url": environment["api_base_url"],
            }
    if db is not None and not snapshot.get("scripts"):
        script_snapshots = []
        for script_id in script_ids:
            script = api_automation_repo.find_script(db, script_id)
            if not script:
                continue
            endpoint = api_automation_repo.find_endpoint(db, script["endpoint_id"]) if script["endpoint_id"] else None
            script_snapshots.append(
                {
                    "id": script["id"],
                    "endpoint_id": script["endpoint_id"],
                    "name": script["name"],
                    "case_count": script["case_count"],
                    "method": endpoint["method"] if endpoint else "",
                    "path": endpoint["path"] if endpoint else "",
                    "endpoint_summary": endpoint["summary"] if endpoint else "",
                }
            )
        snapshot["scripts"] = script_snapshots
    scripts = snapshot.get("scripts", [])
    snapshot.setdefault("script_count", len(scripts) or len(script_ids))
    endpoint_count = len({item.get("endpoint_id") for item in scripts if item.get("endpoint_id")})
    snapshot.setdefault("endpoint_count", endpoint_count or len(scripts) or len(script_ids))
    snapshot.setdefault("case_count", sum(int(item.get("case_count") or 0) for item in scripts))
    created_by_name = snapshot.get("created_by_name", "")
    if not created_by_name and "created_by_nickname" in keys:
        created_by_name = row["created_by_nickname"] or row["created_by_username"] or row["created_by"]
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "api_environment_id": row["api_environment_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "script_ids": script_ids,
        "target_type": row["target_type"] if "target_type" in keys else "scripts",
        "target_ids": api_automation_repo.loads_json(row["target_ids_json"], []) if "target_ids_json" in keys else [],
        "execution_snapshot": snapshot,
        "command_summary": row["command_summary"],
        "stdout_path": row["stdout_path"],
        "stderr_path": row["stderr_path"],
        "json_report_path": row["json_report_path"],
        "summary": api_automation_repo.loads_json(row["summary_json"], {}),
        "error_message": row["error_message"],
        "created_by_name": created_by_name or row["created_by"],
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
        "revision": row["revision"],
        "published_hash": row["published_hash"],
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
        "api_test_case_id": row["api_test_case_id"],
        "step_order": row["step_order"],
        "name": row["name"],
        "request_overrides": api_automation_repo.loads_json(row["request_overrides_json"], {}),
        "bindings": api_automation_repo.loads_json(row["bindings_json"], []),
        "extractors": api_automation_repo.loads_json(row["extractors_json"], []),
        "assertions": api_automation_repo.loads_json(row["assertions_json"], []),
        "on_failure": row["on_failure"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _require_scenario(db, project_id: str, scenario_id: str) -> Row:
    row = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
    if not row or row["project_id"] != project_id:
        raise api_error(404, "API_SCENARIO_NOT_FOUND", "接口场景不存在。")
    return row


def _list_scenario_step_rows(db, scenario_id: str) -> list[Row]:
    return db.execute(
        "SELECT * FROM api_scenario_steps WHERE scenario_id = ? ORDER BY step_order ASC, created_at ASC",
        (scenario_id,),
    ).fetchall()


def _prepare_scenario_step(db, project_id: str, payload: ApiScenarioStepIn, step_order: int, *, step_id: str = "") -> dict:
    case = None
    endpoint_id = payload.endpoint_id
    if payload.api_test_case_id:
        case = api_automation_repo.find_api_test_case(db, payload.api_test_case_id)
        if not case or case["project_id"] != project_id:
            raise api_error(400, "API_TEST_CASE_INVALID", "接口用例不存在或不属于当前项目。")
        endpoint_id = str(case["endpoint_id"] or "") or endpoint_id
    if endpoint_id:
        endpoint = api_automation_repo.find_endpoint(db, endpoint_id)
        if not endpoint or endpoint["project_id"] != project_id:
            raise api_error(400, "API_ENDPOINT_INVALID", "接口不存在或不属于当前项目。")
    return {
        "id": step_id or payload.id or f"apistep-{secrets.token_hex(8)}",
        "api_test_case_id": payload.api_test_case_id,
        "endpoint_id": endpoint_id,
        "step_order": step_order,
        "name": payload.name or (str(case["title"]) if case else ""),
        "request_overrides": payload.request_overrides,
        "bindings": payload.bindings,
        "extractors": payload.extractors,
        "assertions": payload.assertions,
        "on_failure": payload.on_failure,
        "enabled": payload.enabled,
    }


def _insert_scenario_step(db, scenario_id: str, project_id: str, step: dict) -> None:
    db.execute(
        """
        INSERT INTO api_scenario_steps (
          id, scenario_id, project_id, endpoint_id, api_test_case_id, step_order, name,
          request_overrides_json, bindings_json, extractors_json, assertions_json, on_failure, enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            step["id"], scenario_id, project_id, step["endpoint_id"], step["api_test_case_id"],
            step["step_order"], step["name"], api_automation_repo.dumps_json(step["request_overrides"]),
            api_automation_repo.dumps_json(step["bindings"]), api_automation_repo.dumps_json(step["extractors"]),
            api_automation_repo.dumps_json(step["assertions"]), step["on_failure"], int(step["enabled"]),
        ),
    )


def _validate_scenario_definition(db, scenario: Row, steps: list[dict]) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    enabled_steps = [step for step in steps if step["enabled"]]
    if not enabled_steps:
        errors.append("场景至少需要一个启用步骤。")
    prior_outputs: dict[str, set[str]] = {}
    known_ids = {step["id"] for step in enabled_steps}
    for index, step in enumerate(enabled_steps, start=1):
        prefix = f"步骤 {index}（{step['name'] or step['id']}）"
        case_id = step.get("api_test_case_id")
        case = api_automation_repo.find_api_test_case(db, case_id) if case_id else None
        if not case or case["project_id"] != scenario["project_id"]:
            errors.append(f"{prefix}必须选择当前项目的接口用例。")
        extractor_names: set[str] = set()
        for extractor in step["extractors"]:
            name = str(extractor.get("name") or "").strip()
            if not name:
                errors.append(f"{prefix}存在未命名的变量提取器。")
            elif name in extractor_names:
                errors.append(f"{prefix}重复提取变量 {name}。")
            else:
                extractor_names.add(name)
        for binding in step["bindings"]:
            target = str(binding.get("target") or "")
            source = binding.get("source") if isinstance(binding.get("source"), dict) else {}
            source_type = source.get("type")
            if not target.startswith(("/request/", "/test_data/")):
                errors.append(f"{prefix}的绑定目标必须位于 /request 或 /test_data。")
            if source_type == "step_output":
                source_step_id = str(source.get("step_id") or "")
                variable = str(source.get("variable") or "")
                if source_step_id not in prior_outputs:
                    suffix = "只能引用前序步骤。" if source_step_id in known_ids else "引用的步骤不存在。"
                    errors.append(f"{prefix}的变量绑定{suffix}")
                elif variable not in prior_outputs[source_step_id]:
                    errors.append(f"{prefix}引用了前序步骤未提取的变量 {variable}。")
            elif source_type not in {"environment", "scenario", "literal"}:
                errors.append(f"{prefix}存在不支持的变量来源 {source_type or '空'}。")
        prior_outputs[step["id"]] = extractor_names
        if not step["assertions"] and case and not api_automation_repo.loads_json(case["assertions_json"], []):
            warnings.append(f"{prefix}没有断言。")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _build_scenario_snapshot(db, scenario: Row, steps: list[dict]) -> dict:
    snapshot_steps = []
    for step in steps:
        if not step["enabled"]:
            continue
        case = api_automation_repo.find_api_test_case(db, step["api_test_case_id"])
        if not case:
            continue
        snapshot_steps.append(
            {
                **step,
                "case": {
                    "id": case["id"],
                    "title": case["title"],
                    "request": api_automation_repo.loads_json(case["request_json"], {}),
                    "test_data": api_automation_repo.loads_json(case["test_data_json"], {}),
                    "assertions": api_automation_repo.loads_json(case["assertions_json"], []),
                },
            }
        )
    return {
        "id": scenario["id"],
        "project_id": scenario["project_id"],
        "name": scenario["name"],
        "description": scenario["description"],
        "variables": api_automation_repo.loads_json(scenario["variables_json"], {}),
        "revision": int(scenario["revision"]) + 1,
        "steps": snapshot_steps,
    }


def _resolve_generated_path(project_id: str, stored_path: str) -> Path:
    path = storage.resolve_stored_path(stored_path)
    if path is None:
        raise api_error(404, "API_SCRIPT_FILE_NOT_FOUND", "脚本文件不存在。")
    resolved = path.resolve()
    allowed_root = (storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation").resolve()
    if allowed_root not in resolved.parents and resolved != allowed_root:
        raise api_error(400, "API_SCRIPT_PATH_INVALID", "脚本路径不在允许的接口自动化目录下。")
    if not resolved.exists():
        raise api_error(404, "API_SCRIPT_FILE_NOT_FOUND", "脚本文件不存在。")
    return resolved


def _build_debug_environment(db, project_id: str, api_environment_id: str | None) -> dict:
    if not api_environment_id:
        return {
            "api_base_url": "",
            "timeout_seconds": 30,
            "verify_ssl": True,
            "headers": {},
        }
    row = api_automation_repo.find_api_environment(db, api_environment_id)
    if not row or row["project_id"] != project_id:
        raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
    auth_config = api_automation_repo.loads_json(row["auth_config_json"], {})
    headers = _stringify_mapping(api_automation_repo.loads_json(row["default_headers_json"], {}))
    if row["auth_type"] == "static_bearer" and auth_config.get("token_encrypted"):
        token = decrypt_api_environment_secret(auth_config["token_encrypted"]) or ""
        if token:
            headers.setdefault("Authorization", f"Bearer {token}")
    if row["auth_type"] == "static_headers":
        for key, encrypted_value in api_automation_repo.loads_json(row["auth_config_json"], {}).get("headers_encrypted", {}).items():
            headers[str(key)] = decrypt_api_environment_secret(str(encrypted_value)) or ""
    if row["auth_type"] == "cybertron_agent":
        _apply_cybertron_headers(headers, auth_config)
    return {
        "api_base_url": row["api_base_url"],
        "timeout_seconds": row["timeout_seconds"],
        "verify_ssl": bool(row["verify_ssl"]),
        "headers": headers,
    }


def _build_debug_request(endpoint: dict, environment: dict, payload: ApiEndpointDebugIn) -> dict:
    url = _build_debug_url(environment["api_base_url"], endpoint["path"], payload.path_params)
    headers = {**environment["headers"], **_stringify_mapping(payload.headers)}
    query_params = _clean_mapping(payload.query_params)
    body = payload.body
    json_body = None
    raw_body = None
    if isinstance(body, (dict, list)):
        json_body = body
        content_type = _request_body_content_type(endpoint.get("request_body", {}))
        if content_type:
            _setdefault_header_case_insensitive(headers, "Content-Type", content_type)
    elif body is not None and str(body) != "":
        raw_body = str(body)
    return {
        "method": endpoint["method"].upper(),
        "url": url,
        "query_params": query_params,
        "headers": headers,
        "json_body": json_body,
        "raw_body": raw_body,
    }


def _build_debug_url(base_url: str, endpoint_path: str, path_params: dict[str, object]) -> str:
    path = endpoint_path
    for key, value in path_params.items():
        path = path.replace(f"{{{key}}}", str(value)).replace(f":{key}", str(value))
    if not path.startswith(("http://", "https://")):
        if not base_url:
            raise api_error(400, "API_DEBUG_BASE_URL_REQUIRED", "请先选择带 API Base URL 的接口环境。")
        path = urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))
    parsed = urlparse(path)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise api_error(400, "API_DEBUG_URL_INVALID", "调试地址必须是有效的 HTTP/HTTPS URL。")
    return path


def _public_debug_request(request: dict) -> dict:
    return {
        "method": request["method"],
        "url": request["url"],
        "query_params": request["query_params"],
        "headers": _mask_debug_headers(request["headers"]),
        "body": request["json_body"] if request["json_body"] is not None else request["raw_body"],
    }


def _mask_debug_headers(headers: dict[str, str]) -> dict[str, str]:
    sensitive_names = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "cybertron-robot-key",
        "cybertron-robot-token",
    }
    return {
        key: ("******" if key.lower() in sensitive_names else value)
        for key, value in headers.items()
    }


def _stringify_mapping(value: dict[str, object]) -> dict[str, str]:
    return {str(key): str(item) for key, item in value.items() if str(key).strip() and item is not None}


def _clean_mapping(value: dict[str, object]) -> dict[str, object]:
    return {str(key): item for key, item in value.items() if str(key).strip() and item not in (None, "")}


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
    headers = _stringify_mapping(api_automation_repo.loads_json(row["default_headers_json"], {}))
    if row["auth_type"] == "cybertron_agent":
        _apply_cybertron_headers(headers, auth_config)
    return {
        "api_base_url": row["api_base_url"],
        "timeout_seconds": row["timeout_seconds"],
        "auth": auth,
        "headers": headers,
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
    }


def _read_optional_text(stored_path: str) -> str:
    path = storage.resolve_stored_path(stored_path)
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _validate_auth_config(auth_type: str, auth_config: dict) -> None:
    if auth_type in {"none", "account_password"}:
        return
    if auth_type == "cybertron_agent":
        required = ["cybertron_robot_key", "cybertron_robot_token", "username"]
        missing = [
            key
            for key in required
            if not auth_config.get(key) and not auth_config.get(f"{key}_encrypted")
        ]
        if missing:
            raise api_error(400, "API_AUTH_CYBERTRON_CONFIG_REQUIRED", f"塞伯坦智能体缺少配置：{', '.join(missing)}。")
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


def _validate_account_password_config(payload: ApiEnvironmentIn, existing: Row | None = None) -> None:
    if payload.auth_type != "account_password":
        return
    has_saved_password = bool(existing and existing["password_hash"])
    if not payload.username or (not payload.password and not has_saved_password):
        raise api_error(400, "API_AUTH_ACCOUNT_PASSWORD_REQUIRED", "账号密码鉴权必须填写用户名和密码。")


def _prepare_auth_config_for_storage(auth_type: str, auth_config: dict) -> dict:
    stored = dict(auth_config)
    if auth_type != "cybertron_agent":
        return stored
    for key in ("cybertron_robot_key", "cybertron_robot_token"):
        if stored.get(key):
            stored[f"{key}_encrypted"] = encrypt_api_environment_secret(str(stored.pop(key)))
    return stored


def _mask_auth_config(auth_config: dict) -> dict:
    masked = dict(auth_config)
    if masked.pop("cybertron_robot_key_encrypted", ""):
        masked["cybertron_robot_key_saved"] = True
    if masked.pop("cybertron_robot_token_encrypted", ""):
        masked["cybertron_robot_token_saved"] = True
    if masked.pop("token_encrypted", ""):
        masked["token_saved"] = True
    if masked.pop("cookie_value_encrypted", ""):
        masked["cookie_value_saved"] = True
    if "headers_encrypted" in masked:
        masked["headers_saved"] = sorted(masked.pop("headers_encrypted").keys())
    return masked


def _merge_auth_config_for_update(existing: Row, payload: ApiEnvironmentIn) -> dict:
    auth_config = dict(payload.auth_config)
    if payload.auth_type != existing["auth_type"]:
        return auth_config
    existing_config = api_automation_repo.loads_json(existing["auth_config_json"], {})
    if payload.auth_type == "cybertron_agent":
        for key in ("cybertron_robot_key", "cybertron_robot_token"):
            encrypted_key = f"{key}_encrypted"
            if not auth_config.get(key) and existing_config.get(encrypted_key):
                auth_config[encrypted_key] = existing_config[encrypted_key]
    return auth_config


def _apply_cybertron_headers(headers: dict[str, str], auth_config: dict) -> None:
    robot_key = decrypt_api_environment_secret(auth_config.get("cybertron_robot_key_encrypted", "")) or ""
    robot_token = decrypt_api_environment_secret(auth_config.get("cybertron_robot_token_encrypted", "")) or ""
    username = str(auth_config.get("username", "")).strip()
    if robot_key:
        headers["cybertron-robot-key"] = robot_key
    if robot_token:
        headers["cybertron-robot-token"] = robot_token
    if username:
        headers["username"] = username


def _request_body_content_type(request_body: dict[str, Any]) -> str:
    content = request_body.get("content")
    if not isinstance(content, dict):
        return ""
    return next((str(key) for key in content.keys() if str(key).strip()), "")


def _setdefault_header_case_insensitive(headers: dict[str, str], key: str, value: str) -> None:
    if any(existing_key.lower() == key.lower() for existing_key in headers):
        return
    headers[key] = value


def _require_visible_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return project
    if project["name"] == actor["project_scope"]:
        return project
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _validate_linked_ui_environment(db, project_id: str, environment_id: str | None) -> None:
    if environment_id and not environment_repo.belongs_to_project(db, environment_id, project_id):
        raise api_error(400, "UI_ENVIRONMENT_PROJECT_MISMATCH", "关联的探索环境不属于当前项目。")


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
