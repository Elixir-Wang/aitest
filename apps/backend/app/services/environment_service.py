import secrets

from app.core.environment_auth_state import delete_auth_state
from app.core.db import connect
from app.core.exceptions import api_error
from app.presentation.serializers import serialize_project_environment
from app.repositories import environment_repo, project_repo
from app.schemas.environment import ProjectEnvironmentCreateIn, ProjectEnvironmentUpdateIn
from app.services import operation_log_service

LOGIN_STRATEGIES = {"account_password", "skip_login"}
LEGACY_LOGIN_STRATEGIES = {"reuse_state", "manual"}
CAPTCHA_STRATEGIES = {"none", "ai_letter", "manual"}


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
                username=auth_config["username"],
                password_mask=_mask_password(auth_config["password"]),
                login_strategy=auth_config["login_strategy"],
                captcha_strategy=auth_config["captcha_strategy"],
                reuse_auth_state=auth_config["reuse_auth_state"],
                description=payload.description.strip(),
                created_by=actor["id"],
            )
        except Exception as exc:
            raise api_error(409, "ENVIRONMENT_CONFLICT", "同一项目下环境名称已存在。") from exc
        row = environment_repo.find_by_id(db, environment_id)
        result = serialize_project_environment(row, actor["role"])
    operation_log_service.record_change(
        log_type="config",
        module="environment",
        action="create",
        object_type="project_environment",
        object_id=environment_id,
        object_name=result["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"新建项目环境：{result['name']}",
        after=_environment_snapshot(result),
    )
    return result


def update_project_environment(project_id: str, environment_id: str, payload: ProjectEnvironmentUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    with connect() as db:
        existing = environment_repo.find_by_id(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        _ensure_project_visible(existing, actor)
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
            existing_password_mask=existing["password_mask"],
        )
        updates = {
            **updates,
            "username": effective["username"],
            "login_strategy": effective["login_strategy"],
            "captcha_strategy": effective["captcha_strategy"],
            "reuse_auth_state": effective["reuse_auth_state"],
        }
        if "password" in updates or effective["login_strategy"] == "skip_login":
            updates["password"] = effective["password"]
        assignments, values = _build_update_assignments(updates)
        if "name" in updates:
            duplicate = environment_repo.find_by_project_and_name(
                db,
                project_id,
                updates["name"].strip(),
                exclude_id=environment_id,
            )
            if duplicate:
                raise api_error(409, "ENVIRONMENT_CONFLICT", "同一项目下环境名称已存在。")
        should_clear_auth_state = _should_clear_auth_state(existing, updates)
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                environment_repo.update(db, environment_id, assignments, values)
            except Exception as exc:
                raise api_error(409, "ENVIRONMENT_CONFLICT", "同一项目下环境名称已存在。") from exc
        if should_clear_auth_state:
            delete_auth_state(project_id, environment_id)
        row = environment_repo.find_by_id(db, environment_id)
        result = serialize_project_environment(row, actor["role"])
        before = _environment_snapshot(existing)
        after = _environment_snapshot(result)
    operation_log_service.record_change(
        log_type="config",
        module="environment",
        action="update",
        object_type="project_environment",
        object_id=environment_id,
        object_name=result["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑项目环境：{result['name']}",
        before=before,
        after=after,
    )
    return result


def delete_project_environment(project_id: str, environment_id: str, actor) -> dict:
    with connect() as db:
        existing = environment_repo.find_by_id(db, environment_id)
        if not existing or existing["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "环境不存在。")
        _ensure_project_visible(existing, actor)
        snapshot = _environment_snapshot(existing)
        environment_repo.delete(db, environment_id)
        delete_auth_state(project_id, environment_id)
    operation_log_service.record_change(
        log_type="config",
        module="environment",
        action="delete",
        object_type="project_environment",
        object_id=environment_id,
        object_name=snapshot["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除项目环境：{snapshot['name']}",
        before=snapshot,
        after={},
    )
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
    if "password" in updates:
        assignments.append("password_mask = ?")
        values.append(_mask_password(updates["password"]))
    return assignments, values


def _normalize_auth_config(
    *,
    login_strategy: str,
    captcha_strategy: str,
    reuse_auth_state: bool,
    username: str,
    password: str,
    require_password: bool,
    existing_password_mask: str = "",
) -> dict:
    login_strategy = (login_strategy or "skip_login").strip()
    captcha_strategy = (captcha_strategy or "none").strip()
    if login_strategy == "reuse_state":
        login_strategy = "account_password"
        captcha_strategy = "none"
        reuse_auth_state = True
    elif login_strategy == "manual":
        login_strategy = "account_password"
        captcha_strategy = "manual"
        reuse_auth_state = True
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
    if not require_password and not password and not existing_password_mask:
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
        "name": environment["name"],
        "site_url": environment["site_url"],
        "username": environment["username"],
        "password_mask": environment["password_mask"],
        "login_strategy": environment["login_strategy"],
        "captcha_strategy": environment["captcha_strategy"],
        "reuse_auth_state": environment["reuse_auth_state"],
        "auth_state_status": environment.get("auth_state_status", "none") if isinstance(environment, dict) else "none",
        "auth_state_expires_at": environment.get("auth_state_expires_at") if isinstance(environment, dict) else None,
        "description": environment["description"],
    }


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
