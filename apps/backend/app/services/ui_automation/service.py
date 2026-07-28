from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi.responses import FileResponse, StreamingResponse

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.ui_automation.pytest_playwright.agent import generate_pytest_playwright_case
from app.agents.ui_automation.pytest_playwright.collection import collect_suite
from app.agents.ui_automation.pytest_playwright.renderer import initialize_suite
from app.agents.ui_automation.pytest_playwright.schemas import AutomationPlan
from app.agents.ui_automation.pytest_playwright.suite import (
    case_artifact_paths,
    project_suite_path,
    relative_suite_path,
    resolve_suite_file,
)
from app.core.db import connect
from app.core.environment_auth_state import auth_state_path
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path, store_path
from app.repositories import environment_repo, exploration_artifact_repo, exploration_run_repo, project_repo, test_case_repo, ui_automation_repo

from . import artifact_storage, context, live_view, migration, runner


CAPABILITY_ID = "ui_test_generation"
_BACKGROUND_THREADS: set[threading.Thread] = set()
_BACKGROUND_LOCK = threading.Lock()
_BACKGROUND_SHUTTING_DOWN = False


def prepare_background_tasks() -> None:
    global _BACKGROUND_SHUTTING_DOWN
    with _BACKGROUND_LOCK:
        _BACKGROUND_SHUTTING_DOWN = False


def schedule_generation_run(run_id: str) -> bool:
    return _schedule_background(execute_generation_run, run_id, name=f"ui-generation-{run_id}")


def schedule_execution_run(run_id: str) -> bool:
    return _schedule_background(execute_execution_run, run_id, name=f"ui-execution-{run_id}")


def shutdown_background_tasks(
    *,
    timeout: float = 5,
    process_grace_seconds: float = 3,
    live_view_join_timeout: float = 2,
) -> None:
    global _BACKGROUND_SHUTTING_DOWN
    with _BACKGROUND_LOCK:
        _BACKGROUND_SHUTTING_DOWN = True
        threads = list(_BACKGROUND_THREADS)

    live_view.shutdown_all(join_timeout=live_view_join_timeout)
    runner.shutdown_all(grace_seconds=process_grace_seconds)

    deadline = time.monotonic() + max(timeout, 0)
    for thread in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        thread.join(timeout=remaining)


def _schedule_background(function, run_id: str, *, name: str) -> bool:
    def run() -> None:
        try:
            function(run_id)
        finally:
            with _BACKGROUND_LOCK:
                _BACKGROUND_THREADS.discard(thread)

    with _BACKGROUND_LOCK:
        if _BACKGROUND_SHUTTING_DOWN:
            return False
        thread = threading.Thread(target=run, name=name, daemon=True)
        _BACKGROUND_THREADS.add(thread)
        thread.start()
    return True


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
        exploration_run_id = _resolve_exploration_run_id(
            db,
            project_id=project_id,
            environment_id=environment["id"],
            requested_run_id=payload.get("exploration_run_id", ""),
        )
        ui_automation_repo.create_generation_run(
            db,
            run_id=run_id,
            project_id=project_id,
            test_case_id=None if is_manual else case["id"],
            manual_test_case_id=case["id"] if is_manual else None,
            environment_id=environment["id"],
            exploration_run_id=exploration_run_id,
            created_by=actor["id"],
        )
        return _serialize_generation_run(ui_automation_repo.find_generation_run(db, run_id))


def get_generation_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_generation_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_GENERATION_RUN_NOT_FOUND", "UI 自动化生成任务不存在。")
        return _serialize_generation_run(row)


def list_generation_runs(project_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        return [_serialize_generation_run(row) for row in ui_automation_repo.list_generation_runs(db, project_id)]


def execute_generation_run(run_id: str) -> dict:
    with connect() as db:
        row = ui_automation_repo.find_generation_run(db, run_id)
        if not row or row["status"] not in {"queued", "running"}:
            return _serialize_generation_run(row) if row else {}
        ui_automation_repo.update_generation_run(db, run_id, status="running", started_at=_now())
        row = ui_automation_repo.find_generation_run(db, run_id)

    _ensure_project_suite_migrated(row["project_id"])
    with artifact_storage.project_workspace_lock(row["project_id"]):
        return _execute_generation_run_in_workspace(row)


def _execute_generation_run_in_workspace(row) -> dict:
    suite_path = project_suite_path(row["project_id"])
    snapshots: list[tuple[Path, bytes | None]] = []
    try:
        with connect() as db:
            case, _ = _find_source_case(db, _source_case_id(row))
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
                return _serialize_generation_run(ui_automation_repo.find_generation_run(db, run_id))
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
                test_case_id=None if row["manual_test_case_id"] else case["id"],
                manual_test_case_id=case["id"] if row["manual_test_case_id"] else None,
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
            return _serialize_generation_run(ui_automation_repo.find_generation_run(db, run_id))
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
            return _serialize_generation_run(ui_automation_repo.find_generation_run(db, run_id))


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
        generation_runs = ui_automation_repo.list_asset_generation_runs(db, row)
        execution_runs = ui_automation_repo.list_execution_runs(db, project_id, asset_id)
        case, _ = _find_source_case(db, _source_case_id(row))
        return {
            **_serialize_asset(row),
            "source_title": str(case["title"]) if case else "",
            "latest_generation_run": _serialize_generation_run(generation_runs[0]) if generation_runs else None,
            "latest_execution_run": _serialize_execution_run(execution_runs[0]) if execution_runs else None,
            "locator_summary": _locator_summary(row),
        }


def list_asset_generation_runs(project_id: str, asset_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        asset = ui_automation_repo.find_asset(db, asset_id)
        if not asset or asset["project_id"] != project_id:
            raise api_error(404, "UI_ASSET_NOT_FOUND", "UI 自动化资产不存在。")
        return [_serialize_generation_run(row) for row in ui_automation_repo.list_asset_generation_runs(db, asset)]


def list_asset_execution_runs(project_id: str, asset_id: str, actor) -> list[dict]:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        asset = ui_automation_repo.find_asset(db, asset_id)
        if not asset or asset["project_id"] != project_id:
            raise api_error(404, "UI_ASSET_NOT_FOUND", "UI 自动化资产不存在。")
        return [_serialize_execution_run(row) for row in ui_automation_repo.list_execution_runs(db, project_id, asset_id)]


def get_execution_run(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
        return _serialize_execution_run(row)


def delete_execution_run(project_id: str, run_id: str, actor) -> None:
    _require_admin(actor)
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
        if row["status"] in {"queued", "running", "stopping"}:
            raise api_error(409, "UI_EXECUTION_RUN_ACTIVE", "排队中或执行中的运行记录不能删除。")

        asset = ui_automation_repo.find_asset(db, row["asset_id"])
        if not asset or asset["project_id"] != project_id:
            raise api_error(404, "UI_ASSET_NOT_FOUND", "UI 自动化资产不存在。")
        runs_root = ((resolve_stored_path(asset["suite_path"]) or Path(asset["suite_path"])) / "runs").resolve()
        run_dir = (resolve_stored_path(row["run_dir"]) or (runs_root / run_id)).resolve()
        try:
            run_dir.relative_to(runs_root)
        except ValueError as exc:
            raise api_error(409, "UI_EXECUTION_RUN_DIR_INVALID", "运行产物目录不属于当前自动化资产。") from exc
        if run_dir.name != run_id:
            raise api_error(409, "UI_EXECUTION_RUN_DIR_INVALID", "运行产物目录与运行记录不匹配。")
        if run_dir.exists():
            shutil.rmtree(run_dir)
        ui_automation_repo.delete_execution_run(db, run_id)


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
        return _serialize_execution_run(ui_automation_repo.find_execution_run(db, run_id))


def stop_execution_run(project_id: str, run_id: str, actor) -> dict:
    _require_admin(actor)
    should_stop_process = False
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
        cancelled = {
            "run_id": run_id,
            "status": "cancelled",
            "exitcode": None,
        }
        cancelled_queued = ui_automation_repo.transition_execution_run(
            db,
            run_id,
            ("queued",),
            status="cancelled",
            result=cancelled,
            finished_at=_now(),
        )
        marked_stopping = False
        if not cancelled_queued:
            marked_stopping = ui_automation_repo.transition_execution_run(
                db,
                run_id,
                ("running",),
                status="stopping",
            )
        current = ui_automation_repo.find_execution_run(db, run_id)
        should_stop_process = cancelled_queued or marked_stopping or current["status"] == "stopping"

    if should_stop_process:
        runner.request_stop(run_id)
    with connect() as db:
        return _serialize_execution_run(ui_automation_repo.find_execution_run(db, run_id))


def execute_execution_run(run_id: str) -> dict:
    with connect() as db:
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["status"] != "queued":
            runner.clear_stop_request(run_id)
            return _serialize_execution_run(row) if row else {}
        project_id = row["project_id"]
    _ensure_project_suite_migrated(project_id)
    with connect() as db:
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["status"] != "queued":
            runner.clear_stop_request(run_id)
            return _serialize_execution_run(row) if row else {}
        asset = ui_automation_repo.find_asset(db, row["asset_id"])
        environment = environment_repo.find_by_id(db, row["environment_id"])
        suite_path = resolve_stored_path(asset["suite_path"]) or Path(asset["suite_path"])
        run_dir = suite_path / "runs" / run_id
        started = ui_automation_repo.transition_execution_run(
            db,
            run_id,
            ("queued",),
            status="running",
            run_dir=store_path(run_dir) or str(run_dir),
            started_at=_now(),
        )
        if not started:
            runner.clear_stop_request(run_id)
            return _serialize_execution_run(ui_automation_repo.find_execution_run(db, run_id))
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
            update = {
                "status": result["status"],
                "run_dir": store_path(run_dir) or str(run_dir),
                "result": result,
                "stdout_path": store_path(Path(result["stdout_path"])) or result["stdout_path"],
                "stderr_path": store_path(Path(result["stderr_path"])) or result["stderr_path"],
                "trace_path": store_path(Path(result["trace_path"])) if result.get("trace_path") else "",
                "video_path": store_path(Path(result["video_path"])) if result.get("video_path") else "",
                "screenshot_paths": result.get("screenshot_paths", []),
                "error_message": result.get("error_message", ""),
                "finished_at": _now(),
            }
            finalized = ui_automation_repo.transition_execution_run(
                db,
                run_id,
                ("running",),
                **update,
            )
            if not finalized:
                cancelled_result = {**result, "status": "cancelled"}
                ui_automation_repo.transition_execution_run(
                    db,
                    run_id,
                    ("stopping",),
                    **{**update, "status": "cancelled", "result": cancelled_result, "error_message": ""},
                )
            return _serialize_execution_run(ui_automation_repo.find_execution_run(db, run_id))
    except Exception as exc:
        with connect() as db:
            finalized = ui_automation_repo.transition_execution_run(
                db,
                run_id,
                ("running",),
                status="failed",
                error_message=str(exc)[:4000],
                finished_at=_now(),
            )
            if not finalized:
                ui_automation_repo.transition_execution_run(
                    db,
                    run_id,
                    ("stopping",),
                    status="cancelled",
                    error_message="",
                    finished_at=_now(),
                )
            return _serialize_execution_run(ui_automation_repo.find_execution_run(db, run_id))


def _artifact_rows(db, exploration_run_id: str) -> list:
    return exploration_artifact_repo.list_by_run(db, exploration_run_id) if exploration_run_id else []


def _resolve_exploration_run_id(db, *, project_id: str, environment_id: str, requested_run_id: str) -> str:
    if requested_run_id:
        run = exploration_run_repo.find_by_id(db, requested_run_id)
        if not run or run["project_id"] != project_id:
            raise api_error(404, "UI_EXPLORATION_RUN_NOT_FOUND", "站点探索任务不存在或不属于当前项目。")
        if run["environment_id"] != environment_id:
            raise api_error(409, "UI_EXPLORATION_ENVIRONMENT_MISMATCH", "站点探索任务与运行环境不一致。")
        return requested_run_id

    for run in exploration_run_repo.list_by_project(db, project_id):
        if run["environment_id"] != environment_id:
            continue
        evidence = context.build_evidence_context(
            exploration_run_id=run["id"], artifact_rows=_artifact_rows(db, run["id"])
        )
        if evidence["artifacts"]:
            return str(run["id"])
    return ""


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
                status="cancelled" if row["status"] == "stopping" else "failed",
                error_message="" if row["status"] == "stopping" else "服务重启时中断的 UI 自动化执行任务。",
                finished_at=_now(),
            )


def get_execution_logs(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
    return {
        "stdout": _read_stored_text(row["stdout_path"]),
        "stderr": _read_stored_text(row["stderr_path"]),
    }


def get_execution_live_view(project_id: str, run_id: str, actor) -> dict:
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
    session = live_view.get_session(run_id)
    if session and session.status == "ready":
        return {
            "status": "ready",
            "message": session.message,
            "stream_path": (
                f"/projects/{project_id}/ui-automation/runs/{run_id}/live-view/stream?token={session.token}"
            ),
            "width": live_view.VIEWPORT_WIDTH,
            "height": live_view.VIEWPORT_HEIGHT,
        }
    if session:
        status = session.status
        message = session.message
    elif row["status"] == "queued":
        status = "waiting"
        message = "任务排队中，开始执行后将显示浏览器画面。"
    elif row["status"] == "running":
        status = "starting"
        message = "浏览器画面正在启动。"
    else:
        status = "ended"
        message = "本次运行已结束，可查看录制视频。"
    return {
        "status": status,
        "message": message,
        "stream_path": "",
        "width": live_view.VIEWPORT_WIDTH,
        "height": live_view.VIEWPORT_HEIGHT,
    }


def stream_execution_live_view(project_id: str, run_id: str, token: str):
    session = live_view.validate_stream(run_id, token)
    if not session:
        raise api_error(404, "UI_LIVE_VIEW_NOT_FOUND", "实时浏览器画面不存在或已结束。")
    return StreamingResponse(
        live_view.stream_mjpeg(run_id, token),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "X-Accel-Buffering": "no",
        },
    )


def get_execution_artifact(project_id: str, run_id: str, artifact_kind: str, index: int, actor):
    if artifact_kind not in {"trace", "screenshot", "video"}:
        raise api_error(400, "UI_ARTIFACT_KIND_INVALID", "不支持的 UI 自动化运行证据类型。")
    with connect() as db:
        _require_visible_project(db, project_id, actor)
        row = ui_automation_repo.find_execution_run(db, run_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "UI_EXECUTION_RUN_NOT_FOUND", "UI 自动化执行任务不存在。")
    if artifact_kind == "trace":
        paths = [row["trace_path"]]
    elif artifact_kind == "video":
        paths = [row["video_path"]]
    else:
        paths = json.loads(row["screenshot_paths_json"] or "[]")
    if index >= len(paths) or not paths[index]:
        raise api_error(404, "UI_ARTIFACT_NOT_FOUND", "运行证据文件不存在。")
    path = resolve_stored_path(paths[index])
    if not path or not path.is_file():
        raise api_error(404, "UI_ARTIFACT_NOT_FOUND", "运行证据文件不存在。")
    return FileResponse(path)


def _require_visible_project(db, project_id: str, actor):
    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目" or project["name"] == actor["project_scope"]:
        return project
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _ensure_project_suite_migrated(project_id: str) -> Path:
    with artifact_storage.project_workspace_lock(project_id):
        with connect() as db:
            report = migration.migrate_legacy_project_suite(db, project_id)
        migration.remove_migrated_legacy_project_files(project_id, report["run_ids"])
    return project_suite_path(project_id)


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
    result = dict(row)
    result["test_case_id"] = _source_case_id(row)
    return {**result, "changed_files": json.loads(row["changed_files_json"] or "[]")}


def _serialize_asset(row):
    result = dict(row)
    result["test_case_id"] = _source_case_id(row)
    return result


def _source_case_id(row) -> str:
    return str(row["test_case_id"] or row["manual_test_case_id"] or "")


def _serialize_execution_run(row):
    if row is None:
        return {}
    result = dict(row)
    result["result"] = json.loads(row["result_json"] or "{}")
    result["screenshot_paths"] = json.loads(row["screenshot_paths_json"] or "[]")
    return result


def _asset_file_specs(asset) -> list[dict]:
    suite_path = resolve_stored_path(asset["suite_path"]) or Path(asset["suite_path"])
    specs = [
        {
            "kind": "test",
            "path": resolve_suite_file(suite_path, asset["test_file_path"]),
            "relative_path": asset["test_file_path"],
        },
        {
            "kind": "data",
            "path": resolve_suite_file(suite_path, asset["data_file_path"]),
            "relative_path": asset["data_file_path"],
        },
        {
            "kind": "plan",
            "path": resolve_suite_file(suite_path, asset["plan_file_path"]),
            "relative_path": asset["plan_file_path"],
        },
    ]
    plan_path = specs[-1]["path"]
    if plan_path.exists():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            plan = {}
        for page in plan.get("page_objects", []):
            relative_path = str(page.get("file_path", ""))
            if relative_path:
                specs.append(
                    {
                        "kind": "page_object",
                        "path": resolve_suite_file(suite_path, relative_path),
                        "relative_path": relative_path,
                    }
                )
    return specs


def _read_stored_text(path_value: str | None) -> str:
    path = resolve_stored_path(path_value)
    if not path or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _locator_summary(asset) -> dict:
    specs = _asset_file_specs(asset)
    plan_spec = next((spec for spec in specs if spec["kind"] == "plan"), None)
    if not plan_spec or not Path(plan_spec["path"]).exists():
        return {"required": 0, "available": 0, "missing": []}
    try:
        plan = json.loads(Path(plan_spec["path"]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"required": 0, "available": 0, "missing": []}
    required = sum(len(page.get("elements", [])) for page in plan.get("page_objects", []))
    return {"required": required, "available": required, "missing": []}


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
    "delete_execution_run",
    "execute_execution_run",
    "execute_generation_run",
    "get_asset",
    "get_execution_artifact",
    "get_execution_logs",
    "get_execution_live_view",
    "get_execution_run",
    "get_generation_run",
    "list_asset_execution_runs",
    "list_asset_generation_runs",
    "list_assets",
    "list_generation_runs",
    "prepare_background_tasks",
    "recover_interrupted_ui_automation_tasks",
    "schedule_execution_run",
    "schedule_generation_run",
    "shutdown_background_tasks",
    "stream_execution_live_view",
    "stop_execution_run",
]
