import json
import logging
import re
import secrets
from sqlite3 import Row
from typing import Any
from urllib.parse import urlsplit

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.logging import get_trace_id
from app.repositories import operation_log_repo, project_repo
from app.schemas.operation_log import (
    ClientErrorReport,
    ClientErrorReportOut,
    OperationLogCleanupRequest,
    OperationLogCleanupResult,
    OperationLogCreate,
    OperationLogListOut,
    OperationLogQuery,
    OperationLogRetentionPolicyOut,
    OperationLogRetentionPolicyUpdate,
)

SENSITIVE_KEYS = {
    "password",
    "token",
    "api_key",
    "apikey",
    "secret",
    "authorization",
    "cookie",
    "captcha",
    "verification_code",
    "access_key",
}
SENSITIVE_PATTERN = re.compile(
    r"(?i)(password|token|api[_-]?key|secret|authorization|cookie|captcha|verification[_-]?code|access[_-]?key)"
    r"(\s*[:=]\s*)"
    r"([^\s,;]+)"
)
logger = logging.getLogger(__name__)


def record_success(**kwargs) -> str | None:
    payload = OperationLogCreate(result="success", **kwargs)
    return _record(payload)


def record_failure(*, failure_reason: str, **kwargs) -> str | None:
    payload = OperationLogCreate(result="failed", failure_reason=failure_reason, **kwargs)
    return _record(payload)


def record_change(*, before: Any = None, after: Any = None, **kwargs) -> str | None:
    payload = OperationLogCreate(before=before, after=after, result="success", **kwargs)
    return _record(payload)


def record_task_event(**kwargs) -> str | None:
    payload = OperationLogCreate(log_type="task", source=kwargs.pop("source", "system"), **kwargs)
    return _record(payload)


def record_agent_run(**kwargs) -> str | None:
    payload = OperationLogCreate(log_type="agent", source=kwargs.pop("source", "agent"), **kwargs)
    return _record(payload)


def record_client_error(payload: ClientErrorReport, actor: Row | None, *, ip_address: str = "", user_agent: str = "") -> dict:
    effective_trace_id = payload.trace_id or get_trace_id()
    if effective_trace_id == "-":
        effective_trace_id = ""
    project_id = _client_error_project_id(payload, actor)
    actor_id = actor["id"] if actor else "anonymous"
    actor_name = actor_display_name(actor) if actor else "匿名用户"
    path = _safe_text(payload.path, 500)
    method = _safe_text(payload.method.upper(), 12)
    status = f"HTTP {payload.status}" if payload.status else "前端异常"
    endpoint = " ".join(part for part in (method, path) if part)
    summary_parts = [f"前端错误：{payload.title}", status]
    if endpoint:
        summary_parts.append(endpoint)
    summary = "；".join(summary_parts)
    failure_parts = [payload.message]
    if payload.code:
        failure_parts.append(f"错误码：{payload.code}")
    failure_reason = "；".join(failure_parts)

    log_id = record_failure(
        log_type="audit",
        module="frontend",
        action="client_error",
        object_type="client_error",
        object_id=effective_trace_id or None,
        object_name=payload.title,
        project_id=project_id,
        actor_id=actor_id,
        actor_name=actor_name,
        source="web",
        failure_reason=failure_reason,
        summary=summary,
        before={
            "status": payload.status,
            "code": payload.code,
            "method": method,
            "path": path,
            "page_url": _safe_text(payload.page_url, 1000),
            "action_label": _safe_text(payload.action_label, 120),
            "occurred_at": _safe_text(payload.occurred_at, 80),
        },
        request_id=effective_trace_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return ClientErrorReportOut(log_id=log_id, trace_id=effective_trace_id).model_dump()


def actor_display_name(actor) -> str:
    if not actor:
        return "系统"
    keys = actor.keys() if hasattr(actor, "keys") else actor
    for key in ("nickname", "username", "id"):
        if key in keys and actor[key]:
            return actor[key]
    return "系统"


def list_logs(query: OperationLogQuery, actor: Row) -> dict:
    _require_admin(actor)
    with connect() as db:
        rows, total = operation_log_repo.list_logs(db, query.model_dump(exclude_none=True))
        return OperationLogListOut(
            items=[_serialize_list_item(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        ).model_dump()


def list_project_logs(project_id: str, query: OperationLogQuery, actor: Row) -> dict:
    _ensure_project_access(project_id, actor)
    filters = query.model_dump(exclude_none=True)
    filters["project_id"] = project_id
    with connect() as db:
        rows, total = operation_log_repo.list_logs(db, filters)
        return OperationLogListOut(
            items=[_serialize_list_item(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        ).model_dump()


def get_log(log_id: str, actor: Row) -> dict:
    with connect() as db:
        row = operation_log_repo.get_log(db, log_id)
        if not row:
            raise api_error(404, "NOT_FOUND", "日志不存在。")
    if actor["role"] != "admin":
        if not row["project_id"]:
            raise api_error(403, "PERMISSION_DENIED", "无权查看系统级日志。")
        _ensure_project_access(row["project_id"], actor)
    return _serialize_detail(row)


def get_retention_policy(actor: Row) -> dict:
    _require_admin(actor)
    with connect() as db:
        return _serialize_policy(operation_log_repo.get_retention_policy(db))


def update_retention_policy(payload: OperationLogRetentionPolicyUpdate, actor: Row) -> dict:
    _require_admin(actor)
    with connect() as db:
        before = operation_log_repo.get_retention_policy(db)
        row = operation_log_repo.update_retention_policy(
            db,
            retention_days=payload.retention_days,
            max_rows=payload.max_rows,
            protect_high_risk=payload.protect_high_risk,
            updated_by=actor["id"],
        )
        result = _serialize_policy(row)
    record_change(
        log_type="config",
        module="operation_log",
        action="update_retention_policy",
        object_type="operation_log_retention_policy",
        object_id="default",
        object_name="日志保留策略",
        actor_id=actor["id"],
        actor_name=actor_display_name(actor),
        source="web",
        summary="修改日志保留策略。",
        before=_serialize_policy(before) if before else {},
        after=result,
    )
    return result


def cleanup_logs(payload: OperationLogCleanupRequest, actor: Row) -> dict:
    _require_admin(actor)
    filters = payload.model_dump(exclude_none=True)
    with connect() as db:
        matched = operation_log_repo.count_cleanup_matches(db, filters)
        deleted = 0 if payload.dry_run else operation_log_repo.cleanup_logs(db, filters)
    result = OperationLogCleanupResult(matched_count=matched, deleted_count=deleted, dry_run=payload.dry_run).model_dump()
    record_change(
        log_type="audit",
        module="operation_log",
        action="cleanup",
        object_type="operation_log",
        object_id="cleanup",
        object_name="操作日志清理",
        actor_id=actor["id"],
        actor_name=actor_display_name(actor),
        source="web",
        summary=f"{'试算' if payload.dry_run else '清理'}操作日志：匹配 {matched} 条，删除 {deleted} 条。",
        before={"filters": filters},
        after=result,
    )
    return result


def _record(payload: OperationLogCreate) -> str | None:
    log_id = f"oplog-{secrets.token_hex(8)}"
    request_id = payload.request_id or get_trace_id()
    if request_id == "-":
        request_id = ""
    try:
        with connect() as db:
            operation_log_repo.create_log(
                db,
                {
                    "id": log_id,
                    "log_type": payload.log_type,
                    "module": payload.module,
                    "action": payload.action,
                    "object_type": payload.object_type,
                    "object_id": payload.object_id,
                    "object_name": _mask_sensitive(payload.object_name),
                    "project_id": payload.project_id,
                    "actor_id": payload.actor_id,
                    "actor_name": _mask_sensitive(payload.actor_name),
                    "source": payload.source,
                    "result": payload.result,
                    "failure_reason": _mask_sensitive(payload.failure_reason),
                    "summary": _mask_sensitive(payload.summary),
                    "before_json": json.dumps(_mask_sensitive(payload.before or {}), ensure_ascii=False),
                    "after_json": json.dumps(_mask_sensitive(payload.after or {}), ensure_ascii=False),
                    "task_id": payload.task_id,
                    "artifact_path": json.dumps(_mask_sensitive(payload.artifact_path), ensure_ascii=False),
                    "request_id": request_id,
                    "ip_address": payload.ip_address,
                    "user_agent": _mask_sensitive(payload.user_agent),
                },
            )
        return log_id
    except Exception as exc:
        logger.warning("operation log write failed: %s", exc)
        return None


def _client_error_project_id(payload: ClientErrorReport, actor: Row | None) -> str | None:
    if not actor:
        return None
    project_id = _extract_project_id(payload.path) or _extract_project_id(payload.page_url)
    if not project_id:
        return None
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
    if not project:
        return None
    try:
        _ensure_project_access(project_id, actor)
    except Exception:
        return None
    return project_id


def _extract_project_id(value: str) -> str | None:
    if not value:
        return None
    path = urlsplit(value).path
    match = re.search(r"/projects/([^/?#]+)", path)
    return match.group(1) if match else None


def _safe_text(value: str, limit: int) -> str:
    return value.strip()[:limit]


def _mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                masked[key] = "******"
            else:
                masked[key] = _mask_sensitive(item)
        return masked
    if isinstance(value, list):
        return [_mask_sensitive(item) for item in value]
    if isinstance(value, str):
        return SENSITIVE_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}******", value)
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(part in normalized for part in SENSITIVE_KEYS)


def _serialize_list_item(row: Row) -> dict:
    return {
        "id": row["id"],
        "log_type": row["log_type"],
        "module": row["module"],
        "action": row["action"],
        "object_type": row["object_type"],
        "object_id": row["object_id"],
        "object_name": row["object_name"],
        "project_id": row["project_id"],
        "actor_id": row["actor_id"],
        "actor_name": row["actor_name"],
        "source": row["source"],
        "result": row["result"],
        "failure_reason": row["failure_reason"],
        "summary": row["summary"],
        "task_id": row["task_id"],
        "created_at": row["created_at"],
    }


def _serialize_detail(row: Row) -> dict:
    item = _serialize_list_item(row)
    item.update(
        {
            "before": json.loads(row["before_json"] or "{}"),
            "after": json.loads(row["after_json"] or "{}"),
            "artifact_path": json.loads(row["artifact_path"] or "[]"),
            "request_id": row["request_id"],
            "ip_address": row["ip_address"],
            "user_agent": row["user_agent"],
        }
    )
    return item


def _serialize_policy(row: Row) -> dict:
    return OperationLogRetentionPolicyOut(
        id=row["id"],
        retention_days=row["retention_days"],
        max_rows=row["max_rows"],
        protect_high_risk=bool(row["protect_high_risk"]),
        updated_by=row["updated_by"],
        updated_at=row["updated_at"],
    ).model_dump()


def _require_admin(actor: Row) -> None:
    if actor["role"] != "admin":
        raise api_error(403, "PERMISSION_DENIED", "仅管理员可查看系统日志。")


def _ensure_project_access(project_id: str, actor: Row) -> None:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
    if not project or project["name"] != actor["project_scope"]:
        raise api_error(403, "PERMISSION_DENIED", "无权查看该项目日志。")
