from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
from datetime import datetime
from pathlib import Path

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.ui_automation.pytest_playwright.agent import generate_pytest_playwright_case
from app.agents.ui_automation.pytest_playwright.collection import collect_suite
from app.agents.ui_automation.pytest_playwright.renderer import initialize_suite
from app.agents.ui_automation.pytest_playwright.schemas import AutomationPlan
from app.agents.ui_automation.pytest_playwright.suite import case_artifact_paths, project_suite_path, relative_suite_path
from app.core.db import connect
from app.core.environment_auth_state import auth_state_path
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path, store_path
from app.repositories import environment_repo, exploration_artifact_repo, project_repo, test_case_repo, ui_automation_repo

from . import artifact_storage, context, runner


CAPABILITY_ID = "ui_test_generation"


def create_generation_run(project_id: str, payload: dict, actor) -> dict:
    _require_admin(actor)
    if not payload.get("test_case_id") or not payload.get("environment_id"):
        raise api_error(400, "UI_AUTOMATION_INPUT_REQUIRED", "test_case_id 和 environment_id 必填。")
    run_id = f"uigen-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        case, is_manual = _find_source_case(db, payload["test_case_id"])
        if not case or case["project_id"] != project_id:
            raise api_error(404, "UI_TEST_CASE_NOT_FOUND", "测试用例不存在或不属于当前项目。")
        if not is_manual and case["status"] != "approved":
            raise api_error(409, "UI_TEST_CASE_NOT_APPROVED", "只有已采纳测试用例才能生成 UI 自动化。")
        environment = environment_repo.find_by_id(db, payload["environment_id"])
        if not environment or environment["project_id"] != project_id:
            raise api_error(404, "UI_ENVIRONMENT_NOT_FOUND", "环境不存在或不属于当前项目。")
        ui_automation_repo.create_generation_run(
            db,
            run_id=run_id,
            project_id=project_id,
            test_case_id=case["id"],
            environment_id=environment["id"],
            exploration_run_id=payload.get("exploration_run_id", ""),
            created_by=actor["id"],
        )
        return _serialize_generation_run(db, ui_automation_repo.find_generation_run(db, run_id))


def get_generation_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_generation_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_GENERATION_RUN_NOT_FOUND", "UI 自动化生成任务不存在。")
        return _serialize_generation_run(db, row)


def execute_generation_run(run_id: str) -> dict:
    with connect() as db:
        row = ui_automation_repo.find_generation_run(db, run_id)
        if not row or row["status"] not in {"queued", "running"}:
            return _serialize_generation_run(db, row) if row else {}
        ui_automation_repo.update_generation_run(db, run_id, status="running", started_at=_now())
        row = ui_automation_repo.find_generation_run(db, run_id)

    suite_path = project_suite_path(row["project_id"])
    snapshots: list[tuple[Path, bytes | None]] = []
    try:
        with connect() as db:
            case, _ = _find_source_case(db, row["test_case_id"])
            environment = environment_repo.find_by_id(db, row["environment_id"])
            if not case or not environment:
                raise ValueError("生成任务关联的测试用例或环境不存在。")
            artifacts = _artifact_rows(db, row["exploration_run_id"])
        initialize_suite(suite_path)
        artifact_paths = case_artifact_paths(
            suite_path,
            project_id=row["project_id"],
            automation_case_id=f"uiauto-{row['id']}",
            source_test_case_id=case["id"],
            title=case["title"],
        )
        for path in artifact_paths.values():
            snapshots.append((path, path.read_bytes() if path.exists() else None))
        case_data = context.build_case_data(case, automation_case_id=f"uiauto-{row['id']}")
        artifact_storage.write_yaml_atomic(artifact_paths["data_file"], case_data, suite_path=suite_path)
        evidence = context.build_evidence_context(
            exploration_run_id=row["exploration_run_id"],
            artifact_rows=artifacts,
        )
        if not evidence["artifacts"]:
            with connect() as db:
                ui_automation_repo.update_generation_run(
                    db,
                    run_id,
                    status="waiting_manual",
                    error_message="缺少可用于 UI 自动化生成的结构化探索证据，请先完成或选择站点探索任务。",
                    finished_at=_now(),
                )
                return _serialize_generation_run(db, ui_automation_repo.find_generation_run(db, run_id))
        relative_artifacts = {key: relative_suite_path(suite_path, path) for key, path in artifact_paths.items()}
        selection = resolve_model_selection(CAPABILITY_ID)
        model = build_agent_model(selection)
        case_payload = dict(case)
        case_payload["automation_project_key"] = relative_artifacts["test_file"].split("/")[2]
        with artifact_storage.project_workspace_lock(row["project_id"]):
            asyncio.run(
                generate_pytest_playwright_case(
                    model=model,
                    suite_path=suite_path,
                    case_payload=case_payload,
                    evidence_payload=evidence,
                    artifacts=relative_artifacts,
                )
            )
        plan = AutomationPlan.model_validate(json.loads(artifact_paths["plan_file"].read_text(encoding="utf-8")))
        collection = collect_suite(suite_path, test_paths=[relative_artifacts["test_file"]])
        if not collection["ok"]:
            raise ValueError(f"pytest collection 失败：{collection['stderr'][-2000:]}")
        whole_collection = collect_suite(suite_path)
        if not whole_collection["ok"]:
            raise ValueError(f"pytest 全量 collection 失败：{whole_collection['stderr'][-2000:]}")
        source_hash = _source_hash(case, evidence)
        asset_id = f"uiasset-{secrets.token_hex(8)}"
        node_id = f"{relative_artifacts['test_file']}::test_{_identifier(plan.automation_case_id)}"
        with connect() as db:
            ui_automation_repo.upsert_asset(
                db,
                asset_id=asset_id,
                project_id=row["project_id"],
                test_case_id=case["id"],
                source_version=1,
                generation_run_id=run_id,
                status="ready",
                pytest_node_id=node_id,
                suite_path=store_path(suite_path) or str(suite_path),
                test_file_path=relative_artifacts["test_file"],
                data_file_path=relative_artifacts["data_file"],
                plan_file_path=relative_artifacts["plan_file"],
                source_hash=source_hash,
                created_by=row["created_by"],
            )
            ui_automation_repo.update_generation_run(
                db,
                run_id,
                status="completed",
                suite_path=store_path(suite_path) or str(suite_path),
                changed_files=[relative_suite_path(suite_path, path) for path in artifact_paths.values()],
                finished_at=_now(),
                error_message="",
            )
            return _serialize_generation_run(db, ui_automation_repo.find_generation_run(db, run_id))
    except Exception as exc:
        _restore_snapshots(snapshots)
        with connect() as db:
            ui_automation_repo.update_generation_run(
                db,
                run_id,
                status="failed",
                error_message=str(exc)[:4000],
                finished_at=_now(),
            )
            return _serialize_generation_run(db, ui_automation_repo.find_generation_run(db, run_id))


def list_assets(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [_serialize_asset(row) for row in ui_automation_repo.list_assets(db, project_id)]


def get_asset(project_id: str, asset_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_asset(db, asset_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_ASSET_NOT_FOUND", "UI 自动化资产不存在。")
        return _serialize_asset(row)


def get_execution_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
        return _serialize_execution_run(row)


def create_execution_run(project_id: str, asset_id: str, environment_id: str, actor) -> dict:
    _require_admin(actor)
    run_id = f"uirun-{secrets.token_hex(8)}"
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        asset = ui_automation_repo.find_asset(db, asset_id)
        environment = environment_repo.find_by_id(db, environment_id)
        if not asset or asset["project_id"] != project_id:
            raise api_error(404, "UI_ASSET_NOT_FOUND", "UI 自动化资产不存在。")
        if not environment or environment["project_id"] != project_id:
            raise api_error(404, "UI_ENVIRONMENT_NOT_FOUND", "环境不存在或不属于当前项目。")
        ui_automation_repo.create_execution_run(
            db,
            run_id=run_id,
            project_id=project_id,
            asset_id=asset_id,
            environment_id=environment_id,
            created_by=actor["id"],
        )
        return _serialize_execution_run(db, ui_automation_repo.find_execution_run(db, run_id))


def execute_execution_run(run_id: str) -> dict:
    with connect() as db:
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["status"] not in {"queued", "running"}:
            return _serialize_execution_run(db, row) if row else {}
        asset = ui_automation_repo.find_asset(db, row["asset_id"])
        environment = environment_repo.find_by_id(db, row["environment_id"])
        ui_automation_repo.update_execution_run(db, run_id, status="running", started_at=_now())
    suite_path = resolve_stored_path(asset["suite_path"]) or Path(asset["suite_path"])
    run_dir = suite_path / "runs" / run_id
    try:
        result = runner.run_case(
            run_id=run_id,
            suite_path=suite_path,
            run_dir=run_dir,
            pytest_node_id=asset["pytest_node_id"],
            environment={
                "site_url": environment["site_url"],
                "storage_state_path": str(auth_state_path(environment["id"])) if environment["reuse_auth_state"] else "",
            },
        )
        with connect() as db:
            ui_automation_repo.update_execution_run(
                db,
                run_id,
                status=result["status"],
                run_dir=store_path(run_dir) or str(run_dir),
                result=result,
                stdout_path=store_path(Path(result["stdout_path"])) or result["stdout_path"],
                stderr_path=store_path(Path(result["stderr_path"])) or result["stderr_path"],
                trace_path=store_path(Path(result["trace_path"])) if result.get("trace_path") else "",
                screenshot_paths=result.get("screenshot_paths", []),
                finished_at=_now(),
            )
            return _serialize_execution_run(db, ui_automation_repo.find_execution_run(db, run_id))
    except Exception as exc:
        with connect() as db:
            ui_automation_repo.update_execution_run(db, run_id, status="failed", error_message=str(exc)[:4000], finished_at=_now())
            return _serialize_execution_run(db, ui_automation_repo.find_execution_run(db, run_id))


def _artifact_rows(db, exploration_run_id: str) -> list:
    return exploration_artifact_repo.list_by_run(db, exploration_run_id) if exploration_run_id else []


def recover_interrupted_ui_automation_tasks() -> None:
    with connect() as db:
        generation_runs = ui_automation_repo.list_active_generation_runs(db)
        execution_runs = ui_automation_repo.list_active_execution_runs(db)
        for row in generation_runs:
            ui_automation_repo.update_generation_run(
                db,
                row["id"],
                status="failed",
                error_message="服务重启时中断的 UI 自动化生成任务。",
                finished_at=_now(),
            )
        for row in execution_runs:
            ui_automation_repo.update_execution_run(
                db,
                row["id"],
                status="failed",
                error_message="服务重启时中断的 UI 自动化执行任务。",
                finished_at=_now(),
            )


def _require_visible_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目" or project["name"] == actor["project_scope"]:
        return project
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _find_source_case(db, case_id: str):
    case = test_case_repo.find_case_by_id(db, case_id)
    if case:
        return case, False
    return test_case_repo.find_manual_case_by_id(db, case_id), True


def _require_admin(actor):
    if actor["role"] != "admin":
        raise api_error(403, "PERMISSION_DENIED", "仅管理员可生成和执行 UI 自动化。")


def _serialize_generation_run(row):
    if row is None:
        return {}
    return {**dict(row), "changed_files": json.loads(row["changed_files_json"] or "[]")}


def _serialize_asset(row):
    return dict(row)


def _serialize_execution_run(row):
    if row is None:
        return {}
    result = dict(row)
    result["result"] = json.loads(row["result_json"] or "{}")
    result["screenshot_paths"] = json.loads(row["screenshot_paths_json"] or "[]")
    return result


def _source_hash(case, evidence) -> str:
    payload = json.dumps({"case": dict(case), "evidence": evidence}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _restore_snapshots(snapshots):
    for path, content in snapshots:
        if content is None:
            if path.exists():
                path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _identifier(value: str) -> str:
    return "".join(char if char.isalnum() or char == "_" else "_" for char in value).lower().strip("_") or "generated_case"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


__all__ = [
    "create_execution_run",
    "create_generation_run",
    "execute_execution_run",
    "execute_generation_run",
    "get_asset",
    "get_generation_run",
    "list_assets",
]
