import json
import asyncio
import secrets
import shutil
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from app.core.db import connect
from app.core.environment_auth_state import auth_state_path
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.agents.site_exploration.planning import service as site_exploration_plan_service
from app.agents.site_exploration.planning.schemas import (
    ExplorationPlanInput,
    ExplorationPlanModule,
    ExplorationPlanOutput,
)
from app.presentation.serializers import serialize_exploration_run
from app.repositories import document_repo, environment_repo, exploration_repo, project_repo
from app.schemas.exploration import ExplorationPlanUpdateIn, ExplorationRunCreateIn, ExplorationRunUpdateIn
from app.schemas.requirement_exploration import RequirementPlanImportIn
from app.services import operation_log_service
from app.services.exploration import artifact_service as exploration_artifact_service
from app.services.exploration.browser_session import BrowserSessionError, PlaywrightBrowserSession
from app.services import requirement_exploration_service

STATUSES = {"pending", "queued", "running", "stopping", "cancelled", "partial", "completed", "blocked"}
LOGIN_STRATEGIES = {"account_password", "skip_login"}
AGENT_PLAN_DISPLAY_STATUSES = {
    "pending",
    "queued",
    "running",
    "in-progress",
    "stopping",
    "completed",
    "partial",
    "blocked",
    "failed",
    "cancelled",
}

LOG_EVENT_LABELS = {
    "run_started": "探索开始",
    "login_started": "登录开始",
    "login_completed": "登录完成",
    "page_discovered": "发现页面",
    "page_visited": "访问页面",
    "page_captured": "采集页面",
    "accessibility_captured": "生成无障碍树",
    "action_detected": "发现动作",
    "action_executed": "执行动作",
    "agent_observed": "Agent 观察",
    "agent_decision": "Agent 决策",
    "agent_decision_fallback": "Agent 决策降级",
    "action_started": "开始动作",
    "action_result": "动作结果",
    "action_completed": "动作完成",
    "step_recorded": "探索步骤",
    "edge_created": "记录关系",
    "artifact_written": "写入产物",
    "blocked": "探索阻塞",
    "skipped": "跳过",
    "error": "错误",
    "run_completed": "探索完成",
    "raw": "原始日志",
}


def list_project_runs(project_id: str, actor) -> list[dict]:
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)
        rows = exploration_repo.list_by_project(db, project_id)
        rows = [_recover_stale_stopping_run(db, row) for row in rows]
        return [serialize_exploration_run(row, actor["role"]) for row in rows]


def list_visible_runs(actor) -> list[dict]:
    with connect() as db:
        rows = exploration_repo.list_visible(db, actor)
        rows = [_recover_stale_stopping_run(db, row) for row in rows]
        return [serialize_exploration_run(row, actor["role"]) for row in rows]


def get_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        existing = _recover_stale_stopping_run(db, existing)
        return serialize_exploration_run(existing, actor["role"])


def get_project_run_detail(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        existing = _recover_stale_stopping_run(db, existing)

        modules = [dict(row) for row in exploration_repo.list_module_coverages(db, run_id)]
        artifact_bundle = _load_run_artifact_bundle(existing)
        pages, elements, blockers = _load_run_artifacts(existing, artifact_bundle)

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
        persisted_module_keys = set(module_by_key)

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
                    "status": _normalize_page_display_status(page.get("status")),
                    "blocker_reason": page.get("blocker_reason", ""),
                    "recent_event": page.get("recent_event", ""),
                    "steps": page.get("steps", []),
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
                    "primary_selector": element.get("primary_selector", {}),
                    "fallback_selector": element.get("fallback_selector", {}),
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

        for module in module_by_key.values():
            if module["module_key"] not in persisted_module_keys and (module["pages"] or module["blockers"]):
                module["completion_status"] = _module_status_from_artifacts(module, existing["status"])
            _enrich_module_progress(module)

        return {
            "run": serialize_exploration_run(existing, actor["role"]),
            "artifact_schema_version": artifact_bundle.get("artifact_schema_version", 0),
            "unsupported_artifact": bool(artifact_bundle.get("unsupported_artifact")),
            "unsupported_reason": str(artifact_bundle.get("unsupported_reason") or ""),
            "modules": list(module_by_key.values()),
            "goal_validation": _goal_validation_from_bundle(existing, artifact_bundle),
            "exploration_plan": _load_exploration_plan(existing),
        }


def get_project_run_report(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        artifacts = _load_run_artifact_bundle(existing)
        unsupported = bool(artifacts.get("unsupported_artifact"))
        markdown_content = _render_run_report_markdown(artifacts)
        has_report = bool(markdown_content)
        return {
            "run_id": run_id,
            "version_no": 2 if has_report else None,
            "title": "探索报告" if not unsupported else "历史产物格式不支持新版报告",
            "markdown_content": markdown_content,
            "change_summary": artifacts.get("summary", {}).get("summary", "") if isinstance(artifacts.get("summary"), dict) else "",
            "created_at": existing["created_at"] if has_report else None,
            "artifact_schema_version": artifacts.get("artifact_schema_version", 0),
            "unsupported_artifact": unsupported,
            "unsupported_reason": str(artifacts.get("unsupported_reason") or ""),
        }


def _render_run_report_markdown(artifacts: dict) -> str:
    if bool(artifacts.get("unsupported_artifact")):
        return ""
    if int(artifacts.get("artifact_schema_version") or 0) == exploration_artifact_service.ARTIFACT_SCHEMA_VERSION:
        rendered = exploration_artifact_service.build_exploration_report_markdown(artifacts)
        if rendered:
            return rendered
    return str(artifacts.get("report_content") or "")


def get_project_run_log(
    project_id: str,
    run_id: str,
    actor,
    *,
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    type_filter: str = "",
    level: str = "",
    page_ref: str = "",
    include_raw_content: bool = False,
) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        artifacts = _load_run_artifact_bundle(existing)
        entries = parse_exploration_log_entries(artifacts["log_content"])
        filtered_entries = filter_exploration_log_entries(
            entries,
            keyword=keyword,
            type_filter=type_filter,
            level=level,
            page_ref=page_ref,
        )
        paged_entries, safe_page, safe_page_size = paginate_exploration_log_entries(filtered_entries, page, page_size)
        return {
            "run_id": run_id,
            "log_content": artifacts["log_content"] if include_raw_content else "",
            "log_path": artifacts["log_path"],
            "updated_at": existing["updated_at"],
            "items": paged_entries,
            "total": len(filtered_entries),
            "page": safe_page,
            "page_size": safe_page_size,
        }


def parse_exploration_log_entries(log_content: str) -> list[dict]:
    entries: list[dict] = []
    lines = [line for line in log_content.splitlines() if line.strip()]
    for index, line in enumerate(lines, start=1):
        entry = _parse_json_log_line(line, index)
        entries.append(entry or _raw_log_entry(line, index))
    return _enrich_log_page_labels(entries)


def _enrich_log_page_labels(entries: list[dict]) -> list[dict]:
    page_labels: dict[str, str] = {}
    page_urls: dict[str, str] = {}
    for entry in entries:
        page_id = _string_value(entry.get("page_id"))
        if not page_id:
            continue
        page_title = _string_value(entry.get("page_title"))
        url = _string_value(entry.get("url"))
        if page_title:
            page_labels[page_id] = page_title
        elif url:
            page_labels.setdefault(page_id, url)
        if url:
            page_urls[page_id] = url

    for entry in entries:
        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        source = _string_value(payload.get("source"))
        target = _string_value(payload.get("target"))
        if source:
            entry["source_label"] = page_labels.get(source) or page_urls.get(source) or source
            if not entry.get("page_title") and source in page_labels:
                entry["page_title"] = page_labels[source]
            if not entry.get("url") and source in page_urls:
                entry["url"] = page_urls[source]
        if target:
            entry["target_label"] = page_labels.get(target) or page_urls.get(target) or target
        if entry.get("event") == "edge_created":
            entry["summary"] = _build_edge_log_summary(entry, payload)
    return entries


def _build_edge_log_summary(entry: dict, payload: dict) -> str:
    edge_id = _first_string(payload, ("edge_id",))
    relation_type = _first_string(payload, ("type",))
    source_label = _string_value(entry.get("source_label")) or _first_string(payload, ("source",)) or "-"
    target_label = _string_value(entry.get("target_label")) or _first_string(payload, ("target",)) or "-"
    relation_label = {
        "navigation": "同域链接",
        "external_link": "外部链接",
        "form_submit": "表单动作",
        "button_click": "页面动作",
    }.get(relation_type, relation_type or "页面关系")
    prefix = f"{edge_id} " if edge_id else ""
    return f"{prefix}{relation_label}：{source_label} -> {target_label}"


def filter_exploration_log_entries(
    entries: list[dict],
    *,
    keyword: str = "",
    type_filter: str = "",
    level: str = "",
    page_ref: str = "",
) -> list[dict]:
    keyword_normalized = keyword.strip().lower()
    type_normalized = type_filter.strip().lower()
    level_normalized = level.strip().lower()
    page_ref_normalized = page_ref.strip().lower()

    def matches(entry: dict) -> bool:
        if keyword_normalized:
            haystack = "\n".join(
                str(entry.get(key, ""))
                for key in (
                    "summary",
                    "raw",
                    "url",
                    "page_title",
                    "page_id",
                    "action_name",
                    "result",
                    "source_label",
                    "target_label",
                    "artifact_path",
                )
            ).lower()
            if keyword_normalized not in haystack:
                return False
        if type_normalized and type_normalized not in {str(entry.get("event", "")).lower(), str(entry.get("category", "")).lower()}:
            return False
        if level_normalized and level_normalized != str(entry.get("level", "")).lower():
            return False
        if page_ref_normalized:
            page_haystack = "\n".join(str(entry.get(key, "")) for key in ("page_id", "page_title", "url")).lower()
            if page_ref_normalized not in page_haystack:
                return False
        return True

    return [entry for entry in entries if matches(entry)]


def paginate_exploration_log_entries(entries: list[dict], page: int, page_size: int) -> tuple[list[dict], int, int]:
    safe_page = max(1, int(page or 1))
    safe_page_size = min(max(1, int(page_size or 10)), 100)
    start = (safe_page - 1) * safe_page_size
    return entries[start : start + safe_page_size], safe_page, safe_page_size


def _enrich_module_progress(module: dict) -> None:
    pages = module.get("pages") if isinstance(module.get("pages"), list) else []
    blockers = module.get("blockers") if isinstance(module.get("blockers"), list) else []
    explored = int(module.get("explored_page_count") or len(pages) or 0)
    planned = int(module.get("planned_page_count") or max(explored, len(pages), 1))
    blocked = int(module.get("blocked_page_count") or len(blockers) or 0)
    module["planned_page_count"] = planned
    module["explored_page_count"] = explored
    module["blocked_page_count"] = blocked


def _module_status_from_artifacts(module: dict, run_status: str) -> str:
    blockers = module.get("blockers") if isinstance(module.get("blockers"), list) else []
    pages = module.get("pages") if isinstance(module.get("pages"), list) else []
    if any(blocker.get("is_blocking") for blocker in blockers):
        return "blocked"
    if blockers:
        return "partial"
    if pages:
        return "partial" if run_status == "partial" else "completed"
    return _status_to_completion(run_status)


def _parse_json_log_line(line: str, index: int) -> dict | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    event = _string_value(payload.get("event")) or "raw"
    return {
        "id": f"log-{index:06d}",
        "timestamp": _format_log_timestamp(_first_string(payload, ("ts", "time", "timestamp"))),
        "event": event,
        "event_label": LOG_EVENT_LABELS.get(event, event),
        "category": _infer_log_category(event),
        "level": _infer_log_level(event, payload),
        "page_id": _first_string(payload, ("page_id", "page", "source")),
        "page_title": _first_string(payload, ("page_title", "title")),
        "url": _first_string(payload, ("url", "target")),
        "action_name": _first_string(payload, ("action", "name", "locator_hint")),
        "result": _first_string(payload, ("status", "reason", "type", "target", "edge_id")),
        "source_label": "",
        "target_label": "",
        "artifact_path": _first_string(payload, ("artifact_path", "evidence_path", "file_path", "log_path")),
        "summary": _build_log_summary(event, payload),
        "raw": line,
        "payload": payload,
    }


def _raw_log_entry(line: str, index: int) -> dict:
    level = "error" if re.search(r"error|traceback|typeerror|exception|failed|失败", line, re.IGNORECASE) else "info"
    return {
        "id": f"log-{index:06d}",
        "timestamp": "",
        "event": "raw",
        "event_label": LOG_EVENT_LABELS["raw"],
        "category": "error" if level == "error" else "raw",
        "level": level,
        "page_id": "",
        "page_title": "",
        "url": "",
        "action_name": "",
        "result": "",
        "source_label": "",
        "target_label": "",
        "artifact_path": "",
        "summary": line.strip(),
        "raw": line,
        "payload": {},
    }


def _infer_log_category(event: str) -> str:
    if event == "blocked":
        return "blocked"
    if event == "error":
        return "error"
    if "page" in event or event in {"accessibility_captured", "agent_observed", "observe", "step_recorded"}:
        return "page"
    if "action" in event or "edge" in event or event in {"agent_decision", "agent_decision_fallback"}:
        return "action"
    if "artifact" in event:
        return "artifact"
    if "run" in event or "login" in event or event == "skipped":
        return "run"
    return "raw"


def _infer_log_level(event: str, payload: dict) -> str:
    explicit = _string_value(payload.get("level")).lower()
    if explicit in {"info", "warning", "error"}:
        return explicit
    if event == "error" or _string_value(payload.get("status")) == "failed":
        return "error"
    if event in {"blocked", "skipped"}:
        return "warning"
    return "info"


def _build_log_summary(event: str, payload: dict) -> str:
    if event == "run_started":
        return f"开始探索 {_first_string(payload, ('url',)) or '目标站点'}"
    if event == "run_completed":
        return f"探索完成，状态 {_first_string(payload, ('status',)) or 'completed'}"
    if event in {"page_captured", "page_visited", "page_discovered"}:
        return f"采集页面 {_first_string(payload, ('title', 'page_id', 'url')) or '-'}"
    if event == "edge_created":
        return f"记录关系 {_first_string(payload, ('edge_id',))}：{_first_string(payload, ('source',)) or '-'} -> {_first_string(payload, ('target',)) or '-'}"
    if event == "agent_decision":
        return f"Agent 决策 {_first_string(payload, ('decision_type',)) or '-'}：{_first_string(payload, ('action',)) or '-'}"
    if event == "agent_decision_fallback":
        return f"Agent 决策降级：{_first_string(payload, ('reason',)) or '-'}"
    if event == "action_executed":
        return f"执行动作 {_first_string(payload, ('action', 'name', 'locator_hint')) or '-'}"
    if event in {"action_started", "action_result", "action_completed"}:
        return f"动作 {_first_string(payload, ('action', 'action_type')) or '-'}：{_first_string(payload, ('status', 'target')) or '-'}"
    if event == "step_recorded":
        title = _first_string(payload, ("title", "step_type")) or "探索步骤"
        detail = _first_string(payload, ("detail", "summary"))
        return f"{title}：{detail}" if detail else title
    if event in {"blocked", "skipped"}:
        return _first_string(payload, ("reason", "action", "page_id", "page")) or LOG_EVENT_LABELS.get(event, event)
    if event == "artifact_written":
        return f"写入产物 {_first_string(payload, ('artifact_path', 'file_path')) or '-'}"
    if event == "error":
        return _first_string(payload, ("message", "reason", "error")) or "探索执行错误"
    return _first_string(payload, ("summary", "recent_event", "message", "url", "page_id")) or LOG_EVENT_LABELS.get(event, event)


def _first_string(payload: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = _string_value(payload.get(key))
        if value:
            return value
    return ""


def _string_value(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _format_log_timestamp(value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        target_timezone = ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        target_timezone = timezone(timedelta(hours=8))
    return parsed.astimezone(target_timezone).strftime("%Y-%m-%d %H:%M:%S")


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
        requirement_doc_id = payload.requirement_doc_id.strip()
        _ensure_requirement_document_in_project(db, project_id, requirement_doc_id)

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
            requirement_doc_id=requirement_doc_id,
            title=payload.title.strip(),
            scope=payload.scope.strip(),
            forbidden_paths=payload.forbidden_paths.strip(),
            login_strategy=environment["login_strategy"],
            goal=payload.goal.strip(),
            notes=payload.notes.strip(),
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
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能修改。")
        if "environment_id" in updates:
            environment = environment_repo.find_by_id(db, updates["environment_id"])
            if not environment or environment["project_id"] != project_id:
                raise api_error(400, "INVALID_ENVIRONMENT", "请选择当前项目下的环境。")
        if "requirement_doc_id" in updates:
            updates["requirement_doc_id"] = str(updates["requirement_doc_id"] or "").strip()
            _ensure_requirement_document_in_project(db, project_id, updates["requirement_doc_id"])
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
        existing = _recover_stale_stopping_run(db, existing)
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "EXPLORATION_ALREADY_RUNNING", "探索任务正在执行。")
        if existing["status"] not in {"pending", "partial", "completed", "blocked", "cancelled"}:
            raise api_error(409, "EXPLORATION_NOT_STARTABLE", "当前状态不能发起探索。")
        plan = _load_exploration_plan(existing)
        has_discovery_artifacts = _has_first_discovery_artifacts(existing)
        if has_discovery_artifacts and plan["plan_status"] != "confirmed":
            raise api_error(409, "EXPLORATION_PLAN_NOT_CONFIRMED", "请先根据首次探索生成并确认探索计划，再按计划开始探索。")
        if plan["plan_status"] == "confirmed":
            plan["plan_status"] = "running"
        _remove_run_artifact_directory(existing)
        if plan["plan_status"] == "running":
            _write_exploration_plan(existing, plan)
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


def generate_project_run_plan(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能重新生成探索计划。")
        plan = _build_ai_generated_exploration_plan(existing)
        _write_exploration_plan(existing, plan)
        return plan


def update_project_run_plan(project_id: str, run_id: str, payload: ExplorationPlanUpdateIn, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能修改探索计划。")
        current = _load_exploration_plan(existing)
        if current["plan_status"] in {"running", "completed", "blocked"}:
            raise api_error(409, "EXPLORATION_PLAN_LOCKED", "探索计划已进入执行阶段，不能修改。")
        items = [_normalize_plan_item(item.model_dump(), index + 1, _plan_business_boundary(existing)) for index, item in enumerate(payload.items)]
        if not items:
            raise api_error(400, "EMPTY_EXPLORATION_PLAN", "探索计划至少需要一个计划项。")
        plan = {
            **current,
            "plan_status": "draft",
            "items": items,
            "summary": f"已人工调整 {len(items)} 个探索计划项，等待确认。",
        }
        _write_exploration_plan(existing, plan)
        return plan


def confirm_project_run_plan(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能确认探索计划。")
        plan = _load_exploration_plan(existing)
        if not plan["items"]:
            raise api_error(400, "EMPTY_EXPLORATION_PLAN", "请先生成或补充探索计划项。")
        plan["plan_status"] = "confirmed"
        plan["summary"] = f"已确认 {len(plan['items'])} 个探索计划项，可按计划开始探索。"
        _write_exploration_plan(existing, plan)
        return plan


def import_plan_from_requirement(project_id: str, run_id: str, payload: RequirementPlanImportIn, actor) -> dict:
    """从需求分析导入探索计划到探索任务"""
    from app.services import requirement_exploration_service

    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务执行中，不能修改探索计划。")
        current = _load_exploration_plan(existing)
        if current["plan_status"] in {"running", "completed", "blocked"}:
            raise api_error(409, "EXPLORATION_PLAN_LOCKED", "探索计划已进入执行阶段，不能修改。")

        # 获取需求探索计划
        req_plan = requirement_exploration_service.get_exploration_plan_from_requirement(
            project_id=project_id,
            document_id=payload.requirement_doc_id,
            run_id=payload.requirement_run_id,
            actor=actor,
        )

        # 转换为探索模块的计划格式
        business_boundary = req_plan.get("business_boundary", "")
        items = []
        for req_item in req_plan.get("items", []):
            # 转换为探索模块的item格式
            item = {
                "id": req_item.get("id", ""),
                "business_module": req_item.get("business_module", ""),
                "capability_type": req_item.get("capability_type", ""),
                "title": req_item.get("title", ""),
                "steps": req_item.get("steps", []),
                "exploration_points": req_item.get("exploration_points", []),
            }
            items.append(item)

        if not items:
            raise api_error(400, "EMPTY_REQUIREMENT_PLAN", "需求探索计划为空，无法导入。")

        # 更新探索计划
        plan = {
            **current,
            "plan_status": "draft",
            "business_boundary": business_boundary,
            "items": items,
            "summary": f"已从需求分析导入 {len(items)} 个探索计划项，等待确认。",
        }
        _write_exploration_plan(existing, plan)

        return plan


def _remove_run_artifact_directory(run) -> None:
    artifact_root = resolve_stored_path(run["artifact_root"])
    if artifact_root and artifact_root.exists():
        shutil.rmtree(artifact_root)


def stop_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        existing = _recover_stale_stopping_run(db, existing)
        before = _run_snapshot(existing)
        if existing["status"] in {"completed", "partial", "blocked", "cancelled"}:
            result = serialize_exploration_run(existing, actor["role"])
            after = _run_snapshot(result)
            should_log = False
        elif existing["status"] == "stopping":
            if existing["finished_at"]:
                exploration_repo.update_run_state(
                    db,
                    run_id,
                    status="cancelled",
                    result_summary=existing["result_summary"] or "用户已停止探索，已保留停止前生成的日志和产物。",
                    finished=True,
                )
                row = exploration_repo.find_by_id(db, run_id)
                result = serialize_exploration_run(row, actor["role"])
            else:
                result = serialize_exploration_run(existing, actor["role"])
            after = _run_snapshot(result)
            should_log = False
        elif existing["status"] in {"queued", "running"}:
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


def _recover_stale_stopping_run(db, run):
    if run["status"] != "stopping":
        return run
    terminal_status = _terminal_status_from_finished_run(run)
    if not terminal_status:
        return run
    summary = _recovered_stopping_summary(run["result_summary"], terminal_status)
    exploration_repo.update_run_state(db, run["id"], status=terminal_status, result_summary=summary, finished=True)
    return exploration_repo.find_by_id(db, run["id"]) or run


def _terminal_status_from_finished_run(run) -> str:
    log_content = _load_run_artifact_bundle(run).get("log_content", "")
    for entry in reversed(parse_exploration_log_entries(log_content)):
        event = entry.get("event")
        if event == "run_completed":
            return "completed"
        if event == "run_cancelled":
            return "cancelled"
        if event in {"run_failed", "blocked", "error"}:
            return "blocked"
    if run["finished_at"]:
        return "cancelled"
    return ""


def _stale_stopping_summary(status: str) -> str:
    return {
        "completed": "探索已完成，停止请求发生在任务结束后，状态已自动恢复。",
        "cancelled": "探索已停止，已保留停止前生成的日志和产物。",
        "blocked": "探索已结束但存在阻塞，请查看日志确认原因。",
    }.get(status, "探索任务已结束。")


def _recovered_stopping_summary(current_summary: str, status: str) -> str:
    if current_summary and "正在终止" not in current_summary and "正在停止" not in current_summary:
        return current_summary
    return _stale_stopping_summary(status)


def delete_project_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)
        if existing["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "RUNNING_EXPLORATION", "探索任务运行中，不能删除。")
        snapshot = _run_snapshot(existing)
        artifact_root = _resolve_run_artifact_root(existing)
        exploration_repo.delete(db, run_id)
    if artifact_root and artifact_root.exists():
        shutil.rmtree(artifact_root)
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


def _resolve_run_artifact_root(run) -> Path | None:
    artifact_root = resolve_stored_path(run["artifact_root"])
    if artifact_root is None:
        artifact_root = resolve_stored_path(f"{run['project_id']}/exploration/{run['id']}")
    project_root = resolve_stored_path(run["project_id"])
    if artifact_root is None:
        return None
    if project_root is None:
        return None
    if artifact_root.name != run["id"] or artifact_root.parent.name != "exploration":
        return None
    try:
        artifact_root.resolve().relative_to(project_root.resolve())
    except ValueError:
        return None
    return artifact_root


def _exploration_plan_path(run) -> Path | None:
    artifact_root = _resolve_run_artifact_root(run)
    if artifact_root is None:
        return None
    return artifact_root / "exploration-plan.yaml"


def _load_exploration_plan(run) -> dict:
    path = _exploration_plan_path(run)
    if not path or not path.exists():
        return _empty_exploration_plan(run)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return _empty_exploration_plan(run)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    boundary = str(data.get("business_boundary") or _plan_business_boundary(run))
    return {
        "artifact_schema_version": 1,
        "plan_status": str(data.get("plan_status") or "not_generated"),
        "business_boundary": boundary,
        "goal": str(data.get("goal") or _run_value(run, "goal", "")),
        "summary": str(data.get("summary") or ""),
        "items": [_normalize_plan_item(item, index + 1, boundary) for index, item in enumerate(items) if isinstance(item, dict)],
    }


def _write_exploration_plan(run, plan: dict) -> None:
    path = _exploration_plan_path(run)
    if path is None:
        raise api_error(500, "INVALID_ARTIFACT_ROOT", "探索任务产物目录无效，无法保存探索计划。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(plan, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")


def _empty_exploration_plan(run) -> dict:
    return {
        "artifact_schema_version": 1,
        "plan_status": "not_generated",
        "business_boundary": _plan_business_boundary(run),
        "goal": _run_value(run, "goal", ""),
        "summary": "尚未生成探索计划。",
        "items": [],
    }


def _has_first_discovery_artifacts(run) -> bool:
    artifacts = _load_run_artifact_bundle(run)
    if bool(artifacts.get("unsupported_artifact")):
        return False
    pages = artifacts.get("pages") if isinstance(artifacts.get("pages"), list) else []
    return any(isinstance(page, dict) and isinstance(page.get("content"), dict) for page in pages)


def _build_discovery_based_exploration_plan(run, artifact_bundle: dict) -> dict:
    if bool(artifact_bundle.get("unsupported_artifact")):
        raise api_error(409, "UNSUPPORTED_EXPLORATION_ARTIFACT", "历史探索产物无法生成探索计划，请先重新执行首次探索。")
    modules = _discovered_plan_modules(run, artifact_bundle)
    if not modules:
        raise api_error(409, "EXPLORATION_DISCOVERY_REQUIRED", "请先执行首次探索，采集探索范围内的模块。")
    boundary = _plan_business_boundary(run)
    items = [_module_plan_item(module, index) for index, module in enumerate(modules, start=1)]
    return {
        "artifact_schema_version": 1,
        "plan_status": "draft",
        "business_boundary": boundary,
        "goal": _run_value(run, "goal", ""),
        "summary": f"已根据首次探索采集结果生成 {len(items)} 个模块计划项，等待人工确认或补充。",
        "items": items,
    }


def _build_ai_generated_exploration_plan(run) -> dict:
    page_facts = _collect_scope_plan_facts(run)
    scope_constraints = _plan_scope_constraints(run, page_facts)
    try:
        output = asyncio.run(
            site_exploration_plan_service.generate_exploration_plan(
                ExplorationPlanInput(
                    run=_run_plan_context(run),
                    page_facts=page_facts,
                    scope_constraints=scope_constraints,
                )
            )
        )
    except Exception as error:
        raise api_error(502, "EXPLORATION_PLAN_AI_FAILED", f"AI 生成探索计划失败：{str(error)[:300]}") from error

    plan = _normalize_ai_exploration_plan(run, output, page_facts, scope_constraints)
    if not plan["items"]:
        raise api_error(409, "EXPLORATION_PLAN_MODULES_REQUIRED", "AI 未能根据当前探索范围识别模块，请补充探索范围或先人工确认页面内容。")
    return plan


def _collect_scope_plan_facts(run) -> dict:
    start_url = _run_site_url(run)
    if not start_url:
        raise api_error(409, "EXPLORATION_SITE_URL_REQUIRED", "探索环境未配置站点地址，无法访问探索范围生成计划。")
    storage_state_path = _stored_auth_state_path_for_run(run)
    try:
        with PlaywrightBrowserSession(
            start_url=start_url,
            storage_state_path=str(storage_state_path or ""),
            timeout_seconds=45,
        ) as session:
            observation = session.observe()
    except BrowserSessionError as error:
        raise api_error(502, "EXPLORATION_PLAN_COLLECT_FAILED", f"访问探索范围并采集页面事实失败：{str(error)[:300]}") from error
    return _plan_facts_from_observation(run, observation)


def _plan_facts_from_observation(run, observation: dict) -> dict:
    elements = observation.get("elements") if isinstance(observation.get("elements"), list) else []
    visible_elements = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        visible_elements.append(
            {
                "id": str(element.get("id") or ""),
                "role": str(element.get("role") or ""),
                "name": str(element.get("name") or ""),
                "text": str(element.get("text") or ""),
                "action_type": str(element.get("action_type") or ""),
                "enabled": bool(element.get("enabled", True)),
                "visible": bool(element.get("visible", True)),
            }
        )
    return {
        "url": str(observation.get("url") or ""),
        "normalized_url": str(observation.get("normalized_url") or observation.get("url") or ""),
        "title": str(observation.get("title") or ""),
        "page_text_summary": str(observation.get("page_text_summary") or observation.get("text_summary") or ""),
        "scope": _run_value(run, "scope", ""),
        "goal": _run_value(run, "goal", ""),
        "forbidden_paths": _run_value(run, "forbidden_paths", ""),
        "elements": visible_elements[:120],
    }


def _run_plan_context(run) -> dict:
    return {
        "id": _run_value(run, "id", ""),
        "title": _run_value(run, "title", ""),
        "scope": _run_value(run, "scope", ""),
        "goal": _run_value(run, "goal", ""),
        "forbidden_paths": _run_value(run, "forbidden_paths", ""),
        "site_url": _run_site_url(run),
        "environment_name": _run_value(run, "environment_name", ""),
    }


def _normalize_ai_exploration_plan(
    run,
    output: ExplorationPlanOutput,
    page_facts: dict,
    scope_constraints: dict | None = None,
) -> dict:
    boundary = _plan_business_boundary(run)
    items = _dom_group_plan_items(boundary, page_facts)
    skipped_modules = []
    scope_constraints = scope_constraints or _plan_scope_constraints(run, page_facts)
    used_capability_types = {str(item.get("capability_type") or "") for item in items}
    for index, module in enumerate(output.modules, start=1):
        module_name = module.module_name.strip()
        if not module_name:
            continue
        capability_type = _capability_type_from_module_name(module_name)
        if capability_type in used_capability_types:
            continue
        if not _module_matches_plan_scope(module, scope_constraints):
            skipped_modules.append(module_name)
            continue
        if capability_type == "custom":
            continue
        steps = module.steps or [
            f"基于真实 DOM 入口探索{module_name}",
            "记录该功能内的操作结果和页面变化",
        ]
        item = _normalize_plan_item(
            {
                "id": f"plan-ai-module-{index:02d}",
                "business_module": boundary,
                "capability_type": capability_type,
                "title": module_name,
                "steps": steps,
                "exploration_points": [module.reason, module.entry_hint],
                "entry_path": str(page_facts.get("normalized_url") or page_facts.get("url") or ""),
            },
            index,
            boundary,
        )
        items.append(item)
        used_capability_types.add(capability_type)
    summary = f"AI 已根据探索范围和 DOM 元素分组生成 {len(items)} 个功能计划项，等待人工确认或补充。"
    if skipped_modules:
        summary = f"{summary} 已过滤范围外模块：{'、'.join(skipped_modules)}。"
    return {
        "artifact_schema_version": 1,
        "plan_status": "draft",
        "business_boundary": boundary,
        "goal": _run_value(run, "goal", ""),
        "summary": summary,
        "items": items,
    }


def _capability_type_from_module_name(module_name: str) -> str:
    text = str(module_name or "").lower()
    if _contains_any(text, ("搜索", "查询", "筛选", "过滤", "排序", "标签", "search", "filter", "sort")):
        return "query_filter"
    if _contains_any(text, ("视图", "宫格", "网格", "列表视图", "布局", "view", "grid", "layout")):
        return "view_switch"
    if _contains_any(text, ("卡片", "更多菜单", "主操作", "对话历史", "日志查询", "复制", "下线", "card", "menu")):
        return "card_action"
    if _contains_any(text, ("创建导入", "创建", "新增", "新建", "导入", "上传", "create", "new", "add", "import", "upload")):
        return "create_import"
    if _contains_any(text, ("导入", "导出", "上传", "下载", "模板", "import", "export", "upload", "download")):
        return "import_export"
    if _contains_any(text, ("批量", "全选", "多选", "batch", "select all")):
        return "batch_operation"
    if _contains_any(text, ("新增", "新建", "创建", "查看", "详情", "编辑", "删除", "保存", "crud", "create", "detail", "edit", "delete")):
        return "crud"
    if _contains_any(text, ("卡片", "列表", "表格", "展示", "内容", "card", "list", "table")):
        return "content_display"
    return "custom"


def _dom_group_plan_items(boundary: str, page_facts: dict) -> list[dict]:
    groups = _classify_plan_dom_groups(page_facts)
    entry_path = str(page_facts.get("normalized_url") or page_facts.get("url") or "")
    items: list[dict] = []
    for definition in _dom_plan_definitions():
        capability_type = definition["capability_type"]
        sources = groups.get(capability_type, [])
        if not sources:
            continue
        index = len(items) + 1
        items.append(
            _normalize_plan_item(
                {
                    "id": f"plan-dom-{capability_type}-{index:02d}",
                    "business_module": boundary,
                    "capability_type": capability_type,
                    "title": definition["title"],
                    "steps": [step.replace("当前模块", boundary) for step in definition["steps"]],
                    "exploration_points": [
                        f"已发现入口：{_format_dom_sources(sources)}",
                        *definition["exploration_points"],
                    ],
                    "entry_path": entry_path,
                },
                index,
                boundary,
            )
        )
    return items


def _classify_plan_dom_groups(page_facts: dict) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for element in page_facts.get("elements") if isinstance(page_facts.get("elements"), list) else []:
        if not isinstance(element, dict):
            continue
        text = _plan_element_text(element)
        if not text:
            continue
        for capability_type in _capability_types_for_element(element, text):
            groups.setdefault(capability_type, [])
            if text not in groups[capability_type]:
                groups[capability_type].append(text)
    _merge_card_menu_sources(groups)
    return groups


def _merge_card_menu_sources(groups: dict[str, list[str]]) -> None:
    card_sources = groups.get("card_action", [])
    if not card_sources:
        return
    display_sources = groups.get("content_display", [])
    card_display_sources = [source for source in display_sources if _contains_any(source, ("卡片", "card"))]
    for source in card_display_sources:
        if source not in card_sources:
            card_sources.append(source)
    groups["content_display"] = [source for source in display_sources if source not in card_display_sources]
    if not groups["content_display"]:
        groups.pop("content_display", None)
    has_menu_context = any(
        _contains_any(source, ("更多", "日志查询", "更新发布平台", "复制", "下线", "对话历史"))
        for source in card_sources
    )
    if not has_menu_context:
        return
    query_sources = groups.get("query_filter", [])
    menu_query_sources = [source for source in query_sources if _contains_any(source, ("日志查询",))]
    for source in menu_query_sources:
        if source not in card_sources:
            card_sources.append(source)
    groups["query_filter"] = [source for source in query_sources if source not in menu_query_sources]
    if not groups["query_filter"]:
        groups.pop("query_filter", None)
    import_sources = groups.get("import_export", [])
    menu_export_sources = [source for source in import_sources if _contains_any(source, ("导出", "下载"))]
    for source in menu_export_sources:
        if source not in card_sources:
            card_sources.append(source)
    groups["import_export"] = [source for source in import_sources if source not in menu_export_sources]
    if not groups["import_export"]:
        groups.pop("import_export", None)


def _capability_types_for_element(element: dict, text: str) -> list[str]:
    haystack = f"{text} {element.get('role') or ''} {element.get('action_type') or ''}".lower()
    role = str(element.get("role") or "").lower()
    action_type = str(element.get("action_type") or "").lower()
    types: list[str] = []
    if role in {"textbox", "searchbox", "combobox", "select", "tab"} or action_type == "fill":
        if _contains_any(haystack, ("搜索", "查询", "筛选", "过滤", "排序", "类型", "状态", "日期", "重置", "全部", "search", "query", "filter", "sort", "status", "date", "reset")):
            types.append("query_filter")
    if _contains_any(haystack, ("搜索", "查询", "筛选", "过滤", "排序", "重置", "search", "query", "filter", "sort", "reset")):
        types.append("query_filter")
    if _contains_any(haystack, ("视图", "宫格", "网格", "列表视图", "布局", "view", "grid", "layout")):
        types.append("view_switch")
    if _contains_any(
        haystack,
        (
            "卡片",
            "分析",
            "使用",
            "对话历史",
            "更多",
            "日志查询",
            "更新发布平台",
            "复制",
            "下线",
            "card",
            "history",
            "more",
            "copy",
        ),
    ):
        types.append("card_action")
    if _contains_any(haystack, ("创建", "新增", "新建", "导入", "上传", "create", "new", "add", "import", "upload")):
        types.append("create_import")
    if not _contains_any(haystack, ("视图", "view")) and _contains_any(haystack, ("卡片", "列表", "表格", "统计", "缩略图", "card", "list", "table", "row")):
        types.append("content_display")
    if _contains_any(haystack, ("查看", "详情", "编辑", "修改", "删除", "保存", "取消", "确认", "view", "detail", "edit", "update", "delete", "save", "cancel", "confirm")):
        types.append("crud")
    if _contains_any(haystack, ("导出", "下载", "模板", "文件", "export", "download", "template", "file")):
        types.append("import_export")
    if role in {"checkbox"} or _contains_any(haystack, ("批量", "全选", "多选", "选择", "batch", "select all", "checkbox")):
        types.append("batch_operation")
    return _unique_preserve_order(types)


def _plan_element_text(element: dict) -> str:
    readable = str(element.get("name") or element.get("text") or "").strip()
    if readable:
        return re.sub(r"\s+", " ", readable).strip()[:80]
    candidates = [element.get("id")]
    text = " ".join(str(item).strip() for item in candidates if str(item or "").strip())
    return re.sub(r"\s+", " ", text).strip()[:80]


def _format_dom_sources(sources: list[str]) -> str:
    return "、".join(sources[:8])


def _dom_plan_definitions() -> list[dict]:
    return [
        {
            "capability_type": "query_filter",
            "title": "查询筛选功能",
            "steps": ["完整探索当前模块中的查询、筛选、搜索、排序能力，记录可操作项、交互结果、数据变化和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "view_switch",
            "title": "视图切换功能",
            "steps": ["完整探索当前模块中的视图切换能力，记录可切换视图、切换结果、信息展示变化和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "content_display",
            "title": "内容展示功能",
            "steps": ["完整探索当前模块中的内容展示能力，记录字段展示、状态标识、入口操作、信息展示变化和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "card_action",
            "title": "卡片功能",
            "steps": ["完整探索当前模块中卡片的信息展示、主操作按钮和更多菜单，记录卡片字段、按钮入口、菜单项、交互结果和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "create_import",
            "title": "创建导入功能",
            "steps": ["完整探索当前模块中的创建和导入入口，记录入口位置、打开结果、流程边界、可操作项和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "crud",
            "title": "CRUD 功能",
            "steps": ["完整探索当前模块中真实出现的新增、查看、编辑、删除等操作入口，记录流程边界、可操作项、交互结果和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "import_export",
            "title": "导入导出功能",
            "steps": ["完整探索当前模块中的导入、导出、上传或下载入口，记录入口位置、打开结果、流程边界、可操作项和过程中发现的问题。"],
            "exploration_points": [],
        },
        {
            "capability_type": "batch_operation",
            "title": "批量操作功能",
            "steps": ["完整探索当前模块中的批量选择和批量操作能力，记录选择规则、可用条件、确认结果和过程中发现的问题。"],
            "exploration_points": [],
        },
    ]


def _contains_any(value: str, needles: tuple[str, ...]) -> bool:
    text = str(value or "").lower()
    return any(needle.lower() in text for needle in needles)


def _plan_scope_constraints(run, page_facts: dict | None = None) -> dict:
    scope = _run_value(run, "scope", "").strip()
    allow_all = not scope or _is_full_site_scope(scope)
    allowed_terms = [] if allow_all else _scope_constraint_terms(scope)
    page_facts = page_facts if isinstance(page_facts, dict) else {}
    return {
        "scope": scope,
        "allow_all": allow_all,
        "allowed_terms": allowed_terms,
        "instruction": (
            "scope 未限制具体模块，可基于页面事实识别模块。"
            if allow_all
            else "只能生成 allowed_terms 或 scope 明确包含的模块；同级导航、相邻菜单和范围外页面必须忽略。"
        ),
        "current_url": str(page_facts.get("normalized_url") or page_facts.get("url") or ""),
        "current_title": str(page_facts.get("title") or ""),
    }


def _scope_constraint_terms(scope: str) -> list[str]:
    named_items = _scope_named_items(scope)
    candidates = named_items or _split_scope_terms(scope)
    terms: list[str] = []
    for candidate in candidates:
        text = _clean_scope_term(candidate)
        if text:
            terms.append(text)
        route_label = _scope_route_label(text)
        if route_label:
            terms.append(route_label)
    return _unique_preserve_order(terms)


def _split_scope_terms(scope: str) -> list[str]:
    normalized = re.sub(r"\s*和\s*", "\n", scope)
    normalized = re.sub(r"\s*及\s*", "\n", normalized)
    return [item.strip() for item in re.split(r"[、,，;；。\n]+", normalized) if item.strip()]


def _clean_scope_term(term: str) -> str:
    text = str(term or "").strip()
    text = re.sub(r"^范围包含[：:]", "", text).strip()
    text = re.sub(r"(模块|页面|菜单|入口|路径|URL)$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"(的)?(全部内容|全部模块|相关内容|范围|探索)$", "", text).strip()
    return text[:80]


def _scope_route_label(term: str) -> str:
    route_labels = {
        "agentStore": "探索广场",
        "workspace": "工作台",
        "agentAnalysis": "效果评测",
        "resource": "资源库",
        "publish": "发布管理",
        "manage": "管理中心",
    }
    normalized = str(term or "").strip("/").split("?")[0]
    for segment, label in route_labels.items():
        if segment in normalized:
            return label
    return ""


def _module_matches_plan_scope(module: ExplorationPlanModule, scope_constraints: dict) -> bool:
    if bool(scope_constraints.get("allow_all")):
        return True
    allowed_terms = [str(item).strip() for item in scope_constraints.get("allowed_terms", []) if str(item).strip()]
    if not allowed_terms:
        return True
    haystack = _scope_match_text(
        " ".join(
            [
                module.module_name,
                module.reason,
                module.entry_hint,
                " ".join(module.steps),
            ]
        )
    )
    module_name = _scope_match_text(module.module_name)
    scope_text = _scope_match_text(str(scope_constraints.get("scope") or ""))
    for term in allowed_terms:
        normalized_term = _scope_match_text(term)
        if not normalized_term:
            continue
        if normalized_term in module_name or module_name in normalized_term:
            return True
        if normalized_term in haystack:
            return True
        if module_name and module_name in scope_text:
            return True
    return False


def _scope_match_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _discovered_plan_modules(run, artifact_bundle: dict) -> list[dict]:
    pages = artifact_bundle.get("pages") if isinstance(artifact_bundle.get("pages"), list) else []
    modules: dict[str, dict] = {}
    fallback_module = _plan_business_boundary(run)
    for page_item in pages:
        if not isinstance(page_item, dict):
            continue
        content = page_item.get("content") if isinstance(page_item.get("content"), dict) else {}
        page = content.get("page") if isinstance(content.get("page"), dict) else {}
        module_name = str(page.get("module") or fallback_module).strip() or fallback_module
        module = modules.setdefault(
            module_name,
            {
                "name": module_name,
                "entry_path": str(page.get("normalized_url") or page.get("url") or "").strip(),
                "page_titles": [],
                "page_count": 0,
                "action_count": 0,
                "field_count": 0,
                "blocked_count": 0,
            },
        )
        if not module["entry_path"]:
            module["entry_path"] = str(page.get("normalized_url") or page.get("url") or "").strip()
        title = str(page.get("title") or page.get("semantic_title") or page.get("url") or "").strip()
        if title and title not in module["page_titles"]:
            module["page_titles"].append(title)
        module["page_count"] += 1
        module["action_count"] += len(content.get("actions")) if isinstance(content.get("actions"), list) else 0
        module["field_count"] += len(content.get("forms")) if isinstance(content.get("forms"), list) else 0
        status = str(page.get("status") or "").strip()
        if status in {"blocked", "failed"}:
            module["blocked_count"] += 1
    return list(modules.values())


def _module_plan_item(module: dict, index: int) -> dict:
    name = str(module["name"])
    entry_path = str(module.get("entry_path") or "")
    page_titles = [str(title) for title in module.get("page_titles", []) if str(title).strip()]
    sampled_pages = "、".join(page_titles[:3]) if page_titles else "首次探索采集页面"
    steps = [
        f"进入{name}模块入口" + (f"（{entry_path}）" if entry_path else ""),
        f"按首次探索采集结果复核页面：{sampled_pages}",
        "补充遗漏入口、关键页面状态和阻塞原因",
    ]
    exploration_points = [
        f"覆盖{name}模块已采集的 {int(module.get('page_count') or 0)} 个页面/状态",
        f"记录模块动作、表单和跳转证据（已发现 {int(module.get('action_count') or 0)} 个动作）",
    ]
    if int(module.get("blocked_count") or 0):
        exploration_points.append(f"复核 {int(module.get('blocked_count') or 0)} 个阻塞页面并记录处理建议")
    return _normalize_plan_item(
        {
            "id": f"plan-module-{index:02d}",
            "business_module": name,
            "capability_type": "module_discovery",
            "title": f"探索{name}模块",
            "steps": steps,
            "exploration_points": exploration_points,
        },
        index,
        name,
    )


def _build_default_exploration_plan(run) -> dict:
    boundary = _plan_business_boundary(run)
    items = [
        _plan_item(boundary, "access", "访问边界首页", ["进入指定探索边界", "确认主内容区、导航和核心入口出现"], ["页面访问", "导航与主内容"], 1),
        _plan_item(boundary, "search", f"搜索{boundary}内容", ["定位搜索框", "输入关键词并观察结果区变化"], ["搜索入口", "结果区状态"], 2),
        _plan_item(boundary, "filter", f"筛选{boundary}内容", ["识别类型、范围、状态等筛选控件", "至少展开一个筛选项"], ["筛选入口", "筛选项与回显"], 3),
        _plan_item(boundary, "sort", f"排序{boundary}列表", ["识别排序控件", "切换排序条件"], ["排序入口", "排序回显"], 4),
        _plan_item(boundary, "create", f"打开{boundary}新建入口", ["点击创建或新增入口", "检查弹窗或创建页字段", "取消提交并返回"], ["新建入口", "表单结构"], 5),
        _plan_item(boundary, "import", f"检查{boundary}导入入口", ["点击导入入口", "检查上传控件、模板或格式限制", "关闭弹窗"], ["导入入口", "上传限制和模板入口"], 6),
        _plan_item(boundary, "detail", f"查看{boundary}详情", ["点击一条列表、卡片或业务对象", "记录详情页、抽屉或弹窗内容"], ["详情入口", "详情字段和返回路径"], 7),
        _plan_item(boundary, "agent_usage", f"验证{boundary}智能体使用入口", ["识别使用、试用、运行或对话入口", "进入入口并记录状态", "遇到扣费、发布或外部调用时停止"], ["智能体使用入口", "运行前状态和阻塞原因"], 8),
        _plan_item(boundary, "empty_state", f"检查{boundary}空状态", ["观察无数据状态", "记录空状态文案和主按钮"], ["空状态文案", "空状态引导入口"], 9),
    ]
    return {
        "artifact_schema_version": 1,
        "plan_status": "draft",
        "business_boundary": boundary,
        "goal": _run_value(run, "goal", ""),
        "summary": f"已根据“{boundary}”边界生成 {len(items)} 个探索计划项，等待人工确认或补充。",
        "items": items,
    }


def _plan_item(
    boundary: str,
    capability_type: str,
    title: str,
    steps: list[str],
    exploration_points: list[str],
    index: int,
) -> dict:
    return _normalize_plan_item(
        {
            "id": f"plan-{capability_type}-{index:02d}",
            "business_module": boundary,
            "capability_type": capability_type,
            "title": title,
            "steps": steps,
            "exploration_points": exploration_points,
        },
        index,
        boundary,
    )


def _normalize_plan_item(raw: dict, index: int, boundary: str) -> dict:
    capability_type = str(raw.get("capability_type") or "custom").strip() or "custom"
    item = {
        "id": str(raw.get("id") or f"plan-{capability_type}-{index:02d}"),
        "business_module": str(raw.get("business_module") or boundary),
        "capability_type": capability_type,
        "title": str(raw.get("title") or f"{boundary}探索计划项"),
        "steps": _string_list(raw.get("steps")),
        "exploration_points": _string_list(raw.get("exploration_points")),
    }
    entry_path = str(raw.get("entry_path") or "").strip()
    if entry_path:
        item["entry_path"] = entry_path
    return item


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _plan_business_boundary(run) -> str:
    scope = _run_value(run, "scope", "").strip()
    if scope:
        return scope.splitlines()[0][:80]
    goal = _run_value(run, "goal", "").strip()
    if goal:
        return goal.splitlines()[0][:80]
    return _run_value(run, "title", "站点入口").strip() or "站点入口"


def _run_value(run, key: str, default: str = "") -> str:
    if isinstance(run, dict):
        return str(run.get(key) or default)
    if key in run.keys():
        return str(run[key] or default)
    return default


def _run_site_url(run) -> str:
    return _run_value(run, "environment_site_url", "").strip()


def _stored_auth_state_path_for_run(run) -> Path | None:
    login_strategy, _, reuse_auth_state = _snapshot_auth_config(run)
    if login_strategy != "account_password" or not reuse_auth_state:
        return None
    path = auth_state_path(_run_value(run, "project_id", ""), _run_value(run, "environment_id", ""))
    return path if path.exists() else None


def _ensure_project_visible(project, actor) -> None:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    project_name = project["project_name"] if "project_name" in project.keys() else project["name"]
    if project_name == actor["project_scope"]:
        return
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _ensure_requirement_document_in_project(db, project_id: str, requirement_doc_id: str) -> None:
    if not requirement_doc_id:
        return
    document = document_repo.find_by_project_and_id(db, project_id, requirement_doc_id)
    if not document:
        raise api_error(400, "INVALID_REQUIREMENT_DOCUMENT", "请选择当前项目下的需求。")


def _status_to_completion(status: str) -> str:
    if status == "completed":
        return "completed"
    if status == "blocked":
        return "blocked"
    if status in {"queued", "running", "stopping"}:
        return "in-progress"
    if status == "cancelled":
        return "blocked"
    if status == "partial":
        return "partial"
    return "pending"


def _normalize_page_display_status(status: str | None) -> str:
    normalized = str(status or "").strip()
    if normalized == "explored":
        return "completed"
    if normalized in AGENT_PLAN_DISPLAY_STATUSES:
        return normalized
    return "pending"


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
    field_map = {
        "environment_id": "environment_id",
        "requirement_doc_id": "requirement_doc_id",
        "title": "title",
        "scope": "scope",
        "forbidden_paths": "forbidden_paths",
        "login_strategy": "login_strategy",
        "goal": "goal",
        "notes": "notes",
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
    if run["status"] in {"queued", "running", "stopping"}:
        modules = {}
        completion_status = _planned_module_status(run["status"])
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
                "completion_status": completion_status,
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


def _planned_module_status(run_status: str) -> str:
    if run_status in {"running", "stopping"}:
        return run_status
    return "pending"


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
    login_strategy, captcha_strategy, reuse_auth_state = _snapshot_auth_config(run)
    has_login_credentials = _snapshot_value(run, "has_login_credentials", None)
    if has_login_credentials is None:
        has_login_credentials = bool(
            login_strategy == "account_password"
            and str(_snapshot_value(run, "environment_username", "") or "").strip()
            and _snapshot_value(run, "environment_has_password", 0)
        )
    return {
        "title": run["title"],
        "status": run["status"],
        "environment_id": run["environment_id"],
        "requirement_doc_id": _snapshot_value(run, "requirement_doc_id", ""),
        "requirement_doc_title": _snapshot_value(run, "requirement_doc_title", ""),
        "scope": run["scope"],
        "forbidden_paths": run["forbidden_paths"],
        "login_strategy": login_strategy,
        "captcha_strategy": captcha_strategy,
        "reuse_auth_state": reuse_auth_state,
        "has_login_credentials": bool(has_login_credentials),
        "goal": run["goal"],
        "notes": run["notes"],
        "max_pages": run["max_pages"],
        "max_actions": run["max_actions"],
        "timeout_minutes": run["timeout_minutes"],
        "result_summary": run["result_summary"],
    }


def _snapshot_auth_config(run) -> tuple[str, str, bool]:
    login_strategy = str(_snapshot_value(run, "environment_login_strategy", _snapshot_value(run, "login_strategy", "skip_login")) or "skip_login")
    captcha_strategy = str(_snapshot_value(run, "environment_captcha_strategy", _snapshot_value(run, "captcha_strategy", "none")) or "none")
    reuse_auth_state = _snapshot_bool(
        _snapshot_value(run, "environment_reuse_auth_state", _snapshot_value(run, "reuse_auth_state", login_strategy != "skip_login")),
        default=login_strategy != "skip_login",
    )
    if login_strategy == "skip_login":
        return "skip_login", "none", False
    if captcha_strategy == "manual" and not reuse_auth_state:
        return "account_password", "none", False
    return login_strategy, captcha_strategy, reuse_auth_state


def _snapshot_value(run, key: str, default=None):
    return run[key] if key in run.keys() else default


def _snapshot_bool(value, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _load_run_artifacts(run, bundle: dict | None = None) -> tuple[list[dict], list[dict], list[dict]]:
    bundle = bundle or _load_run_artifact_bundle(run)
    if bundle.get("unsupported_artifact"):
        return [], [], []
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
                "structure_summary": page.get("structure_summary") or page.get("title", ""),
                "yaml_path": page_item.get("file_path", ""),
                "status": _normalize_page_display_status(page.get("status")),
                "blocker_reason": "",
                "recent_event": "",
                "steps": _normalize_steps(content.get("steps", [])),
            }
        )
        elements.extend(_elements_from_v2_states(content, page, page_item))
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


def _elements_from_v2_states(content: dict, page: dict, page_item: dict) -> list[dict]:
    states = content.get("states") if isinstance(content.get("states"), list) else []
    page_id = str(page.get("id") or page_item.get("file_path", ""))
    module_key = str(page.get("module") or "site-entry")
    source_ref = str(page.get("url") or "")
    elements = []
    for state_index, state in enumerate(states, start=1):
        if not isinstance(state, dict):
            continue
        state_id = str(state.get("id") or f"state-{state_index:03d}")
        raw_elements = state.get("elements") if isinstance(state.get("elements"), list) else []
        for element_index, element in enumerate(raw_elements, start=1):
            if not isinstance(element, dict):
                continue
            primary_selector = element.get("primary_selector") if isinstance(element.get("primary_selector"), dict) else {}
            fallback_selector = element.get("fallback_selector") if isinstance(element.get("fallback_selector"), dict) else {}
            name = str(element.get("name") or element.get("label") or _selector_code(primary_selector) or "未命名元素")
            role = str(element.get("role") or element.get("type") or "element")
            element_id = str(element.get("id") or f"element-{element_index:03d}")
            elements.append(
                {
                    "id": f"{page_id}:{state_id}:{element_id}",
                    "page_id": page_id,
                    "module_key": module_key,
                    "element_name": name,
                    "element_type": role,
                    "recommended_locator": _selector_code(primary_selector),
                    "fallback_locator": _selector_code(fallback_selector),
                    "stability_note": _selector_stability_note(primary_selector),
                    "source_ref": source_ref,
                    "primary_selector": primary_selector,
                    "fallback_selector": fallback_selector,
                }
            )
    return elements


def _selector_code(selector: dict) -> str:
    return str(selector.get("code") or "") if isinstance(selector, dict) else ""


def _selector_stability_note(selector: dict) -> str:
    verification = selector.get("verification") if isinstance(selector.get("verification"), dict) else {}
    if verification.get("checked") and verification.get("unique") and verification.get("visible"):
        return "主 selector 已通过唯一性和可见性校验。"
    if verification.get("checked"):
        return "主 selector 未通过唯一性或可见性校验，生成自动化前需复核。"
    return "主 selector 尚未完成唯一性和可见性校验。"


def _normalize_steps(raw_steps) -> list[dict]:
    if not isinstance(raw_steps, list):
        return []
    steps = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        step_id = str(raw_step.get("id") or f"step-{index:03d}")
        title = str(raw_step.get("title") or raw_step.get("detail") or raw_step.get("type") or "探索步骤")
        steps.append(
            {
                "id": step_id,
                "type": str(raw_step.get("type") or "event"),
                "title": title,
                "detail": str(raw_step.get("detail") or ""),
                "status": str(raw_step.get("status") or "completed"),
                "occurred_at": raw_step.get("occurred_at") if raw_step.get("occurred_at") else None,
                "artifact_path": str(raw_step.get("artifact_path") or ""),
                "source": str(raw_step.get("source") or ""),
            }
        )
    return steps


def _load_run_artifact_bundle(run) -> dict:
    artifact_root = resolve_stored_path(run["artifact_root"])
    if not artifact_root:
        return {
            "artifact_schema_version": 0,
            "unsupported_artifact": False,
            "unsupported_reason": "",
            "run": {},
            "summary": {},
            "graph": {},
            "blockers": {},
            "goal_validation": {},
            "pages": [],
            "log_content": "",
            "report_content": "",
            "report_path": "",
            "log_path": "",
        }
    bundle = exploration_artifact_service.load_exploration_run_artifacts(artifact_root)
    bundle["log_path"] = f"{run['artifact_root'].rstrip('/')}/logs/run.log"
    if not bundle.get("goal_validation"):
        bundle["goal_validation"] = _goal_validation_from_bundle(run, bundle)
    return bundle


def _goal_validation_from_bundle(run, bundle: dict) -> dict:
    existing = bundle.get("goal_validation") if isinstance(bundle.get("goal_validation"), dict) else {}
    if existing:
        return existing
    summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
    summary_validation = summary.get("goal_validation") if isinstance(summary.get("goal_validation"), dict) else {}
    if summary_validation:
        return summary_validation
    if isinstance(run, dict):
        goal = str(run.get("goal") or summary.get("goal", "") or "")
    else:
        goal = str(run["goal"] if "goal" in run.keys() else summary.get("goal", "") or "")
    if goal:
        return {"goal": goal, "status": "pending", "summary": "目标验证尚未执行。", "stats": {}, "items": []}
    return {"goal": "", "status": "skipped", "summary": "未设置探索目标。", "stats": {}, "items": []}
