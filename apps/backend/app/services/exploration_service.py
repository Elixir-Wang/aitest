from __future__ import annotations

import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.presentation.serializers import serialize_exploration_run
from app.repositories import environment_repo, exploration_repo, project_repo
from app.schemas.exploration import ExplorationRunCreateIn, ExplorationRunUpdateIn

STATUSES = {"pending", "queued", "running", "waiting_human", "partial", "completed", "blocked"}
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


def get_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        return serialize_exploration_run(existing, actor["role"])


def get_project_run_detail(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        modules = [dict(row) for row in exploration_repo.list_module_coverages(db, run_id)]
        pages = [dict(row) for row in exploration_repo.list_pages(db, run_id)]
        elements = [dict(row) for row in exploration_repo.list_elements(db, run_id)]
        blockers = [dict(row) for row in exploration_repo.list_blockers(db, run_id)]

        module_by_key = {
            module["module_key"]: {
                "id": module["id"],
                "module_key": module["module_key"],
                "module_name": module["module_name"],
                "entry_path": module["entry_path"],
                "planned_page_count": module["planned_page_count"],
                "explored_page_count": module["explored_page_count"],
                "blocked_page_count": module["blocked_page_count"],
                "action_count": module["action_count"],
                "field_count": module["field_count"],
                "state_transition_count": module["state_transition_count"],
                "completion_status": module["completion_status"],
                "completion_summary": module["completion_summary"],
                "pages": [],
                "elements": [],
                "blockers": [],
            }
            for module in modules
        }

        fallback_key = "current"
        if not module_by_key:
            module_by_key[fallback_key] = {
                "id": f"{run_id}-current",
                "module_key": fallback_key,
                "module_name": existing["title"],
                "entry_path": existing["scope"] or existing["environment_name"],
                "planned_page_count": 1,
                "explored_page_count": 0,
                "blocked_page_count": 0,
                "action_count": 0,
                "field_count": 0,
                "state_transition_count": 0,
                "completion_status": _status_to_completion(existing["status"]),
                "completion_summary": existing["result_summary"] or "等待探索执行。",
                "pages": [],
                "elements": [],
                "blockers": [],
            }

        for page in pages:
            target = module_by_key.setdefault(page["module_key"] or fallback_key, _fallback_module(run_id, existing, page["module_key"] or fallback_key))
            target["pages"].append(
                {
                    "id": page["id"],
                    "module_key": page["module_key"],
                    "title": page["title"],
                    "url": page["url"],
                    "entry_path": page["entry_path"],
                    "structure_summary": page["structure_summary"],
                    "screenshot_path": page["screenshot_path"],
                    "snapshot_path": page["snapshot_path"],
                    "trace_path": page["trace_path"],
                }
            )

        for element in elements:
            target = module_by_key.setdefault(
                element["module_key"] or fallback_key,
                _fallback_module(run_id, existing, element["module_key"] or fallback_key),
            )
            target["elements"].append(
                {
                    "id": element["id"],
                    "page_id": element["page_id"],
                    "module_key": element["module_key"],
                    "element_name": element["element_name"],
                    "element_type": element["element_type"],
                    "recommended_locator": element["recommended_locator"],
                    "fallback_locator": element["fallback_locator"],
                    "stability_note": element["stability_note"],
                    "source_ref": element["source_ref"],
                }
            )

        for blocker in blockers:
            target = module_by_key.setdefault(
                blocker["module_key"] or fallback_key,
                _fallback_module(run_id, existing, blocker["module_key"] or fallback_key),
            )
            target["blockers"].append(
                {
                    "id": blocker["id"],
                    "module_key": blocker["module_key"],
                    "page_ref": blocker["page_ref"],
                    "reason_type": blocker["reason_type"],
                    "reason": blocker["reason"],
                    "evidence_path": blocker["evidence_path"],
                    "impact_scope": blocker["impact_scope"],
                    "suggested_action": blocker["suggested_action"],
                    "is_blocking": bool(blocker["is_blocking"]),
                }
            )

        return {
            "run": serialize_exploration_run(existing, actor["role"]),
            "modules": list(module_by_key.values()),
        }


def get_project_run_report(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        version = exploration_repo.latest_document_version(db, run_id)
        if not version:
            return {
                "run_id": run_id,
                "version_no": None,
                "title": "探索报告",
                "markdown_content": "",
                "change_summary": "",
                "created_at": None,
            }

        markdown_path = resolve_stored_path(version["markdown_path"])
        if not markdown_path or not markdown_path.exists():
            raise api_error(404, "REPORT_NOT_FOUND", "探索报告文件不存在。")

        return {
            "run_id": run_id,
            "version_no": version["version_no"],
            "title": f"探索报告 v{version['version_no']}",
            "markdown_content": markdown_path.read_text(encoding="utf-8"),
            "change_summary": version["change_summary"],
            "created_at": version["created_at"],
        }


def get_project_run_log(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        artifact = exploration_repo.latest_artifact_by_type(db, run_id, "log")
        log_path_value = artifact["file_path"] if artifact else ""
        log_path = resolve_stored_path(log_path_value)
        if (not log_path or not log_path.exists()) and existing["artifact_root"]:
            artifact_root = resolve_stored_path(existing["artifact_root"])
            log_path = artifact_root / "logs" / "run.log" if artifact_root else None
            log_path_value = f"{existing['artifact_root'].rstrip('/')}/logs/run.log"

        return {
            "run_id": run_id,
            "log_content": log_path.read_text(encoding="utf-8") if log_path and log_path.exists() else "",
            "log_path": log_path_value,
            "updated_at": existing["updated_at"],
        }


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


def update_project_run(project_id: str, run_id: str, payload: ExplorationRunUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if updates.get("login_strategy") and updates["login_strategy"] not in LOGIN_STRATEGIES:
        raise api_error(400, "INVALID_LOGIN_STRATEGY", "登录策略不合法。")

    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"running", "waiting_human"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能修改。")
        if "environment_id" in updates:
            environment = environment_repo.find_by_id(db, updates["environment_id"])
            if not environment or environment["project_id"] != project_id:
                raise api_error(400, "INVALID_ENVIRONMENT", "请选择当前项目下的环境。")

        assignments, values = _build_update_assignments(updates)
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            exploration_repo.update(db, run_id, assignments, values)
        row = exploration_repo.find_by_id(db, run_id)
        return serialize_exploration_run(row, actor["role"])


def start_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"running", "waiting_human"}:
            raise api_error(409, "EXPLORATION_ALREADY_RUNNING", "探索任务正在执行或等待人工处理。")
        if existing["status"] not in {"pending", "queued", "partial", "completed", "blocked"}:
            raise api_error(409, "EXPLORATION_NOT_STARTABLE", "当前状态不能发起探索。")
        exploration_repo.update_run_state(
            db,
            run_id,
            status="queued",
            result_summary="探索任务已提交，等待执行。",
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


def _status_to_completion(status: str) -> str:
    if status == "completed":
        return "completed"
    if status == "blocked":
        return "blocked"
    if status in {"running", "waiting_human"}:
        return "in-progress"
    if status == "partial":
        return "partial"
    return "pending"


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
    field_map = {
        "environment_id": "environment_id",
        "title": "title",
        "scope": "scope",
        "forbidden_paths": "forbidden_paths",
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
    return assignments, values


def _fallback_module(run_id: str, run, module_key: str) -> dict:
    return {
        "id": f"{run_id}-{module_key}",
        "module_key": module_key,
        "module_name": module_key,
        "entry_path": run["scope"] or run["environment_name"],
        "planned_page_count": 0,
        "explored_page_count": 0,
        "blocked_page_count": 0,
        "action_count": 0,
        "field_count": 0,
        "state_transition_count": 0,
        "completion_status": _status_to_completion(run["status"]),
        "completion_summary": run["result_summary"] or "",
        "pages": [],
        "elements": [],
        "blockers": [],
    }
