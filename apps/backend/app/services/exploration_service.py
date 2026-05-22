from __future__ import annotations

import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.presentation.serializers import serialize_exploration_run
from app.repositories import environment_repo, exploration_repo, project_repo
from app.schemas.exploration import ExplorationRunCreateIn

STATUSES = {"queued", "running", "waiting_human", "partial", "completed", "blocked"}
LOGIN_STRATEGIES = {"reuse_state", "manual", "account_password", "skip_login"}


def list_project_runs(project_id: str, actor) -> list[dict]:
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)
        rows = exploration_repo.list_by_project(db, project_id)
        return [serialize_exploration_run(row, actor["role"]) for row in rows]


def list_visible_runs(actor) -> list[dict]:
    with connect() as db:
        rows = exploration_repo.list_visible(db, actor)
        return [serialize_exploration_run(row, actor["role"]) for row in rows]


def create_project_run(project_id: str, payload: ExplorationRunCreateIn, actor) -> dict:
    target_project_id = payload.project_id or project_id
    if target_project_id != project_id:
        raise api_error(400, "PROJECT_MISMATCH", "探索任务所属项目与当前项目不一致。")
    if payload.login_strategy not in LOGIN_STRATEGIES:
        raise api_error(400, "INVALID_LOGIN_STRATEGY", "登录策略不合法。")

    run_id = f"explore-{secrets.token_hex(8)}"
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)

        environment = environment_repo.find_by_id(db, payload.environment_id)
        if not environment or environment["project_id"] != project_id:
            raise api_error(400, "INVALID_ENVIRONMENT", "请选择当前项目下的环境。")

        exploration_repo.create(
            db,
            run_id=run_id,
            project_id=project_id,
            environment_id=payload.environment_id,
            title=payload.title.strip(),
            scope=payload.scope.strip(),
            forbidden_paths=payload.forbidden_paths.strip(),
            login_strategy=payload.login_strategy,
            description=payload.description.strip(),
            created_by=actor["id"],
        )
        row = exploration_repo.find_by_id(db, run_id)
        return serialize_exploration_run(row, actor["role"])


def delete_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] == "running":
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务运行中，不能删除。")
        exploration_repo.delete(db, run_id)
        return {"success": True}


def _ensure_project_visible(project, actor) -> None:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    project_name = project["project_name"] if "project_name" in project.keys() else project["name"]
    if project_name == actor["project_scope"]:
        return
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")
