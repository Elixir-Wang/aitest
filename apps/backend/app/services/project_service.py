from __future__ import annotations

import secrets

from fastapi import HTTPException

from app.core.db import connect
from app.repositories import project_repo
from app.schemas.project import ProjectCreateIn, ProjectUpdateIn
from app.services.serializers import serialize_project

STATUSES = {"active", "archived"}


def list_projects(actor) -> list[dict]:
    with connect() as db:
        if actor["role"] == "admin":
            rows = project_repo.list_all(db)
        else:
            rows = project_repo.list_visible(db, actor)
        return [serialize_project(row, actor["role"]) for row in rows]


def create_project(payload: ProjectCreateIn, actor) -> dict:
    validate_status(payload.status)
    project_id = f"project-{secrets.token_hex(8)}"
    with connect() as db:
        try:
            project_repo.create(
                db,
                project_id=project_id,
                name=payload.name.strip(),
                status=payload.status,
                description=payload.description.strip(),
            )
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "PROJECT_CONFLICT", "message": "项目名称已存在。"}) from exc
        row = project_repo.find_by_id(db, project_id)
        return serialize_project(row, actor["role"])


def update_project(project_id: str, payload: ProjectUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        validate_status(updates["status"])

    assignments, values = _build_update_assignments(updates)
    with connect() as db:
        existing = project_repo.find_by_id(db, project_id)
        if not existing:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "项目不存在。"})
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                project_repo.update(db, project_id, assignments, values)
            except Exception as exc:
                raise HTTPException(status_code=409, detail={"code": "PROJECT_CONFLICT", "message": "项目名称已存在。"}) from exc
        row = project_repo.find_by_id(db, project_id)
        return serialize_project(row, actor["role"])


def delete_project(project_id: str, actor) -> dict:
    with connect() as db:
        project_repo.delete(db, project_id)
        return {"success": True}


def validate_status(status: str) -> None:
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATUS", "message": "项目状态不合法。"})


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
    field_map = {
        "name": "name",
        "description": "description",
        "status": "status",
    }
    assignments = []
    values = []
    for key, column in field_map.items():
        if key in updates:
            assignments.append(f"{column} = ?")
            value = updates[key]
            values.append(value.strip() if isinstance(value, str) else value)
    return assignments, values
