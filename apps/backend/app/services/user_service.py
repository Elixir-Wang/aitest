import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.security import hash_secret
from app.repositories import user_repo
from app.schemas.user import UserCreateIn, UserUpdateIn
from app.presentation.serializers import serialize_user
from app.services import operation_log_service

ROLES = {"admin", "tester", "guest"}
STATUSES = {"enabled", "disabled"}


def list_users(actor) -> list[dict]:
    with connect() as db:
        return [serialize_user(row, actor["role"]) for row in user_repo.list_all(db)]


def create_user(payload: UserCreateIn, actor) -> dict:
    validate_role_status(payload.role, payload.status)
    user_id = f"u-{secrets.token_hex(8)}"
    with connect() as db:
        try:
            user_repo.create(
                db,
                user_id=user_id,
                username=payload.username,
                email=payload.email,
                nickname=payload.nickname,
                password_hash=hash_secret(payload.password),
                role=payload.role,
                status=payload.status,
                project_scope=payload.project_scope,
                description=payload.description,
            )
        except Exception as exc:
            raise api_error(409, "USER_CONFLICT", "用户名或邮箱已存在。") from exc
        row = user_repo.find_by_id(db, user_id)
        result = serialize_user(row, actor["role"])
    operation_log_service.record_change(
        log_type="audit",
        module="user",
        action="create",
        object_type="user",
        object_id=user_id,
        object_name=result["username"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"新建用户：{result['username']}",
        after={
            "username": result["username"],
            "email": result["email"],
            "role": result["role"],
            "status": result["status"],
            "project_scope": result["project_scope"],
        },
    )
    return result


def update_user(user_id: str, payload: UserUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates or "status" in updates:
        validate_role_status(updates.get("role", "admin"), updates.get("status", "enabled"))

    assignments, values = _build_update_assignments(updates)
    with connect() as db:
        existing = user_repo.find_by_id(db, user_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "用户不存在。")
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                user_repo.update(db, user_id, assignments, values)
            except Exception as exc:
                raise api_error(409, "USER_CONFLICT", "邮箱已存在。") from exc

        row = user_repo.find_by_id(db, user_id)
        result = serialize_user(row, actor["role"])
        before = _user_log_snapshot(existing)
        after = _user_log_snapshot(row)
    operation_log_service.record_change(
        log_type="audit",
        module="user",
        action="update",
        object_type="user",
        object_id=user_id,
        object_name=result["username"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"编辑用户：{result['username']}",
        before=before,
        after=after,
    )
    return result


def delete_user(user_id: str, actor) -> dict:
    if user_id == actor["id"]:
        raise api_error(400, "SELF_DELETE_DENIED", "不能删除当前登录账号。")
    with connect() as db:
        existing = user_repo.find_by_id(db, user_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "用户不存在。")
        snapshot = _user_log_snapshot(existing)
        user_repo.delete(db, user_id)
    operation_log_service.record_change(
        log_type="audit",
        module="user",
        action="delete",
        object_type="user",
        object_id=user_id,
        object_name=snapshot["username"],
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"删除用户：{snapshot['username']}",
        before=snapshot,
        after={},
    )
    return {"success": True}


def validate_role_status(role: str, status: str) -> None:
    if role not in ROLES:
        raise api_error(400, "INVALID_ROLE", "角色不合法。")
    if status not in STATUSES:
        raise api_error(400, "INVALID_STATUS", "状态不合法。")


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
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
    return assignments, values


def _user_log_snapshot(row) -> dict:
    return {
        "username": row["username"],
        "email": row["email"],
        "nickname": row["nickname"],
        "role": row["role"],
        "status": row["status"],
        "project_scope": row["project_scope"],
        "description": row["description"],
    }
