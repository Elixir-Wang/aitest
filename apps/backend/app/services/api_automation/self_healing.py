from __future__ import annotations

import asyncio
import difflib
import json
import secrets
import shutil
from pathlib import Path

import yaml

from app.agents.api_automation.self_healing.diagnosis_agent import diagnose_failure, enforce_uncertain_oracle_policy
from app.agents.api_automation.self_healing.repair_agent import repair_failure
from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.core.db import connect
from app.core.exceptions import api_error
from app.core import storage
from app.repositories import api_automation_repo
from app.services.api_automation import service as api_service
from app.services.api_automation.artifact_storage import (
    materialize_scenario_entrypoint,
    project_suite_path,
    project_workspace_lock,
)
from app.services.api_automation.runner import collect_script_suite, run_script_suite
from app.services.api_automation.self_healing_artifacts import (
    build_manifest,
    create_attempt_workspace,
    create_revision_snapshot,
)
from app.services.api_automation.self_healing_context import build_failure_context


def _serialize_attempt(row) -> dict:
    actions = []
    if row["status"] == "waiting_approval":
        actions = ["approve_proposal", "reject_proposal"]
    elif row["status"] == "proposal_ready":
        actions = ["reanalyze"]
    elif row["status"] == "ready_to_apply":
        actions = ["view_diff", "apply", "discard"]
    elif row["status"] in {"completed", "proposal_rejected", "rejected", "failed", "superseded"}:
        actions = []
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "attempt_number": row["attempt_number"],
        "base_run_id": row["base_run_id"],
        "base_revision": row["base_revision"],
        "status": row["status"],
        "user_context": row["user_context"],
        "diagnosis": api_automation_repo.loads_json(row["diagnosis_json"], {}),
        "validation": api_automation_repo.loads_json(row["validation_json"], {}),
        "decision": row["decision"],
        "applied_run_id": row["applied_run_id"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "available_actions": actions,
    }


def _serialize_session(row, attempts) -> dict:
    actions = ["rollback", "close"]
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "source_run_id": row["source_run_id"],
        "current_run_id": row["current_run_id"],
        "status": row["status"],
        "current_revision": row["current_revision"],
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "attempts": [_serialize_attempt(item) for item in attempts],
        "available_actions": actions,
    }


def create_repair_session(project_id: str, run_id: str, user_context: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        run = api_automation_repo.find_api_run(db, run_id)
        if not run or run["project_id"] != project_id:
            raise api_error(404, "API_RUN_NOT_FOUND", "接口自动化运行记录不存在。")
        if run["status"] not in {"failed", "observed"}:
            raise api_error(409, "API_REPAIR_RUN_NOT_FAILED", "仅失败的接口自动化运行可以发起 AI 修复。")
        if run["target_type"] != "scripts":
            raise api_error(409, "API_REPAIR_TARGET_UNSUPPORTED", "当前仅支持脚本运行的 AI 修复。")
        existing = api_automation_repo.find_active_repair_session_for_run(db, project_id, run_id)
        if existing:
            attempts = api_automation_repo.list_repair_attempts(db, existing["id"])
            current = attempts[-1]
            return {
                "session_id": existing["id"],
                "attempt_id": current["id"],
                "status": current["status"],
            }
        session_id = f"apirepair-{secrets.token_hex(8)}"
        attempt_id = f"apirepairatt-{secrets.token_hex(8)}"
        api_automation_repo.create_repair_session(
            db,
            session_id=session_id,
            project_id=project_id,
            source_run_id=run_id,
            current_run_id=run_id,
            created_by=actor["id"],
        )
        api_automation_repo.create_repair_attempt(
            db,
            attempt_id=attempt_id,
            session_id=session_id,
            attempt_number=1,
            base_run_id=run_id,
            base_revision=0,
            user_context=user_context,
        )
    suite_path = project_suite_path(project_id)
    if not suite_path.exists():
        raise api_error(404, "API_REPAIR_SUITE_NOT_FOUND", "接口自动化 pytest 项目不存在。")
    create_revision_snapshot(project_id, session_id, 0, suite_path)
    return {"session_id": session_id, "attempt_id": attempt_id, "status": "queued"}


def get_repair_session(project_id: str, session_id: str, actor) -> dict:
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        row = api_automation_repo.find_repair_session(db, session_id)
        if not row or row["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_SESSION_NOT_FOUND", "AI 修复会话不存在。")
        return _serialize_session(row, api_automation_repo.list_repair_attempts(db, session_id))


def create_next_repair_attempt(project_id: str, session_id: str, user_context: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        session = api_automation_repo.find_repair_session(db, session_id)
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_SESSION_NOT_FOUND", "AI 修复会话不存在。")
        if session["status"] != "active":
            raise api_error(409, "API_REPAIR_SESSION_NOT_ACTIVE", "当前 AI 修复会话不可继续分析。")
        attempts = api_automation_repo.list_repair_attempts(db, session_id)
        if not attempts or attempts[-1]["status"] != "proposal_ready":
            raise api_error(409, "API_REPAIR_ATTEMPT_NOT_REANALYZABLE", "当前修复轮次不可重新分析。")
        attempt_id = f"apirepairatt-{secrets.token_hex(8)}"
        attempt_number = attempts[-1]["attempt_number"] + 1
        api_automation_repo.create_repair_attempt(
            db,
            attempt_id=attempt_id,
            session_id=session_id,
            attempt_number=attempt_number,
            base_run_id=session["current_run_id"],
            base_revision=session["current_revision"],
            user_context=user_context,
        )
    return {"session_id": session_id, "attempt_id": attempt_id, "status": "queued"}


def _attempt_dir(project_id: str, session_id: str, attempt_number: int) -> Path:
    return (
        storage.PROJECT_FILE_STORAGE_ROOT
        / project_id
        / "api_automation"
        / "repairs"
        / f"repair-{session_id}"
        / "attempts"
        / f"attempt-{attempt_number:04d}"
    )


def _read_run_artifacts(run) -> tuple[dict, dict]:
    logs = {"stdout": "", "stderr": ""}
    for key in ("stdout", "stderr"):
        path = storage.resolve_stored_path(run[f"{key}_path"])
        if path and path.exists():
            logs[key] = path.read_text(encoding="utf-8", errors="replace")
    report = {}
    report_path = storage.resolve_stored_path(run["json_report_path"])
    if report_path and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    observation_path = (
        storage.resolve_stored_path(run["observation_result_path"])
        if "observation_result_path" in run.keys()
        else None
    )
    if observation_path and observation_path.exists():
        try:
            observation_payload = json.loads(observation_path.read_text(encoding="utf-8"))
            if isinstance(observation_payload, dict):
                report["observations"] = observation_payload.get("observations", [])
            elif isinstance(observation_payload, list):
                report["observations"] = observation_payload
        except (OSError, UnicodeError, json.JSONDecodeError):
            report["observations"] = []
    return logs, report


def _write_diff(base: Path, workspace: Path, output: Path) -> list[str]:
    changed = []
    chunks = []
    paths = sorted(set(build_manifest(base)) | set(build_manifest(workspace)))
    for relative in paths:
        before_path = base / relative
        after_path = workspace / relative
        before = before_path.read_text(encoding="utf-8", errors="replace").splitlines() if before_path.exists() else []
        after = after_path.read_text(encoding="utf-8", errors="replace").splitlines() if after_path.exists() else []
        if before == after:
            continue
        changed.append(relative)
        chunks.extend(
            difflib.unified_diff(before, after, fromfile=f"a/{relative}", tofile=f"b/{relative}", lineterm="")
        )
    output.write_text("\n".join(chunks), encoding="utf-8")
    return changed


def execute_repair_attempt(attempt_id: str) -> None:
    with connect() as db:
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt:
            return
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        run = api_automation_repo.find_api_run(db, attempt["base_run_id"])
        api_automation_repo.update_repair_attempt(db, attempt_id, status="collecting_context")
        history = [_serialize_attempt(item) for item in api_automation_repo.list_repair_attempts(db, session["id"])[:-1]]
    suite_path = project_suite_path(session["project_id"])
    logs, report = _read_run_artifacts(run)
    context = build_failure_context(
        api_service._serialize_api_run(run), logs, report, suite_path, history, attempt["user_context"]
    )
    selection = resolve_model_selection("api_test_generation")
    model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    try:
        with connect() as db:
            api_automation_repo.update_repair_attempt(db, attempt_id, status="diagnosing")
        diagnosis = asyncio.run(diagnose_failure(model=model, context=context))
        diagnosis = enforce_uncertain_oracle_policy(diagnosis, context)
        attempt_dir = _attempt_dir(session["project_id"], session["id"], attempt["attempt_number"])
        attempt_dir.mkdir(parents=True, exist_ok=True)
        (attempt_dir / "diagnosis.json").write_text(diagnosis.model_dump_json(indent=2), encoding="utf-8")
        proposal = diagnosis.proposal
        script_repair_allowed = bool(proposal and proposal.script_repair_allowed)
        validation = {"summary": run and api_automation_repo.loads_json(run["summary_json"], {}), "changed_files": []}
        with connect() as db:
            api_automation_repo.update_repair_attempt(
                db,
                attempt_id,
                status="waiting_approval" if script_repair_allowed else "proposal_ready",
                diagnosis=diagnosis.model_dump(),
                validation=validation,
            )
    except Exception as exc:
        with connect() as db:
            api_automation_repo.update_repair_attempt(db, attempt_id, status="failed", error_message=str(exc)[:2000])


def get_repair_attempt(project_id: str, attempt_id: str, actor) -> dict:
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt:
            raise api_error(404, "API_REPAIR_ATTEMPT_NOT_FOUND", "AI 修复轮次不存在。")
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_ATTEMPT_NOT_FOUND", "AI 修复轮次不存在。")
        return _serialize_attempt(attempt)


def _load_case_updates(
    workspace: Path,
    project_id: str,
    db,
    *,
    case_ids: set[str] | None = None,
    created_by: str = "system",
) -> None:
    allowed = {
        "title", "priority", "coverage", "preconditions", "request", "test_data", "expected",
        "assertions", "notes", "test_description", "oracle_status",
    }
    loaded_case_ids: set[str] = set()
    for path in workspace.rglob("cases.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(payload, list):
            raise ValueError(f"用例数据格式错误：{path}")
        for item in payload:
            if not isinstance(item, dict):
                continue
            case_id = str(item.get("case_id") or item.get("id") or "")
            if not case_id:
                continue
            if case_ids is not None and case_id not in case_ids:
                continue
            row = api_automation_repo.find_api_test_case(db, case_id)
            if not row or row["project_id"] != project_id:
                raise ValueError(f"用例不属于当前项目：{case_id}")
            loaded_case_ids.add(case_id)
            changes = {key: item[key] for key in allowed if key in item}
            current = api_service._serialize_api_test_case(row)
            effective_changes = {
                key: value for key, value in changes.items() if current.get(key) != value
            }
            if not effective_changes:
                continue
            api_automation_repo.update_api_test_case(db, case_id, **effective_changes)
            updated = api_automation_repo.find_api_test_case(db, case_id)
            versions = api_automation_repo.list_api_test_case_versions(db, case_id)
            api_automation_repo.create_api_test_case_version(
                db,
                version_id=f"apitcv-{secrets.token_hex(8)}",
                case_id=case_id,
                version=max((int(version["version"]) for version in versions), default=0) + 1,
                snapshot=api_service._serialize_api_test_case(updated),
                change_source="ai_repair",
                created_by=created_by,
            )
    if case_ids is not None:
        missing = sorted(case_ids - loaded_case_ids)
        if missing:
            raise ValueError(f"候选修复未找到对应测试用例：{', '.join(missing)}")


def _apply_proposed_case_updates(workspace: Path, case_updates: list[dict]) -> list[dict]:
    pending = {str(item["case_id"]): item for item in case_updates}
    applied: list[dict] = []
    for path in workspace.rglob("cases.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(payload, list):
            raise ValueError(f"用例数据格式错误：{path}")
        changed = False
        for case in payload:
            if not isinstance(case, dict):
                continue
            case_id = str(case.get("case_id") or case.get("id") or "")
            update = pending.get(case_id)
            if not update:
                continue
            expected = update["expected_status_code"]
            actual = update["actual_status_code"]
            assertions = case.get("assertions") or []
            status_assertion = next(
                (item for item in assertions if item.get("type") == "status_code"),
                None,
            )
            if not status_assertion or status_assertion.get("expected") != expected:
                raise ValueError(f"用例 {case_id} 的原状态码断言已变化，请重新分析。")
            status_assertion["expected"] = actual
            case["oracle_status"] = "confirmed"
            note = f"AI 修复根据实际响应将状态码从 {expected} 校准为 {actual}，经人工审批后生效。"
            existing_notes = str(case.get("notes") or "").strip()
            case["notes"] = f"{existing_notes} {note}".strip()
            applied.append(
                {
                    "case_id": case_id,
                    "changes": {
                        "assertions": assertions,
                        "oracle_status": "confirmed",
                        "notes": case["notes"],
                    },
                    "reason": note,
                }
            )
            changed = True
        if changed:
            path.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
    missing = sorted(set(pending) - {item["case_id"] for item in applied})
    if missing:
        raise ValueError(f"候选修复未找到对应测试用例：{', '.join(missing)}")
    return applied


def approve_repair_attempt(project_id: str, attempt_id: str, comment: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt or attempt["status"] != "waiting_approval":
            raise api_error(409, "API_REPAIR_ATTEMPT_NOT_APPROVABLE", "当前修复建议不可审批。")
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_SESSION_NOT_FOUND", "AI 修复会话不存在。")
        diagnosis = api_automation_repo.loads_json(attempt["diagnosis_json"], {})
        if not diagnosis.get("proposal", {}).get("script_repair_allowed"):
            raise api_error(409, "API_REPAIR_SCRIPT_CHANGE_NOT_ALLOWED", "当前建议不允许修改测试脚本。")
        api_automation_repo.update_repair_attempt(
            db, attempt_id, status="candidate_generating", decision="proposal_approved", error_message=comment
        )
        return _serialize_attempt(api_automation_repo.find_repair_attempt(db, attempt_id))


def execute_candidate_repair(attempt_id: str) -> None:
    with connect() as db:
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt or attempt["status"] != "candidate_generating":
            return
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        run = api_automation_repo.find_api_run(db, attempt["base_run_id"])
        diagnosis_data = api_automation_repo.loads_json(attempt["diagnosis_json"], {})
        history = [_serialize_attempt(item) for item in api_automation_repo.list_repair_attempts(db, session["id"])[:-1]]
    suite_path = project_suite_path(session["project_id"])
    logs, report = _read_run_artifacts(run)
    context = build_failure_context(
        api_service._serialize_api_run(run), logs, report, suite_path, history, attempt["user_context"]
    )
    attempt_dir = _attempt_dir(session["project_id"], session["id"], attempt["attempt_number"])
    try:
        workspace = create_attempt_workspace(session["project_id"], session["id"], attempt["attempt_number"], suite_path)
        case_updates = diagnosis_data.get("proposal", {}).get("case_updates", [])
        if case_updates:
            from app.agents.api_automation.self_healing.schemas import RepairResult

            applied_updates = _apply_proposed_case_updates(workspace, case_updates)
            repair_result = RepairResult(
                summary=f"已按审批建议校准 {len(applied_updates)} 条不确定用例。",
                case_updates=applied_updates,
                changed_source_files=[],
            )
        else:
            from app.agents.api_automation.self_healing.schemas import FailureDiagnosis

            selection = resolve_model_selection("api_test_generation")
            model = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
            repair_result = asyncio.run(
                repair_failure(
                    model=model,
                    workspace=workspace,
                    diagnosis=FailureDiagnosis.model_validate(diagnosis_data),
                    context=context,
                )
            )
            (workspace / ".repair-result.json").unlink(missing_ok=True)
        with connect() as db:
            api_automation_repo.update_repair_attempt(db, attempt_id, status="candidate_validating")
        collect_result = collect_script_suite(suite_path=workspace, timeout=120)
        with connect() as db:
            environment = api_service._build_runtime_environment(db, run["api_environment_id"])
        scenario_file = None
        test_paths = None
        target_type = run["target_type"] if "target_type" in run.keys() else "scripts"
        if target_type == "scenario":
            snapshot = api_automation_repo.loads_json(run["execution_snapshot_json"], {})
            stored_suite_path = api_service._resolve_generated_path(
                session["project_id"], snapshot.get("suite_path", "")
            )
            scenario_test_path = materialize_scenario_entrypoint(workspace)
            test_paths = [str(scenario_test_path.relative_to(workspace))]
            stored_data_file = snapshot.get("data_file_path", "")
            if stored_data_file:
                stored_data_path = api_service._resolve_generated_path(
                    session["project_id"], stored_data_file
                )
                scenario_file = str(stored_data_path.relative_to(stored_suite_path))
        run_result = run_script_suite(
            run_id=f"repair-validation-{attempt_id}",
            project_id=session["project_id"],
            suite_path=workspace,
            run_dir=attempt_dir / "validation",
            environment=environment,
            timeout=environment.get("timeout_seconds", 30),
            test_paths=test_paths,
            scenario_file=scenario_file,
        )
        base_revision = (
            storage.PROJECT_FILE_STORAGE_ROOT / session["project_id"] / "api_automation" / "repairs"
            / f"repair-{session['id']}" / "revisions" / f"rev-{attempt['base_revision']:04d}"
        )
        changed_files = _write_diff(base_revision, workspace, attempt_dir / "changes.diff")
        validation = {
            "collection": collect_result,
            "summary": run_result["summary"],
            "status": run_result["status"],
            "changed_files": changed_files,
            "repair_result": repair_result.model_dump(),
        }
        with connect() as db:
            api_automation_repo.update_repair_attempt(
                db, attempt_id, status="ready_to_apply", validation=validation
            )
    except Exception as exc:
        with connect() as db:
            api_automation_repo.update_repair_attempt(db, attempt_id, status="failed", error_message=str(exc)[:2000])


def apply_repair_attempt(project_id: str, attempt_id: str, comment: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt or attempt["status"] != "ready_to_apply":
            raise api_error(409, "API_REPAIR_ATTEMPT_NOT_APPLICABLE", "当前候选修复不可应用。")
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_SESSION_NOT_FOUND", "AI 修复会话不存在。")
        if session["current_revision"] != attempt["base_revision"]:
            api_automation_repo.update_repair_attempt(db, attempt_id, status="superseded")
            raise api_error(409, "REPAIR_BASE_CHANGED", "正式测试项目已变化，请重新分析。")
        base_run = api_automation_repo.find_api_run(db, attempt["base_run_id"])
    attempt_dir = _attempt_dir(project_id, session["id"], attempt["attempt_number"])
    workspace = attempt_dir / "workspace"
    if not workspace.exists():
        raise api_error(404, "API_REPAIR_WORKSPACE_NOT_FOUND", "候选修复 workspace 不存在。")
    suite_path = project_suite_path(project_id)
    revision_root = (
        storage.PROJECT_FILE_STORAGE_ROOT
        / project_id
        / "api_automation"
        / "repairs"
        / f"repair-{session['id']}"
        / "revisions"
        / f"rev-{attempt['base_revision']:04d}"
    )
    if build_manifest(suite_path) != build_manifest(revision_root):
        with connect() as db:
            api_automation_repo.update_repair_attempt(db, attempt_id, status="superseded")
        raise api_error(409, "REPAIR_BASE_CHANGED", "正式测试项目已变化，请重新分析。")
    next_revision = session["current_revision"] + 1
    validation = api_automation_repo.loads_json(attempt["validation_json"], {})
    repair_result = validation.get("repair_result", {})
    changed_case_ids = {
        str(item.get("case_id"))
        for item in repair_result.get("case_updates", [])
        if isinstance(item, dict) and item.get("case_id")
    }
    backup = suite_path.parent / f".{suite_path.name}.repair-backup"
    staging = suite_path.parent / f".{suite_path.name}.repair-staging"
    with project_workspace_lock(project_id):
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(workspace, staging, ignore=shutil.ignore_patterns(".repair-result.json", ".pytest_cache", "__pycache__"))
        collect_result = collect_script_suite(suite_path=staging, timeout=120)
        if not collect_result["ok"]:
            raise api_error(422, "API_REPAIR_COLLECTION_FAILED", collect_result["stderr"] or "候选修复收集失败。")
        with connect() as db:
            _load_case_updates(
                staging,
                project_id,
                db,
                case_ids=changed_case_ids,
                created_by=actor["id"],
            )
            shutil.rmtree(backup, ignore_errors=True)
            suite_path.rename(backup)
            try:
                staging.rename(suite_path)
                create_revision_snapshot(project_id, session["id"], next_revision, suite_path)
                run_id = f"apirun-{secrets.token_hex(8)}"
                api_automation_repo.create_api_run(
                    db,
                    run_id=run_id,
                    task_id=f"api_automation_run:{run_id}",
                    project_id=project_id,
                    api_environment_id=base_run["api_environment_id"],
                    script_ids=api_automation_repo.loads_json(base_run["script_ids_json"], []),
                    execution_snapshot=api_automation_repo.loads_json(base_run["execution_snapshot_json"], {}),
                    target_type=base_run["target_type"],
                    target_ids=api_automation_repo.loads_json(base_run["target_ids_json"], []),
                    command_summary=base_run["command_summary"],
                    created_by=actor["id"],
                    parent_run_id=base_run["id"],
                    source_repair_attempt_id=attempt_id,
                )
                api_automation_repo.update_repair_attempt(
                    db,
                    attempt_id,
                    status="rerunning",
                    decision="approved",
                    applied_run_id=run_id,
                )
                api_automation_repo.update_repair_session(
                    db,
                    session["id"],
                    current_run_id=run_id,
                    current_revision=next_revision,
                )
            except Exception:
                shutil.rmtree(suite_path, ignore_errors=True)
                backup.rename(suite_path)
                raise
            else:
                shutil.rmtree(backup, ignore_errors=True)
    return {"session_id": session["id"], "attempt_id": attempt_id, "run_id": run_id, "status": "rerunning"}


def discard_repair_attempt(project_id: str, attempt_id: str, comment: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt or attempt["status"] != "ready_to_apply":
            raise api_error(409, "API_REPAIR_ATTEMPT_NOT_DISCARDABLE", "当前候选修复不可放弃。")
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_SESSION_NOT_FOUND", "AI 修复会话不存在。")
        workspace = _attempt_dir(project_id, session["id"], attempt["attempt_number"]) / "workspace"
        shutil.rmtree(workspace, ignore_errors=True)
        api_automation_repo.update_repair_attempt(
            db, attempt_id, status="proposal_rejected", decision="candidate_discarded", error_message=comment
        )
        return _serialize_attempt(api_automation_repo.find_repair_attempt(db, attempt_id))


def reject_repair_attempt(project_id: str, attempt_id: str, comment: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt:
            raise api_error(404, "API_REPAIR_ATTEMPT_NOT_FOUND", "AI 修复轮次不存在。")
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_ATTEMPT_NOT_FOUND", "AI 修复轮次不存在。")
        api_automation_repo.update_repair_attempt(
            db, attempt_id, status="proposal_rejected", decision="rejected", error_message=comment
        )
        return _serialize_attempt(api_automation_repo.find_repair_attempt(db, attempt_id))


def _artifact_path(project_id: str, attempt_id: str, filename: str, actor) -> Path:
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        attempt = api_automation_repo.find_repair_attempt(db, attempt_id)
        if not attempt:
            raise api_error(404, "API_REPAIR_ATTEMPT_NOT_FOUND", "AI 修复轮次不存在。")
        session = api_automation_repo.find_repair_session(db, attempt["session_id"])
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_ATTEMPT_NOT_FOUND", "AI 修复轮次不存在。")
    path = _attempt_dir(project_id, session["id"], attempt["attempt_number"]) / filename
    if not path.exists():
        raise api_error(404, "API_REPAIR_ARTIFACT_NOT_FOUND", "AI 修复产物不存在。")
    return path


def get_repair_diff(project_id: str, attempt_id: str, actor) -> str:
    return _artifact_path(project_id, attempt_id, "changes.diff", actor).read_text(encoding="utf-8")


def get_repair_logs(project_id: str, attempt_id: str, actor) -> dict:
    root = _artifact_path(project_id, attempt_id, "validation", actor)
    return {
        "stdout": (root / "stdout.txt").read_text(encoding="utf-8", errors="replace") if (root / "stdout.txt").exists() else "",
        "stderr": (root / "stderr.txt").read_text(encoding="utf-8", errors="replace") if (root / "stderr.txt").exists() else "",
    }


def get_repair_report(project_id: str, attempt_id: str, actor) -> dict:
    path = _artifact_path(project_id, attempt_id, "validation/report.json", actor)
    return json.loads(path.read_text(encoding="utf-8"))


def rollback_repair_session(project_id: str, session_id: str, revision: int, reason: str, actor) -> dict:
    api_service._require_admin(actor)
    with connect() as db:
        api_service._require_visible_project(db, project_id, actor)
        session = api_automation_repo.find_repair_session(db, session_id)
        if not session or session["project_id"] != project_id:
            raise api_error(404, "API_REPAIR_SESSION_NOT_FOUND", "AI 修复会话不存在。")
        base_run = api_automation_repo.find_api_run(db, session["current_run_id"])
    repair_root = storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "repairs" / f"repair-{session_id}"
    source = repair_root / "revisions" / f"rev-{revision:04d}"
    if not source.exists():
        raise api_error(404, "API_REPAIR_REVISION_NOT_FOUND", "指定修复版本不存在。")
    suite_path = project_suite_path(project_id)
    staging = suite_path.parent / f".{suite_path.name}.rollback-staging"
    backup = suite_path.parent / f".{suite_path.name}.rollback-backup"
    next_revision = session["current_revision"] + 1
    with project_workspace_lock(project_id):
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(source, staging)
        collect_result = collect_script_suite(suite_path=staging, timeout=120)
        if not collect_result["ok"]:
            raise api_error(422, "API_REPAIR_COLLECTION_FAILED", collect_result["stderr"] or "回退版本收集失败。")
        with connect() as db:
            _load_case_updates(staging, project_id, db)
            shutil.rmtree(backup, ignore_errors=True)
            suite_path.rename(backup)
            try:
                staging.rename(suite_path)
                create_revision_snapshot(project_id, session_id, next_revision, suite_path)
                run_id = f"apirun-{secrets.token_hex(8)}"
                api_automation_repo.create_api_run(
                    db,
                    run_id=run_id,
                    task_id=f"api_automation_run:{run_id}",
                    project_id=project_id,
                    api_environment_id=base_run["api_environment_id"],
                    script_ids=api_automation_repo.loads_json(base_run["script_ids_json"], []),
                    execution_snapshot=api_automation_repo.loads_json(base_run["execution_snapshot_json"], {}),
                    target_type=base_run["target_type"],
                    target_ids=api_automation_repo.loads_json(base_run["target_ids_json"], []),
                    command_summary=f"回退到 Revision {revision}: {reason}",
                    created_by=actor["id"],
                    parent_run_id=base_run["id"],
                )
                api_automation_repo.update_repair_session(
                    db, session_id, status="active", current_run_id=run_id, current_revision=next_revision
                )
            except Exception:
                shutil.rmtree(suite_path, ignore_errors=True)
                backup.rename(suite_path)
                raise
            else:
                shutil.rmtree(backup, ignore_errors=True)
    return {"session_id": session_id, "revision": next_revision, "run_id": run_id, "status": "rerunning"}
