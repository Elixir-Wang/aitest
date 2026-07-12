import secrets
import sqlite3

from loguru import logger

from app.core.environment_auth_state import auth_state_summary, delete_auth_state
from app.core.environment_credentials import delete_credentials, load_credentials, save_credentials
from app.core.db import connect
from app.core.exceptions import api_error
from app.presentation.serializers import apply_environment_auth_display, serialize_exploration_environment
from app.repositories import environment_repo, project_repo
from app.schemas.environment import ExplorationEnvironmentCreateIn, ExplorationEnvironmentUpdateIn
from app.services import auto_auth_service
from app.services import operation_log_service

LOGIN_STRATEGIES = {"account_password", "skip_login"}
CAPTCHA_STRATEGIES = {"none", "ai_letter", "manual"}


def list_visible_environments(actor, project_id: str | None = None) -> list[dict]:
    with connect() as db:
        rows = environment_repo.list_visible(db, actor, project_id)
        return [serialize_exploration_environment(row) for row in rows]


def create_environment(payload: ExplorationEnvironmentCreateIn, actor) -> dict:
    auth_config = _normalize_auth_config(
        login_strategy=payload.login_strategy,
        captcha_strategy=payload.captcha_strategy,
        reuse_auth_state=payload.reuse_auth_state,
        username=payload.username,
        password=payload.password,
        require_password=True,
    )

    environment_id = f"env-{secrets.token_hex(8)}"
    with connect() as db:
        project = project_repo.find_by_id(db, payload.project_id)
        if not project or project["status"] == "archived":
            raise api_error(400, "INVALID_PROJECT", "请选择有效项目。")
        try:
            environment_repo.create(
                db,
                environment_id=environment_id,
                project_id=payload.project_id,
                name=payload.name.strip(),
                site_url=payload.site_url.strip(),
                username=auth_config["username"],
                login_strategy=auth_config["login_strategy"],
                captcha_strategy=auth_config["captcha_strategy"],
                reuse_auth_state=auth_config["reuse_auth_state"],
                description=payload.description.strip(),
                created_by=actor["id"],
            )
        except sqlite3.IntegrityError as exc:
            raise api_error(409, "ENVIRONMENT_CONFLICT", "环境名称已存在。") from exc
        row = environment_repo.find_by_id(db, environment_id)
        result = serialize_exploration_environment(row)
    if auth_config["login_strategy"] == "account_password":
        save_credentials(
            environment_id,
            username=auth_config["username"],
            password=auth_config["password"],
        )
        result["has_saved_credentials"] = True
    else:
        result["has_saved_credentials"] = False
    operation_log_service.record_change(
        log_type="config",
        module="environment",
        action="create",
        object_type="exploration_environment",
        object_id=environment_id,
        object_name=result["name"],
        project_id=result["project_id"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"新建探索环境：{result['name']}",
        after=_environment_snapshot(result),
    )
    return _finalize_environment_result(result, is_create=True)


def update_environment(environment_id: str, payload: ExplorationEnvironmentUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    password_provided = "password" in updates and bool(updates.get("password"))
    if "password" in updates and not updates["password"]:
        updates.pop("password")
    with connect() as db:
        existing = environment_repo.find_by_id(db, environment_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        effective = _normalize_auth_config(
            login_strategy=updates.get("login_strategy", existing["login_strategy"]),
            captcha_strategy=updates.get(
                "captcha_strategy",
                existing["captcha_strategy"] if "captcha_strategy" in existing.keys() else "none",
            ),
            reuse_auth_state=updates.get(
                "reuse_auth_state",
                bool(existing["reuse_auth_state"]) if "reuse_auth_state" in existing.keys() else True,
            ),
            username=updates.get("username", existing["username"]),
            password=updates.get("password", ""),
            require_password=False,
            existing_password_available=bool(existing["password_encrypted"]),
        )
        updates = {
            **updates,
            "username": effective["username"],
            "login_strategy": effective["login_strategy"],
            "captcha_strategy": effective["captcha_strategy"],
            "reuse_auth_state": effective["reuse_auth_state"],
        }
        if password_provided:
            updates["password"] = effective["password"]
        assignments, values = _build_update_assignments(updates)
        if "name" in updates:
            duplicate = environment_repo.find_by_name(
                db, existing["project_id"], updates["name"].strip(), exclude_id=environment_id
            )
            if duplicate:
                raise api_error(409, "ENVIRONMENT_CONFLICT", "环境名称已存在。")
        should_clear_auth_state = _should_clear_auth_state(existing, updates)
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                environment_repo.update(db, environment_id, assignments, values)
            except sqlite3.IntegrityError as exc:
                raise api_error(409, "ENVIRONMENT_CONFLICT", "环境名称已存在。") from exc
        row = environment_repo.find_by_id(db, environment_id)
        result = serialize_exploration_environment(row)
        before = _environment_snapshot(existing)
    if should_clear_auth_state:
        delete_auth_state(environment_id)
        auto_auth_service.reset_auto_auth_status(environment_id)
    if result["login_strategy"] == "skip_login":
        delete_credentials(environment_id)
        result["has_saved_credentials"] = False
    elif password_provided:
        save_credentials(
            environment_id,
            username=result["username"],
            password=updates["password"],
        )
        result["has_saved_credentials"] = True
    else:
        result["has_saved_credentials"] = load_credentials(environment_id) is not None
    after = _environment_snapshot(result)
    operation_log_service.record_change(
        log_type="config",
        module="environment",
        action="update",
        object_type="exploration_environment",
        object_id=environment_id,
        object_name=result["name"],
        project_id=result["project_id"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑探索环境：{result['name']}",
        before=before,
        after=after,
    )
    return _finalize_environment_result(result, auth_state_cleared=should_clear_auth_state)


def start_environment_auto_auth(environment_id: str, actor) -> dict:
    with connect() as db:
        row = environment_repo.find_by_id(db, environment_id)
        if not row:
            raise api_error(404, "NOT_FOUND", "环境不存在。")

    result = serialize_exploration_environment(row)
    result["has_saved_credentials"] = load_credentials(environment_id) is not None

    if result["captcha_strategy"] != "ai_letter":
        raise api_error(400, "AUTO_AUTH_NOT_SUPPORTED", "当前环境未启用字母 AI 验证码登录。")
    if result["login_strategy"] != "account_password":
        raise api_error(400, "AUTO_AUTH_NOT_SUPPORTED", "当前环境未启用账号密码登录。")
    if not result["reuse_auth_state"]:
        raise api_error(400, "AUTO_AUTH_NOT_SUPPORTED", "当前环境未开启复用登录态。")
    if not result["has_saved_credentials"]:
        raise api_error(400, "AUTO_AUTH_CREDENTIALS_REQUIRED", "请先保存账号密码后再登录。")

    try:
        auto_auth_service.trigger_ai_letter_auto_auth(environment_id)
    except ValueError as exc:
        raise api_error(400, "AUTO_AUTH_NOT_SUPPORTED", "当前环境无法自动登录。") from exc

    return apply_environment_auth_display(result)


def delete_environment(environment_id: str, actor) -> dict:
    with connect() as db:
        existing = environment_repo.find_by_id(db, environment_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        snapshot = _environment_snapshot(existing)
        try:
            environment_repo.delete(db, environment_id)
        except sqlite3.IntegrityError as exc:
            raise api_error(409, "ENVIRONMENT_IN_USE", "环境已被探索任务引用，不能删除。") from exc
    _cleanup_deleted_environment_files(environment_id)
    operation_log_service.record_change(
        log_type="config",
        module="environment",
        action="delete",
        object_type="exploration_environment",
        object_id=environment_id,
        object_name=snapshot["name"],
        project_id=snapshot.get("project_id", ""),
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除探索环境：{snapshot['name']}",
        before=snapshot,
        after={},
    )
    return {"success": True}


def _cleanup_deleted_environment_files(environment_id: str) -> None:
    try:
        delete_auth_state(environment_id)
    except OSError:
        logger.exception("环境已删除，但登录态文件清理失败：{}", environment_id)


def _finalize_environment_result(
    result: dict,
    *,
    is_create: bool = False,
    auth_state_cleared: bool = False,
) -> dict:
    environment_id = result["id"]
    if auto_auth_service.should_schedule_ai_letter_auto_auth(result) and _should_trigger_ai_letter_auto_auth(
        environment_id,
        result,
        is_create=is_create,
        auth_state_cleared=auth_state_cleared,
    ):
        auto_auth_service.schedule_ai_letter_auto_auth(environment_id)
    return apply_environment_auth_display(result)


def _should_trigger_ai_letter_auto_auth(
    environment_id: str,
    result: dict,
    *,
    is_create: bool,
    auth_state_cleared: bool,
) -> bool:
    if is_create or auth_state_cleared:
        return True
    file_state = auth_state_summary(
        environment_id=environment_id,
        login_strategy=result["login_strategy"],
        reuse_auth_state=bool(result.get("reuse_auth_state")),
    )
    return file_state["status"] != "valid"


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
    field_map = {
        "name": "name",
        "site_url": "site_url",
        "username": "username",
        "login_strategy": "login_strategy",
        "captcha_strategy": "captcha_strategy",
        "reuse_auth_state": "reuse_auth_state",
        "description": "description",
    }
    assignments = []
    values = []
    for key, column in field_map.items():
        if key in updates:
            assignments.append(f"{column} = ?")
            value = updates[key]
            if key == "reuse_auth_state":
                values.append(int(bool(value)))
            else:
                values.append(value.strip() if isinstance(value, str) else value)
    return assignments, values


def _normalize_auth_config(
    *,
    login_strategy: str,
    captcha_strategy: str,
    reuse_auth_state: bool,
    username: str,
    password: str,
    require_password: bool,
    existing_password_available: bool = False,
) -> dict:
    login_strategy = (login_strategy or "skip_login").strip()
    captcha_strategy = (captcha_strategy or "none").strip()
    if login_strategy not in LOGIN_STRATEGIES:
        raise api_error(400, "INVALID_LOGIN_STRATEGY", "登录策略不合法。")
    if captcha_strategy not in CAPTCHA_STRATEGIES:
        raise api_error(400, "INVALID_CAPTCHA_STRATEGY", "验证码策略不合法。")
    if login_strategy == "skip_login":
        return {
            "login_strategy": "skip_login",
            "captcha_strategy": "none",
            "reuse_auth_state": False,
            "username": "",
            "password": "",
        }
    username = username.strip()
    if not username:
        raise api_error(400, "INVALID_LOGIN_CREDENTIALS", "账号密码登录必须填写用户名。")
    if require_password and not password:
        raise api_error(400, "INVALID_LOGIN_CREDENTIALS", "账号密码登录必须填写密码。")
    if not require_password and not password and not existing_password_available:
        raise api_error(400, "INVALID_LOGIN_CREDENTIALS", "账号密码登录必须填写密码。")
    if captcha_strategy == "manual" and not reuse_auth_state:
        raise api_error(400, "INVALID_CAPTCHA_STRATEGY", "人工登录必须开启复用登录态。")
    return {
        "login_strategy": "account_password",
        "captcha_strategy": captcha_strategy,
        "reuse_auth_state": bool(reuse_auth_state),
        "username": username,
        "password": password,
    }


def _environment_snapshot(environment) -> dict:
    return {
        "project_id": _environment_value(environment, "project_id", ""),
        "name": _environment_value(environment, "name", ""),
        "site_url": _environment_value(environment, "site_url", ""),
        "username": _environment_value(environment, "username", ""),
        "login_strategy": _environment_value(environment, "login_strategy", "skip_login"),
        "captcha_strategy": _environment_value(environment, "captcha_strategy", "none"),
        "reuse_auth_state": _environment_value(environment, "reuse_auth_state", False),
        "description": _environment_value(environment, "description", ""),
    }


def _environment_value(environment, key: str, default=None):
    if isinstance(environment, dict):
        return environment.get(key, default)
    return environment[key] if key in environment.keys() else default


def _should_clear_auth_state(existing, updates: dict) -> bool:
    if existing["login_strategy"] == "skip_login":
        return False
    sensitive_keys = {"username", "password", "login_strategy", "captcha_strategy", "reuse_auth_state"}
    if not sensitive_keys.intersection(updates):
        return False
    if updates.get("login_strategy") == "skip_login":
        return True
    for key in sensitive_keys:
        if key not in updates:
            continue
        existing_value = existing[key] if key in existing.keys() else None
        next_value = updates[key]
        if key == "reuse_auth_state":
            if bool(existing_value) != bool(next_value):
                return True
        elif str(existing_value or "") != str(next_value or ""):
            return True
    return False
