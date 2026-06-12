from sqlite3 import Row

from app.core.environment_auth_state import auth_state_summary


def user_actions(role: str) -> list[str]:
    return ["read", "create", "update", "delete"] if role == "admin" else ["read"]


def model_actions(role: str) -> list[str]:
    return ["read", "create", "update", "delete"] if role == "admin" else ["read"]


def project_actions(role: str, has_assets: bool = False) -> list[str]:
    if role != "admin":
        return ["read"]
    actions = ["read", "create", "update"]
    if not has_assets:
        actions.append("delete")
    return actions


def environment_actions(role: str) -> list[str]:
    return ["read", "create", "delete"] if role == "admin" else ["read"]


def exploration_actions(role: str, status: str) -> list[str]:
    if role != "admin":
        return ["read"]
    actions = ["read", "create"]
    if status in {"queued", "running"}:
        actions.append("cancel")
    if status not in {"queued", "running", "stopping"}:
        actions.append("delete")
    return actions


def serialize_user(row: Row, actor_role: str | None = None) -> dict:
    role = actor_role or row["role"]
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "nickname": row["nickname"],
        "role": row["role"],
        "status": row["status"],
        "project_scope": row["project_scope"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_login_at": row["last_login_at"],
        "available_actions": user_actions(role),
    }


def serialize_model_provider(row: Row, actor_role: str) -> dict:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "model": row["model"],
        "base_url": row["base_url"],
        "api_key": row["api_key"],
        "description": row["description"],
        "status": row["status"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "available_actions": model_actions(actor_role),
    }


def serialize_project(row: Row, actor_role: str, has_assets: bool = False) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "available_actions": project_actions(actor_role, has_assets),
    }


def serialize_project_environment(row: Row, actor_role: str) -> dict:
    login_strategy, captcha_strategy, reuse_auth_state = _normalize_auth_config_values(
        _row_value(row, "login_strategy", "skip_login"),
        _row_value(row, "captcha_strategy", "none"),
        _row_value(row, "reuse_auth_state", True),
    )
    project_id = row["project_id"]
    environment_id = row["id"]
    auth_state = auth_state_summary(
        project_id=project_id,
        environment_id=environment_id,
        login_strategy=login_strategy,
        reuse_auth_state=reuse_auth_state,
    )
    has_saved_credentials = bool(
        login_strategy == "account_password"
        and _row_value(row, "password_encrypted", "")
    )
    return {
        "id": environment_id,
        "project_id": project_id,
        "project_name": row["project_name"],
        "name": row["name"],
        "site_url": row["site_url"],
        "username": row["username"],
        "login_strategy": login_strategy,
        "captcha_strategy": captcha_strategy,
        "reuse_auth_state": reuse_auth_state,
        "has_saved_credentials": has_saved_credentials,
        "auth_state_status": auth_state["status"],
        "auth_state_expires_at": auth_state["expires_at"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "available_actions": environment_actions(actor_role),
    }


def _normalize_auth_config_values(login_strategy: object, captcha_strategy: object, reuse_auth_state: object) -> tuple[str, str, bool]:
    login_strategy = str(login_strategy or "skip_login")
    captcha_strategy = str(captcha_strategy or "none")
    reuse_auth_state = _bool_value(reuse_auth_state, default=True)
    if login_strategy == "skip_login":
        return "skip_login", "none", False
    if captcha_strategy == "manual" and not reuse_auth_state:
        return "account_password", "none", False
    return login_strategy, captcha_strategy or "none", reuse_auth_state


def _row_value(row: Row, key: str, default=None):
    return row[key] if key in row.keys() else default


def _bool_value(value: object, *, default: bool = False) -> bool:
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


def serialize_exploration_run(row: Row, actor_role: str) -> dict:
    login_strategy, captcha_strategy, reuse_auth_state = _normalize_auth_config_values(
        _row_value(row, "environment_login_strategy", _row_value(row, "login_strategy", "skip_login")),
        _row_value(row, "environment_captcha_strategy", "none"),
        _row_value(row, "environment_reuse_auth_state", True),
    )
    has_login_credentials = bool(login_strategy == "account_password" and _row_value(row, "environment_has_password", 0))
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "environment_id": row["environment_id"],
        "environment_name": row["environment_name"],
        "environment_site_url": row["environment_site_url"] if "environment_site_url" in row.keys() else "",
        "requirement_doc_id": _row_value(row, "requirement_doc_id", "") or "",
        "requirement_doc_title": _row_value(row, "requirement_doc_title", "") or "",
        "title": row["title"],
        "status": row["status"],
        "scope": row["scope"],
        "forbidden_paths": row["forbidden_paths"],
        "login_strategy": login_strategy,
        "captcha_strategy": captcha_strategy,
        "reuse_auth_state": reuse_auth_state,
        "has_login_credentials": has_login_credentials,
        "goal": row["goal"] if "goal" in row.keys() else "",
        "notes": row["notes"] if "notes" in row.keys() else "",
        "max_pages": row["max_pages"] if "max_pages" in row.keys() else 50,
        "max_actions": row["max_actions"] if "max_actions" in row.keys() else 1000,
        "timeout_minutes": row["timeout_minutes"] if "timeout_minutes" in row.keys() else 120,
        "artifact_root": row["artifact_root"] if "artifact_root" in row.keys() else "",
        "result_summary": row["result_summary"] if "result_summary" in row.keys() else "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"] if "started_at" in row.keys() else None,
        "finished_at": row["finished_at"] if "finished_at" in row.keys() else None,
        "available_actions": exploration_actions(actor_role, row["status"]),
    }
