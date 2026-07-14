from contextlib import contextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, Request, Response

from app.dependencies.auth import current_user, get_token
from app.repositories import api_automation_repo, performance_script_repo, project_repo
from app.services.performance_testing.locust_session import (
    LocustSession,
    build_proxy_target,
    require_session,
    start_session,
)


test_router = APIRouter(prefix="/projects/{project_id}/performance-tests/{test_id}", tags=["performance-tests"])
run_router = APIRouter(prefix="/projects/{project_id}/performance-test-runs", tags=["performance-test-runs"])


@test_router.post("/runs")
def create_performance_run(
    project_id: str,
    test_id: str,
    payload: dict,
    actor=Depends(current_user),
) -> dict[str, str]:
    script_id = str(payload.get("script_id") or "")
    if not script_id:
        from app.core.exceptions import api_error

        raise api_error(400, "PERFORMANCE_RUN_INVALID", "必须提供 script_id。")
    with _script_lookup(project_id, test_id, script_id, actor) as context:
        session: LocustSession = start_session(
            project_id,
            test_id,
            script_id,
            script_code=context["script_code"],
            runtime_payload=context["runtime_environment"],
        )
    return {"run_id": session.run_id, "locust_ui_path": session.base_path}


@run_router.post("/{run_id}/locust-ui-session")
def create_locust_ui_session(
    project_id: str,
    run_id: str,
    request: Request,
    response: Response,
    token: str = Depends(get_token),
    actor=Depends(current_user),
) -> dict[str, str]:
    _ensure_project_visible(project_id, actor)
    session = require_session(project_id, run_id)
    response.set_cookie(
        "locust_ui_session",
        token,
        max_age=3600,
        httponly=True,
        samesite="lax",
        path=session.base_path,
    )
    return {"url": f"{str(request.base_url).rstrip('/')}{session.base_path}"}


@run_router.api_route(
    "/{run_id}/locust-ui",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_locust_ui_root(
    project_id: str,
    run_id: str,
    request: Request,
    actor=Depends(current_user),
) -> Response:
    _ensure_project_visible(project_id, actor)
    return await _proxy_locust_ui(project_id, run_id, "", request)


@run_router.api_route(
    "/{run_id}/locust-ui/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_locust_ui_path(
    project_id: str,
    run_id: str,
    path: str,
    request: Request,
    actor=Depends(current_user),
) -> Response:
    _ensure_project_visible(project_id, actor)
    return await _proxy_locust_ui(project_id, run_id, path, request)


@contextmanager
def _script_lookup(project_id: str, test_id: str, script_id: str, actor):
    from app.core.db import connect
    from app.core.exceptions import api_error

    with connect() as db:
        _ensure_project_visible_db(db, project_id, actor)
        test_row = db.execute(
            "SELECT * FROM performance_tests WHERE id = ? AND project_id = ?",
            (test_id, project_id),
        ).fetchone()
        if not test_row:
            raise api_error(404, "PERFORMANCE_TEST_NOT_FOUND", "性能测试不存在。")
        script_row = performance_script_repo.find_script(db, script_id)
        if (
            not script_row
            or script_row["project_id"] != project_id
            or script_row["performance_test_id"] != test_id
        ):
            raise api_error(404, "PERFORMANCE_SCRIPT_NOT_FOUND", "性能测试脚本不存在。")
        if script_row["validation_status"] != "confirmed":
            raise api_error(409, "PERFORMANCE_SCRIPT_NOT_CONFIRMED", "只有已确认脚本可以启动正式压测。")
        endpoint = api_automation_repo.find_endpoint(db, test_row["endpoint_id"])
        environment = api_automation_repo.find_api_environment(db, test_row["api_environment_id"])
        if not endpoint or endpoint["project_id"] != project_id:
            raise api_error(409, "PERFORMANCE_ENDPOINT_INVALID", "接口引用已失效。")
        if not environment or environment["project_id"] != project_id:
            raise api_error(409, "PERFORMANCE_ENVIRONMENT_INVALID", "接口环境引用已失效。")
        yield {
            "script_code": script_row["code"],
            "runtime_environment": _build_runtime_environment(environment),
        }


def _ensure_project_visible(project_id: str, actor) -> None:
    from app.core.db import connect
    from app.core.exceptions import api_error

    with connect() as db:
        _ensure_project_visible_db(db, project_id, actor)
        if not project_repo.find_by_id(db, project_id):  # noqa: F841 — silence unused
            raise api_error(404, "NOT_FOUND", "项目不存在。")


def _ensure_project_visible_db(db, project_id: str, actor) -> None:
    from app.core.exceptions import api_error

    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    if project["name"] == actor["project_scope"]:
        return
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _build_runtime_environment(row) -> dict:
    from app.core.environment_credentials import decrypt_api_environment_secret

    auth_config = api_automation_repo.loads_json(row["auth_config_json"], {})
    headers: dict[str, str] = {
        str(key): str(value)
        for key, value in api_automation_repo.loads_json(row["default_headers_json"], {}).items()
    }
    if row["auth_type"] == "static_bearer" and auth_config.get("token_encrypted"):
        token = decrypt_api_environment_secret(auth_config["token_encrypted"]) or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
    if row["auth_type"] == "static_headers":
        for key, encrypted in auth_config.get("headers_encrypted", {}).items():
            headers[str(key)] = decrypt_api_environment_secret(str(encrypted)) or ""
    if row["auth_type"] == "cookie" and auth_config.get("cookie_name"):
        cookie_value = decrypt_api_environment_secret(auth_config.get("cookie_value_encrypted", "")) or ""
        if cookie_value:
            headers["Cookie"] = f"{auth_config['cookie_name']}={cookie_value}"
    if row["auth_type"] == "cybertron_agent":
        if auth_config.get("username"):
            headers["username"] = str(auth_config["username"])
        robot_key = decrypt_api_environment_secret(auth_config.get("cybertron_robot_key_encrypted", "")) or ""
        robot_token = decrypt_api_environment_secret(auth_config.get("cybertron_robot_token_encrypted", "")) or ""
        if robot_key:
            headers["cybertron-robot-key"] = robot_key
        if robot_token:
            headers["cybertron-robot-token"] = robot_token
    return {
        "api_base_url": row["api_base_url"],
        "headers": headers,
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
        "verify_ssl": bool(row["verify_ssl"]),
    }


async def _proxy_locust_ui(project_id: str, run_id: str, path: str, request: Request) -> Response:
    session = require_session(project_id, run_id)
    target = build_proxy_target(session, path)
    if request.url.query:
        target = f"{target}?{request.url.query}"
    headers = _proxy_request_headers(request.headers)
    try:
        async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
            proxied = await client.request(
                request.method,
                target,
                headers=headers,
                content=await request.body(),
            )
    except httpx.HTTPError as exc:
        from app.core.exceptions import api_error

        raise api_error(502, "LOCUST_UI_UNAVAILABLE", "Locust UI 暂时不可用。") from exc
    response_headers = {
        key: value
        for key, value in proxied.headers.items()
        if key.lower() not in {"content-length", "content-encoding", "transfer-encoding", "connection"}
    }
    if "location" in response_headers:
        response_headers["location"] = _rewrite_locust_location(response_headers["location"])
    return Response(content=proxied.content, status_code=proxied.status_code, headers=response_headers)


def _rewrite_locust_location(location: str) -> str:
    parsed = urlsplit(location)
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        return location
    return f"{parsed.path}{'?' + parsed.query if parsed.query else ''}"


def _proxy_request_headers(headers) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in {"host", "content-length", "connection", "upgrade", "cookie", "authorization"}
    }
