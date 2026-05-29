from __future__ import annotations

import secrets
import re

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.presentation.serializers import serialize_exploration_run
from app.repositories import environment_repo, exploration_repo, project_repo
from app.schemas.exploration import ExplorationRunCreateIn, ExplorationRunUpdateIn
from app.services import exploration_artifact_service, operation_log_service

STATUSES = {"pending", "queued", "running", "waiting_human", "stopping", "cancelled", "partial", "completed", "blocked"}
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
        pages, elements, blockers = _load_run_artifacts(existing)

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
            module_by_key.update(_planned_or_fallback_modules(run_id, existing, fallback_key))

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
                    "yaml_path": page.get("yaml_path", ""),
                    "page_type": page.get("page_type", "unknown"),
                    "status": page.get("status", "explored"),
                    "blocker_reason": page.get("blocker_reason", ""),
                    "recent_event": page.get("recent_event", ""),
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

        artifacts = _load_run_artifact_bundle(existing)
        has_summary = bool(artifacts["summary"])
        return {
            "run_id": run_id,
            "version_no": 1 if has_summary else None,
            "title": "探索报告 v1" if has_summary else "探索报告",
            "markdown_content": artifacts["summary"].get("markdown_content", ""),
            "change_summary": artifacts["summary"].get("summary", ""),
            "created_at": existing["created_at"] if has_summary else None,
        }


def get_project_run_log(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        artifacts = _load_run_artifact_bundle(existing)
        return {
            "run_id": run_id,
            "log_content": artifacts["log_content"],
            "log_path": artifacts["log_path"],
            "updated_at": existing["updated_at"],
        }


def create_project_run(project_id: str, payload: ExplorationRunCreateIn, actor) -> dict:
    target_project_id = payload.project_id or project_id
    if target_project_id != project_id:
        raise api_error(400, "PROJECT_MISMATCH", "探索任务所属项目与当前项目不一致。")
    run_id = f"explore-{secrets.token_hex(8)}"
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)

        environment = environment_repo.find_by_id(db, payload.environment_id)
        if not environment or environment["project_id"] != project_id:
            raise api_error(400, "INVALID_ENVIRONMENT", "请选择当前项目下的环境。")

        _validate_execution_limits(
            max_pages=payload.max_pages,
            max_actions=payload.max_actions,
            timeout_minutes=payload.timeout_minutes,
        )
        exploration_repo.create(
            db,
            run_id=run_id,
            project_id=project_id,
            environment_id=payload.environment_id,
            title=payload.title.strip(),
            scope=payload.scope.strip(),
            forbidden_paths=payload.forbidden_paths.strip(),
            login_strategy=environment["login_strategy"],
            description=payload.description.strip(),
            max_pages=payload.max_pages,
            max_actions=payload.max_actions,
            timeout_minutes=payload.timeout_minutes,
            created_by=actor["id"],
        )
        row = exploration_repo.find_by_id(db, run_id)
        result = serialize_exploration_run(row, actor["role"])
    operation_log_service.record_task_event(
        module="exploration",
        action="create",
        object_type="exploration_run",
        object_id=run_id,
        object_name=result["title"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        result="success",
        summary=f"新建站点探索任务：{result['title']}",
        after=_run_snapshot(result),
        task_id=run_id,
    )
    return result


def update_project_run(project_id: str, run_id: str, payload: ExplorationRunUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    updates.pop("login_strategy", None)

    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "waiting_human", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能修改。")
        if "environment_id" in updates:
            environment = environment_repo.find_by_id(db, updates["environment_id"])
            if not environment or environment["project_id"] != project_id:
                raise api_error(400, "INVALID_ENVIRONMENT", "请选择当前项目下的环境。")
        _validate_execution_limits(
            max_pages=updates.get("max_pages"),
            max_actions=updates.get("max_actions"),
            timeout_minutes=updates.get("timeout_minutes"),
        )

        assignments, values = _build_update_assignments(updates)
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            exploration_repo.update(db, run_id, assignments, values)
        row = exploration_repo.find_by_id(db, run_id)
        result = serialize_exploration_run(row, actor["role"])
        before = _run_snapshot(existing)
        after = _run_snapshot(result)
    operation_log_service.record_task_event(
        module="exploration",
        action="update",
        object_type="exploration_run",
        object_id=run_id,
        object_name=result["title"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        result="success",
        summary=f"编辑站点探索任务：{result['title']}",
        before=before,
        after=after,
        task_id=run_id,
    )
    return result


def start_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "waiting_human", "stopping"}:
            raise api_error(409, "EXPLORATION_ALREADY_RUNNING", "探索任务正在执行或等待人工处理。")
        if existing["status"] not in {"pending", "partial", "completed", "blocked", "cancelled"}:
            raise api_error(409, "EXPLORATION_NOT_STARTABLE", "当前状态不能发起探索。")
        exploration_repo.update_run_state(
            db,
            run_id,
            status="queued",
            result_summary="探索任务已提交，等待执行。",
            started=True,
        )
        exploration_repo.clear_run_outputs(db, run_id)
        _seed_planned_modules(db, existing)
        row = exploration_repo.find_by_id(db, run_id)
        result = serialize_exploration_run(row, actor["role"])
    operation_log_service.record_task_event(
        module="exploration",
        action="run",
        object_type="exploration_run",
        object_id=run_id,
        object_name=result["title"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        result="success",
        summary=f"启动站点探索任务：{result['title']}",
        after={"status": result["status"], "result_summary": result["result_summary"]},
        task_id=run_id,
    )
    return result


def stop_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        before = _run_snapshot(existing)
        if existing["status"] in {"completed", "partial", "blocked", "cancelled"}:
            result = serialize_exploration_run(existing, actor["role"])
            after = _run_snapshot(result)
            should_log = False
        elif existing["status"] == "stopping":
            result = serialize_exploration_run(existing, actor["role"])
            after = _run_snapshot(result)
            should_log = False
        elif existing["status"] in {"queued", "running", "waiting_human"}:
            exploration_repo.update_run_state(
                db,
                run_id,
                status="stopping",
                result_summary="用户已请求停止探索，正在终止浏览器探索进程。",
            )
            row = exploration_repo.find_by_id(db, run_id)
            result = serialize_exploration_run(row, actor["role"])
            after = _run_snapshot(result)
            should_log = True
        else:
            raise api_error(409, "EXPLORATION_NOT_RUNNING", "只有排队中或探索中的任务可以停止。")
    if should_log:
        operation_log_service.record_task_event(
            module="exploration",
            action="cancel",
            object_type="exploration_run",
            object_id=run_id,
            object_name=result["title"],
            project_id=project_id,
            actor_id=actor["id"],
            actor_name=operation_log_service.actor_display_name(actor),
            source="web",
            result="success",
            summary=f"请求停止站点探索任务：{result['title']}",
            before=before,
            after=after,
            task_id=run_id,
        )
    return result


def delete_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "waiting_human", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务运行中，不能删除。")
        snapshot = _run_snapshot(existing)
        exploration_repo.delete(db, run_id)
    operation_log_service.record_task_event(
        module="exploration",
        action="delete",
        object_type="exploration_run",
        object_id=run_id,
        object_name=snapshot["title"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        result="success",
        summary=f"删除站点探索任务：{snapshot['title']}",
        before=snapshot,
        after={},
        task_id=run_id,
    )
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
    if status in {"queued", "running", "waiting_human", "stopping"}:
        return "in-progress"
    if status == "cancelled":
        return "blocked"
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
        "max_pages": "max_pages",
        "max_actions": "max_actions",
        "timeout_minutes": "timeout_minutes",
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


def _planned_or_fallback_modules(run_id: str, run, fallback_key: str) -> dict[str, dict]:
    if run["status"] in {"queued", "running", "waiting_human", "stopping"}:
        modules = {}
        for index, name in enumerate(_planned_module_names(run), start=1):
            module_key = f"planned-{index:02d}"
            modules[module_key] = {
                "id": f"{run_id}-{module_key}",
                "module_key": module_key,
                "module_name": name,
                "entry_path": run["scope"] or run["environment_name"],
                "planned_page_count": 1,
                "explored_page_count": 0,
                "blocked_page_count": 0,
                "action_count": 0,
                "field_count": 0,
                "state_transition_count": 0,
                "completion_status": "pending",
                "completion_summary": run["result_summary"] or "等待探索执行。",
                "pages": [],
                "elements": [],
                "blockers": [],
            }
        return modules
    return {
        fallback_key: {
            "id": f"{run_id}-current",
            "module_key": fallback_key,
            "module_name": run["title"],
            "entry_path": run["scope"] or run["environment_name"],
            "planned_page_count": 1,
            "explored_page_count": 0,
            "blocked_page_count": 0,
            "action_count": 0,
            "field_count": 0,
            "state_transition_count": 0,
            "completion_status": _status_to_completion(run["status"]),
            "completion_summary": run["result_summary"] or "等待探索执行。",
            "pages": [],
            "elements": [],
            "blockers": [],
        }
    }


def seed_planned_modules_for_run(db, run) -> None:
    _seed_planned_modules(db, run)


def _seed_planned_modules(db, run) -> None:
    for index, name in enumerate(_planned_module_names(run), start=1):
        exploration_repo.create_module_coverage(
            db,
            coverage_id=f"expcov-plan-{secrets.token_hex(8)}",
            exploration_run_id=run["id"],
            module_key=f"planned-{index:02d}",
            module_name=name,
            entry_path=run["scope"] or run["environment_name"],
            planned_page_count=1,
            explored_page_count=0,
            blocked_page_count=0,
            action_count=0,
            field_count=0,
            state_transition_count=0,
            completion_status="pending",
            completion_summary="已纳入本次探索计划，等待 Playwright 采集页面事实。",
        )


def _planned_module_names(run) -> list[str]:
    scope = str(run["scope"] or "").strip()
    names = _scope_named_items(scope)
    if names:
        return names
    if _is_full_site_scope(scope):
        return [
            "入口页",
            "目录导航链接",
            "文档正文链接",
            "侧边栏链接",
            "上一篇/下一篇链接",
            "面包屑链接",
            "页面内按钮与输入框",
            "登录/权限拦截页",
            "异常状态页",
            "外链与禁止路径",
        ]
    return [scope.splitlines()[0][:80] if scope else "站点入口"]


def _scope_named_items(scope: str) -> list[str]:
    match = re.search(r"范围包含[：:](.+)", scope, flags=re.S)
    if not match:
        return []
    items = []
    for raw_item in re.split(r"[、,，;；。\n]+", match.group(1)):
        item = raw_item.strip()
        if item and len(item) <= 40:
            items.append(item)
    return _unique_preserve_order(["入口页", *items])


def _validate_execution_limits(*, max_pages: int | None, max_actions: int | None, timeout_minutes: int | None) -> None:
    values = {
        "max_pages": max_pages,
        "max_actions": max_actions,
        "timeout_minutes": timeout_minutes,
    }
    if any(value is not None and value < 1 for value in values.values()):
        raise api_error(400, "INVALID_EXPLORATION_LIMIT", "探索执行边界必须大于 0。")


def _is_full_site_scope(scope: str) -> bool:
    full_site_terms = ("全部站点", "全部内容", "所有内容", "所有页面", "全站", "遍历")
    return any(term in scope for term in full_site_terms)


def _unique_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _run_snapshot(run) -> dict:
    return {
        "title": run["title"],
        "status": run["status"],
        "environment_id": run["environment_id"],
        "scope": run["scope"],
        "forbidden_paths": run["forbidden_paths"],
        "login_strategy": run["login_strategy"],
        "description": run["description"],
        "max_pages": run["max_pages"],
        "max_actions": run["max_actions"],
        "timeout_minutes": run["timeout_minutes"],
        "result_summary": run["result_summary"],
    }


def _load_run_artifacts(run) -> tuple[list[dict], list[dict], list[dict]]:
    bundle = _load_run_artifact_bundle(run)
    pages = []
    elements = []
    blockers = []
    for page_item in bundle["pages"]:
        content = page_item.get("content", {})
        page = content.get("page", {})
        pages.append(
            {
                "id": page.get("id") or page_item.get("file_path", ""),
                "module_key": page.get("module", "site-entry"),
                "title": page.get("title", ""),
                "url": page.get("url", ""),
                "entry_path": page.get("normalized_url") or page.get("entry_path", ""),
                "structure_summary": page.get("title", ""),
                "yaml_path": page_item.get("file_path", ""),
                "page_type": page.get("page_type", "unknown"),
                "status": page.get("status", "explored"),
                "blocker_reason": "",
                "recent_event": "",
            }
        )
        for element in content.get("accessibility_tree", []):
            if not isinstance(element, dict):
                continue
            elements.append(
                {
                    "id": f"{page.get('id') or page_item.get('file_path', '')}:{element.get('role', '')}:{element.get('name', '')}",
                    "page_id": page.get("id") or page_item.get("file_path", ""),
                    "module_key": page.get("module", "site-entry"),
                    "element_name": element.get("name", ""),
                    "element_type": element.get("role", ""),
                    "recommended_locator": element.get("locator_hint", ""),
                    "fallback_locator": element.get("href", ""),
                    "stability_note": "来自页面 YAML 产物。",
                    "source_ref": page.get("url", ""),
                }
            )
        for blocker in content.get("relations", {}).get("outgoing_edges", []):
            if not isinstance(blocker, dict):
                continue
            blockers.append(
                {
                    "id": f"{page.get('id') or page_item.get('file_path', '')}:{blocker.get('type', '')}",
                    "module_key": page.get("module", "site-entry"),
                    "page_ref": page.get("url", ""),
                    "reason_type": blocker.get("type", ""),
                    "reason": blocker.get("action", ""),
                    "evidence_path": bundle["log_path"],
                    "impact_scope": "站点探索",
                    "suggested_action": blocker.get("action", ""),
                    "is_blocking": False,
                }
            )
    for blocker in bundle["blockers"].get("blockers", []):
        page_ref = blocker.get("page_ref", "")
        if any(existing["page_ref"] == page_ref and existing["reason_type"] == blocker.get("reason_type", "") for existing in blockers):
            continue
        blockers.append(
            {
                "id": f"{page_ref}:{blocker.get('reason_type', '')}",
                "module_key": blocker.get("module_key", "site-entry"),
                "page_ref": page_ref,
                "reason_type": blocker.get("reason_type", ""),
                "reason": blocker.get("reason", ""),
                "evidence_path": blocker.get("evidence_path") or bundle["log_path"],
                "impact_scope": "站点探索",
                "suggested_action": blocker.get("suggested_action", ""),
                "is_blocking": True,
            }
        )
    return pages, elements, blockers


def _load_run_artifact_bundle(run) -> dict:
    artifact_root = resolve_stored_path(run["artifact_root"])
    if not artifact_root:
        return {"run": {}, "summary": {}, "graph": {}, "blockers": {}, "pages": [], "log_content": "", "log_path": ""}
    bundle = exploration_artifact_service.load_exploration_run_artifacts(artifact_root)
    bundle["log_path"] = f"{run['artifact_root'].rstrip('/')}/logs/run.log"
    return bundle
