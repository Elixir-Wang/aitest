from __future__ import annotations

from sqlite3 import Row


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
        "api_key_mask": row["api_key_mask"],
        "description": row["description"],
        "status": row["status"],
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
