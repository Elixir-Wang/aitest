from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.security import verify_secret
from app.repositories import session_repo, user_repo
from app.presentation.serializers import serialize_user


def login(username: str, password: str) -> dict:
    with connect() as db:
        user = user_repo.find_by_login(db, username)
        if not user or not verify_secret(password, user["password_hash"]):
            raise _login_failed()
        if user["status"] != "enabled":
            raise _login_failed()

        token = create_session(db, user["id"])
        user_repo.update_login_time(db, user["id"])
        refreshed = user_repo.find_by_id(db, user["id"])
        return {"access_token": token, "current_user": serialize_user(refreshed)}


def logout(token: str) -> dict:
    with connect() as db:
        session_repo.delete(db, token)
    return {"success": True}


def me(user) -> dict:
    actions = ["read", "write"] if user["role"] in {"admin", "tester"} else ["read"]
    return {
        "user": serialize_user(user),
        "roles": [user["role"]],
        "project_permissions": {user["project_scope"]: actions},
    }


def create_session(db, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    session_repo.create(db, token, user_id, expires_at)
    return token


def _login_failed():
    return api_error(401, "LOGIN_FAILED", "账号或密码不正确，请联系管理员确认账号状态。")
