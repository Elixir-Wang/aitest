import json
import secrets
import shutil
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.presentation.serializers import serialize_exploration_run
from app.repositories import environment_repo, exploration_repo, project_repo
from app.schemas.exploration import ExplorationRunCreateIn, ExplorationRunUpdateIn
from app.services import operation_log_service
from app.services.exploration import artifact_service as exploration_artifact_service

STATUSES = {"pending", "queued", "running", "waiting_human", "stopping", "cancelled", "partial", "completed", "blocked"}
LOGIN_STRATEGIES = {"reuse_state", "manual", "account_password", "skip_login"}
AGENT_PLAN_DISPLAY_STATUSES = {
    "pending",
    "queued",
    "running",
    "in-progress",
    "stopping",
    "completed",
    "partial",
    "blocked",
    "waiting_human",
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
    "edge_created": "记录关系",
    "artifact_written": "写入产物",
    "blocked": "探索阻塞",
    "skipped": "跳过",
    "safety_blocked": "安全拦截",
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
        }


def get_project_run_report(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        existing = exploration_repo.find_by_id(db, run_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "探索任务不存在。")
        _ensure_project_visible(existing, actor)

        artifacts = _load_run_artifact_bundle(existing)
        unsupported = bool(artifacts.get("unsupported_artifact"))
        markdown_content = "" if unsupported else str(artifacts.get("report_content") or "")
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
    recent_page = pages[-1] if pages else {}
    blocker_summary = "无"
    if blockers:
        blocker_summary = str(blockers[0].get("reason") or blockers[0].get("reason_type") or "存在阻塞项")
    progress_percent = min(100, round((explored / max(planned, explored, 1)) * 100))
    module["planned_page_count"] = planned
    module["explored_page_count"] = explored
    module["blocked_page_count"] = blocked
    module["recent_page_title"] = str(recent_page.get("title") or "")
    module["recent_page_url"] = str(recent_page.get("url") or "")
    module["blocker_summary"] = blocker_summary
    module["progress_percent"] = progress_percent
    module["page_progress_text"] = f"{explored}/{planned} 页面"
    if not module.get("completion_summary") or _looks_like_run_summary(str(module.get("completion_summary"))):
        module["completion_summary"] = _module_progress_summary(module)


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


def _looks_like_run_summary(value: str) -> bool:
    return "已探索" in value and "可交互元素" in value and "阻塞项" in value


def _module_progress_summary(module: dict) -> str:
    recent = module.get("recent_page_title") or "无"
    blocker = module.get("blocker_summary") or "无"
    if blocker != "无":
        return f"页面进度 {module['page_progress_text']}，最近页面：{recent}，阻塞：{blocker}。"
    return f"页面进度 {module['page_progress_text']}，最近页面：{recent}，无阻塞。"


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
    if event == "safety_blocked":
        return "safety"
    if event == "error":
        return "error"
    if "page" in event or event == "accessibility_captured":
        return "page"
    if "action" in event or "edge" in event:
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
    if event in {"blocked", "safety_blocked", "skipped"}:
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
    if event == "action_executed":
        return f"执行动作 {_first_string(payload, ('action', 'name', 'locator_hint')) or '-'}"
    if event in {"blocked", "safety_blocked", "skipped"}:
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
    return parsed.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")


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
        _remove_run_artifact_directory(existing)
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
    if run["status"] in {"queued", "running", "waiting_human", "stopping"}:
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
    if run_status in {"running", "waiting_human", "stopping"}:
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
            and str(_snapshot_value(run, "environment_password_mask", "") or "").strip()
        )
    return {
        "title": run["title"],
        "status": run["status"],
        "environment_id": run["environment_id"],
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
    if login_strategy == "reuse_state":
        return "account_password", "none", True
    if login_strategy == "manual":
        return "account_password", "manual", True
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
