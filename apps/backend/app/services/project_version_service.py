import re
import secrets
from sqlite3 import Connection, IntegrityError

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import project_repo, project_version_repo
from app.repositories.project_repo import SYSTEM_RESERVED_PROJECT_IDS
from app.schemas.project_version import ProjectVersionCreateIn, ProjectVersionUpdateIn
from app.services import operation_log_service


SEMVER_CORE_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_version(value: str) -> tuple[str, int, int, int]:
    normalized = value.strip()
    match = SEMVER_CORE_PATTERN.fullmatch(normalized)
    if not match:
        raise api_error(422, "PROJECT_VERSION_INVALID", "版本号必须使用 MAJOR.MINOR.PATCH 格式，例如 1.0.0。")
    major, minor, patch = (int(part) for part in match.groups())
    return normalized, major, minor, patch


def serialize_version(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "version": row["version"],
        "name": row["name"],
        "description": row["description"],
        "planned_release_at": row["planned_release_at"],
        "is_default": bool(row["is_default"]),
        "requirement_count": int(row["requirement_count"]),
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def version_summary(row) -> dict:
    return {"id": row["id"], "version": row["version"], "name": row["name"], "is_default": bool(row["is_default"])}


def list_versions(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [serialize_version(row) for row in project_version_repo.list_by_project(db, project_id)]


def create_initial_version(db: Connection, project_id: str, actor_id: str) -> str:
    version_id = f"pver-{secrets.token_hex(8)}"
    project_version_repo.create(
        db,
        version_id=version_id,
        project_id=project_id,
        version="1.0.0",
        major=1,
        minor=0,
        patch=0,
        name="初始版本",
        description="",
        planned_release_at=None,
        created_by=actor_id,
    )
    project_version_repo.set_default(db, project_id, version_id)
    return version_id


def create_version(project_id: str, payload: ProjectVersionCreateIn, actor) -> dict:
    version, major, minor, patch = parse_version(payload.version)
    version_id = f"pver-{secrets.token_hex(8)}"
    with connect() as db:
        project = _require_project(db, project_id)
        try:
            project_version_repo.create(
                db,
                version_id=version_id,
                project_id=project_id,
                version=version,
                major=major,
                minor=minor,
                patch=patch,
                name=payload.name.strip(),
                description=payload.description.strip(),
                planned_release_at=_normalize_optional_text(payload.planned_release_at),
                created_by=actor["id"],
            )
            if payload.set_as_default:
                project_version_repo.set_default(db, project_id, version_id)
        except IntegrityError as exc:
            raise api_error(409, "PROJECT_VERSION_EXISTS", "当前项目已存在该版本号。") from exc
        result = serialize_version(project_version_repo.find_by_id(db, version_id))
    operation_log_service.record_change(
        log_type="audit", module="project", action="create_version", object_type="project_version",
        object_id=version_id, object_name=version, project_id=project_id, actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor), source="web",
        summary=f"创建项目版本：{version}", before={"default_version_id": project["default_version_id"]},
        after={"version": version, "set_as_default": payload.set_as_default},
    )
    return result


def update_version(project_id: str, version_id: str, payload: ProjectVersionUpdateIn, actor) -> dict:
    with connect() as db:
        _require_project(db, project_id)
        existing = _require_version(db, project_id, version_id)
        project_version_repo.update_metadata(
            db, version_id, name=payload.name.strip(), description=payload.description.strip(),
            planned_release_at=_normalize_optional_text(payload.planned_release_at),
        )
        result = serialize_version(project_version_repo.find_by_id(db, version_id))
    operation_log_service.record_change(
        log_type="audit", module="project", action="update_version", object_type="project_version",
        object_id=version_id, object_name=result["version"], project_id=project_id, actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor), source="web",
        summary=f"编辑项目版本：{result['version']}",
        before={"name": existing["name"], "description": existing["description"], "planned_release_at": existing["planned_release_at"]},
        after={"name": result["name"], "description": result["description"], "planned_release_at": result["planned_release_at"]},
    )
    return result


def set_default_version(project_id: str, version_id: str, actor) -> dict:
    with connect() as db:
        project = _require_project(db, project_id)
        _require_version(db, project_id, version_id)
        project_version_repo.set_default(db, project_id, version_id)
        result = serialize_version(project_version_repo.find_by_id(db, version_id))
    if project["default_version_id"] != version_id:
        operation_log_service.record_change(
            log_type="audit", module="project", action="set_default_version", object_type="project_version",
            object_id=version_id, object_name=result["version"], project_id=project_id, actor_id=actor["id"],
            actor_name=operation_log_service.actor_display_name(actor), source="web",
            summary=f"设置当前版本：{result['version']}", before={"default_version_id": project["default_version_id"]},
            after={"default_version_id": version_id},
        )
    return result


def delete_version(project_id: str, version_id: str, actor) -> dict:
    with connect() as db:
        _require_project(db, project_id)
        existing = _require_version(db, project_id, version_id)
        if existing["is_default"]:
            raise api_error(409, "PROJECT_VERSION_IS_DEFAULT", "当前版本不能删除，请先设置其他当前版本。")
        if existing["requirement_count"]:
            raise api_error(409, "PROJECT_VERSION_IN_USE", "该版本已关联需求，不能删除。")
        project_version_repo.delete(db, version_id)
    operation_log_service.record_change(
        log_type="audit", module="project", action="delete_version", object_type="project_version",
        object_id=version_id, object_name=existing["version"], project_id=project_id, actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor), source="web",
        summary=f"删除项目版本：{existing['version']}", before={"version": existing["version"], "name": existing["name"]}, after={},
    )
    return {"success": True}


def resolve_requirement_version(db: Connection, project_id: str, requested_version_id: str = ""):
    project = _require_project(db, project_id)
    version_id = requested_version_id.strip() or str(project["default_version_id"] or "")
    if not version_id:
        raise api_error(409, "PROJECT_DEFAULT_VERSION_MISSING", "项目缺少当前版本，请先创建或设置当前版本。")
    version = project_version_repo.find_by_project_and_id(db, project_id, version_id)
    if version is None:
        raise api_error(422, "PROJECT_VERSION_PROJECT_MISMATCH", "所选版本不属于当前项目。")
    return version


def _require_project(db: Connection, project_id: str):
    if project_id in SYSTEM_RESERVED_PROJECT_IDS:
        raise api_error(409, "PROJECT_SYSTEM_RESERVED", "系统保留项目不支持版本管理。")
    project = project_repo.find_by_id(db, project_id)
    if project is None:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    return project


def _require_visible_project(db: Connection, project_id: str, actor):
    project = _require_project(db, project_id)
    if actor["role"] != "admin" and project_id not in {row["id"] for row in project_repo.list_visible(db, actor)}:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    return project


def _require_version(db: Connection, project_id: str, version_id: str):
    version = project_version_repo.find_by_project_and_id(db, project_id, version_id)
    if version is None:
        raise api_error(404, "PROJECT_VERSION_NOT_FOUND", "项目版本不存在。")
    return version


def _normalize_optional_text(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None
