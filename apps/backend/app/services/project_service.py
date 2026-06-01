import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import project_repo
from app.schemas.project import ProjectCreateIn, ProjectUpdateIn
from app.presentation.serializers import serialize_project
from app.services import operation_log_service

STATUSES = {"active", "archived"}


def list_projects(actor) -> list[dict]:
    with connect() as db:
        if actor["role"] == "admin":
            rows = project_repo.list_all(db)
        else:
            rows = project_repo.list_visible(db, actor)
        return [serialize_project(row, actor["role"], project_repo.has_project_assets(db, row["id"])) for row in rows]


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
            raise api_error(409, "PROJECT_CONFLICT", "项目名称已存在。") from exc
        row = project_repo.find_by_id(db, project_id)
        result = serialize_project(row, actor["role"], False)
    operation_log_service.record_success(
        module="project",
        action="create",
        object_type="project",
        object_id=project_id,
        object_name=result["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=_actor_display_name(actor),
        source="web",
        summary=f"新建项目：{result['name']}",
        after={"name": result["name"], "description": result["description"], "status": result["status"]},
    )
    return result


def update_project(project_id: str, payload: ProjectUpdateIn, actor) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        validate_status(updates["status"])

    assignments, values = _build_update_assignments(updates)
    with connect() as db:
        existing = project_repo.find_by_id(db, project_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                project_repo.update(db, project_id, assignments, values)
            except Exception as exc:
                raise api_error(409, "PROJECT_CONFLICT", "项目名称已存在。") from exc
        row = project_repo.find_by_id(db, project_id)
        result = serialize_project(row, actor["role"], project_repo.has_project_assets(db, project_id))
        before = {"name": existing["name"], "description": existing["description"], "status": existing["status"]}
        after = {"name": result["name"], "description": result["description"], "status": result["status"]}
    operation_log_service.record_change(
        module="project",
        action="update",
        object_type="project",
        object_id=project_id,
        object_name=result["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=_actor_display_name(actor),
        source="web",
        summary=f"编辑项目：{result['name']}",
        before=before,
        after=after,
    )
    return result


def delete_project(project_id: str, actor) -> dict:
    with connect() as db:
        existing = project_repo.find_by_id(db, project_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        if project_repo.has_project_assets(db, project_id):
            requirement_names = project_repo.list_requirement_names(db, project_id)
            if requirement_names:
                raise api_error(409, "PROJECT_HAS_REQUIREMENTS", f"项目下存在需求：{'、'.join(requirement_names)}")
            raise api_error(409, "PROJECT_HAS_ASSETS", "项目下存在关联数据，不能删除项目。")
        snapshot = {"name": existing["name"], "description": existing["description"], "status": existing["status"]}
        project_repo.delete(db, project_id)
    operation_log_service.record_change(
        module="project",
        action="delete",
        object_type="project",
        object_id=project_id,
        object_name=snapshot["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=_actor_display_name(actor),
        source="web",
        summary=f"删除项目：{snapshot['name']}",
        before=snapshot,
        after={},
    )
    return {"success": True}


def validate_status(status: str) -> None:
    if status not in STATUSES:
        raise api_error(400, "INVALID_STATUS", "项目状态不合法。")


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


def _actor_display_name(actor) -> str:
    return operation_log_service.actor_display_name(actor)
