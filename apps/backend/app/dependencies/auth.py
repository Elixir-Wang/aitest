from sqlite3 import Row

from fastapi import Cookie, Depends, Header, HTTPException

from app.core.db import connect
from app.repositories import session_repo


def get_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "请先登录。"})
    return authorization.removeprefix("Bearer ").strip()


def get_token_or_locust_cookie(
    authorization: str | None = Header(default=None),
    locust_ui_session: str | None = Cookie(default=None),
) -> str:
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    if locust_ui_session:
        return locust_ui_session
    raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "请先登录。"})


def _current_user_for_token(token: str) -> Row:
    with connect() as db:
        row = session_repo.get_user_by_active_token(db, token)
        if not row:
            raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "登录已过期，请重新登录。"})
        if row["status"] != "enabled":
            raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "账号已禁用。"})
        return row


def current_user(token: str = Depends(get_token)) -> Row:
    return _current_user_for_token(token)


def current_user_or_locust_cookie(token: str = Depends(get_token_or_locust_cookie)) -> Row:
    return _current_user_for_token(token)


def require_admin(user: Row = Depends(current_user)) -> Row:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED", "message": "仅管理员可执行该操作。"})
    return user
