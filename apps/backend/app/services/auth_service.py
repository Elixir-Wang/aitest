import secrets
from datetime import datetime, timedelta, timezone

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.security import verify_secret
from app.repositories import session_repo, user_repo
from app.presentation.serializers import serialize_user
from app.services import operation_log_service


def login(username: str, password: str) -> dict:
    with connect() as db:
        user = user_repo.find_by_login(db, username)
        if not user or not verify_secret(password, user["password_hash"]):
            operation_log_service.record_failure(
                log_type="audit",
                module="auth",
                action="login",
                object_type="user",
                object_name=username,
                actor_id="anonymous",
                actor_name=username,
                source="web",
                failure_reason="账号或密码不正确，或账号已禁用。",
                summary=f"登录失败：{username}",
            )
            raise _login_failed()
        if user["status"] != "enabled":
            operation_log_service.record_failure(
                log_type="audit",
                module="auth",
                action="login",
                object_type="user",
                object_id=user["id"],
                object_name=user["username"],
                actor_id=user["id"],
                actor_name=operation_log_service.actor_display_name(user),
                source="web",
                failure_reason="账号已禁用。",
                summary=f"登录失败：{user['username']}",
            )
            raise _login_failed()

        token = create_session(db, user["id"])
        user_repo.update_login_time(db, user["id"])
        refreshed = user_repo.find_by_id(db, user["id"])
        result = {"access_token": token, "current_user": serialize_user(refreshed)}
    operation_log_service.record_success(
        log_type="audit",
        module="auth",
        action="login",
        object_type="user",
        object_id=result["current_user"]["id"],
        object_name=result["current_user"]["username"],
        actor_id=result["current_user"]["id"],
        actor_name=result["current_user"]["nickname"] or result["current_user"]["username"],
        source="web",
        summary=f"登录成功：{result['current_user']['username']}",
    )
    return result


def logout(token: str) -> dict:
    with connect() as db:
        user = session_repo.get_user_by_active_token(db, token)
        session_repo.delete(db, token)
    if user:
        operation_log_service.record_success(
            log_type="audit",
            module="auth",
            action="logout",
            object_type="user",
            object_id=user["id"],
            object_name=user["username"],
            actor_id=user["id"],
            actor_name=operation_log_service.actor_display_name(user),
            source="web",
            summary=f"登出：{user['username']}",
        )
    return {"success": True}


def me(user) -> dict:
    role = user["role"]
    project_scope = user["project_scope"]

    if role == "admin":
        # 管理员：始终全局读写
        actions = ["read", "write"]
    elif role == "tester":
        # 测试工程师：在已分配的范围内（project_scope 即为授权边界）可读写
        actions = ["read", "write"]
    else:
        # 访客：全局只读
        actions = ["read"]

    return {
        "user": serialize_user(user),
        "roles": [role],
        "project_permissions": {project_scope: actions},
    }


def create_session(db, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    session_repo.create(db, token, user_id, expires_at)
    return token


def _login_failed():
    return api_error(401, "LOGIN_FAILED", "账号或密码不正确，请联系管理员确认账号状态。")
