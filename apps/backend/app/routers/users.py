from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..database import connect, hash_secret
from ..formatters import serialize_user
from ..schemas import UserCreateIn, UserOut, UserUpdateIn
from ..security import current_user, require_admin

router = APIRouter(prefix="/users", tags=["users"])

ROLES = {"admin", "tester", "guest"}
STATUSES = {"enabled", "disabled"}


@router.get("", response_model=list[UserOut])
def list_users(actor=Depends(current_user)) -> list[dict]:
    with connect() as db:
        rows = db.execute("SELECT * FROM users ORDER BY created_at DESC, username ASC").fetchall()
        return [serialize_user(row, actor["role"]) for row in rows]


@router.post("", response_model=UserOut)
def create_user(payload: UserCreateIn, actor=Depends(require_admin)) -> dict:
    validate_role_status(payload.role, payload.status)
    user_id = f"u-{secrets.token_hex(8)}"
    with connect() as db:
        try:
            db.execute(
                """
                INSERT INTO users (id, username, email, nickname, password_hash, role, status, project_scope, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    payload.username,
                    payload.email,
                    payload.nickname,
                    hash_secret(payload.password),
                    payload.role,
                    payload.status,
                    payload.project_scope,
                    payload.description,
                ),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "USER_CONFLICT", "message": "用户名或邮箱已存在。"}) from exc
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return serialize_user(row, actor["role"])


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdateIn, actor=Depends(require_admin)) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates or "status" in updates:
        validate_role_status(updates.get("role", "admin"), updates.get("status", "enabled"))
    field_map = {
        "email": "email",
        "nickname": "nickname",
        "role": "role",
        "status": "status",
        "project_scope": "project_scope",
        "description": "description",
    }
    assignments = []
    values = []
    for key, column in field_map.items():
        if key in updates:
            assignments.append(f"{column} = ?")
            values.append(updates[key])
    if updates.get("password"):
        assignments.append("password_hash = ?")
        values.append(hash_secret(updates["password"]))
    if assignments:
        assignments.append("updated_at = CURRENT_TIMESTAMP")
        with connect() as db:
            values.append(user_id)
            try:
                db.execute(f"UPDATE users SET {', '.join(assignments)} WHERE id = ?", values)
            except Exception as exc:
                raise HTTPException(status_code=409, detail={"code": "USER_CONFLICT", "message": "邮箱已存在。"}) from exc
            row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "用户不存在。"})
            return serialize_user(row, actor["role"])
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "用户不存在。"})
        return serialize_user(row, actor["role"])


@router.delete("/{user_id}")
def delete_user(user_id: str, actor=Depends(require_admin)) -> dict:
    if user_id == actor["id"]:
        raise HTTPException(status_code=400, detail={"code": "SELF_DELETE_DENIED", "message": "不能删除当前登录账号。"})
    with connect() as db:
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return {"success": True}


def validate_role_status(role: str, status: str) -> None:
    if role not in ROLES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ROLE", "message": "角色不合法。"})
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATUS", "message": "状态不合法。"})
