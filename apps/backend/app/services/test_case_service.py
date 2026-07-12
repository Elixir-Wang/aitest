import json
import secrets
from pathlib import Path

from app.agents.test_case_generation import generate_test_cases
from app.agents.test_case_generation.schemas import (
    RejectedTestCaseFeedback,
    TestCaseGenerationInput,
    TestCaseGenerationResult,
)
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.repositories import document_repo, project_repo, test_case_repo
from app.schemas.test_case import TestCaseReviewIn, TestCaseSetCreateIn
from app.services.test_case_xmind_exporter import build_test_case_set_xmind, safe_xmind_filename


STATUS_LABELS = {
    "generating": "生成中",
    "ready_for_review": "待评审",
    "review_completed": "评审完成",
    "failed": "生成失败",
    "archived": "已归档",
}

PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


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
        return _serialize_set(db, row, include_cases=True)


def export_test_case_set_xmind(project_id: str, set_id: str, actor) -> tuple[bytes, str]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        cases = [_serialize_case(case) for case in test_case_repo.list_cases_by_set(db, row["id"])]
    return build_test_case_set_xmind(dict(row), cases), safe_xmind_filename(row["name"])


def delete_test_case_set(project_id: str, set_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        test_case_repo.delete_set(db, set_id)


def review_test_case(project_id: str, set_id: str, case_id: str, payload: TestCaseReviewIn, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        test_case = test_case_repo.find_case_by_id(db, case_id)
        if not test_case or test_case["test_case_set_id"] != set_id or test_case["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例不存在。")

        test_case_repo.update_case_review(
            db,
            case_id=case_id,
            status=payload.status,
            review_feedback=payload.review_feedback,
            reviewed_by=actor["id"],
            preconditions=payload.preconditions,
            steps_json=json.dumps(_steps_to_jsonable(payload.steps), ensure_ascii=False) if payload.steps is not None else None,
            expected_result=payload.expected_result,
        )
        updated_case = test_case_repo.find_case_by_id(db, case_id)
        if not updated_case:
            raise api_error(500, "TEST_CASE_REVIEW_FAILED", "测试用例评审保存失败。")
        review_stats = test_case_repo.review_stats_by_set(db, set_id)
        _sync_set_review_status(db, set_id, review_stats)
        return {
            "case": _serialize_case(updated_case),
            "review_stats": review_stats,
        }


def regenerate_test_case_set(project_id: str, set_id: str, actor) -> dict:
    _require_admin(actor)
    run_id = f"tcgr-{secrets.token_hex(8)}"
    task_id = f"test_case_generation:{run_id}"
    with connect() as db:
        project = _require_visible_project(db, project_id, actor)
        row = test_case_repo.find_set_by_id(db, set_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "NOT_FOUND", "测试用例集不存在。")
        if test_case_repo.has_active_generation_run(db, set_id):
            raise api_error(409, "TEST_CASE_GENERATION_RUNNING", "该测试用例集正在生成中，请稍后再试。")
        requirement = document_repo.find_by_project_and_id(db, project_id, row["requirement_doc_id"])
        if not requirement:
            raise api_error(400, "INVALID_REQUIREMENT_DOCUMENT", "请选择当前项目下的需求。")
        final_requirement_version = _require_final_requirement_version(db, requirement["id"])
        payload = TestCaseSetCreateIn(
            name=row["name"],
            requirement_doc_id=row["requirement_doc_id"],
            generation_scope_type=row["generation_scope_type"],
            generation_scope_text=row["generation_scope_text"],
            notes=row["notes"],
        )
        input_snapshot = _generation_input_snapshot(
            project=project,
            requirement=requirement,
            final_requirement_version=final_requirement_version,
            payload=payload,
            rejected_case_feedback=_serialize_rejected_feedback_rows(
                test_case_repo.list_rejected_case_feedback_by_set(db, set_id)
            ),
        )
        test_case_repo.update_set_status(db, set_id, status="generating")
        test_case_repo.create_generation_run(
            db,
            run_id=run_id,
            test_case_set_id=set_id,
            task_id=task_id,
            input_json=json.dumps(input_snapshot, ensure_ascii=False),
        )
        updated = test_case_repo.find_set_by_id(db, set_id)
        if not updated:
            raise api_error(500, "TEST_CASE_SET_REGENERATE_FAILED", "测试用例集重新生成失败。")
        return _serialize_set(db, updated)


def recover_interrupted_test_case_generation_runs() -> None:
    failure_reason = "服务已重启，内存中的测试用例生成任务已中断，请重新创建测试用例集。"
    with connect() as db:
        rows = test_case_repo.list_active_generation_runs(db)
        for row in rows:
            test_case_repo.update_set_status(db, row["test_case_set_id"], status="failed")
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
        final_requirement_version = _require_final_requirement_version(db, requirement["id"])

        input_snapshot = _generation_input_snapshot(
            project=project,
            requirement=requirement,
            final_requirement_version=final_requirement_version,
            payload=payload,
        )
        test_case_repo.create_set(
            db,
            set_id=set_id,
            project_id=project_id,
            name=payload.name,
            requirement_doc_id=payload.requirement_doc_id,
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

        version = document_repo.find_latest_final_requirement_version(db, requirement["id"])
        if not version:
            raise ValueError("该需求文档尚未生成最终需求，请先完成需求分析。")

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
        rejected_case_feedback=[
            RejectedTestCaseFeedback.model_validate(item)
            for item in _generation_run_input_snapshot(run_context).get("rejected_case_feedback", [])
        ],
    )


def _read_final_requirement_content(version) -> str:
    file_path = version["file_path"]
    if file_path:
        resolved_path = resolve_stored_path(file_path) or Path(file_path)
        if resolved_path.exists():
            return resolved_path.read_text(encoding="utf-8")
    return version["markdown_content"] or ""


def _complete_generation_run(run_context: dict, result: TestCaseGenerationResult) -> None:
    generated_cases = []
    for module in result.modules:
        for test_case in module.test_cases:
            generated_cases.append(
                {
                    "title": test_case.title,
                    "module": test_case.module or module.module_name,
                    "priority": test_case.priority,
                    "preconditions": test_case.precondition,
                    "steps_json": json.dumps(_steps_to_jsonable(test_case.steps), ensure_ascii=False),
                    "expected_result": test_case.expected_result,
                    "source_requirement_refs": json.dumps([run_context["requirement_doc_id"]], ensure_ascii=False),
                    "source_exploration_refs": "[]",
                }
            )

    module_order: dict[str, int] = {}
    for case in generated_cases:
        module_name = case["module"].strip()
        module_order.setdefault(module_name, len(module_order))
    generated_cases.sort(
        key=lambda case: (
            module_order[case["module"].strip()],
            PRIORITY_RANK.get(case["priority"].strip().upper(), len(PRIORITY_RANK)),
        )
    )
    cases = [
        {
            **case,
            "id": f"{run_context['test_case_set_id']}-tc-{index:03d}",
            "display_order": index - 1,
        }
        for index, case in enumerate(generated_cases, start=1)
    ]

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
        test_case_repo.update_set_status(db, run["test_case_set_id"], status="failed")
        test_case_repo.update_generation_run_status(
            db,
            run_id,
            status="failed",
            error_message=error_message[:1000],
        )


def _require_final_requirement_version(db, document_id: str):
    final_requirement_version = document_repo.find_latest_final_requirement_version(db, document_id)
    if not final_requirement_version:
        raise api_error(400, "NO_FINAL_REQUIREMENT", "该需求文档尚未生成最终需求，请先完成需求分析。")
    return final_requirement_version


def _generation_run_input_snapshot(run_context: dict) -> dict:
    try:
        snapshot = json.loads(run_context.get("input_json") or "{}")
    except json.JSONDecodeError:
        snapshot = {}
    return snapshot if isinstance(snapshot, dict) else {}


def _generation_input_snapshot(
    *,
    project,
    requirement,
    final_requirement_version,
    payload: TestCaseSetCreateIn,
    rejected_case_feedback: list[dict] | None = None,
) -> dict:
    return {
        "project_id": project["id"],
        "project_name": project["name"],
        "requirement_doc_id": requirement["id"],
        "requirement_doc_title": requirement["name"],
        "final_requirement_version_id": final_requirement_version["id"],
        "final_requirement_version_no": final_requirement_version["version_no"],
        "generation_scope_type": payload.generation_scope_type,
        "generation_scope_text": payload.generation_scope_text,
        "notes": payload.notes,
        "rejected_case_feedback": rejected_case_feedback or [],
    }


def _serialize_set(db, row, *, include_cases: bool = False) -> dict:
    generation_run = test_case_repo.latest_generation_run(db, row["id"])
    result = {
        "id": row["id"],
        "project_id": row["project_id"],
        "project_name": row["project_name"],
        "name": row["name"],
        "requirement_doc_id": row["requirement_doc_id"],
        "requirement_doc_title": row["requirement_doc_title"],
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
        "review_stats": test_case_repo.review_stats_by_set(db, row["id"]),
    }
    if include_cases:
        result["cases"] = [_serialize_case(case) for case in test_case_repo.list_cases_by_set(db, row["id"])]
    return result


def _sync_set_review_status(db, set_id: str, review_stats: dict) -> None:
    next_status = (
        "review_completed"
        if review_stats["case_count"] > 0 and review_stats["reviewed_count"] == review_stats["case_count"]
        else "ready_for_review"
    )
    test_case_repo.update_set_status(db, set_id, status=next_status)


def _serialize_case(row) -> dict:
    try:
        raw_steps = json.loads(row["steps_json"] or "[]")
    except json.JSONDecodeError:
        raw_steps = []
    expected_result = row["expected_result"]
    return {
        "id": row["id"],
        "test_case_set_id": row["test_case_set_id"],
        "project_id": row["project_id"],
        "title": row["title"],
        "module": row["module"],
        "priority": row["priority"],
        "preconditions": row["preconditions"],
        "steps": _normalize_step_rows(raw_steps, fallback_expected_result=expected_result),
        "expected_result": expected_result,
        "status": row["status"],
        "review_feedback": row["review_feedback"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_rejected_feedback_rows(rows) -> list[dict]:
    rejected_feedback = []
    for row in rows:
        try:
            raw_steps = json.loads(row["steps_json"] or "[]")
        except json.JSONDecodeError:
            raw_steps = []
        expected_result = row["expected_result"]
        rejected_feedback.append(
            {
                "title": row["title"],
                "module": row["module"],
                "priority": row["priority"],
                "preconditions": row["preconditions"],
                "steps": _normalize_step_rows(raw_steps, fallback_expected_result=expected_result),
                "expected_result": expected_result,
                "review_feedback": row["review_feedback"],
            }
        )
    return rejected_feedback


def _steps_to_jsonable(steps) -> list[dict]:
    return [_step_to_dict(step) for step in steps or [] if _step_to_dict(step)["action"]]


def _normalize_step_rows(value, *, fallback_expected_result: str = "") -> list[dict]:
    if not isinstance(value, list):
        return []
    return [
        normalized
        for step in value
        if (normalized := _step_to_dict(step, fallback_expected_result=fallback_expected_result))["action"]
    ]


def _step_to_dict(step, *, fallback_expected_result: str = "") -> dict:
    if hasattr(step, "model_dump"):
        step = step.model_dump()
    if isinstance(step, str):
        return {"action": step.strip(), "expected_result": fallback_expected_result}
    if isinstance(step, dict):
        return {
            "action": str(step.get("action") or step.get("step") or "").strip(),
            "expected_result": str(step.get("expected_result") or fallback_expected_result).strip(),
        }
    return {"action": "", "expected_result": ""}


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
