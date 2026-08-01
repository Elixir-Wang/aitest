import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from sqlite3 import Row
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
import yaml
from fastapi import HTTPException

from app.agents.api_automation.case_generation import service as api_generation_agent_service
from app.agents.api_automation.case_generation.schemas import ApiAutomationGenerationInput
from app.agents.api_automation.case_generation.planner import plan_api_test_points
from app.agents.api_automation.case_generation.response_contract import (
    compile_response_contract,
    merge_response_assertions,
)
from app.agents.api_automation.case_generation.validation import validate_generated_cases
from app.agents.api_automation.pytest_requests.agent import (
    generate_pytest_requests_endpoints,
    initialize_pytest_requests_suite,
)
from app.agents.api_automation.pytest_requests.suite import (
    endpoint_artifact_paths,
    ensure_suite_root,
    suite_is_initialized,
    suite_missing_files,
)
from app.agents.api_automation.pytest_requests.skill import pytest_requests_skill_fingerprint
from app.agents.api_automation.orchestration.agent import api_scenario_orchestration_agent
from app.agents.api_automation.orchestration.schemas import (
    ScenarioPlanResult,
    binding_to_runtime,
    control_config_to_runtime,
    extractor_to_runtime,
)
from app.core.environment_credentials import decrypt_api_environment_secret, encrypt_api_environment_secret
from app.core.security import hash_secret
from app.core import storage
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import api_automation_repo, environment_repo, project_repo
from app.repositories import test_case_repo
from app.services import operation_log_service
from app.schemas.api_automation import (
    ApiAutomationGenerateIn,
    ApiEndpointDebugIn,
    ApiEndpointIn,
    ApiEndpointUpdateIn,
    ApiEnvironmentIn,
    ApiRunCreateIn,
    ApiScenarioAiPlanApplyIn,
    ApiScenarioAiPlanIn,
    ApiScenarioAiReviewPlan,
    ApiScenarioAiReviewSaveIn,
    ApiScenarioIn,
    ApiScenarioStepIn,
    ApiScenarioStepsReplaceIn,
    ApiScenarioVersionSaveIn,
    ApiTestCaseSetIn,
)
from app.services.api_automation.openapi_parser import OpenAPIParseError, parse_openapi_document
from app.services.api_automation.runner import collect_script_suite, run_script_suite
from app.services.api_automation.oracle import find_case_observation, infer_assertions, load_observations
from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.services.api_automation.artifact_storage import (
    materialize_scenario_snapshot,
    project_suite_path,
    project_workspace_lock,
)
from app.services.api_automation.orchestration_asset_analysis import (
    endpoint_fingerprint,
    endpoint_summary,
    environment_schema_projection,
)
from app.services.api_automation.orchestration_compiler import COMPILER_VERSION, compile_plan, compile_review_plan
from app.services.api_automation.orchestration_job_runner import job_runner as orchestration_job_runner
from app.services.api_automation.orchestration_planner import ApiScenarioPlanner
from app.services.api_automation.orchestration_review import build_review_plan
from app.services.api_automation.orchestration_validator import validate_review_plan


MAX_AI_SCENARIO_CANDIDATE_ENDPOINTS = 12
AI_SCENARIO_GENERATION_TIMEOUT = timedelta(minutes=5)


def artifacts_dir_for(project_id: str):
    return project_suite_path(project_id)


def _ensure_pytest_suite_initialized(suite_path: Path) -> Path:
    suite_path = ensure_suite_root(suite_path)
    if suite_is_initialized(suite_path):
        return suite_path

    selection = resolve_model_selection("api_test_generation")
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    asyncio.run(initialize_pytest_requests_suite(model=model, suite_path=suite_path))
    missing_files = suite_missing_files(suite_path)
    if missing_files:
        raise api_error(
            422,
            "API_SCRIPT_SUITE_INITIALIZATION_FAILED",
            f"pytest 项目基础结构初始化失败，缺少文件：{', '.join(missing_files)}",
        )
    return suite_path


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
        result = _serialize_document(document)
        operation_log_service.record_change(
            log_type="audit",
            module="api_automation",
            action="import",
            object_type="api_document",
            object_id=document_id,
            object_name=result["name"],
            project_id=project_id,
            actor_id=actor["id"],
            actor_name=operation_log_service.actor_display_name(actor),
            source="web",
            summary=f"导入 OpenAPI 文档：{result['name']}，包含 {result['endpoint_count']} 个接口。",
            after={"name": result["name"], "endpoint_count": result["endpoint_count"], "version": result["version"]},
        )
        return result


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
        result = _serialize_endpoint(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="create",
        object_type="api_endpoint",
        object_id=endpoint_id,
        object_name=payload.summary or payload.path,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"创建接口：{payload.method} {payload.path}",
        after={"method": payload.method, "path": payload.path, "summary": payload.summary},
    )
    return result


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
        result = _serialize_endpoint(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="update",
        object_type="api_endpoint",
        object_id=endpoint_id,
        object_name=endpoint_data.get("summary") or endpoint_data.get("path"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"更新接口：{endpoint_data.get('method')} {endpoint_data.get('path')}",
        before={"method": existing["method"], "path": existing["path"], "summary": existing["summary"]},
        after={"method": endpoint_data["method"], "path": endpoint_data["path"], "summary": endpoint_data["summary"]},
    )
    return result


def delete_project_endpoint(project_id: str, endpoint_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_endpoint(db, endpoint_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        existing_data = _serialize_endpoint(existing)
        api_automation_repo.delete_endpoint(db, endpoint_id)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="delete",
        object_type="api_endpoint",
        object_id=endpoint_id,
        object_name=existing_data.get("summary") or existing_data.get("path"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除接口：{existing_data.get('method')} {existing_data.get('path')}",
        before={"method": existing_data.get("method"), "path": existing_data.get("path"), "summary": existing_data.get("summary")},
    )


def debug_project_endpoint(
    project_id: str,
    endpoint_id: str,
    payload: ApiEndpointDebugIn,
    actor,
    *,
    files: dict[str, tuple[str, Any, str, int]] | None = None,
) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        endpoint_row = api_automation_repo.find_endpoint(db, endpoint_id)
        if not endpoint_row or endpoint_row["project_id"] != project_id:
            raise api_error(404, "API_ENDPOINT_NOT_FOUND", "接口不存在。")
        endpoint = _serialize_endpoint(endpoint_row)
        environment = _build_debug_environment(db, project_id, payload.api_environment_id)

    request = _build_debug_request(endpoint, environment, payload, files=files)
    started = time.perf_counter()
    try:
        response = requests.request(
            method=request["method"],
            url=request["url"],
            params=request["query_params"],
            headers=request["headers"],
            json=request["json_body"],
            data=request["form_body"] if request["form_body"] is not None else request["raw_body"],
            files=request["files"] or None,
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
        result = _serialize_api_environment(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="create",
        object_type="api_environment",
        object_id=environment_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"创建接口环境：{payload.name}",
        after={"name": payload.name, "api_base_url": payload.api_base_url},
    )
    return result


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
        existing_data = _serialize_api_environment(existing)
        _validate_linked_ui_environment(db, project_id, payload.linked_ui_environment_id)
        _validate_account_password_config(payload, existing)
        auth_config = dict(payload.auth_config)
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
        result = _serialize_api_environment(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="update",
        object_type="api_environment",
        object_id=environment_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"更新接口环境：{payload.name}",
        before={"name": existing_data.get("name"), "api_base_url": existing_data.get("api_base_url")},
        after={"name": payload.name, "api_base_url": payload.api_base_url},
    )
    return result


def delete_api_environment(project_id: str, environment_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        existing = api_automation_repo.find_api_environment(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        existing_data = _serialize_api_environment(existing)
        api_automation_repo.delete_api_environment(db, environment_id)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="delete",
        object_type="api_environment",
        object_id=environment_id,
        object_name=existing_data.get("name"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除接口环境：{existing_data.get('name')}",
        before={"name": existing_data.get("name"), "api_base_url": existing_data.get("api_base_url")},
    )


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
        existing_data = _serialize_api_test_case(row)
        api_automation_repo.delete_api_test_case(db, case_id)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="delete",
        object_type="api_test_case",
        object_id=case_id,
        object_name=existing_data.get("title") or "未命名用例",
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除接口自动化用例：{existing_data.get('title') or '未命名用例'}",
        before={"title": existing_data.get("title"), "endpoint_id": existing_data.get("endpoint_id")},
    )


def create_oracle_proposal(project_id: str, case_id: str, run_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        case = api_automation_repo.find_api_test_case(db, case_id)
        run = api_automation_repo.find_api_run(db, run_id)
        if not case or case["project_id"] != project_id:
            raise api_error(404, "API_TEST_CASE_NOT_FOUND", "接口自动化用例不存在。")
        if not run or run["project_id"] != project_id:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        observation_path = storage.resolve_stored_path(run["observation_result_path"])
        if observation_path is None:
            raise api_error(409, "API_OBSERVATION_NOT_FOUND", "运行记录没有观察执行证据。")
        existing = api_automation_repo.find_oracle_proposal_by_run_case(db, run_id, case_id)
        if existing:
            return _serialize_oracle_proposal(existing)
        try:
            observation = find_case_observation(observation_path, case_id)
            proposal = _create_oracle_proposal_from_observation(
                db,
                case=case,
                run=run,
                observation=observation,
                created_by=actor["id"],
            )
        except ValueError as exc:
            raise api_error(409, "API_ORACLE_INFERENCE_UNAVAILABLE", str(exc)) from exc
        return _serialize_oracle_proposal(proposal)


def create_oracle_proposals_for_run(run_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {"created": 0, "skipped": 0, "errors": []}
    with connect() as db:
        run = api_automation_repo.find_api_run(db, run_id)
        if not run:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        observation_path = storage.resolve_stored_path(run["observation_result_path"])
        if observation_path is None:
            return result
        try:
            observations = load_observations(observation_path)
        except ValueError as exc:
            result["errors"].append(str(exc))
            return result
        for observation in observations:
            case_id = str(observation.get("case_id") or "").strip()
            if not case_id:
                result["errors"].append("观察证据缺少 case_id。")
                continue
            case = api_automation_repo.find_api_test_case(db, case_id)
            if not case or case["project_id"] != run["project_id"]:
                result["errors"].append(f"观察证据关联用例不存在：{case_id}")
                continue
            if case["oracle_status"] not in {"inferred", "needs_confirmation"}:
                result["skipped"] += 1
                continue
            if api_automation_repo.find_oracle_proposal_by_run_case(db, run_id, case_id):
                result["skipped"] += 1
                continue
            try:
                _create_oracle_proposal_from_observation(
                    db,
                    case=case,
                    run=run,
                    observation=observation,
                    created_by="system",
                )
            except ValueError as exc:
                result["errors"].append(f"{case_id}: {exc}")
                continue
            result["created"] += 1
    return result


def _create_oracle_proposal_from_observation(
    db,
    *,
    case: Row,
    run: Row,
    observation: dict[str, Any],
    created_by: str,
) -> Row:
    assertions = infer_assertions(observation)
    current_snapshot = _oracle_case_snapshot(case)
    proposed_snapshot = {
        **current_snapshot,
        "oracle_status": "confirmed",
        "assertions": assertions,
    }
    proposal_id = f"apioracle-{secrets.token_hex(8)}"
    api_automation_repo.create_oracle_proposal(
        db,
        proposal_id=proposal_id,
        project_id=run["project_id"],
        endpoint_id=case["endpoint_id"],
        case_id=case["id"],
        run_id=run["id"],
        test_point_key=case["test_point_key"],
        current_snapshot=current_snapshot,
        proposed_snapshot=proposed_snapshot,
        reasoning="根据真实观察响应推断 HTTP 状态码和稳定业务码，需人工审批后生效。",
        confidence=0.9 if len(assertions) > 1 else 0.75,
        created_by=created_by,
    )
    return api_automation_repo.find_oracle_proposal(db, proposal_id)


def list_oracle_proposals(project_id: str, actor, *, status: str = "") -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [
            _serialize_oracle_proposal(row)
            for row in api_automation_repo.list_oracle_proposals(db, project_id, status=status)
        ]


def approve_oracle_proposal(
    project_id: str,
    proposal_id: str,
    *,
    scope: str,
    review_comment: str,
    assertions: list[dict[str, Any]] | None,
    actor,
) -> dict:
    _require_admin(actor)
    if scope not in {"case_only", "case_and_endpoint_asset"}:
        raise api_error(422, "API_ORACLE_SCOPE_INVALID", "审批范围不正确。")
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        proposal = api_automation_repo.find_oracle_proposal(db, proposal_id)
        if not proposal or proposal["project_id"] != project_id:
            raise api_error(404, "API_ORACLE_PROPOSAL_NOT_FOUND", "Oracle 建议不存在。")
        if proposal["status"] != "pending":
            raise api_error(409, "API_ORACLE_PROPOSAL_REVIEWED", "Oracle 建议已完成审批。")
        case = api_automation_repo.find_api_test_case(db, proposal["case_id"])
        if not case:
            raise api_error(404, "API_TEST_CASE_NOT_FOUND", "接口自动化用例不存在。")
        proposed_snapshot = api_automation_repo.loads_json(proposal["proposed_snapshot_json"], {})
        approved_assertions = assertions if assertions is not None else proposed_snapshot.get("assertions", [])
        if not approved_assertions:
            raise api_error(422, "API_ORACLE_ASSERTIONS_REQUIRED", "审批通过时必须提供有效断言。")
        versions = api_automation_repo.list_api_test_case_versions(db, case["id"])
        version = max((int(row["version"]) for row in versions), default=0) + 1
        approved_snapshot = {
            **_oracle_case_snapshot(case),
            "oracle_status": "confirmed",
            "assertions": approved_assertions,
        }
        api_automation_repo.create_api_test_case_version(
            db,
            version_id=f"apitcv-{secrets.token_hex(8)}",
            case_id=case["id"],
            version=version,
            snapshot=approved_snapshot,
            change_source="oracle_approval",
            created_by=actor["id"],
        )
        api_automation_repo.update_api_test_case(
            db,
            case["id"],
            assertions=approved_assertions,
            oracle_status="confirmed",
            updated_by=actor["id"],
        )
        if scope == "case_and_endpoint_asset":
            api_automation_repo.upsert_endpoint_oracle_fact(
                db,
                fact_id=f"apifact-{secrets.token_hex(8)}",
                endpoint_id=proposal["endpoint_id"],
                test_point_key=proposal["test_point_key"],
                assertions=approved_assertions,
                evidence_run_ids=[proposal["run_id"]],
                approved_by=actor["id"],
            )
        api_automation_repo.review_oracle_proposal(
            db,
            proposal_id,
            status="approved",
            review_scope=scope,
            review_comment=review_comment,
            reviewed_by=actor["id"],
        )
        return _serialize_oracle_proposal(api_automation_repo.find_oracle_proposal(db, proposal_id))


def reject_oracle_proposal(project_id: str, proposal_id: str, *, review_comment: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        proposal = api_automation_repo.find_oracle_proposal(db, proposal_id)
        if not proposal or proposal["project_id"] != project_id:
            raise api_error(404, "API_ORACLE_PROPOSAL_NOT_FOUND", "Oracle 建议不存在。")
        if proposal["status"] != "pending":
            raise api_error(409, "API_ORACLE_PROPOSAL_REVIEWED", "Oracle 建议已完成审批。")
        api_automation_repo.review_oracle_proposal(
            db,
            proposal_id,
            status="rejected",
            review_scope="",
            review_comment=review_comment,
            reviewed_by=actor["id"],
        )
        return _serialize_oracle_proposal(api_automation_repo.find_oracle_proposal(db, proposal_id))


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
        result = _serialize_api_test_case_set(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="create",
        object_type="api_test_case_set",
        object_id=set_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"创建接口用例集：{payload.name}",
        after={"name": payload.name},
    )
    return result


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
        existing_data = _serialize_api_test_case_set(existing)
        api_automation_repo.update_api_test_case_set(db, set_id, name=payload.name, notes=payload.notes)
        row = api_automation_repo.find_api_test_case_set(db, set_id)
        result = _serialize_api_test_case_set(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="update",
        object_type="api_test_case_set",
        object_id=set_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"更新接口用例集：{payload.name}",
        before={"name": existing_data.get("name"), "notes": existing_data.get("notes")},
        after={"name": payload.name, "notes": payload.notes},
    )
    return result


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
            generated_case_count = _persist_generation_item_cases(
                db,
                run_id,
                item_id,
                attempt_id,
                result,
                planned_test_points=input_data.planned_test_points,
            )
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
    serialized_endpoint = _serialize_endpoint(endpoint)
    planned_test_points = [
        asdict(point)
        for point in plan_api_test_points(serialized_endpoint)
    ]
    oracle_facts = {
        fact["test_point_key"]: fact
        for fact in api_automation_repo.list_endpoint_oracle_facts(db, endpoint["id"])
    }
    for planned_point in planned_test_points:
        fact = oracle_facts.get(planned_point["key"])
        if not fact:
            continue
        planned_point["oracle_status"] = "confirmed"
        planned_point["assertions"] = api_automation_repo.loads_json(fact["assertions_json"], [])
        planned_point["oracle_fact"] = {
            "approved_by": fact["approved_by"],
            "evidence_run_ids": api_automation_repo.loads_json(fact["evidence_run_ids_json"], []),
        }
    for planned_point in planned_test_points:
        if planned_point.get("oracle_fact") or planned_point.get("category") != "positive":
            continue
        planned_point["required_assertions"] = [
            assertion.model_dump()
            for assertion in compile_response_contract(serialized_endpoint)
        ]
    return ApiAutomationGenerationInput(
        project_id=run["project_id"],
        endpoints=[_serialize_endpoint(endpoint)],
        environment_summary=environment_summary,
        source_test_cases=source_test_cases,
        generation_goal=run["generation_goal"],
        include_security_cases=bool(
            api_automation_repo.loads_json(run["options_json"], {}).get("include_security_cases")
        ),
        planned_test_points=planned_test_points,
    )


def _persist_generation_item_cases(
    db,
    run_id: str,
    item_id: str,
    attempt_id: str,
    result,
    *,
    planned_test_points: list[dict[str, Any]],
) -> int:
    item = api_automation_repo.find_generation_item(db, item_id)
    endpoint = api_automation_repo.find_endpoint(db, item["endpoint_id"]) if item else None
    if not item or not endpoint:
        raise ValueError("接口自动化生成子任务关联接口不存在。")
    # Models occasionally serialize a missing request body as ``body: {}`` (or
    # another empty value).  The canonical request contract represents an
    # omitted body by omitting the key entirely.  Normalize only this exact,
    # unambiguous test point before strict validation; all other malformed
    # requests must still fail the item atomically.
    normalized_cases = [
        generated_case.model_copy(
            update={
                "request": generated_case.request.model_validate(
                    {
                        key: value
                        for key, value in generated_case.request.model_dump(exclude_unset=True).items()
                        if key != "body"
                    }
                )
            }
        )
        if (
            generated_case.test_point_key == "request_body.missing"
            and "body" in generated_case.request.model_fields_set
        )
        else generated_case
        for generated_case in result.cases
    ]
    planned_points_by_key = {point["key"]: point for point in planned_test_points}
    completed_cases = [
        generated_case.model_copy(
            update={
                "assertions": merge_response_assertions(
                    _required_generated_case_assertions(
                        _serialize_endpoint(endpoint),
                        planned_points_by_key.get(generated_case.test_point_key, {}),
                        generated_case.assertions,
                    ),
                    generated_case.assertions,
                )
            }
        )
        for generated_case in normalized_cases
    ]
    validate_generated_cases(_serialize_endpoint(endpoint), planned_test_points, completed_cases)
    for generated_case in completed_cases:
        api_automation_repo.create_api_test_case(
            db,
            case_id=f"apitc-{secrets.token_hex(8)}",
            project_id=endpoint["project_id"],
            endpoint_id=generated_case.endpoint_id,
            source_test_case_id=None,
            generation_run_id=run_id,
            generation_item_id=item_id,
            generation_attempt_id=attempt_id,
            test_point_key=generated_case.test_point_key,
            oracle_status=generated_case.oracle_status,
            title=generated_case.title,
            test_description=generated_case.test_description,
            priority=generated_case.priority,
            coverage=generated_case.coverage,
            source=generated_case.source,
            preconditions=[],
            request=generated_case.request.model_dump(exclude_unset=True),
            test_data=generated_case.test_data,
            expected={},
            assertions=[assertion.model_dump() for assertion in generated_case.assertions],
            variables={},
            data_origin={},
            data_file_path="",
            notes=generated_case.generation_notes,
            created_by="system",
        )
    return len(result.cases)


def _required_generated_case_assertions(
    endpoint: dict[str, Any],
    planned_point: dict[str, Any],
    generated_assertions: list,
) -> list:
    required = planned_point.get("required_assertions", [])
    if planned_point.get("oracle_fact"):
        return required

    success_status_code = next(
        (
            assertion.expected
            for assertion in generated_assertions
            if assertion.type == "status_code"
            and isinstance(assertion.expected, int)
            and not isinstance(assertion.expected, bool)
            and 200 <= assertion.expected <= 299
        ),
        None,
    )
    if success_status_code is None:
        return required
    return merge_response_assertions(
        compile_response_contract(endpoint, expected_status_code=success_status_code),
        required,
    )


def _generation_error_message(exc: Exception) -> str:
    message = str(exc)
    return "模型输出超出长度限制" if "finish_reason" in message and "length" in message else message


def _prepare_endpoint_generation(suite_path: Path, endpoints: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    suite_path = suite_path.resolve()
    endpoint_payload = []
    artifacts_by_endpoint = {}
    claimed_directories = {}
    for endpoint in endpoints:
        endpoint_dir, test_file_key, data_file_key = endpoint_artifact_paths(endpoint)
        endpoint_id = endpoint["id"]
        conflicting_endpoint_id = claimed_directories.get(endpoint_dir)
        if conflicting_endpoint_id and conflicting_endpoint_id != endpoint_id:
            raise api_error(
                409,
                "API_SCRIPT_ARTIFACT_PATH_CONFLICT",
                f"接口 {conflicting_endpoint_id} 与 {endpoint_id} 生成目录冲突：{endpoint_dir}",
            )
        claimed_directories[endpoint_dir] = endpoint_id
        artifacts = {
            "directory": endpoint_dir,
            "test_file": test_file_key,
            "data_file": data_file_key,
        }
        payload_endpoint = dict(endpoint)
        payload_endpoint["artifacts"] = artifacts
        endpoint_payload.append(payload_endpoint)
        normalized_path = str(endpoint.get("normalized_path") or endpoint.get("path") or "/")
        artifacts_by_endpoint[endpoint_id] = {
            "endpoint_id": endpoint_id,
            "suite_path": suite_path,
            "test_file_key": test_file_key,
            "data_file_key": data_file_key,
            "test_file_path": suite_path / test_file_key,
            "data_file_path": suite_path / data_file_key,
            "script_name": f"{str(endpoint.get('method', '')).upper()} {normalized_path}",
        }
    return endpoint_payload, artifacts_by_endpoint


def _write_canonical_endpoint_data(artifacts_by_endpoint: dict[str, dict], cases_by_endpoint: dict[str, list[dict]]) -> None:
    """Write the backend-owned case snapshot before/after the AI edits test code.

    The data file is a persistence artifact, not model output. Keeping it deterministic
    prevents the agent from changing IDs, endpoint ownership, or appending duplicate cases.
    """
    for endpoint_id, artifact in artifacts_by_endpoint.items():
        data_path = Path(artifact["data_file_path"])
        data_path.parent.mkdir(parents=True, exist_ok=True)
        canonical_cases = [
            {**case, "case_id": str(case["id"])}
            for case in cases_by_endpoint[endpoint_id]
        ]
        fd, temp_name = tempfile.mkstemp(prefix=f".{data_path.name}.", suffix=".tmp", dir=data_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                yaml.safe_dump(
                    canonical_cases,
                    handle,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, data_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def _snapshot_endpoint_artifacts(artifacts_by_endpoint: dict[str, dict]) -> dict[Path, bytes | None]:
    paths = {
        Path(artifact[key])
        for artifact in artifacts_by_endpoint.values()
        for key in ("test_file_path", "data_file_path")
    }
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def _restore_endpoint_artifacts(snapshot: dict[Path, bytes | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def _validate_generated_endpoint_artifacts(suite_path: Path, artifacts_by_endpoint: dict[str, dict]) -> None:
    suite_path = suite_path.resolve()
    for endpoint_id, artifact in artifacts_by_endpoint.items():
        for file_type in ("test", "data"):
            file_key = artifact[f"{file_type}_file_key"]
            file_path = Path(artifact[f"{file_type}_file_path"]).resolve()
            expected_path = (suite_path / file_key).resolve()
            try:
                file_path.relative_to(suite_path)
                expected_path.relative_to(suite_path)
            except ValueError as exc:
                raise api_error(
                    422,
                    "API_SCRIPT_ARTIFACT_PATH_INVALID",
                    f"接口 {endpoint_id} 的生成文件路径不在 pytest 项目内：{file_key}",
                ) from exc
            if file_path != expected_path:
                raise api_error(
                    422,
                    "API_SCRIPT_ARTIFACT_PATH_INVALID",
                    f"接口 {endpoint_id} 的生成文件路径与后端指定路径不一致：{file_key}",
                )
            if not file_path.is_file():
                raise api_error(
                    422,
                    "API_SCRIPT_ARTIFACT_MISSING",
                    f"接口 {endpoint_id} 缺少生成文件：{file_key}",
                )
        data_file_path = Path(artifact["data_file_path"])
        try:
            cases = yaml.safe_load(data_file_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise api_error(
                422,
                "API_SCRIPT_ARTIFACT_DATA_INVALID",
                f"接口 {endpoint_id} 的生成数据文件无法解析：{artifact['data_file_key']}",
            ) from exc
        if not isinstance(cases, list) or not cases:
            raise api_error(
                422,
                "API_SCRIPT_ARTIFACT_DATA_INVALID",
                f"接口 {endpoint_id} 的生成数据文件必须是非空用例列表：{artifact['data_file_key']}",
            )
        if not all(isinstance(case, dict) and case.get("endpoint_id") == endpoint_id for case in cases):
            raise api_error(
                422,
                "API_SCRIPT_ARTIFACT_ENDPOINT_MISMATCH",
                f"接口 {endpoint_id} 的生成数据包含其他接口用例：{artifact['data_file_key']}",
            )
        expected_case_ids = set(artifact.get("expected_case_ids") or [])
        generated_case_ids = {str(case.get("id")) for case in cases if case.get("id")}
        if expected_case_ids and generated_case_ids != expected_case_ids:
            raise api_error(
                422,
                "API_SCRIPT_ARTIFACT_CASE_MISMATCH",
                f"接口 {endpoint_id} 的生成用例集合与已选用例不一致：{artifact['data_file_key']}",
            )
        uncertain_oracle = any(
            case.get("oracle_status") in {"inferred", "needs_confirmation"}
            for case in cases
            if isinstance(case, dict)
        )
        if uncertain_oracle:
            test_source = Path(artifact["test_file_path"]).read_text(encoding="utf-8", errors="replace")
            if "record_observation" not in test_source or "oracle_status" not in test_source:
                raise api_error(
                    422,
                    "API_SCRIPT_ORACLE_OBSERVATION_MISSING",
                    f"接口 {endpoint_id} 包含不确定 Oracle 用例，但测试文件未记录实际响应：{artifact['test_file_key']}",
                )


def _script_artifacts_are_current(existing, suite_path: Path, endpoint: dict) -> bool:
    if existing is None:
        return False
    _, test_file_key, data_file_key = endpoint_artifact_paths(endpoint)
    expected_test_path = (suite_path.resolve() / test_file_key).resolve()
    expected_data_path = (suite_path.resolve() / data_file_key).resolve()
    stored_test_path = storage.resolve_stored_path(existing["test_file_path"])
    stored_data_path = storage.resolve_stored_path(existing["data_file_path"])
    if stored_test_path is None or stored_data_path is None:
        return False
    resolved_test_path = stored_test_path.resolve()
    resolved_data_path = stored_data_path.resolve()
    return (
        resolved_test_path == expected_test_path
        and resolved_data_path == expected_data_path
        and resolved_test_path.is_file()
        and resolved_data_path.is_file()
    )


def _collect_generated_suite(suite_path: Path, artifacts_by_endpoint: dict[str, dict]) -> None:
    suite_path = suite_path.resolve()
    changed_test_paths = [artifact["test_file_key"] for artifact in artifacts_by_endpoint.values()]
    _collect_suite_or_raise(suite_path, changed_test_paths)
    _collect_suite_or_raise(suite_path, None)


def _collect_suite_or_raise(suite_path: Path, test_paths: list[str] | None) -> None:
    try:
        collection = collect_script_suite(suite_path=suite_path.resolve(), timeout=120, test_paths=test_paths)
    except Exception as exc:
        raise api_error(
            422,
            "API_SCRIPT_COLLECTION_FAILED",
            f"生成的 pytest 项目无法收集：{str(exc)[:2000]}",
        ) from exc
    if not collection["ok"]:
        error_output = (collection["stderr"] or collection["stdout"] or "pytest 收集失败。").strip()
        raise api_error(
            422,
            "API_SCRIPT_COLLECTION_FAILED",
            f"生成的 pytest 项目无法收集：{error_output[:2000]}",
        )


def _find_legacy_endpoint_artifacts(suite_path: Path, endpoint_id: str, canonical_artifact: dict) -> list[Path]:
    testcases_path = (suite_path.resolve() / "testcases").resolve()
    canonical_data_path = Path(canonical_artifact["data_file_path"]).resolve()
    canonical_test_path = Path(canonical_artifact["test_file_path"]).resolve()
    legacy_paths = []
    if not testcases_path.is_dir():
        return legacy_paths
    for pattern in ("*.yaml", "*.yml"):
        for data_path in sorted(testcases_path.rglob(pattern)):
            resolved_data_path = data_path.resolve()
            if resolved_data_path == canonical_data_path:
                continue
            try:
                cases = yaml.safe_load(data_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, yaml.YAMLError):
                continue
            if not isinstance(cases, list) or not cases:
                continue
            if not all(isinstance(case, dict) and case.get("endpoint_id") == endpoint_id for case in cases):
                continue
            test_path = data_path.with_suffix(".py").resolve()
            if test_path == canonical_test_path or not test_path.is_file():
                continue
            legacy_paths.extend([test_path, resolved_data_path])
    return legacy_paths


def _remove_legacy_endpoint_artifacts(paths: list[Path]) -> list[tuple[Path, bytes]]:
    backups = []
    for path in paths:
        resolved_path = path.resolve()
        if not resolved_path.is_file():
            continue
        backups.append((resolved_path, resolved_path.read_bytes()))
        resolved_path.unlink()
    return backups


def _restore_removed_endpoint_artifacts(backups: list[tuple[Path, bytes]]) -> None:
    for path, content in backups:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _cleanup_legacy_endpoint_artifacts(suite_path: Path, legacy_paths: list[Path]) -> None:
    removed_artifacts = _remove_legacy_endpoint_artifacts(list(dict.fromkeys(legacy_paths)))
    if not removed_artifacts:
        return
    try:
        _collect_suite_or_raise(suite_path, None)
    except Exception:
        _restore_removed_endpoint_artifacts(removed_artifacts)
        raise


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
    serialized_endpoints = {
        endpoint_id: _serialize_endpoint(endpoint_rows[endpoint_id])
        for endpoint_id in endpoint_ids
    }
    source_hashes = {
        endpoint_id: _script_source_hash(serialized_endpoints[endpoint_id], cases_by_endpoint[endpoint_id])
        for endpoint_id in endpoint_ids
    }
    project_suite_path = artifacts_dir_for(project_id)
    changed_endpoint_ids = [
        endpoint_id
        for endpoint_id in endpoint_ids
        if force
        or existing_by_endpoint[endpoint_id] is None
        or existing_by_endpoint[endpoint_id]["source_hash"] != source_hashes[endpoint_id]
        or not _script_artifacts_are_current(
            existing_by_endpoint[endpoint_id],
            project_suite_path,
            serialized_endpoints[endpoint_id],
        )
    ]

    suite_id = f"{project_id}-pytest-requests"
    artifacts_by_endpoint = {}
    if changed_endpoint_ids:
        with project_workspace_lock(project_id):
            generated_suite_path = _ensure_pytest_suite_initialized(artifacts_dir_for(project_id))
            endpoint_payload, artifacts_by_endpoint = _prepare_endpoint_generation(
                generated_suite_path,
                [serialized_endpoints[endpoint_id] for endpoint_id in changed_endpoint_ids],
            )
            for endpoint_id in changed_endpoint_ids:
                artifacts_by_endpoint[endpoint_id]["expected_case_ids"] = [
                    case["id"] for case in cases_by_endpoint[endpoint_id]
                ]
            artifact_snapshot = _snapshot_endpoint_artifacts(artifacts_by_endpoint)
            selection = resolve_model_selection("api_test_generation")
            model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
            try:
                _write_canonical_endpoint_data(artifacts_by_endpoint, cases_by_endpoint)
                asyncio.run(
                    generate_pytest_requests_endpoints(
                        model=model,
                        suite_path=generated_suite_path,
                        endpoints=endpoint_payload,
                        cases_by_endpoint={
                            endpoint_id: cases_by_endpoint[endpoint_id]
                            for endpoint_id in changed_endpoint_ids
                        },
                    )
                )
                # Re-assert the DB snapshot because the agent is not allowed to own data files.
                _write_canonical_endpoint_data(artifacts_by_endpoint, cases_by_endpoint)
                _validate_generated_endpoint_artifacts(generated_suite_path, artifacts_by_endpoint)
                _collect_generated_suite(generated_suite_path, artifacts_by_endpoint)
                legacy_paths = [
                    path
                    for endpoint_id in changed_endpoint_ids
                    for path in _find_legacy_endpoint_artifacts(
                        generated_suite_path,
                        endpoint_id,
                        artifacts_by_endpoint[endpoint_id],
                    )
                ]
                _cleanup_legacy_endpoint_artifacts(generated_suite_path, legacy_paths)
            except Exception as exc:
                _restore_endpoint_artifacts(artifact_snapshot)
                if isinstance(exc, HTTPException):
                    raise
                raise api_error(
                    422,
                    "API_SCRIPT_GENERATION_FAILED",
                    f"DeepAgents 生成 pytest 项目失败：{str(exc)[:2000]}",
                ) from exc
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


def create_script_generation_run(
    project_id: str,
    endpoint_ids: list[str],
    actor,
    *,
    force: bool = False,
    api_environment_id: str | None = None,
) -> dict:
    _require_admin(actor)
    endpoint_ids = list(dict.fromkeys(endpoint_ids))
    if not endpoint_ids:
        raise api_error(400, "API_ENDPOINT_REQUIRED", "请至少选择一个接口。")
    run_id = f"apiscriptgen-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_endpoint_ids(db, project_id, endpoint_ids)
        if api_environment_id:
            environment = api_automation_repo.find_api_environment(db, api_environment_id)
            if not environment or environment["project_id"] != project_id:
                raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        api_automation_repo.create_script_generation_run(
            db,
            run_id=run_id,
            project_id=project_id,
            task_id=f"api_script_generation:{run_id}",
            endpoint_ids=endpoint_ids,
            api_environment_id=api_environment_id,
            force=force,
            created_by=actor["id"],
        )
        return _serialize_script_generation_run(db, api_automation_repo.find_script_generation_run(db, run_id))


def get_script_generation_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_script_generation_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_SCRIPT_GENERATION_RUN_NOT_FOUND", "接口脚本生成任务不存在。")
        return _serialize_script_generation_run(db, row)


def execute_script_generation_run(run_id: str) -> None:
    with connect() as db:
        row = api_automation_repo.find_script_generation_run(db, run_id)
        if not row or row["status"] not in {"queued", "running"}:
            return
        api_automation_repo.update_script_generation_run(db, run_id, status="running", started_at=_current_timestamp_sql_value())
        row = api_automation_repo.find_script_generation_run(db, run_id)
    try:
        result = generate_project_scripts(
            row["project_id"],
            api_automation_repo.loads_json(row["endpoint_ids_json"], []),
            {"id": row["created_by"], "role": "admin", "project_scope": "全部项目"},
            force=bool(row["force"]),
        )
        changed_files = [
            path
            for script in result["scripts"]
            if script.get("change") in {"created", "updated"}
            for path in (script.get("test_file_path"), script.get("data_file_path"))
            if path
        ]
        with connect() as db:
            api_automation_repo.update_script_generation_run(
                db,
                run_id,
                status="completed",
                suite_path=result["suite_path"],
                changed_files=changed_files,
                result_summary=result["summary"],
                error_message="",
                finished_at=_current_timestamp_sql_value(),
            )
    except Exception as exc:
        with connect() as db:
            api_automation_repo.update_script_generation_run(
                db,
                run_id,
                status="failed",
                error_message=str(exc)[:4000],
                finished_at=_current_timestamp_sql_value(),
            )


def _serialize_script_generation_run(db, row: Row | None) -> dict:
    if row is None:
        return {}
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "endpoint_ids": api_automation_repo.loads_json(row["endpoint_ids_json"], []),
        "api_environment_id": row["api_environment_id"],
        "force": bool(row["force"]),
        "suite_path": row["suite_path"],
        "changed_files": api_automation_repo.loads_json(row["changed_files_json"], []),
        "summary": api_automation_repo.loads_json(row["result_summary_json"], {}),
        "error_message": row["error_message"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def _current_timestamp_sql_value() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def list_project_scripts(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [_serialize_script(row) for row in api_automation_repo.list_scripts(db, project_id)]


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
        existing_data = _serialize_script(row)
    path = _resolve_generated_path(project_id, existing_data["test_file_path"])
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
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="update",
        object_type="api_script",
        object_id=script_id,
        object_name=existing_data.get("name"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"更新接口自动化脚本：{existing_data.get('name')}",
        before={"notes": existing_data.get("notes")},
        after={"notes": notes},
    )
    return result


def delete_api_script(project_id: str, script_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_script(db, script_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_SCRIPT_NOT_FOUND", "接口自动化脚本不存在。")
        existing_data = _serialize_script(row)
        api_automation_repo.delete_script(db, script_id)

    suite_path = _resolve_generated_path(project_id, existing_data["suite_path"]).resolve()
    testcases_root = (suite_path / "testcases").resolve()
    feature_dirs: set[Path] = set()
    for stored_path in (existing_data["test_file_path"], existing_data["data_file_path"]):
        if not stored_path:
            continue
        path = _resolve_generated_path(project_id, stored_path).resolve()
        path.relative_to(suite_path)
        feature_dirs.add(path.parent)
        if path.exists() and path.is_file():
            path.unlink()
    for feature_dir in feature_dirs:
        feature_dir.rmdir() if False else None  # noqa: E701
        if feature_dir.exists() and feature_dir.is_relative_to(testcases_root):
            for child in sorted(feature_dir.rglob("*"), key=lambda p: len(p.as_posix()), reverse=True):
                if child.is_file():
                    child.unlink()
            if feature_dir.exists() and not any(feature_dir.iterdir()):
                feature_dir.rmdir()
            cursor = feature_dir.parent
            while cursor != testcases_root and cursor.is_relative_to(testcases_root) and cursor.exists() and not any(cursor.iterdir()):
                cursor.rmdir()
                cursor = cursor.parent
                if cursor == testcases_root:
                    break

    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="delete",
        object_type="api_script",
        object_id=script_id,
        object_name=existing_data.get("name"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除接口自动化脚本：{existing_data.get('name')}",
        before={"name": existing_data.get("name")},
    )


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
        }
        api_automation_repo.create_api_run(
            db,
            run_id=run_id,
            task_id=task_id,
            project_id=project_id,
            api_environment_id=payload.api_environment_id,
            script_ids=payload.script_ids,
            execution_snapshot=execution_snapshot,
            command_summary="python -m pytest tests --json-report",
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
    result_summary = dict(result["summary"])
    with connect() as db:
        api_automation_repo.update_api_run(
            db,
            run_id,
            status=result["status"],
            stdout_path=storage.store_path(result["stdout_path"]) or result["stdout_path"],
            stderr_path=storage.store_path(result["stderr_path"]) or result["stderr_path"],
            json_report_path=storage.store_path(result["json_report_path"]) or result["json_report_path"],
            scenario_result_path=storage.store_path(result.get("scenario_result_path", "")) or result.get("scenario_result_path", ""),
            observation_result_path=storage.store_path(result.get("observation_result_path", ""))
            or result.get("observation_result_path", ""),
            summary=result_summary,
            error_message=result["error_message"],
            finished=True,
        )
        api_automation_repo.update_scripts_last_run(db, script_ids, result["status"])
    if result.get("observation_result_path"):
        try:
            proposal_summary = create_oracle_proposals_for_run(run_id)
        except Exception as exc:
            proposal_summary = {"created": 0, "skipped": 0, "errors": [str(exc)[:1000]]}
        result_summary["oracle_proposals"] = proposal_summary
    with connect() as db:
        api_automation_repo.update_api_run(
            db,
            run_id,
            status=result["status"],
            summary=result_summary,
            error_message=result["error_message"],
        )
        updated = api_automation_repo.find_api_run(db, run_id)
        if updated and "source_repair_attempt_id" in updated.keys() and updated["source_repair_attempt_id"]:
            attempt = api_automation_repo.find_repair_attempt(db, updated["source_repair_attempt_id"])
            if attempt:
                api_automation_repo.update_repair_attempt(db, attempt["id"], status="completed")
                api_automation_repo.update_repair_session(
                    db,
                    attempt["session_id"],
                    status="passed" if result["status"] == "passed" else "active",
                    current_run_id=run_id,
                )
        return _serialize_api_run(updated, db)


def create_api_scenario_run(
    project_id: str,
    scenario_id: str,
    api_environment_id: str,
    actor,
    *,
    source: str = "published",
) -> dict:
    _require_admin(actor)
    run_id = f"apirun-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        environment = api_automation_repo.find_api_environment(db, api_environment_id)
        if not environment or environment["project_id"] != project_id:
            raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        if source == "draft":
            steps = [_serialize_scenario_step(row) for row in _list_scenario_step_rows(db, scenario_id)]
            validation = _validate_scenario_definition(db, scenario, steps)
            if not validation["valid"]:
                raise api_error(409, "API_SCENARIO_INVALID", "；".join(validation["errors"]))
            snapshot = _build_scenario_snapshot(db, scenario, steps)
        else:
            if scenario["status"] != "ready":
                raise api_error(409, "API_SCENARIO_NOT_READY", "请先保存场景版本。")
            snapshot = api_automation_repo.loads_json(scenario["published_snapshot_json"], {})
            serialized_snapshot = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            snapshot_hash = hashlib.sha256(serialized_snapshot.encode("utf-8")).hexdigest()
            if snapshot_hash != scenario["published_hash"]:
                raise api_error(409, "API_SCENARIO_SNAPSHOT_INVALID", "场景版本快照校验失败，请重新保存版本。")
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
            "source": source,
        },
        "environment": {
            "id": environment["id"],
            "name": environment["name"],
            "api_base_url": environment["api_base_url"],
        },
        "suite_path": storage.store_path(artifacts["suite_path"]) or str(artifacts["suite_path"]),
        "test_file_path": storage.store_path(artifacts["test_file_path"]) or str(artifacts["test_file_path"]),
        "data_file_path": storage.store_path(artifacts["data_file_path"]) or str(artifacts["data_file_path"]),
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
            command_summary=f"python -m pytest {relative_test_path} --json-report",
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


def get_api_scenario_run_result(project_id: str, run_id: str, actor) -> dict:
    run = get_api_run(project_id, run_id, actor)
    if run["target_type"] != "scenario":
        raise api_error(409, "API_RUN_NOT_SCENARIO", "当前运行记录不是接口场景运行。")
    path = storage.resolve_stored_path(run["scenario_result_path"])
    if path is None or not path.exists():
        raise api_error(404, "API_SCENARIO_RUN_RESULT_NOT_FOUND", "接口场景步骤结果不存在。")
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
        result = _serialize_scenario(row, [])
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="create",
        object_type="api_scenario",
        object_id=scenario_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"创建接口场景：{payload.name}",
        after={"name": payload.name, "description": payload.description},
    )
    return result


def update_api_scenario(project_id: str, scenario_id: str, payload: ApiScenarioIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        existing_data = _serialize_scenario(scenario, [])
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
        result = _serialize_scenario(db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone(), [_serialize_scenario_step(step) for step in steps])
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="update",
        object_type="api_scenario",
        object_id=scenario_id,
        object_name=payload.name,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"更新接口场景：{payload.name}",
        before={"name": existing_data.get("name"), "description": existing_data.get("description")},
        after={"name": payload.name, "description": payload.description},
    )
    return result


def save_api_scenario_version(
    project_id: str,
    scenario_id: str,
    payload: ApiScenarioVersionSaveIn,
    actor,
) -> dict:
    """Atomically save the editor state as the current runnable version."""
    _require_admin(actor)
    step_ids = [step.id for step in payload.steps if step.id]
    if len(step_ids) != len(set(step_ids)):
        raise api_error(400, "API_SCENARIO_STEP_ID_DUPLICATE", "场景步骤 ID 不能重复。")
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_scenario(db, project_id, scenario_id)
        prepared = [_prepare_scenario_step(db, project_id, step, index) for index, step in enumerate(payload.steps)]
        db.execute(
            """
            UPDATE api_scenarios
            SET name = ?, description = ?, variables_json = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.name,
                payload.description,
                api_automation_repo.dumps_json(payload.variables),
                actor["id"],
                scenario_id,
            ),
        )
        db.execute("DELETE FROM api_scenario_steps WHERE scenario_id = ?", (scenario_id,))
        for step in prepared:
            _insert_scenario_step(db, scenario_id, project_id, step)
        scenario = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        steps = [_serialize_scenario_step(row) for row in _list_scenario_step_rows(db, scenario_id)]
        validation = _validate_scenario_definition(db, scenario, steps)
        if not validation["valid"]:
            raise api_error(409, "API_SCENARIO_INVALID", "；".join(validation["errors"]))
        return _create_scenario_version(db, scenario, steps, actor)


def delete_api_scenario(project_id: str, scenario_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        existing_data = _serialize_scenario(scenario, [])
        db.execute("DELETE FROM api_scenarios WHERE id = ?", (scenario_id,))
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="delete",
        object_type="api_scenario",
        object_id=scenario_id,
        object_name=existing_data.get("name"),
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除接口场景：{existing_data.get('name')}",
        before={"name": existing_data.get("name"), "description": existing_data.get("description")},
    )


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
        serialized_steps = [_serialize_scenario_step(step) for step in steps]
        return _serialize_scenario(row, serialized_steps, asset_changes=_list_scenario_asset_changes(db, row, serialized_steps))


def enqueue_api_scenario_ai_plan(project_id: str, payload: ApiScenarioAiPlanIn, actor) -> dict:
    """Persist an AI orchestration task before its generation work starts."""
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, payload.scenario_id) if payload.scenario_id else None
        endpoints = _select_orchestration_endpoints(api_automation_repo.list_endpoints(db, project_id), payload)
        if not endpoints:
            raise api_error(422, "API_SCENARIO_AI_NO_ASSETS", "当前范围内没有可用的接口资产。")
        if scenario:
            active = db.execute(
                """
                SELECT id, created_at FROM api_scenario_ai_plans
                WHERE project_id = ? AND scenario_id = ? AND lifecycle_status = 'generating'
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id, payload.scenario_id),
            ).fetchone()
            if active and _ai_plan_generation_timed_out(active["created_at"]):
                db.execute(
                    """
                    UPDATE api_scenario_ai_plans
                    SET lifecycle_status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND lifecycle_status = 'generating'
                    """,
                    (_ai_plan_timeout_message(), active["id"]),
                )
                active = None
            if active:
                return {
                    "plan_id": active["id"],
                    "scenario_id": payload.scenario_id,
                    "lifecycle_status": "generating",
                    "created": False,
                }

        plan_id = f"aiplan-{secrets.token_hex(8)}"
        expires_at = datetime.now(UTC) + timedelta(minutes=30)
        db.execute(
            """
            INSERT INTO api_scenario_ai_plans
              (id, project_id, scenario_id, expected_revision, goal, request_json, status,
               lifecycle_status, created_by, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, 'preview', 'generating', ?, ?)
            """,
            (
                plan_id,
                project_id,
                payload.scenario_id,
                int(scenario["revision"]) if scenario else None,
                _redact_orchestration_text(payload.goal),
                api_automation_repo.dumps_json(payload.model_dump()),
                actor["id"],
                expires_at.isoformat(),
            ),
        )
    return {
        "plan_id": plan_id,
        "scenario_id": payload.scenario_id,
        "lifecycle_status": "generating",
        "created": True,
    }


def submit_api_scenario_ai_plan(
    project_id: str,
    payload: ApiScenarioAiPlanIn,
    actor,
    *,
    plan_id: str,
) -> bool:
    return orchestration_job_runner.submit(
        plan_id,
        execute_api_scenario_ai_plan,
        project_id,
        payload,
        dict(actor),
        plan_id=plan_id,
    )


def execute_api_scenario_ai_plan(
    project_id: str,
    payload: ApiScenarioAiPlanIn,
    actor,
    *,
    plan_id: str,
) -> dict | None:
    started_at = time.monotonic()
    try:
        with connect() as db:
            _require_visible_project(db, project_id, actor)
            scenario = _require_scenario(db, project_id, payload.scenario_id) if payload.scenario_id else None
            endpoints = _select_orchestration_endpoints(api_automation_repo.list_endpoints(db, project_id), payload)
            if not endpoints:
                raise ValueError("当前范围内没有可用的接口资产。")
            endpoint_context = [_serialize_endpoint(endpoint) for endpoint in endpoints]
            environment_row = None
            if payload.constraints.environment_id:
                environment_row = api_automation_repo.find_api_environment(db, payload.constraints.environment_id)
                if not environment_row or environment_row["project_id"] != project_id:
                    raise ValueError("接口环境不存在。")
            environment_projection = environment_schema_projection(environment_row)
            expected_revision = int(scenario["revision"]) if scenario else None
            assets_hash = endpoint_fingerprint(endpoint_context)
            row = db.execute(
                "SELECT expires_at FROM api_scenario_ai_plans WHERE id = ? AND project_id = ?",
                (plan_id, project_id),
            ).fetchone()
            if not row:
                return None
            expires_at = str(row["expires_at"])

        try:
            selection = resolve_model_selection("api_scenario_orchestration")
        except (KeyError, ValueError):
            selection = resolve_model_selection("api_test_generation")
        model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
        planner = ApiScenarioPlanner(model)
        snapshot = {
            "goal": _redact_orchestration_text(payload.goal),
            "constraints": payload.constraints.model_dump(),
            "current_scenario_revision": expected_revision,
            "endpoint_catalog": [endpoint_summary(endpoint) for endpoint in endpoint_context],
            "environment_schema": environment_projection,
        }
        proposal = asyncio.run(planner.plan(snapshot))
        review = build_review_plan(
            proposal,
            endpoint_context,
            environment_projection,
            plan_id=plan_id,
            scenario_id=payload.scenario_id,
            expected_revision=expected_revision,
            asset_fingerprint=assets_hash,
            expires_at=expires_at,
        )
        compiled = compile_review_plan(
            review,
            endpoint_context,
            environment_projection,
            require_cleanup=payload.constraints.require_cleanup,
        )
        compiled_validation = _validate_ai_plan(project_id, compiled, endpoint_context)
        review_data = review.model_dump(mode="json")
        review_data["validation"] = {
            "valid": bool(review.validation.get("valid")) and bool(compiled_validation.get("valid")),
            "errors": [*review.validation.get("errors", []), *compiled_validation.get("errors", [])],
            "warnings": [*review.validation.get("warnings", []), *compiled_validation.get("warnings", [])],
        }
        review = ApiScenarioAiReviewPlan.model_validate(review_data)
        compiled_response = {
            "plan_id": plan_id,
            "plan_version": 2,
            "status": "preview",
            "compiler_version": COMPILER_VERSION,
            "asset_fingerprint": assets_hash,
            "environment_schema": environment_projection,
            **compiled.model_dump(),
            "validation": compiled_validation,
            "expected_revision": expected_revision,
            "expires_at": expires_at,
        }
        generation_meta = {
            "stage": "completed",
            "model_call_count": planner.model_call_count,
            "total_duration_ms": round((time.monotonic() - started_at) * 1000),
        }
        with connect() as db:
            cursor = db.execute(
                """
                UPDATE api_scenario_ai_plans
                SET proposal_json = ?, review_json = ?, plan_json = ?, validation_json = ?,
                    generation_meta_json = ?, asset_fingerprint = ?, model_provider = ?, model_name = ?,
                    lifecycle_status = 'completed', error_message = '', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND lifecycle_status = 'generating'
                """,
                (
                    api_automation_repo.dumps_json(proposal.model_dump(mode="json")),
                    api_automation_repo.dumps_json(review.model_dump(mode="json")),
                    api_automation_repo.dumps_json(compiled_response),
                    api_automation_repo.dumps_json(review.validation),
                    api_automation_repo.dumps_json(generation_meta),
                    assets_hash,
                    selection.provider,
                    selection.model,
                    plan_id,
                ),
            )
        return review.model_dump(mode="json") if cursor.rowcount else None
    except Exception as exc:
        with connect() as db:
            db.execute(
                """
                UPDATE api_scenario_ai_plans
                SET lifecycle_status = 'failed', error_message = ?, generation_meta_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND lifecycle_status = 'generating'
                """,
                (
                    str(exc),
                    api_automation_repo.dumps_json(
                        {
                            "stage": "failed",
                            "total_duration_ms": round((time.monotonic() - started_at) * 1000),
                        }
                    ),
                    plan_id,
                ),
            )
        return None

def create_api_scenario_ai_plan(
    project_id: str,
    payload: ApiScenarioAiPlanIn,
    actor,
    *,
    existing_plan_id: str | None = None,
):
    """Generate a validated, non-executable scenario draft from project endpoint assets."""
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, payload.scenario_id) if payload.scenario_id else None
        endpoints = _select_orchestration_endpoints(api_automation_repo.list_endpoints(db, project_id), payload)
        if not endpoints:
            raise api_error(422, "API_SCENARIO_AI_NO_ASSETS", "当前范围内没有可用的接口资产。")
        endpoint_context = [_serialize_endpoint(endpoint) for endpoint in endpoints[:100]]
        environment_row = None
        if payload.constraints.environment_id:
            environment_row = api_automation_repo.find_api_environment(db, payload.constraints.environment_id)
            if not environment_row or environment_row["project_id"] != project_id:
                raise api_error(404, "API_ENVIRONMENT_NOT_FOUND", "接口环境不存在。")
        environment_projection = environment_schema_projection(environment_row)
        expected_revision = int(scenario["revision"]) if scenario else None
        assets_hash = endpoint_fingerprint(endpoint_context)

    plan_id = existing_plan_id or f"aiplan-{secrets.token_hex(8)}"
    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    redacted_goal = _redact_orchestration_text(payload.goal)
    request_data = {
        **payload.model_dump(),
        "asset_fingerprint": assets_hash,
        "environment_schema": environment_projection,
    }
    if existing_plan_id is None:
        with connect() as db:
            db.execute(
                """
                INSERT INTO api_scenario_ai_plans
                  (id, project_id, scenario_id, expected_revision, goal, request_json, status,
                   lifecycle_status, created_by, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, 'preview', 'generating', ?, ?)
                """,
                (
                    plan_id,
                    project_id,
                    payload.scenario_id,
                    expected_revision,
                    redacted_goal,
                    api_automation_repo.dumps_json(request_data),
                    actor["id"],
                    expires_at.isoformat(),
                ),
            )

    try:
        selection = resolve_model_selection("api_scenario_orchestration")
    except (KeyError, ValueError):
        try:
            selection = resolve_model_selection("api_test_generation")
        except Exception as exc:
            _fail_api_scenario_ai_plan(plan_id, exc)
            raise api_error(503, "API_SCENARIO_AI_PLAN_FAILED", f"AI 编排计划生成失败：{exc}") from exc
    try:
        prompt = json.dumps(
            {
                "goal": redacted_goal,
                "constraints": payload.constraints.model_dump(),
                "current_scenario_revision": expected_revision,
                "endpoint_catalog": [endpoint_summary(endpoint) for endpoint in endpoint_context],
                "environment_schema": environment_projection,
                "instructions": "接口详情由服务端编译器核验。只能使用目录中的 endpoint_id，不要猜测字段路径；无法确定时写入 unresolved_items。",
            },
            ensure_ascii=False,
        )
        result = asyncio.run(
            api_scenario_orchestration_agent(
                build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
            ).ainvoke({"messages": [{"role": "user", "content": prompt}]})
        )
        structured = result.get("structured_response") if isinstance(result, dict) else None
        semantic_plan = structured if isinstance(structured, ScenarioPlanResult) else ScenarioPlanResult.model_validate(structured)
        plan = compile_plan(
            semantic_plan,
            endpoint_context,
            environment_projection,
            require_cleanup=payload.constraints.require_cleanup,
        )
    except Exception as exc:
        _fail_api_scenario_ai_plan(plan_id, exc)
        raise api_error(503, "API_SCENARIO_AI_PLAN_FAILED", f"AI 编排计划生成失败：{exc}") from exc

    validation = _validate_ai_plan(project_id, plan, endpoint_context)
    if plan.unresolved_items:
        validation["warnings"].extend(f"未解决：{item}" for item in plan.unresolved_items)
    validation["errors"] = _dedupe_validation_messages(validation["errors"])
    validation["warnings"] = _dedupe_validation_messages(validation["warnings"])
    validation["valid"] = not validation["errors"] and not plan.unresolved_items
    response = {
        "plan_id": plan_id,
        "plan_version": 2,
        "status": "preview",
        "compiler_version": COMPILER_VERSION,
        "asset_fingerprint": assets_hash,
        "environment_schema": environment_projection,
        **plan.model_dump(),
        "validation": validation,
        "expected_revision": expected_revision,
        "expires_at": expires_at.isoformat(),
    }
    with connect() as db:
        db.execute(
            """
            UPDATE api_scenario_ai_plans
            SET request_json = ?, plan_json = ?, validation_json = ?, model_provider = ?, model_name = ?,
                lifecycle_status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND lifecycle_status = 'generating'
            """,
            (
                api_automation_repo.dumps_json(request_data),
                api_automation_repo.dumps_json(response),
                api_automation_repo.dumps_json(validation),
                selection.provider,
                selection.model,
                plan_id,
            ),
        )
    return response


def _fail_api_scenario_ai_plan(plan_id: str, error: Exception) -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE api_scenario_ai_plans
            SET lifecycle_status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (str(error), plan_id),
        )


def get_api_scenario_ai_plan(project_id: str, plan_id: str, actor) -> dict:
    """Recover a persisted preview without replaying an AI request after page refresh."""
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = db.execute("SELECT * FROM api_scenario_ai_plans WHERE id = ? AND project_id = ?", (plan_id, project_id)).fetchone()
        if not row:
            raise api_error(404, "API_SCENARIO_AI_PLAN_NOT_FOUND", "AI 编排计划不存在。")
        lifecycle_status = str(row["lifecycle_status"])
        if lifecycle_status != "completed":
            response = {
                "plan_id": plan_id,
                "scenario_id": row["scenario_id"],
                "lifecycle_status": lifecycle_status,
            }
            if lifecycle_status == "failed":
                meta = api_automation_repo.loads_json(row["generation_meta_json"], {})
                response["error"] = {
                    "stage": meta.get("stage", "failed"),
                    "code": "API_SCENARIO_AI_PLAN_FAILED",
                    "message": row["error_message"],
                }
            return response
        review = api_automation_repo.loads_json(row["review_json"], {})
        if review:
            return review
        status = str(row["status"])
        if status == "preview" and datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) <= datetime.now(UTC):
            db.execute("UPDATE api_scenario_ai_plans SET status = 'expired' WHERE id = ?", (plan_id,))
            status = "expired"
        plan = api_automation_repo.loads_json(row["plan_json"], {})
        plan["status"] = status
        return plan


def save_api_scenario_ai_plan_review(
    project_id: str,
    plan_id: str,
    payload: ApiScenarioAiReviewSaveIn,
    actor,
) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = db.execute(
            "SELECT * FROM api_scenario_ai_plans WHERE id = ? AND project_id = ?",
            (plan_id, project_id),
        ).fetchone()
        if not row:
            raise api_error(404, "API_SCENARIO_AI_PLAN_NOT_FOUND", "AI 编排计划不存在。")
        if row["lifecycle_status"] != "completed" or row["status"] != "preview":
            raise api_error(409, "API_SCENARIO_AI_PLAN_NOT_REVIEWABLE", "当前 AI 编排计划不可编辑。")
        current_revision = int(row["review_revision"] or 0)
        if current_revision != payload.expected_review_revision:
            raise api_error(409, "API_SCENARIO_AI_REVIEW_CONFLICT", "AI 编排审阅内容已更新，请刷新后重试。")
        review_data = api_automation_repo.loads_json(row["review_json"], {})
        if not review_data:
            raise api_error(409, "API_SCENARIO_AI_REVIEW_MISSING", "AI 编排计划缺少审阅数据，请重新生成。")
        review = ApiScenarioAiReviewPlan.model_validate(review_data)
        request_payload = ApiScenarioAiPlanIn.model_validate(api_automation_repo.loads_json(row["request_json"], {}))
        endpoints = _select_orchestration_endpoints(api_automation_repo.list_endpoints(db, project_id), request_payload)
        endpoint_context = [_serialize_endpoint(endpoint) for endpoint in endpoints]
        environment_row = None
        if request_payload.constraints.environment_id:
            environment_row = api_automation_repo.find_api_environment(db, request_payload.constraints.environment_id)
        environment_projection = environment_schema_projection(environment_row)

    saved_steps = {step.step_id: step for step in payload.steps}
    if set(saved_steps) != {step.step_id for step in review.steps}:
        raise api_error(422, "API_SCENARIO_AI_REVIEW_STEPS_INVALID", "审阅保存必须包含当前计划的全部步骤。")
    next_steps = []
    for step in review.steps:
        saved_step = saved_steps[step.step_id]
        field_updates = {field.field_id: field for field in saved_step.fields}
        current_fields = [field for group in step.field_groups for field in group.fields]
        if set(field_updates) != {field.field_id for field in current_fields}:
            raise api_error(422, "API_SCENARIO_AI_REVIEW_FIELDS_INVALID", f"步骤 {step.step_id} 必须包含全部审阅字段。")
        step_data = step.model_dump(mode="json")
        step_data["order"] = saved_step.order
        for group in step_data["field_groups"]:
            for field in group["fields"]:
                update = field_updates[field["field_id"]]
                field["resolved"] = update.resolved.model_dump(mode="json", exclude_none=True) if update.resolved else None
                field["status"] = update.status
        next_steps.append(step_data)

    next_review_data = review.model_dump(mode="json")
    next_review_data["steps"] = next_steps
    next_review_data["review_revision"] = current_revision + 1
    next_review_data["asset_fingerprint"] = endpoint_fingerprint(endpoint_context)
    provisional_review = ApiScenarioAiReviewPlan.model_validate(next_review_data)
    compiled = compile_review_plan(
        provisional_review,
        endpoint_context,
        environment_projection,
        require_cleanup=request_payload.constraints.require_cleanup,
    )
    compiled_validation = _validate_ai_plan(project_id, compiled, endpoint_context)
    review_validation = validate_review_plan(provisional_review, endpoint_context)
    next_review_data["validation"] = {
        "valid": bool(review_validation["valid"]) and bool(compiled_validation["valid"]),
        "errors": [*review_validation["errors"], *compiled_validation["errors"]],
        "warnings": [*review_validation["warnings"], *compiled_validation["warnings"]],
    }
    saved_review = ApiScenarioAiReviewPlan.model_validate(next_review_data)
    compiled_response = {
        "plan_id": plan_id,
        "plan_version": 2,
        "status": "preview",
        "compiler_version": COMPILER_VERSION,
        "asset_fingerprint": saved_review.asset_fingerprint,
        "environment_schema": environment_projection,
        **compiled.model_dump(),
        "validation": compiled_validation,
        "expected_revision": saved_review.expected_revision,
        "expires_at": saved_review.expires_at,
    }
    with connect() as db:
        cursor = db.execute(
            """
            UPDATE api_scenario_ai_plans
            SET review_json = ?, review_revision = ?, plan_json = ?, validation_json = ?,
                asset_fingerprint = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND project_id = ? AND review_revision = ?
            """,
            (
                api_automation_repo.dumps_json(saved_review.model_dump(mode="json")),
                saved_review.review_revision,
                api_automation_repo.dumps_json(compiled_response),
                api_automation_repo.dumps_json(saved_review.validation),
                saved_review.asset_fingerprint,
                plan_id,
                project_id,
                current_revision,
            ),
        )
        if cursor.rowcount != 1:
            raise api_error(409, "API_SCENARIO_AI_REVIEW_CONFLICT", "AI 编排审阅内容已更新，请刷新后重试。")
    return saved_review.model_dump(mode="json")


def apply_api_scenario_ai_plan(project_id: str, plan_id: str, payload: ApiScenarioAiPlanApplyIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = db.execute("SELECT * FROM api_scenario_ai_plans WHERE id = ? AND project_id = ?", (plan_id, project_id)).fetchone()
        if not row:
            raise api_error(404, "API_SCENARIO_AI_PLAN_NOT_FOUND", "AI 编排计划不存在。")
        if row["status"] != "preview":
            raise api_error(409, "API_SCENARIO_AI_PLAN_NOT_APPLICABLE", "AI 编排计划已被处理。")
        if datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")) <= datetime.now(UTC):
            db.execute("UPDATE api_scenario_ai_plans SET status = 'expired' WHERE id = ?", (plan_id,))
            raise api_error(409, "API_SCENARIO_AI_PLAN_EXPIRED", "AI 编排计划已过期，请重新生成。")
        scenario = _require_scenario(db, project_id, payload.scenario_id)
        review_data = api_automation_repo.loads_json(row["review_json"], {})
        if review_data:
            if int(row["review_revision"] or 0) != payload.expected_review_revision:
                raise api_error(409, "API_SCENARIO_AI_REVIEW_CONFLICT", "AI 编排审阅内容已更新，请刷新后重试。")
            review = ApiScenarioAiReviewPlan.model_validate(review_data)
            request_payload = ApiScenarioAiPlanIn.model_validate(api_automation_repo.loads_json(row["request_json"], {}))
            endpoints = _select_orchestration_endpoints(api_automation_repo.list_endpoints(db, project_id), request_payload)
            endpoint_context = [_serialize_endpoint(endpoint) for endpoint in endpoints]
            review_validation = validate_review_plan(review, endpoint_context, for_apply=True)
            if not review_validation["valid"]:
                raise api_error(409, "API_SCENARIO_AI_REVIEW_PENDING", review_validation["errors"][0])
            if int(scenario["revision"]) != int(row["expected_revision"] or 0):
                raise api_error(409, "API_SCENARIO_AI_SCENARIO_CONFLICT", "场景草稿已更新，请重新生成或确认最新版本。")
            current_fingerprint = endpoint_fingerprint(endpoint_context)
            if row["asset_fingerprint"] and current_fingerprint != row["asset_fingerprint"]:
                raise api_error(409, "API_SCENARIO_AI_ASSET_CONFLICT", "接口资产已更新，请重新生成。")
        plan = api_automation_repo.loads_json(row["plan_json"], {})
        if not plan.get("validation", {}).get("valid"):
            raise api_error(409, "API_SCENARIO_AI_PLAN_INVALID", "AI 编排计划未通过服务端校验。")
        variables = api_automation_repo.loads_json(scenario["variables_json"], {})
        for plan_input in plan.get("inputs", []):
            name = str(plan_input.get("name") or "").strip()
            if name and not plan_input.get("sensitive") and name not in variables:
                variables[name] = plan_input.get("default_value")
        db.execute(
            "UPDATE api_scenarios SET variables_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (api_automation_repo.dumps_json(variables), payload.scenario_id),
        )
        steps = [_ai_plan_node_to_step(node, index) for index, node in enumerate(plan.get("nodes", []))]
        version_payload = ApiScenarioVersionSaveIn(
            name=scenario["name"],
            description=scenario["description"],
            variables=variables,
            steps=steps,
        )
    result = save_api_scenario_version(project_id, payload.scenario_id, version_payload, actor)
    with connect() as db:
        db.execute(
            "UPDATE api_scenario_ai_plans SET status = 'applied', applied_by = ?, applied_at = CURRENT_TIMESTAMP WHERE id = ?",
            (actor["id"], plan_id),
        )
    return result


def _redact_orchestration_assets(endpoints: list[dict]) -> list[dict]:
    return [
        {
            "id": endpoint["id"],
            "method": endpoint["method"],
            "path": endpoint["path"],
            "summary": endpoint.get("summary", ""),
            "description": endpoint.get("description", ""),
            "tags": endpoint.get("tags", []),
            "parameters": endpoint.get("parameters", []),
            "request_body": endpoint.get("request_body", {}),
            "responses": endpoint.get("responses", {}),
            "auth": {"required": bool(endpoint.get("auth"))},
        }
        for endpoint in endpoints
    ]


def _redact_orchestration_text(value: str) -> str:
    """Keep intent while ensuring header-like credentials do not enter model or plan storage."""
    patterns = (
        r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)\S+",
        r"(?i)(cookie\s*[:=]\s*)\S+",
        r"(?i)((?:token|secret|password|api[_-]?key)\s*[:=]\s*)\S+",
    )
    redacted = value
    for pattern in patterns:
        redacted = re.sub(pattern, r"\1[REDACTED]", redacted)
    return redacted


def _validate_ai_plan(project_id: str, plan: ScenarioPlanResult, endpoints: list[dict]) -> dict:
    errors: list[str] = []
    warnings = list(plan.warnings)
    endpoint_by_id = {endpoint["id"]: endpoint for endpoint in endpoints}
    node_ids = {node.id for node in plan.nodes}
    if not plan.nodes:
        errors.append("AI 计划至少需要一个步骤。")
    if len(node_ids) != len(plan.nodes):
        errors.append("AI 计划存在重复节点 ID。")
    for node in plan.nodes:
        if node.type == "api_request":
            if not node.endpoint_id or node.endpoint_id not in endpoint_by_id:
                errors.append(f"节点 {node.name or node.id} 引用了无效接口资产。")
            else:
                _validate_ai_node_bindings(node, endpoint_by_id[node.endpoint_id], errors)
        elif node.endpoint_id:
            errors.append(f"工具节点 {node.name or node.id} 不允许绑定接口资产。")
        if _contains_executable_url(node.request_overrides):
            errors.append(f"节点 {node.name or node.id} 不允许携带 AI 生成的 URL。")
    prior_outputs: dict[str, set[str]] = {}
    all_ids = {node.id for node in plan.nodes}
    for node in plan.nodes:
        output_names = {extractor.name for extractor in node.extractors}
        if node.type == "assign":
            name = str(node.control_config.get("name") or "")
            if name:
                output_names.add(name)
        sources = [binding.source for binding in node.bindings]
        if node.type in {"condition", "assign"} and isinstance(node.control_config.get("source"), dict):
            sources.append(node.control_config["source"])
        for source in (nested for root in sources for nested in _iter_scenario_sources(root)):
            source_type = source.type if hasattr(source, "type") else source.get("type") if isinstance(source, dict) else None
            if source_type != "step_output":
                continue
            source_step_id = str(source.step_id if hasattr(source, "step_id") else source.get("step_id", ""))
            variable = str(source.variable if hasattr(source, "variable") else source.get("variable", ""))
            if source_step_id not in prior_outputs:
                detail = "引用了后续步骤输出" if source_step_id in all_ids else "引用了不存在的步骤"
                errors.append(f"节点 {node.id} 的变量来源 {detail}：{source_step_id}.{variable}。")
            elif variable not in prior_outputs[source_step_id]:
                errors.append(f"节点 {node.id} 引用了步骤 {source_step_id} 未输出的变量 {variable}。")
        prior_outputs[node.id] = output_names
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in plan.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            errors.append("AI 计划存在悬空连线。")
            continue
        if edge.target not in adjacency[edge.source]:
            adjacency[edge.source].add(edge.target)
            indegree[edge.target] += 1
    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node_id = ready.pop()
        visited += 1
        for target in adjacency[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(node_ids):
        errors.append("AI 计划不能包含循环依赖。")
    if plan.unresolved_items:
        warnings.extend(f"未解决：{item}" for item in plan.unresolved_items)
    return {"valid": not errors and not plan.unresolved_items, "errors": errors, "warnings": warnings}


def _contains_executable_url(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {"url", "base_url", "baseurl"} and item:
                return True
            if _contains_executable_url(item):
                return True
    elif isinstance(value, list):
        return any(_contains_executable_url(item) for item in value)
    elif isinstance(value, str):
        return value.strip().lower().startswith(("http://", "https://"))
    return False


def _validate_ai_node_bindings(node, endpoint: dict, errors: list[str]) -> None:
    seen_targets: list[tuple[str, str]] = []
    for binding in node.bindings:
        location = binding.target.location
        path = binding.target.path
        for seen_location, seen_path in seen_targets:
            if seen_location == location and _json_pointer_overlaps(seen_path, path):
                errors.append(f"节点 {node.name or node.id} 的绑定目标重复或重叠：{location}{path}。")
                break
        seen_targets.append((location, path))
        schema = _endpoint_target_schema(endpoint, location, path)
        if schema is None:
            if endpoint.get("parameters") or endpoint.get("request_body"):
                errors.append(f"节点 {node.name or node.id} 的绑定目标不在接口资产中：{location}{path}。")
            continue
        enum_values = schema.get("enum")
        if not isinstance(enum_values, list) or len(enum_values) != 1:
            continue
        expected = enum_values[0]
        source = binding.source
        if source.type != "literal" or source.value != expected:
            field_name = path.rsplit("/", 1)[-1].replace("~1", "/").replace("~0", "~")
            errors.append(f"节点 {node.name or node.id} 的字段 {field_name} 必须使用固定值 {expected}。")


def _endpoint_target_schema(endpoint: dict, location: str, path: str) -> dict | None:
    if location in {"path", "query", "header", "cookie"}:
        name = path.removeprefix("/").replace("~1", "/").replace("~0", "~")
        for parameter in endpoint.get("parameters") or []:
            if parameter.get("in") == location and str(parameter.get("name") or "") == name:
                schema = parameter.get("schema")
                return schema if isinstance(schema, dict) else parameter
        return None
    request_body = endpoint.get("request_body") or {}
    content = request_body.get("content") if isinstance(request_body, dict) else {}
    media_type = {
        "json_body": "application/json",
        "form": "application/x-www-form-urlencoded",
        "multipart": "multipart/form-data",
    }.get(location)
    schema = (content or {}).get(media_type, {}).get("schema") if media_type else request_body.get("schema")
    if not isinstance(schema, dict):
        return None
    current = schema
    for part in [item.replace("~1", "/").replace("~0", "~") for item in path.split("/") if item]:
        properties = current.get("properties") if isinstance(current, dict) else None
        if not isinstance(properties, dict) or part not in properties:
            return None
        current = properties[part]
        if isinstance(current, dict) and isinstance(current.get("x-json-schema"), dict):
            current = current["x-json-schema"]
    return current if isinstance(current, dict) else None


def _json_pointer_overlaps(first: str, second: str) -> bool:
    first_parts = [part for part in first.split("/") if part]
    second_parts = [part for part in second.split("/") if part]
    shorter = min(len(first_parts), len(second_parts))
    return first_parts[:shorter] == second_parts[:shorter]


def _ai_plan_node_to_step(node: dict, step_order: int) -> ApiScenarioStepIn:
    return ApiScenarioStepIn(
        id=node["id"],
        step_type=node["type"],
        endpoint_id=node.get("endpoint_id"),
        step_order=step_order,
        name=node.get("name", ""),
        request_overrides=node.get("request_overrides", {}),
        bindings=node.get("bindings", []),
        extractors=node.get("extractors", []),
        assertions=node.get("assertions", []),
        control_config=node.get("control_config", {}),
        on_failure=node.get("on_failure", "stop"),
        enabled=node.get("enabled", True),
    )


def _ai_plan_node_to_step_dict(node: dict, step_order: int, project_id: str, scenario_id: str) -> dict:
    step = _ai_plan_node_to_step(node, step_order)
    return {
        **step.model_dump(exclude={"bindings", "extractors", "assertions", "control_config"}),
        "bindings": [binding_to_runtime(binding) for binding in step.bindings],
        "extractors": [extractor_to_runtime(extractor) for extractor in step.extractors],
        "assertions": [assertion.model_dump(exclude_none=True) for assertion in step.assertions],
        "control_config": control_config_to_runtime(step.step_type, step.control_config),
        "id": step.id or f"ai-step-{step_order}",
        "project_id": project_id,
        "scenario_id": scenario_id,
    }


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
        result = _serialize_scenario_step(row)
    operation_log_service.record_change(
        log_type="audit",
        module="api_automation",
        action="create",
        object_type="api_scenario_step",
        object_id=step_id,
        object_name=f"步骤 {payload.step_order}",
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"在场景 {scenario['name']} 中添加步骤：{payload.step_order}",
        after={"scenario_id": scenario_id, "step_order": payload.step_order},
    )
    return result


def validate_api_scenario(project_id: str, scenario_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        steps = [_serialize_scenario_step(row) for row in _list_scenario_step_rows(db, scenario_id)]
        return _validate_scenario_definition(db, scenario, steps)


def publish_api_scenario(project_id: str, scenario_id: str, actor, *, confirm_asset_changes: bool = False) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        scenario = _require_scenario(db, project_id, scenario_id)
        steps = [_serialize_scenario_step(row) for row in _list_scenario_step_rows(db, scenario_id)]
        validation = _validate_scenario_definition(db, scenario, steps)
        if not validation["valid"]:
            raise api_error(409, "API_SCENARIO_INVALID", "；".join(validation["errors"]))
        asset_changes = _list_scenario_asset_changes(db, scenario, steps)
        if asset_changes and not confirm_asset_changes:
            raise api_error(409, "API_SCENARIO_ASSET_CHANGES_UNCONFIRMED", "接口资产已变化，请确认差异后重新发布。")
        return _create_scenario_version(db, scenario, steps, actor)


def list_api_scenario_revisions(project_id: str, scenario_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_scenario(db, project_id, scenario_id)
        rows = db.execute(
            """
            SELECT revision, snapshot_json, published_hash, created_by, created_at
            FROM api_scenario_revisions
            WHERE scenario_id = ? AND project_id = ?
            ORDER BY revision DESC
            LIMIT ?
            """,
            (scenario_id, project_id, MAX_API_SCENARIO_VERSIONS),
        ).fetchall()
        return [
            {
                "revision": row["revision"],
                "published_hash": row["published_hash"],
                "created_by": row["created_by"],
                "created_at": row["created_at"],
                "step_count": len(api_automation_repo.loads_json(row["snapshot_json"], {}).get("steps", [])),
                "snapshot": api_automation_repo.loads_json(row["snapshot_json"], {}),
            }
            for row in rows
        ]


def restore_api_scenario_revision(project_id: str, scenario_id: str, revision: int, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        _require_scenario(db, project_id, scenario_id)
        row = db.execute(
            """
            SELECT snapshot_json
            FROM api_scenario_revisions
            WHERE scenario_id = ? AND project_id = ? AND revision = ?
            """,
            (scenario_id, project_id, revision),
        ).fetchone()
        if not row:
            raise api_error(404, "API_SCENARIO_REVISION_NOT_FOUND", "接口场景版本不存在。")
        snapshot = api_automation_repo.loads_json(row["snapshot_json"], {})
        db.execute(
            """
            UPDATE api_scenarios
            SET name = ?, description = ?, variables_json = ?,
                updated_by = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                snapshot.get("name", ""),
                snapshot.get("description", ""),
                api_automation_repo.dumps_json(snapshot.get("variables", {})),
                actor["id"],
                scenario_id,
            ),
        )
        db.execute("DELETE FROM api_scenario_steps WHERE scenario_id = ?", (scenario_id,))
        for index, step in enumerate(snapshot.get("steps", [])):
            _insert_scenario_step(
                db,
                scenario_id,
                project_id,
                {
                    "id": step.get("id") or f"apistep-{secrets.token_hex(8)}",
                    "step_type": step.get("step_type", "api_request"),
                    "endpoint_id": step.get("endpoint_id"),
                    "api_test_case_id": step.get("api_test_case_id"),
                    "step_order": index,
                    "name": step.get("name", ""),
                    "request_overrides": step.get("request_overrides", {}),
                    "bindings": step.get("bindings", []),
                    "extractors": step.get("extractors", []),
                    "assertions": step.get("assertions", []),
                    "control_config": step.get("control_config", {}),
                    "on_failure": step.get("on_failure", "stop"),
                    "enabled": bool(step.get("enabled", True)),
                },
            )
        scenario = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario_id,)).fetchone()
        steps = [_serialize_scenario_step(step) for step in _list_scenario_step_rows(db, scenario_id)]
        return _create_scenario_version(db, scenario, steps, actor)


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
        db.execute(
            """
            UPDATE api_script_generation_runs
            SET status = 'interrupted',
                error_message = '服务已重启，接口 pytest 脚本生成任务已中断，请重新生成。',
                updated_at = CURRENT_TIMESTAMP,
                finished_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'running')
            """
        )
        db.execute(
            """
            UPDATE api_scenario_ai_plans
            SET lifecycle_status = 'failed',
                error_message = '服务已重启，内存中的 AI 编排后台任务已中断，请重新生成。',
                updated_at = CURRENT_TIMESTAMP
            WHERE lifecycle_status = 'generating'
            """
        )


def _select_orchestration_endpoints(endpoints: list[Row], payload: ApiScenarioAiPlanIn) -> list[Row]:
    allowed_ids = set(payload.source_scope.endpoint_ids)
    selected = [endpoint for endpoint in endpoints if not allowed_ids or endpoint["id"] in allowed_ids]
    if payload.source_scope.tags:
        wanted_tags = {tag.lower() for tag in payload.source_scope.tags}
        selected = [
            endpoint
            for endpoint in selected
            if wanted_tags.intersection({tag.lower() for tag in api_automation_repo.loads_json(endpoint["tags_json"], [])})
        ]
    if allowed_ids or len(selected) <= MAX_AI_SCENARIO_CANDIDATE_ENDPOINTS:
        return selected
    return sorted(selected, key=lambda endpoint: (-_orchestration_endpoint_relevance(endpoint, payload.goal), endpoint["path"], endpoint["id"]))[
        :MAX_AI_SCENARIO_CANDIDATE_ENDPOINTS
    ]


def _orchestration_endpoint_relevance(endpoint: Row, goal: str) -> int:
    goal_text = goal.lower().strip()
    searchable = " ".join(
        [
            str(endpoint["path"]),
            str(endpoint["summary"]),
            str(endpoint["description"]),
            " ".join(api_automation_repo.loads_json(endpoint["tags_json"], [])),
        ]
    ).lower()
    score = 0
    for fragment in _orchestration_goal_fragments(goal_text):
        if fragment in searchable:
            score += len(fragment)
    return score


def _orchestration_goal_fragments(goal: str) -> set[str]:
    fragments: set[str] = set(re.findall(r"[a-z0-9_]{2,}", goal))
    for sequence in re.findall(r"[\u4e00-\u9fff]{2,}", goal):
        fragments.add(sequence)
        fragments.update(sequence[index : index + size] for size in range(2, len(sequence)) for index in range(len(sequence) - size + 1))
    return fragments


def _ai_plan_generation_timed_out(created_at: str) -> bool:
    created = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return datetime.now(UTC) - created >= AI_SCENARIO_GENERATION_TIMEOUT


def _ai_plan_timeout_message() -> str:
    return f"AI 编排任务超过 {int(AI_SCENARIO_GENERATION_TIMEOUT.total_seconds() // 60)} 分钟未完成，已自动标记为失败，请重新生成。"


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
        "auth_config": _serialize_auth_config(
            row["auth_type"], api_automation_repo.loads_json(row["auth_config_json"], {})
        ),
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
        "test_point_key": row["test_point_key"] if "test_point_key" in row.keys() else "",
        "oracle_status": row["oracle_status"] if "oracle_status" in row.keys() else "confirmed",
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


def _oracle_case_snapshot(row: Row) -> dict:
    return {
        "case_id": row["id"],
        "endpoint_id": row["endpoint_id"],
        "test_point_key": row["test_point_key"],
        "title": row["title"],
        "oracle_status": row["oracle_status"],
        "request": api_automation_repo.loads_json(row["request_json"], {}),
        "assertions": api_automation_repo.loads_json(row["assertions_json"], []),
    }


def _serialize_oracle_proposal(row: Row | None) -> dict:
    if row is None:
        raise api_error(404, "API_ORACLE_PROPOSAL_NOT_FOUND", "Oracle 建议不存在。")
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "endpoint_id": row["endpoint_id"],
        "case_id": row["case_id"],
        "run_id": row["run_id"],
        "test_point_key": row["test_point_key"],
        "status": row["status"],
        "current_snapshot": api_automation_repo.loads_json(row["current_snapshot_json"], {}),
        "proposed_snapshot": api_automation_repo.loads_json(row["proposed_snapshot_json"], {}),
        "reasoning": row["reasoning"],
        "confidence": row["confidence"],
        "review_scope": row["review_scope"],
        "review_comment": row["review_comment"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
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
    payload = {
        "generator_version": 1,
        "skill_fingerprint": pytest_requests_skill_fingerprint(),
        "endpoint": endpoint,
        "cases": cases,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _serialize_api_run(row: Row | None, db=None) -> dict:
    if row is None:
        raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
    keys = set(row.keys())
    snapshot = api_automation_repo.loads_json(
        row["execution_snapshot_json"] if "execution_snapshot_json" in keys else "{}", {}
    )
    snapshot.pop("created_by_name", None)
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
        "scenario_result_path": row["scenario_result_path"] if "scenario_result_path" in keys else "",
        "observation_result_path": row["observation_result_path"] if "observation_result_path" in keys else "",
        "parent_run_id": row["parent_run_id"] if "parent_run_id" in keys else None,
        "source_repair_attempt_id": row["source_repair_attempt_id"]
        if "source_repair_attempt_id" in keys
        else None,
        "summary": api_automation_repo.loads_json(row["summary_json"], {}),
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _serialize_scenario(row: Row, steps: list[dict], *, asset_changes: list[dict] | None = None) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
        "revision": row["revision"],
        "published_hash": row["published_hash"],
        "asset_changes": asset_changes or [],
        "steps": steps,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_scenario_step(row: Row) -> dict:
    return {
        "id": row["id"],
        "scenario_id": row["scenario_id"],
        "project_id": row["project_id"],
        "step_type": row["step_type"] or "api_request",
        "endpoint_id": row["endpoint_id"],
        "api_test_case_id": row["api_test_case_id"],
        "step_order": row["step_order"],
        "name": row["name"],
        "request_overrides": api_automation_repo.loads_json(row["request_overrides_json"], {}),
        "bindings": api_automation_repo.loads_json(row["bindings_json"], []),
        "extractors": api_automation_repo.loads_json(row["extractors_json"], []),
        "assertions": api_automation_repo.loads_json(row["assertions_json"], []),
        "control_config": api_automation_repo.loads_json(row["control_config_json"], {}),
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
    endpoint = None
    if payload.api_test_case_id:
        case = api_automation_repo.find_api_test_case(db, payload.api_test_case_id)
        if not case or case["project_id"] != project_id:
            raise api_error(400, "API_TEST_CASE_INVALID", "接口用例不存在或不属于当前项目。")
        endpoint_id = str(case["endpoint_id"] or "") or endpoint_id
    if payload.step_type == "api_request":
        if not endpoint_id:
            raise api_error(400, "API_ENDPOINT_INVALID", "接口不存在或不属于当前项目。")
        endpoint = api_automation_repo.find_endpoint(db, endpoint_id)
        if not endpoint or endpoint["project_id"] != project_id:
            raise api_error(400, "API_ENDPOINT_INVALID", "接口不存在或不属于当前项目。")
    elif endpoint_id:
        raise api_error(400, "API_SCENARIO_STEP_ENDPOINT_FORBIDDEN", "当前步骤类型不能绑定接口资产。")
    request_overrides, bindings = _canonicalize_step_bindings(payload.request_overrides, payload.bindings)
    return {
        "id": step_id or payload.id or f"apistep-{secrets.token_hex(8)}",
        "step_type": payload.step_type,
        "api_test_case_id": payload.api_test_case_id,
        "endpoint_id": endpoint_id,
        "step_order": step_order,
        "name": payload.name or (str(endpoint["summary"]) if endpoint else str(case["title"]) if case else payload.step_type),
        "request_overrides": request_overrides,
        "bindings": bindings,
        "extractors": [extractor_to_runtime(extractor) for extractor in payload.extractors],
        "assertions": [assertion.model_dump(exclude_none=True) for assertion in payload.assertions],
        "control_config": control_config_to_runtime(payload.step_type, payload.control_config),
        "on_failure": payload.on_failure,
        "enabled": payload.enabled,
    }


def _canonicalize_step_bindings(request_overrides: dict, bindings) -> tuple[dict, list[dict]]:
    normalized_overrides = api_automation_repo.loads_json(api_automation_repo.dumps_json(request_overrides), {})
    normalized_bindings: list[dict] = []
    for binding in bindings:
        runtime_binding = binding_to_runtime(binding)
        if binding.source.type == "literal":
            _set_document_pointer(normalized_overrides, runtime_binding["target"], binding.source.value)
        else:
            normalized_bindings.append(runtime_binding)
    return normalized_overrides, normalized_bindings


def _set_document_pointer(document: dict, pointer: str, value: Any) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/") if part]
    current = document
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    if parts:
        current[parts[-1]] = value


def _insert_scenario_step(db, scenario_id: str, project_id: str, step: dict) -> None:
    db.execute(
        """
        INSERT INTO api_scenario_steps (
          id, scenario_id, project_id, step_type, endpoint_id, api_test_case_id, step_order, name,
          request_overrides_json, bindings_json, extractors_json, assertions_json, control_config_json,
          on_failure, enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            step["id"], scenario_id, project_id, step["step_type"], step["endpoint_id"], step["api_test_case_id"],
            step["step_order"], step["name"], api_automation_repo.dumps_json(step["request_overrides"]),
            api_automation_repo.dumps_json(step["bindings"]), api_automation_repo.dumps_json(step["extractors"]),
            api_automation_repo.dumps_json(step["assertions"]), api_automation_repo.dumps_json(step["control_config"]),
            step["on_failure"], int(step["enabled"]),
        ),
    )


def _dedupe_validation_messages(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(messages))


SUPPORTED_SCENARIO_SOURCE_TYPES = {"environment", "scenario", "literal", "user_input", "secret", "generated", "object"}


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
        step_type = step.get("step_type", "api_request")
        config = step.get("control_config") or {}
        case_id = step.get("api_test_case_id")
        case = api_automation_repo.find_api_test_case(db, case_id) if case_id else None
        endpoint_id = step.get("endpoint_id")
        endpoint = api_automation_repo.find_endpoint(db, endpoint_id) if endpoint_id else None
        if step_type == "api_request" and (
            not endpoint or endpoint["project_id"] != scenario["project_id"]
        ):
            errors.append(f"{prefix}必须选择当前项目的接口资产。")
        if step_type == "wait":
            duration_ms = config.get("duration_ms")
            if not isinstance(duration_ms, (int, float)) or not 0 <= duration_ms <= 300000:
                errors.append(f"{prefix}的等待时长必须在 0 到 300000 毫秒之间。")
        elif step_type == "condition":
            source = config.get("source") if isinstance(config.get("source"), dict) else {}
            _validate_scenario_source(source, prior_outputs, known_ids, prefix, errors)
            if config.get("operator") not in {
                "equals", "not_equals", "contains", "not_contains", "truthy", "falsy", "gt", "gte", "lt", "lte"
            }:
                errors.append(f"{prefix}存在不支持的条件操作符。")
        elif step_type == "assign":
            name = str(config.get("name") or "").strip()
            source = config.get("source") if isinstance(config.get("source"), dict) else {}
            if not name:
                errors.append(f"{prefix}必须填写变量名。")
            _validate_scenario_source(source, prior_outputs, known_ids, prefix, errors)
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
            _validate_scenario_source(source, prior_outputs, known_ids, prefix, errors)
        if step_type == "assign" and str(config.get("name") or "").strip():
            extractor_names.add(str(config["name"]).strip())
        prior_outputs[step["id"]] = extractor_names
        legacy_assertions = api_automation_repo.loads_json(case["assertions_json"], []) if case else []
        if step_type == "api_request" and not step["assertions"] and not legacy_assertions:
            warnings.append(f"{prefix}没有断言。")
    errors = _dedupe_validation_messages(errors)
    warnings = _dedupe_validation_messages(warnings)
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _validate_scenario_source(
    source: dict,
    prior_outputs: dict[str, set[str]],
    known_ids: set[str],
    prefix: str,
    errors: list[str],
) -> None:
    source_type = source.get("type")
    if source_type == "object":
        for child in (source.get("properties") or {}).values():
            if isinstance(child, dict):
                _validate_scenario_source(child, prior_outputs, known_ids, prefix, errors)
    elif source_type == "step_output":
        source_step_id = str(source.get("step_id") or "")
        variable = str(source.get("variable") or "")
        if source_step_id not in prior_outputs:
            suffix = "只能引用前序步骤。" if source_step_id in known_ids else "引用的步骤不存在。"
            errors.append(f"{prefix}的变量来源{suffix}")
        elif variable not in prior_outputs[source_step_id]:
            errors.append(f"{prefix}引用了前序步骤未输出的变量 {variable}。")
    elif source_type not in SUPPORTED_SCENARIO_SOURCE_TYPES:
        errors.append(f"{prefix}存在不支持的变量来源 {source_type or '空'}。")


def _iter_scenario_sources(source):
    yield source
    source_type = source.type if hasattr(source, "type") else source.get("type") if isinstance(source, dict) else None
    if source_type != "object":
        return
    properties = source.properties if hasattr(source, "properties") else source.get("properties", {})
    for child in properties.values():
        yield from _iter_scenario_sources(child)


MAX_API_SCENARIO_VERSIONS = 5


def _create_scenario_version(db, scenario: Row, steps: list[dict], actor) -> dict:
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
        (serialized, published_hash, actor["id"], scenario["id"]),
    )
    updated = db.execute("SELECT * FROM api_scenarios WHERE id = ?", (scenario["id"],)).fetchone()
    db.execute(
        """
        INSERT INTO api_scenario_revisions (
          id, scenario_id, project_id, revision, snapshot_json, published_hash, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"apiscenrev-{secrets.token_hex(8)}",
            scenario["id"],
            scenario["project_id"],
            updated["revision"],
            serialized,
            published_hash,
            actor["id"],
        ),
    )
    db.execute(
        """
        DELETE FROM api_scenario_revisions
        WHERE scenario_id = ? AND id NOT IN (
          SELECT id FROM api_scenario_revisions
          WHERE scenario_id = ?
          ORDER BY revision DESC
          LIMIT ?
        )
        """,
        (scenario["id"], scenario["id"], MAX_API_SCENARIO_VERSIONS),
    )
    return _serialize_scenario(updated, steps)


def _build_scenario_snapshot(db, scenario: Row, steps: list[dict]) -> dict:
    snapshot_steps = []
    for step in steps:
        if not step["enabled"]:
            continue
        endpoint = api_automation_repo.find_endpoint(db, step["endpoint_id"]) if step.get("endpoint_id") else None
        endpoint_snapshot = _serialize_endpoint_snapshot(endpoint) if endpoint else None
        snapshot_steps.append(
            {
                **step,
                "endpoint": endpoint_snapshot,
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


def _serialize_endpoint_snapshot(endpoint: Row) -> dict:
    return {
        "id": endpoint["id"],
        "method": endpoint["method"],
        "path": endpoint["path"],
        "summary": endpoint["summary"],
        "parameters": api_automation_repo.loads_json(endpoint["parameters_json"], []),
        "request_body": api_automation_repo.loads_json(endpoint["request_body_json"], {}),
        "responses": api_automation_repo.loads_json(endpoint["responses_json"], {}),
        "auth": api_automation_repo.loads_json(endpoint["auth_json"], {}),
    }


def _list_scenario_asset_changes(db, scenario: Row, steps: list[dict]) -> list[dict]:
    published = api_automation_repo.loads_json(scenario["published_snapshot_json"], {})
    published_steps = {str(step.get("id") or ""): step for step in published.get("steps", [])}
    if not published_steps:
        return []
    changes = []
    compared_fields = ("method", "path", "summary", "parameters", "request_body", "responses", "auth")
    for step in steps:
        baseline = published_steps.get(step["id"])
        if not baseline or not step.get("endpoint_id"):
            continue
        endpoint = api_automation_repo.find_endpoint(db, step["endpoint_id"])
        if not endpoint:
            changes.append(
                {
                    "step_id": step["id"],
                    "endpoint_id": step["endpoint_id"],
                    "change_type": "missing",
                    "fields": [],
                }
            )
            continue
        current = _serialize_endpoint_snapshot(endpoint)
        previous = baseline.get("endpoint") or {}
        fields = [field for field in compared_fields if current.get(field) != previous.get(field)]
        if fields:
            changes.append(
                {
                    "step_id": step["id"],
                    "endpoint_id": step["endpoint_id"],
                    "change_type": "modified",
                    "fields": fields,
                }
            )
    return changes


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


def _build_debug_request(
    endpoint: dict,
    environment: dict,
    payload: ApiEndpointDebugIn,
    *,
    files: dict[str, tuple[str, Any, str, int]] | None = None,
) -> dict:
    url = _build_debug_url(environment["api_base_url"], endpoint["path"], payload.path_params)
    headers = {**environment["headers"], **_stringify_mapping(payload.headers)}
    query_params = _clean_mapping(payload.query_params)
    body = payload.body
    json_body = None
    form_body = None
    raw_body = None
    content_type = _request_body_content_type(endpoint.get("request_body", {}))
    normalized_content_type = content_type.split(";", 1)[0].strip().lower()
    request_files = files or {}
    if normalized_content_type == "multipart/form-data":
        form_body = body if isinstance(body, dict) else {}
        _pop_header_case_insensitive(headers, "Content-Type")
    elif normalized_content_type == "application/x-www-form-urlencoded" and isinstance(body, dict):
        form_body = body
        _setdefault_header_case_insensitive(headers, "Content-Type", content_type)
    elif isinstance(body, (dict, list)):
        json_body = body
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
        "form_body": form_body,
        "raw_body": raw_body,
        "files": {field: value[:3] for field, value in request_files.items()},
        "file_summaries": {
            field: {"filename": value[0], "content_type": value[2], "size": value[3]}
            for field, value in request_files.items()
        },
        "content_type": normalized_content_type,
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
        "content_type": request["content_type"],
        "body": (
            request["json_body"]
            if request["json_body"] is not None
            else request["form_body"]
            if request["form_body"] is not None
            else request["raw_body"]
        ),
        "files": request["file_summaries"],
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
        value = str(stored.pop(key, "") or "")
        stored.pop(f"{key}_encrypted", None)
        if value:
            stored[f"{key}_encrypted"] = encrypt_api_environment_secret(value)
    return stored


def _serialize_auth_config(auth_type: str, auth_config: dict) -> dict:
    masked = dict(auth_config)
    if auth_type == "cybertron_agent":
        for key in ("cybertron_robot_key", "cybertron_robot_token"):
            encrypted = masked.pop(f"{key}_encrypted", "")
            masked[key] = decrypt_api_environment_secret(encrypted) or ""
            masked[f"{key}_saved"] = bool(encrypted)
    if masked.pop("token_encrypted", ""):
        masked["token_saved"] = True
    if masked.pop("cookie_value_encrypted", ""):
        masked["cookie_value_saved"] = True
    if "headers_encrypted" in masked:
        masked["headers_saved"] = sorted(masked.pop("headers_encrypted").keys())
    return masked


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


def _pop_header_case_insensitive(headers: dict[str, str], key: str) -> None:
    for existing_key in list(headers):
        if existing_key.lower() == key.lower():
            headers.pop(existing_key, None)


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
