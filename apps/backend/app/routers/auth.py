from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..database import connect, verify_secret
from ..formatters import serialize_user
from ..schemas import CurrentUserOut, LoginIn, LoginOut
from ..security import create_session, current_user, delete_session, get_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(payload: LoginIn) -> dict:
    with connect() as db:
        user = db.execute(
            "SELECT * FROM users WHERE lower(username) = lower(?) OR lower(email) = lower(?)",
            (payload.username, payload.username),
        ).fetchone()
        if not user or not verify_secret(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail={"code": "LOGIN_FAILED", "message": "账号或密码不正确，请联系管理员确认账号状态。"})
        if user["status"] != "enabled":
            raise HTTPException(status_code=401, detail={"code": "LOGIN_FAILED", "message": "账号或密码不正确，请联系管理员确认账号状态。"})

        token = create_session(db, user["id"])
        db.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
        refreshed = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        return {"access_token": token, "current_user": serialize_user(refreshed)}


@router.post("/logout")
def logout(token: str = Depends(get_token)) -> dict:
    delete_session(token)
    return {"success": True}


@router.get("/me", response_model=CurrentUserOut)
def me(user=Depends(current_user)) -> dict:
    actions = ["read", "write"] if user["role"] in {"admin", "tester"} else ["read"]
    return {
        "user": serialize_user(user),
        "roles": [user["role"]],
        "project_permissions": {user["project_scope"]: actions},
    }
