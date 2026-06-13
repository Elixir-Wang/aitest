import json
import secrets

from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import document_repo, exploration_repo, project_repo, test_case_repo
from app.schemas.test_case import TestCaseSetCreateIn


STATUS_LABELS = {
    "generating": "生成中",
    "ready_for_review": "待评审",
    "failed": "生成失败",
    "archived": "已归档",
}


def list_project_test_case_sets(project_id: str, actor) -> list[dict]:
    with connect() as db:
        project = _require_visible_project(db, project_id, actor)
        rows = test_case_repo.list_by_project(db, project["id"])
        return [_serialize_set(db, row) for row in rows]


def get_test_case_set(project_id: str, set_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        return _serialize_set(db, row)


def create_test_case_set(project_id: str, payload: TestCaseSetCreateIn, actor) -> dict:
    _require_admin(actor)
    set_id = f"tcs-{secrets.token_hex(8)}"
    run_id = f"tcgr-{secrets.token_hex(8)}"
    task_id = f"test_case_generation:{run_id}"
    with connect() as db:
        project = _require_visible_project(db, project_id, actor)
        requirement = document_repo.find_by_project_and_id(db, project_id, payload.requirement_doc_id)
        if not requirement:
            raise api_error(400, "INVALID_REQUIREMENT_DOCUMENT", "请选择当前项目下的需求。")

        exploration_run_id = _resolve_exploration_run_id(
            db,
            project_id=project_id,
            requirement_doc_id=payload.requirement_doc_id,
            requested_exploration_run_id=payload.exploration_run_id,
        )
        input_snapshot = _generation_input_snapshot(
            project=project,
            requirement=requirement,
            payload=payload,
            exploration_run_id=exploration_run_id,
        )
        test_case_repo.create_set(
            db,
            set_id=set_id,
            project_id=project_id,
            name=payload.name,
            requirement_doc_id=payload.requirement_doc_id,
            exploration_run_id=exploration_run_id,
            include_company_knowledge=payload.include_company_knowledge,
            generation_scope_type=payload.generation_scope_type,
            generation_scope_text=payload.generation_scope_text,
            notes=payload.notes,
            created_by=actor["id"],
        )
        test_case_repo.create_generation_run(
            db,
            run_id=run_id,
            test_case_set_id=set_id,
            task_id=task_id,
            input_json=json.dumps(input_snapshot, ensure_ascii=False),
        )
        created = test_case_repo.find_set_by_id(db, set_id)
        if not created:
            raise api_error(500, "TEST_CASE_SET_CREATE_FAILED", "测试用例集创建失败。")
        return _serialize_set(db, created)


def _resolve_exploration_run_id(
    db,
    *,
    project_id: str,
    requirement_doc_id: str,
    requested_exploration_run_id: str,
) -> str:
    if requested_exploration_run_id:
        exploration = exploration_repo.find_by_id(db, requested_exploration_run_id)
        if not exploration or exploration["project_id"] != project_id or exploration["requirement_doc_id"] != requirement_doc_id:
            raise api_error(400, "INVALID_EXPLORATION_RUN", "请选择当前需求关联的探索任务。")
        return requested_exploration_run_id
    related = test_case_repo.latest_related_exploration(db, project_id, requirement_doc_id)
    return related["id"] if related else ""


def _generation_input_snapshot(*, project, requirement, payload: TestCaseSetCreateIn, exploration_run_id: str) -> dict:
    return {
        "project_id": project["id"],
        "project_name": project["name"],
        "requirement_doc_id": requirement["id"],
        "requirement_doc_title": requirement["name"],
        "exploration_run_id": exploration_run_id,
        "include_company_knowledge": payload.include_company_knowledge,
        "company_knowledge_role": "testing_guidance_only",
        "generation_scope_type": payload.generation_scope_type,
        "generation_scope_text": payload.generation_scope_text,
        "notes": payload.notes,
    }


def _serialize_set(db, row) -> dict:
    generation_run = test_case_repo.latest_generation_run(db, row["id"])
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "name": row["name"],
        "requirement_doc_id": row["requirement_doc_id"],
        "requirement_doc_title": row["requirement_doc_title"],
        "exploration_run_id": row["exploration_run_id"],
        "exploration_run_title": row["exploration_run_title"],
        "include_company_knowledge": bool(row["include_company_knowledge"]),
        "generation_scope_type": row["generation_scope_type"],
        "generation_scope_text": row["generation_scope_text"],
        "notes": row["notes"],
        "status": row["status"],
        "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        "case_count": row["case_count"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "generation_run": _serialize_generation_run(generation_run),
    }


def _serialize_generation_run(row) -> dict | None:
    if not row:
        return None
    try:
        input_snapshot = json.loads(row["input_json"] or "{}")
    except json.JSONDecodeError:
        input_snapshot = {}
    return {
        "id": row["id"],
        "test_case_set_id": row["test_case_set_id"],
        "task_id": row["task_id"],
        "status": row["status"],
        "input_snapshot": input_snapshot,
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
    }


def _require_visible_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return project
    if project["name"] == actor["project_scope"]:
        return project
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _require_admin(actor) -> None:
    if actor["role"] != "admin":
        raise api_error(403, "PERMISSION_DENIED", "无权创建测试用例集。")
