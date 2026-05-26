from __future__ import annotations

import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.presentation.serializers import serialize_project_environment
from app.repositories import environment_repo, project_repo
from app.schemas.environment import ProjectEnvironmentCreateIn, ProjectEnvironmentUpdateIn

LOGIN_STRATEGIES = {"reuse_state", "manual", "account_password", "skip_login"}


def list_project_environments(project_id: str, actor) -> list[dict]:
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)
        rows = environment_repo.list_by_project(db, project_id)
        return [serialize_project_environment(row, actor["role"]) for row in rows]


def list_visible_environments(actor) -> list[dict]:
    with connect() as db:
        rows = environment_repo.list_visible(db, actor)
        return [serialize_project_environment(row, actor["role"]) for row in rows]


def create_project_environment(project_id: str, payload: ProjectEnvironmentCreateIn, actor) -> dict:
    target_project_id = payload.project_id or project_id
    if target_project_id != project_id:
        raise api_error(400, "PROJECT_MISMATCH", "环境所属项目与当前项目不一致。")
    if payload.login_strategy not in LOGIN_STRATEGIES:
        raise api_error(400, "INVALID_LOGIN_STRATEGY", "登录策略不合法。")

    environment_id = f"env-{secrets.token_hex(8)}"
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)
        try:
            environment_repo.create(
                db,
                environment_id=environment_id,
                project_id=project_id,
                name=payload.name.strip(),
                site_url=payload.site_url.strip(),
                username=payload.username.strip(),
                password_mask=_mask_password(payload.password),
                login_strategy=payload.login_strategy,
                description=payload.description.strip(),
                created_by=actor["id"],
            )
        except Exception as exc:
            raise api_error(409, "ENVIRONMENT_CONFLICT", "同一项目下环境名称已存在。") from exc
        row = environment_repo.find_by_id(db, environment_id)
        return serialize_project_environment(row, actor["role"])


def update_project_environment(project_id: str, environment_id: str, payload: ProjectEnvironmentUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("login_strategy") and updates["login_strategy"] not in LOGIN_STRATEGIES:
        raise api_error(400, "INVALID_LOGIN_STRATEGY", "登录策略不合法。")
    assignments, values = _build_update_assignments(updates)
    with connect() as db:
        existing = environment_repo.find_by_id(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        _ensure_project_visible(existing, actor)
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                environment_repo.update(db, environment_id, assignments, values)
            except Exception as exc:
                raise api_error(409, "ENVIRONMENT_CONFLICT", "同一项目下环境名称已存在。") from exc
        row = environment_repo.find_by_id(db, environment_id)
        return serialize_project_environment(row, actor["role"])


def delete_project_environment(project_id: str, environment_id: str, actor) -> dict:
    with connect() as db:
        existing = environment_repo.find_by_id(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        _ensure_project_visible(existing, actor)
        environment_repo.delete(db, environment_id)
        return {"success": True}


def _ensure_project_visible(project, actor) -> None:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    project_name = project["project_name"] if "project_name" in project.keys() else project["name"]
    if project_name == actor["project_scope"]:
        return
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _mask_password(password: str) -> str:
    if not password:
        return ""
    if len(password) <= 2:
        return "*" * len(password)
    return f"{password[0]}{'*' * max(len(password) - 2, 1)}{password[-1]}"


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
    field_map = {
        "name": "name",
        "site_url": "site_url",
        "username": "username",
        "login_strategy": "login_strategy",
        "description": "description",
    }
    assignments = []
    values = []
    for key, column in field_map.items():
        if key in updates:
            assignments.append(f"{column} = ?")
            value = updates[key]
            values.append(value.strip() if isinstance(value, str) else value)
    if updates.get("password"):
        assignments.append("password_mask = ?")
        values.append(_mask_password(updates["password"]))
    return assignments, values
