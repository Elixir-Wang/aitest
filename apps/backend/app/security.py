from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from sqlite3 import Connection, Row

from fastapi import Depends, Header, HTTPException

from .database import connect


def create_session(db: Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    db.execute("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)", (token, user_id, expires_at))
    return token


def delete_session(token: str) -> None:
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def get_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "请先登录。"})
    return authorization.removeprefix("Bearer ").strip()


def current_user(token: str = Depends(get_token)) -> Row:
    with connect() as db:
        row = db.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ? AND sessions.expires_at > CURRENT_TIMESTAMP
            """,
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "登录已过期，请重新登录。"})
        if row["status"] != "enabled":
            raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "账号已禁用。"})
        return row


def require_admin(user: Row = Depends(current_user)) -> Row:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "仅管理员可执行该操作。"})
    return user
