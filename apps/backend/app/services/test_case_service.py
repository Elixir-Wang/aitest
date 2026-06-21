import json
import secrets
from pathlib import Path

from app.agents.test_case_generation import generate_test_cases
from app.agents.test_case_generation.schemas import TestCaseGenerationInput, TestCaseGenerationResult
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.repositories import document_repo, exploration_repo, project_repo, test_case_repo
from app.schemas.test_case import TestCaseGenerationRequest, TestCaseSetCreateIn


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


def delete_test_case_set(project_id: str, set_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        test_case_repo.delete_set(db, set_id)


def recover_interrupted_test_case_generation_runs() -> None:
    failure_reason = "服务已重启，内存中的测试用例生成任务已中断，请重新创建测试用例集。"
    with connect() as db:
        rows = test_case_repo.list_active_generation_runs(db)
        for row in rows:
            test_case_repo.update_set_generation_result(
                db,
                row["test_case_set_id"],
                status="failed",
                case_count=0,
            )
            test_case_repo.update_generation_run_status(
                db,
                row["id"],
                status="failed",
                error_message=failure_reason,
            )


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


async def execute_test_case_generation_run(run_id: str) -> None:
    try:
        run_context = _mark_generation_run_running(run_id)
        if not run_context:
            return

        generation_input = _build_generation_input(run_context)
        result = await generate_test_cases(generation_input)
        _complete_generation_run(run_context, result)
    except Exception as exc:  # noqa: BLE001 - background task must persist failures for the UI
        _fail_generation_run(run_id, str(exc) or exc.__class__.__name__)


def _mark_generation_run_running(run_id: str) -> dict | None:
    with connect() as db:
        run = test_case_repo.find_generation_run(db, run_id)
        if not run or run["status"] != "queued":
            return None
        test_case_repo.update_generation_run_status(db, run_id, status="running")
        return dict(run)


def _build_generation_input(run_context: dict) -> TestCaseGenerationInput:
    with connect() as db:
        requirement = document_repo.find_by_project_and_id(
            db,
            run_context["project_id"],
            run_context["requirement_doc_id"],
        )
        if not requirement:
            raise ValueError("需求文档不存在，无法生成测试用例。")
        if not requirement["current_version_id"]:
            raise ValueError("该需求文档尚未生成最终需求，请先完成需求分析。")

        version = document_repo.find_version(db, requirement["current_version_id"])
        if not version:
            raise ValueError("无法找到最终需求版本。")

    final_requirement_content = _read_final_requirement_content(version)
    if not final_requirement_content.strip():
        raise ValueError("最终需求内容为空，无法生成测试用例。")

    generation_scope = ""
    if run_context["generation_scope_type"] == "specified":
        generation_scope = run_context["generation_scope_text"]

    return TestCaseGenerationInput(
        requirement_name=requirement["name"],
        requirement_content=final_requirement_content,
        generation_scope=generation_scope,
        include_company_knowledge=bool(run_context["include_company_knowledge"]),
    )


def _read_final_requirement_content(version) -> str:
    file_path = version["file_path"]
    if file_path:
        resolved_path = resolve_stored_path(file_path) or Path(file_path)
        if resolved_path.exists():
            return resolved_path.read_text(encoding="utf-8")
    return version["markdown_content"] or ""


def _complete_generation_run(run_context: dict, result: TestCaseGenerationResult) -> None:
    cases = []
    case_index = 1
    for module in result.modules:
        for test_case in module.test_cases:
            cases.append(
                {
                    "id": f"{run_context['test_case_set_id']}-tc-{case_index:03d}",
                    "title": test_case.title,
                    "module": test_case.module or module.module_name,
                    "priority": test_case.priority,
                    "preconditions": test_case.precondition,
                    "steps_json": json.dumps(test_case.steps, ensure_ascii=False),
                    "expected_result": test_case.expected_result,
                    "source_requirement_refs": json.dumps([run_context["requirement_doc_id"]], ensure_ascii=False),
                    "source_exploration_refs": json.dumps(
                        [run_context["exploration_run_id"]] if run_context.get("exploration_run_id") else [],
                        ensure_ascii=False,
                    ),
                }
            )
            case_index += 1

    with connect() as db:
        test_case_repo.replace_cases(
            db,
            test_case_set_id=run_context["test_case_set_id"],
            project_id=run_context["project_id"],
            cases=cases,
        )
        test_case_repo.update_set_generation_result(
            db,
            run_context["test_case_set_id"],
            status="ready_for_review",
            case_count=len(cases),
        )
        test_case_repo.update_generation_run_status(db, run_context["id"], status="completed")


def _fail_generation_run(run_id: str, error_message: str) -> None:
    with connect() as db:
        run = test_case_repo.find_generation_run(db, run_id)
        if not run:
            return
        test_case_repo.update_set_generation_result(
            db,
            run["test_case_set_id"],
            status="failed",
            case_count=0,
        )
        test_case_repo.update_generation_run_status(
            db,
            run_id,
            status="failed",
            error_message=error_message[:1000],
        )


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


async def generate_test_cases_from_requirement(
    project_id: str,
    payload: TestCaseGenerationRequest,
    actor,
) -> dict:
    """根据最终需求文档生成测试用例集"""
    _require_admin(actor)

    with connect() as db:
        # 验证项目
        project = _require_visible_project(db, project_id, actor)

        # 验证需求文档
        requirement = document_repo.find_by_project_and_id(db, project_id, payload.requirement_doc_id)
        if not requirement:
            raise api_error(400, "INVALID_REQUIREMENT_DOCUMENT", "请选择当前项目下的需求文档。")

        # 检查是否有最终需求（current_version）
        if not requirement["current_version_id"]:
            raise api_error(400, "NO_FINAL_REQUIREMENT", "该需求文档尚未生成最终需求，请先完成需求分析。")

        version = document_repo.find_version(db, requirement["current_version_id"])
        if not version:
            raise api_error(400, "NO_FINAL_REQUIREMENT_FILE", "无法找到最终需求文件。")
        final_requirement_content = _read_final_requirement_content(version)
        if not final_requirement_content.strip():
            raise api_error(500, "REQUIREMENT_FILE_NOT_FOUND", "最终需求文件不存在或内容为空。")

    # 构建生成输入
    generation_input = TestCaseGenerationInput(
        requirement_name=requirement["name"],
        requirement_content=final_requirement_content,
        generation_scope=payload.generation_scope,
        include_company_knowledge=payload.include_company_knowledge,
    )

    # 调用 Agent 生成测试用例
    result = await generate_test_cases(generation_input)

    # 转换为响应格式
    return {
        "summary": result.summary,
        "total_count": result.total_count,
        "modules": [
            {
                "module_name": module.module_name,
                "test_cases": [tc.model_dump() for tc in module.test_cases],
            }
            for module in result.modules
        ],
        "markdown": result.to_markdown(),
    }
