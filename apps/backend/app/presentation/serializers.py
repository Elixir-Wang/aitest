from sqlite3 import Row

from app.core.environment_auth_state import auth_state_summary
from app.services.auto_auth_service import get_auto_auth_status


def resolve_environment_auth_state_display(
    *,
    environment_id: str,
    login_strategy: str,
    reuse_auth_state: bool,
) -> dict:
    auto_auth = get_auto_auth_status(environment_id)
    auto_auth_status = auto_auth["status"]
    auto_auth_message = auto_auth["message"]
    file_state = auth_state_summary(
        environment_id=environment_id,
        login_strategy=login_strategy,
        reuse_auth_state=reuse_auth_state,
    )

    if login_strategy != "account_password" or not reuse_auth_state:
        return {
            "auth_state_status": "none",
            "auth_state_expires_at": None,
            "auth_state_message": "",
        }

    if auto_auth_status in {"queued", "running"}:
        return {
            "auth_state_status": "logging_in",
            "auth_state_expires_at": None,
            "auth_state_message": auto_auth_message or "正在自动登录",
        }

    if auto_auth_status == "failed":
        return {
            "auth_state_status": "login_failed",
            "auth_state_expires_at": None,
            "auth_state_message": auto_auth_message or "自动登录失败",
        }

    return {
        "auth_state_status": file_state["status"],
        "auth_state_expires_at": file_state["expires_at"],
        "auth_state_message": "",
    }


def apply_environment_auth_display(environment: dict) -> dict:
    display = resolve_environment_auth_state_display(
        environment_id=environment["id"],
        login_strategy=environment["login_strategy"],
        reuse_auth_state=bool(environment.get("reuse_auth_state")),
    )
    environment.update(display)
    return environment


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
        "health_status": _row_value(row, "health_status", "unknown"),
        "last_test_at": _row_value(row, "last_test_at", None),
        "last_test_message": _row_value(row, "last_test_message", ""),
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


def serialize_exploration_environment(row: Row) -> dict:
    login_strategy, captcha_strategy, reuse_auth_state = _normalize_auth_config_values(
        _row_value(row, "login_strategy", "skip_login"),
        _row_value(row, "captcha_strategy", "none"),
        _row_value(row, "reuse_auth_state", True),
    )
    environment_id = row["id"]
    auth_display = resolve_environment_auth_state_display(
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
        "project_id": row["project_id"],
        "project_name": _row_value(row, "project_name", ""),
        "name": row["name"],
        "site_url": row["site_url"],
        "username": row["username"],
        "login_strategy": login_strategy,
        "captcha_strategy": captcha_strategy,
        "reuse_auth_state": reuse_auth_state,
        "has_saved_credentials": has_saved_credentials,
        "auth_state_status": auth_display["auth_state_status"],
        "auth_state_expires_at": auth_display["auth_state_expires_at"],
        "auth_state_message": auth_display["auth_state_message"],
        "description": row["description"],
        "updated_at": row["updated_at"],
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
