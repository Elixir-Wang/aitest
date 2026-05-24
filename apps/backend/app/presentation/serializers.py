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


def environment_actions(role: str) -> list[str]:
    return ["read", "create", "delete"] if role == "admin" else ["read"]


def exploration_actions(role: str, status: str) -> list[str]:
    if role != "admin":
        return ["read"]
    actions = ["read", "create"]
    if status != "running":
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
        "api_key": row["api_key"],
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


def serialize_project_environment(row: Row, actor_role: str) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "name": row["name"],
        "site_url": row["site_url"],
        "username": row["username"],
        "password_mask": row["password_mask"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "available_actions": environment_actions(actor_role),
    }


def serialize_exploration_run(row: Row, actor_role: str) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "environment_id": row["environment_id"],
        "environment_name": row["environment_name"],
        "title": row["title"],
        "status": row["status"],
        "scope": row["scope"],
        "forbidden_paths": row["forbidden_paths"],
        "login_strategy": row["login_strategy"],
        "description": row["description"],
        "artifact_root": row["artifact_root"] if "artifact_root" in row.keys() else "",
        "result_summary": row["result_summary"] if "result_summary" in row.keys() else "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"] if "started_at" in row.keys() else None,
        "finished_at": row["finished_at"] if "finished_at" in row.keys() else None,
        "available_actions": exploration_actions(actor_role, row["status"]),
    }
