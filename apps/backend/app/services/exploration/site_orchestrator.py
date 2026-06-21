import threading
import traceback
from pathlib import Path
import secrets

from app.core.environment_auth_state import auth_state_path, auth_state_summary
from app.core.db import connect
from app.core.storage import PROJECT_FILE_STORAGE_ROOT, store_path
from app.repositories import exploration_repo
from app.services import operation_log_service
from app.services.exploration import artifact_service as exploration_artifact_service
from app.services.exploration import event_bus as exploration_event_bus
from app.services.exploration import goal_validation_service as exploration_goal_validation_service
from app.services.exploration import service as exploration_service
from app.services.exploration import unified_orchestrator


def run_exploration(run_id: str) -> None:
    try:
        _run_exploration(run_id)
    except Exception as error:
        _mark_run_failed_after_unhandled_error(run_id, error)


def _run_exploration(run_id: str) -> None:
    start_event = None
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return
        if run["status"] in {"stopping", "cancelled"}:
            _mark_cancelled(db, run, "用户已停止探索，任务未继续执行。")
            return
        if run["status"] != "queued":
            return
        artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
        _ensure_artifact_dirs(artifact_root)
        exploration_repo.clear_run_outputs(db, run_id)
        exploration_service.seed_planned_modules_for_run(db, run)
        exploration_repo.update_run_state(
            db,
            run_id,
            status="running",
            artifact_root=store_path(artifact_root) or "",
            result_summary="站点探索已开始，正在生成运行合同。",
            started=True,
        )
        exploration_repo.update_module_coverages_status(
            db,
            run_id,
            from_status="pending",
            to_status="running",
            completion_summary="站点探索已开始，正在生成运行合同。",
        )
        start_event = (
            run,
            {
                "action": "start",
                "result": "success",
                "summary": f"站点探索开始执行：{run['title']}",
                "after": {"status": "running", "artifact_root": store_path(artifact_root) or ""},
            },
        )
        _publish_run_event(
            "run_started",
            run,
            {"status": "running", "artifact_root": store_path(artifact_root) or ""},
        )
        for module in exploration_repo.list_module_coverages(db, run_id):
            _publish_module_event("module_discovered", run_id, module)

    if start_event:
        _record_runner_event(start_event[0], **start_event[1])

    with connect() as db:
        current = exploration_repo.find_by_id(db, run_id)
        if not current:
            return
        finish_event = None
        if current["status"] == "stopping":
            _mark_cancelled(db, current, "用户已停止探索，任务未继续执行。")
            _publish_run_event("run_cancelled", current, {"status": "cancelled", "result_summary": "用户已停止探索，任务未继续执行。"})
            exploration_event_bus.close(run_id)
            finish_event = (
                current,
                {
                    "action": "finish",
                    "result": "cancelled",
                    "summary": f"站点探索已停止：{current['title']}",
                    "after": {"status": "cancelled", "result_summary": "用户已停止探索，任务未继续执行。"},
                },
            )
        else:
            exploration_repo.update_run_state(
                db,
                run_id,
                status="running",
                artifact_root=store_path(artifact_root) or "",
                result_summary="Agentic Loop 已开始，正在观察页面并决策下一步。",
            )
    if finish_event:
        _record_runner_event(finish_event[0], **finish_event[1])
        return

    result = _execute_unified_exploration(run_id, artifact_root)
    _persist_runner_result(run_id, artifact_root, result)


def _persist_runner_result(run_id: str, artifact_root: Path, result: dict) -> None:
    finish_event = None
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return
        if run["status"] in {"cancelled", "interrupted"}:
            exploration_event_bus.close(run_id)
            return
        if run["status"] == "stopping":
            _mark_cancelled(db, run, "用户已停止探索，已保留停止前生成的日志和产物。")
            _publish_run_event("run_cancelled", run, {"status": "cancelled", "result_summary": "用户已停止探索，已保留停止前生成的日志和产物。"})
            exploration_event_bus.close(run_id)
            finish_event = (
                run,
                {
                    "action": "finish",
                    "result": "cancelled",
                    "summary": f"站点探索已停止：{run['title']}",
                    "after": {"status": "cancelled", "result_summary": "用户已停止探索，已保留停止前生成的日志和产物。"},
                    "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                },
            )
        else:
            exploration_repo.clear_run_outputs(db, run_id)
            if result["status"] == "cancelled":
                _mark_cancelled(db, run, result["summary"])
                _publish_run_event("run_cancelled", run, {"status": "cancelled", "result_summary": result["summary"]})
                exploration_event_bus.close(run_id)
                finish_event = (
                    run,
                    {
                        "action": "finish",
                        "result": "cancelled",
                        "summary": f"站点探索已停止：{run['title']}，{result['summary']}",
                        "after": {"status": "cancelled", "result_summary": result["summary"], "log_path": result.get("log_path", "")},
                        "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                    },
                )
            elif result["status"] == "blocked":
                _persist_blocked_result(db, run, artifact_root, result)
                finish_event = (
                    run,
                    {
                        "action": "finish",
                        "result": "failed",
                        "summary": f"站点探索阻塞：{run['title']}，{result['summary']}",
                        "failure_reason": result.get("failure_detail", result["summary"]),
                        "after": {"status": "blocked", "result_summary": result["summary"], "log_path": result.get("log_path", "")},
                        "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                    },
                )
            else:
                persisted_status, persisted_summary = _persist_completed_result(db, run, artifact_root, result)
                finish_event = (
                    run,
                    {
                        "action": "finish",
                        "result": "success" if persisted_status == "completed" else "partial_success",
                        "summary": f"站点探索执行完成：{run['title']}，{persisted_summary}",
                        "after": {"status": persisted_status, "result_summary": persisted_summary, "log_path": result.get("log_path", "")},
                        "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                    },
                )

    if finish_event:
        _record_runner_event(finish_event[0], **finish_event[1])


def _execute_unified_exploration(run_id: str, artifact_root: Path) -> dict:
    """执行目标驱动的统一探索。"""

    log_path = artifact_root / "logs" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        exploration_event_bus.publish(run_id, "execution_started", {
            "message": "使用统一编排器执行目标驱动探索",
            "mode": "unified"
        })

        page_url, forbidden_paths, storage_state_path = _safe_run_context_from_db(run_id)

        exploration_event_bus.publish(run_id, "context_loaded", {
            "start_url": page_url,
            "has_auth": bool(storage_state_path)
        })

        return unified_orchestrator.run_unified_exploration_sync(
            run_id=run_id,
            artifact_root=artifact_root,
            start_url=page_url,
            forbidden_paths=forbidden_paths,
            storage_state_path=storage_state_path,
        )

    except Exception as e:
        error_msg = f"统一探索执行异常: {type(e).__name__}: {str(e)}"

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{error_msg}\n")
                import traceback
                f.write(traceback.format_exc())
        except:
            pass

        exploration_event_bus.publish(run_id, "error", {"message": error_msg})

        return {
            "status": "blocked",
            "summary": error_msg,
            "log_path": store_path(log_path) or "",
        }


def _mark_run_failed_after_unhandled_error(run_id: str, error: Exception) -> None:
    error_detail = f"{type(error).__name__}: {error}"
    summary = f"探索执行异常中断：{error_detail[:500]}"
    try:
        with connect() as db:
            run = exploration_repo.find_by_id(db, run_id)
            if not run or run["status"] not in {"queued", "running", "stopping"}:
                return
            artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
            _ensure_artifact_dirs(artifact_root)
            log_path = artifact_root / "logs" / "run.log"
            log_path.write_text(
                "\n".join(
                    [
                        "Unhandled site exploration error.",
                        error_detail,
                        traceback.format_exc(),
                    ]
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            exploration_repo.update_run_state(
                db,
                run_id,
                status="blocked",
                artifact_root=store_path(artifact_root) or run["artifact_root"],
                result_summary=summary,
                finished=True,
            )
            failure_event = (
                run,
                {
                    "action": "finish",
                    "result": "failed",
                    "summary": f"站点探索异常中断：{run['title']}，{summary}",
                    "failure_reason": summary,
                    "after": {
                        "status": "blocked",
                        "result_summary": summary,
                        "log_path": store_path(log_path) or "",
                    },
                    "artifact_path": [store_path(log_path) or ""],
                },
            )
            _publish_run_event("run_failed", run, {"status": "blocked", "result_summary": summary})
            exploration_event_bus.close(run_id)
    except Exception:
        return
    _record_runner_event(failure_event[0], **failure_event[1])


def _ensure_artifact_dirs(root: Path) -> None:
    for name in ("pages", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)


def _agent_login_context(run) -> tuple[str, str, bool]:
    login_strategy = str(_run_value(run, "environment_login_strategy", _run_value(run, "login_strategy", "skip_login")) or "skip_login")
    captcha_strategy = str(_run_value(run, "environment_captcha_strategy", "none") or "none")
    reuse_auth_state = _bool_value(_run_value(run, "environment_reuse_auth_state", login_strategy != "skip_login"))
    if login_strategy == "skip_login":
        return "skip_login", "none", False
    if captcha_strategy == "manual" and not reuse_auth_state:
        return "account_password", "none", False
    return login_strategy, captcha_strategy, reuse_auth_state


def _has_login_credentials(run, login_strategy: str) -> bool:
    if login_strategy != "account_password":
        return False
    username = str(_run_value(run, "environment_username", "") or "").strip()
    has_password = bool(_run_value(run, "environment_has_password", 0))
    return bool(username and has_password)


def _run_value(run, key: str, default=None):
    return run[key] if key in run.keys() else default


def _bool_value(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _result_log_content(result: dict) -> str:
    log = str(result.get("log") or result.get("summary") or "")
    return log if log.endswith("\n") else f"{log}\n"


def _safe_run_context_from_db(run_id: str) -> tuple[str, str, str]:
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return "about:blank", "", ""
        storage_state_path = _stored_auth_state_path_for_run(run)
        start_url = _exploration_start_url(run)
        return start_url or "about:blank", str(run["forbidden_paths"] or ""), str(storage_state_path or "")


def _stored_auth_state_path_for_run(run) -> Path | None:
    login_strategy, _, reuse_auth_state = _agent_login_context(run)
    if login_strategy != "account_password" or not reuse_auth_state:
        return None
    environment_id = str(run["environment_id"])
    summary = auth_state_summary(
        environment_id=environment_id,
        login_strategy=login_strategy,
        reuse_auth_state=reuse_auth_state,
    )
    if summary["status"] != "valid":
        return None
    path = auth_state_path(environment_id)
    return path if path.exists() else None


def _exploration_start_url(run) -> str:
    site_url = _safe_site_url(run)
    if not site_url:
        return "about:blank"
    return site_url


def _record_runner_event(
    run,
    *,
    action: str,
    result: str,
    summary: str,
    after: dict,
    artifact_path: list[str] | None = None,
    failure_reason: str = "",
) -> None:
    operation_log_service.record_task_event(
        module="exploration",
        action=action,
        object_type="exploration_run",
        object_id=run["id"],
        object_name=run["title"],
        project_id=run["project_id"],
        actor_id="system",
        actor_name="系统",
        source="runner",
        result=result,
        failure_reason=failure_reason,
        summary=summary,
        after=after,
        task_id=run["id"],
        artifact_path=artifact_path or [],
    )


def _publish_run_event(event_type: str, run, payload: dict | None = None) -> None:
    base_payload = {
        "id": run["id"],
        "project_id": run["project_id"],
        "title": run["title"],
    }
    if payload:
        base_payload.update(payload)
    exploration_event_bus.publish(run["id"], event_type, base_payload)


def _publish_module_event(event_type: str, run_id: str, module) -> None:
    exploration_event_bus.publish(
        run_id,
        event_type,
        {
            "module_id": module["id"],
            "module_key": module["module_key"],
            "module_name": module["module_name"],
            "entry_path": module["entry_path"],
            "planned_page_count": module["planned_page_count"],
            "explored_page_count": module["explored_page_count"],
            "blocked_page_count": module["blocked_page_count"],
            "action_count": module["action_count"],
            "field_count": module["field_count"],
            "state_transition_count": module["state_transition_count"],
            "completion_status": module["completion_status"],
            "completion_summary": module["completion_summary"],
        },
    )


def _publish_page_event(event_type: str, run_id: str, page: dict) -> None:
    exploration_event_bus.publish(
        run_id,
        event_type,
        {
            "module_key": page.get("module_key", ""),
            "page_id": page.get("id", ""),
            "title": page.get("title", ""),
            "url": page.get("url", ""),
            "entry_path": page.get("entry_path", ""),
            "structure_summary": page.get("structure_summary", ""),
            "status": page.get("status", "completed"),
            "yaml_path": page.get("yaml_path", ""),
            "recent_event": page.get("recent_event", ""),
            "blocker_reason": page.get("blocker_reason", ""),
            "steps": page.get("steps", []),
        },
    )


def _publish_step_event(run_id: str, module_key: str, page_id: str, step: dict) -> None:
    exploration_event_bus.publish(
        run_id,
        "step_recorded",
        {
            "module_key": module_key,
            "page_id": page_id,
            "step": step,
        },
    )


def _publish_blocker_event(run_id: str, blocker: dict) -> None:
    exploration_event_bus.publish(
        run_id,
        "blocker_detected",
        {
            "module_key": blocker.get("module_key", ""),
            "page_ref": blocker.get("page_ref", ""),
            "reason_type": blocker.get("reason_type", ""),
            "reason": blocker.get("reason", ""),
            "evidence_path": blocker.get("evidence_path", ""),
            "suggested_action": blocker.get("suggested_action", ""),
        },
    )


def _mark_cancelled(db, run, summary: str) -> None:
    exploration_repo.update_run_state(
        db,
        run["id"],
        status="cancelled",
        result_summary=summary,
        finished=True,
    )


def _failure_detail_from_log(log: str) -> str:
    for raw_line in log.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        return line[:500]
    return ""


def _summary_with_failure_detail(summary: str, failure_detail: str) -> str:
    if not failure_detail or failure_detail in summary:
        return summary
    return f"{summary} 真实原因：{failure_detail}"


def _suggested_action_with_failure_detail(suggested_action: str, failure_detail: str) -> str:
    if not failure_detail:
        return suggested_action
    return f"{suggested_action} 真实失败原因：{failure_detail}"


def _persist_blocked_result(db, run, artifact_root: Path, result: dict) -> None:
    module_key = _module_key(run)
    reason_type = str(result.get("reason_type") or "exploration_blocked")
    log_path = str(result.get("log_path") or "")
    log_content = str(result.get("log") or result["summary"]) + "\n"
    suggested_action = str(result.get("suggested_action") or "查看执行日志并修正阻塞原因后重新探索。")
    markdown = _render_markdown(
        run=run,
        status="blocked",
        summary=result["summary"],
        module_status="blocked",
        page_url="",
        blocker=result["summary"],
    )
    artifacts = exploration_artifact_service.write_exploration_artifacts(
        artifact_root,
        run=run,
        summary={"status": "blocked", "summary": result["summary"], "markdown_content": markdown},
        page_artifacts=[],
        graph={"nodes": [], "edges": [], "paths": []},
        blockers=[
            {
                "module_key": module_key,
                "page_ref": run["environment_name"],
                "reason_type": reason_type,
                "reason": result["summary"],
                "evidence_path": log_path,
                "suggested_action": suggested_action,
            }
        ],
        log_content=log_content,
    )

    exploration_repo.create_module_coverage(
        db,
        coverage_id=_id("expcov"),
        exploration_run_id=run["id"],
        module_key=module_key,
        module_name=_module_name(run),
        entry_path=run["scope"] or run["environment_name"],
        planned_page_count=1,
        explored_page_count=0,
        blocked_page_count=1,
        action_count=0,
        field_count=0,
        state_transition_count=0,
        completion_status="blocked",
        completion_summary=result["summary"],
    )
    for module in exploration_repo.list_module_coverages(db, run["id"]):
        _publish_module_event("module_updated", run["id"], module)
    exploration_repo.create_blocker(
        db,
        blocker_id=_id("expblk"),
        exploration_run_id=run["id"],
        module_key=module_key,
        page_ref=run["environment_name"],
        reason_type=reason_type,
        reason=result["summary"],
        evidence_path=log_path,
        impact_scope="站点探索、候选需求、知识库、用例、自动化",
        suggested_action=suggested_action,
    )
    _publish_blocker_event(
        run["id"],
        {
            "module_key": module_key,
            "page_ref": run["environment_name"],
            "reason_type": reason_type,
            "reason": result["summary"],
            "evidence_path": log_path,
            "suggested_action": suggested_action,
        },
    )
    _persist_common_artifacts(db, run["id"], artifacts, log_path)
    exploration_repo.update_run_state(
        db,
        run["id"],
        status="blocked",
        result_summary=result["summary"],
        finished=True,
    )
    _publish_run_event("run_failed", run, {"status": "blocked", "result_summary": result["summary"]})
    exploration_event_bus.close(run["id"])


def _persist_completed_result(db, run, artifact_root: Path, result: dict) -> tuple[str, str]:
    page_url = _safe_site_url(run)
    result_log = str(result.get("log") or result.get("summary") or "")
    result_log_path = str(result.get("log_path") or "")
    page_artifacts = _result_page_artifacts(result)
    result_status, coverage_gap_blocker = _completion_status_with_coverage_gate(run, result, page_artifacts)
    goal_validation = exploration_goal_validation_service.validate_goal(run["goal"], page_artifacts, _result_graph(result))
    result_status = exploration_goal_validation_service.terminal_status_for_goal_validation(result_status, goal_validation)
    goal_summary = _goal_validation_status_summary(goal_validation)
    result_summary = result["summary"] if not goal_summary else f"{result['summary']} {goal_summary}"
    module_coverages = _build_module_coverages(run, result, page_artifacts, result_status, coverage_gap_blocker, page_url)
    markdown = _render_markdown(
        run=run,
        status=result_status,
        summary=result_summary,
        module_status="partial" if result_status == "partial" else "completed",
        page_url=page_url,
        blocker="",
        pages=[page for module in module_coverages for page in module["pages"]],
        elements=[element for module in module_coverages for element in module["elements"]],
    )
    payload_blockers = []
    for module in module_coverages:
        for blocker in module["blockers"]:
            payload_blockers.append(
                {
                    "module_key": module["module_key"],
                    "page_ref": blocker.get("page_ref") or page_url,
                    "reason_type": blocker.get("reason_type") or "exploration_gap",
                    "reason": blocker.get("reason") or "探索过程中存在未覆盖项。",
                    "evidence_path": result_log_path,
                    "suggested_action": blocker.get("suggested_action") or "人工确认后重新探索。",
                    "is_blocking": bool(blocker.get("is_blocking", True)),
                }
            )
    artifacts = exploration_artifact_service.write_exploration_artifacts(
        artifact_root,
        run=run,
        summary={
            "status": result_status,
            "summary": result_summary,
            "markdown_content": markdown,
            "modules": result.get("modules") if isinstance(result.get("modules"), list) else [],
        },
        page_artifacts=page_artifacts,
        graph=_result_graph(result),
        blockers=payload_blockers,
        log_content=result_log,
        goal_validation=goal_validation,
    )

    for module in module_coverages:
        # 尝试更新已存在的规划模块，如果不存在则创建新的
        existing_modules = {m["module_key"]: m for m in exploration_repo.list_module_coverages(db, run["id"])}

        if module["module_key"] in existing_modules:
            # 更新已存在的规划模块
            exploration_repo.update_module_coverage(
                db,
                exploration_run_id=run["id"],
                module_key=module["module_key"],
                module_name=module["module_name"],
                entry_path=module["entry_path"],
                planned_page_count=module["planned_page_count"],
                explored_page_count=module["explored_page_count"],
                blocked_page_count=module["blocked_page_count"],
                action_count=module["action_count"],
                field_count=module["field_count"],
                state_transition_count=module["state_transition_count"],
                completion_status=module["completion_status"],
                completion_summary=module["completion_summary"],
            )
        else:
            # 创建新模块（对于未在规划中的模块）
            exploration_repo.create_module_coverage(
                db,
                coverage_id=_id("expcov"),
                exploration_run_id=run["id"],
                module_key=module["module_key"],
                module_name=module["module_name"],
                entry_path=module["entry_path"],
                planned_page_count=module["planned_page_count"],
                explored_page_count=module["explored_page_count"],
                blocked_page_count=module["blocked_page_count"],
                action_count=module["action_count"],
                field_count=module["field_count"],
                state_transition_count=module["state_transition_count"],
                completion_status=module["completion_status"],
                completion_summary=module["completion_summary"],
            )
    for module in exploration_repo.list_module_coverages(db, run["id"]):
        _publish_module_event("module_updated", run["id"], module)
    for module in module_coverages:
        for page in module["pages"]:
            _publish_page_event("page_completed", run["id"], {**page, "status": "completed"})
            for step in page.get("steps", []):
                _publish_step_event(run["id"], module["module_key"], page["id"], step)
    for module in module_coverages:
        for blocker in module["blockers"]:
            _publish_blocker_event(run["id"], blocker)
    _persist_common_artifacts(db, run["id"], artifacts, result_log_path)
    exploration_repo.update_run_state(
        db,
        run["id"],
        status=result_status,
        result_summary=result_summary,
        finished=True,
    )
    terminal_event = "run_completed" if result_status == "completed" else "run_failed"
    _publish_run_event(terminal_event, run, {"status": result_status, "result_summary": result_summary})
    exploration_event_bus.close(run["id"])
    return result_status, result_summary


def _goal_validation_status_summary(goal_validation: dict) -> str:
    status = str(goal_validation.get("status") or "")
    if status in {"", "skipped", "passed"}:
        return ""
    summary = str(goal_validation.get("summary") or "").strip()
    return summary or "目标验证未完全通过。"


def _build_module_coverages(
    run,
    result: dict,
    page_artifacts: list[dict],
    result_status: str,
    coverage_gap_blocker: dict | None,
    page_url: str,
) -> list[dict]:
    # 获取规划的模块列表，建立模块名到 module_key 的映射
    from app.core.db import connect
    from app.repositories import exploration_repo

    planned_module_map = {}
    with connect() as db:
        for module in exploration_repo.list_module_coverages(db, run["id"]):
            # 将规划的模块名映射到 module_key (planned-01, planned-02 等)
            planned_module_map[module["module_name"]] = module["module_key"]

    module_groups: dict[str, dict] = {}
    for page_artifact in page_artifacts:
        page = page_artifact["page"]
        page_module_name = str(page.get("module") or "unclassified")

        # 如果页面的模块名在规划中存在，使用规划的 module_key
        if page_module_name in planned_module_map:
            module_key = planned_module_map[page_module_name]
            module_name = page_module_name
        else:
            module_key = page_module_name
            module_name = page_module_name if page_module_name != "unclassified" else _module_name(run)

        module = module_groups.setdefault(
            module_key,
            {
                "module_key": module_key,
                "module_name": module_name,
                "entry_path": str(page.get("normalized_url") or page.get("url") or page_url),
                "pages": [],
                "elements": [],
                "blockers": [],
                "observed_action_count": 0,
            },
        )
        module["pages"].append(_page_index_payload(page_artifact, module_key))
        module["elements"].extend(_elements_from_page_artifacts([page_artifact], module_key, page_url))
        module["observed_action_count"] += len(page_artifact.get("actions", [])) if isinstance(page_artifact.get("actions"), list) else 0

    if not module_groups:
        module_groups["unclassified"] = {
            "module_key": "unclassified",
            "module_name": "未分组模块",
            "entry_path": run["scope"] or page_url,
            "pages": [],
            "elements": [],
            "blockers": [],
            "observed_action_count": 0,
        }

    for blocker in _module_blockers_from_result(result, coverage_gap_blocker, module_groups, page_url):
        module_groups[blocker["module_key"]]["blockers"].append(blocker)

    module_count = len(module_groups)
    for module in module_groups.values():
        pages = module["pages"]
        blockers = module["blockers"]
        explored_page_count = len(pages)
        planned_page_count = max(explored_page_count, 1)
        blocking_blockers = [blocker for blocker in blockers if blocker.get("is_blocking")]
        blocked_page_count = len(blocking_blockers)
        has_blocking = bool(blocking_blockers)
        recent_page = pages[-1] if pages else None
        blocker_summary = blockers[0]["reason"] if blockers else "无"
        if result_status == "partial" and coverage_gap_blocker and pages:
            completion_status = "partial"
        elif has_blocking:
            completion_status = "blocked"
        elif blockers:
            completion_status = "partial"
        elif explored_page_count == 0:
            completion_status = "partial"
        else:
            completion_status = "completed"
        module["planned_page_count"] = planned_page_count
        module["explored_page_count"] = explored_page_count
        module["blocked_page_count"] = blocked_page_count
        module["action_count"] = int(result.get("action_count") or 0) if module_count == 1 else int(module["observed_action_count"])
        module["field_count"] = (
            int(result.get("field_count") or 0)
            if module_count == 1
            else sum(1 for element in module["elements"] if element["element_type"] in {"textbox", "combobox", "checkbox", "radio"})
        )
        module["state_transition_count"] = int(result.get("state_transition_count") or 0)
        module["completion_status"] = completion_status
        module["completion_summary"] = _build_module_summary(
            explored_page_count=explored_page_count,
            planned_page_count=planned_page_count,
            recent_page=recent_page,
            blocker_summary=_empty_page_summary(result_status) if explored_page_count == 0 and blocker_summary == "无" else blocker_summary,
            completion_status=completion_status,
            result_status=result_status,
        )
        module["blocker_summary"] = blocker_summary
    return list(module_groups.values())


def _empty_page_summary(result_status: str) -> str:
    if result_status == "running":
        return "等待页面事实生成"
    return "未探索到页面事实，无法确认探索目标已完成"


def _module_blockers_from_result(
    result: dict,
    coverage_gap_blocker: dict | None,
    module_groups: dict[str, dict],
    page_url: str,
) -> list[dict]:
    page_module_by_ref = {}
    for module_key, module in module_groups.items():
        for page in module["pages"]:
            page_module_by_ref[page["id"]] = module_key
            page_module_by_ref[page["url"]] = module_key
            page_module_by_ref[page["entry_path"]] = module_key

    raw_blockers = list(result.get("blockers", [])) if isinstance(result.get("blockers"), list) else []
    if coverage_gap_blocker:
        raw_blockers.append(coverage_gap_blocker)

    normalized = []
    fallback_key = next(iter(module_groups.keys()), "unclassified")
    for blocker in raw_blockers:
        if not isinstance(blocker, dict):
            continue
        page_ref = str(blocker.get("page_ref") or blocker.get("page") or blocker.get("url") or page_url)
        module_key = str(blocker.get("module_key") or page_module_by_ref.get(page_ref) or fallback_key)
        if module_key not in module_groups:
            module_key = fallback_key
        normalized.append(
            {
                "module_key": module_key,
                "page_ref": page_ref,
                "reason_type": str(blocker.get("reason_type") or blocker.get("type") or "exploration_gap"),
                "reason": str(blocker.get("reason") or "探索过程中存在未覆盖项。"),
                "evidence_path": str(blocker.get("evidence_path") or result.get("log_path") or ""),
                "suggested_action": str(blocker.get("suggested_action") or "人工确认后重新探索。"),
                "is_blocking": bool(blocker.get("is_blocking", True)),
            }
        )
    return normalized


def _build_module_summary(
    *,
    explored_page_count: int,
    planned_page_count: int,
    recent_page: dict | None,
    blocker_summary: str,
    completion_status: str,
    result_status: str,
) -> str:
    recent_text = f"最近页面：{recent_page['title']}" if recent_page else "最近页面：无"
    if completion_status == "blocked":
        return f"已覆盖 {explored_page_count}/{planned_page_count} 个页面，{recent_text}，阻塞：{blocker_summary}。"
    if completion_status == "partial":
        return f"已覆盖 {explored_page_count}/{planned_page_count} 个页面，{recent_text}，部分完成：{blocker_summary}。"
    if result_status == "running":
        return f"已覆盖 {explored_page_count}/{planned_page_count} 个页面，{recent_text}，探索中。"
    return f"已覆盖 {explored_page_count}/{planned_page_count} 个页面，{recent_text}，无阻塞。"


def _completion_status_with_coverage_gate(run, result: dict, page_artifacts: list[dict]) -> tuple[str, dict | None]:
    status = str(result.get("status") or "completed")
    if status != "completed" or not _is_full_site_scope(run):
        return status, None
    if len(page_artifacts) != 1:
        return status, None

    discovery = result.get("discovery") if isinstance(result.get("discovery"), dict) else {}
    discovered_link_count = int(discovery.get("discovered_link_count") or 0)
    same_origin_link_count = int(discovery.get("same_origin_link_count") or 0)
    action_count = int(result.get("action_count") or 0)
    state_transition_count = int(result.get("state_transition_count") or 0)
    has_existing_blocker = bool(result.get("blockers"))
    if has_existing_blocker or discovered_link_count > 0 or same_origin_link_count > 0 or action_count > 0 or state_transition_count > 0:
        return status, None

    reason = str(discovery.get("reason_if_stopped") or "探索范围要求覆盖全部站点，但本次仅覆盖入口页，未发现可继续递归探索的页面入口。")
    return "partial", {
        "page_ref": page_artifacts[0].get("page", {}).get("url") or _safe_site_url(run),
        "reason_type": "coverage_gap",
        "reason": f"仅覆盖入口页：{reason}",
        "suggested_action": "补充目录解析、搜索探测、站点地图或人工入口清单后重新探索。",
    }


def _is_full_site_scope(run) -> bool:
    scope = str(run["scope"] or "").lower()
    full_site_terms = ("全部站点", "全部内容", "所有内容", "所有页面", "全站", "遍历")
    return any(term in scope for term in full_site_terms)


def _persist_common_artifacts(db, run_id: str, artifacts: dict[str, str], log_path: str) -> None:
    for artifact_type, path_value, title in (
        ("yaml", artifacts.get("run_path", ""), "探索运行配置"),
        ("yaml", artifacts.get("summary_path", ""), "探索概览摘要"),
        ("yaml", artifacts.get("graph_path", ""), "探索页面关系"),
        ("yaml", artifacts.get("blockers_path", ""), "探索阻塞清单"),
        ("markdown", artifacts.get("report_path", ""), "探索报告"),
        ("log", log_path, "探索执行日志"),
    ):
        exploration_repo.create_artifact(
            db,
            artifact_id=_id("expart"),
            exploration_run_id=run_id,
            artifact_type=artifact_type,
            file_path=path_value,
            title=title,
            summary="站点探索 v2 产物。",
        )


def _render_markdown(
    *,
    run,
    status: str,
    summary: str,
    module_status: str,
    page_url: str,
    blocker: str,
    pages: list[dict] | None = None,
    elements: list[dict] | None = None,
) -> str:
    blocker_block = f"\n## 阻塞项\n\n- {blocker}\n" if blocker else "\n## 阻塞项\n\n- 无\n"
    page_lines = ["## 页面事实", ""]
    if pages:
        for page in pages:
            page_lines.extend(
                [
                    f"### {page['title'] or page['url']}",
                    "",
                    f"- URL：{page['url']}",
                    f"- 结构摘要：{page['structure_summary']}",
                    "",
                ]
            )
    else:
        page_lines.extend([f"- 起始页面：{page_url or '未完成访问'}", ""])
    element_lines = ["## 元素事实", ""]
    if elements:
        for element in elements[:80]:
            element_lines.append(
                f"- {element['element_type']}｜{element['element_name']}｜{element['recommended_locator'] or '-'}"
            )
    else:
        element_lines.append("- 未识别可交互元素")
    return "\n".join(
        [
            f"# {run['title']} 探索文档",
            "",
            "## 探索摘要",
            "",
            f"- 状态：{status}",
            f"- 项目：{run['project_name']}",
            f"- 环境：{run['environment_name']}",
            f"- 站点：{page_url or '-'}",
            f"- 探索目标：{run['goal'] or '-'}",
            f"- 说明：{summary}",
            "",
            "## 模块覆盖矩阵",
            "",
            "| 模块 | 状态 | 说明 |",
            "| --- | --- | --- |",
            f"| {_module_name(run)} | {module_status} | {summary} |",
            "",
            *page_lines,
            *element_lines,
            blocker_block,
            "## 附件",
            "",
            "- 执行日志：logs/run.log",
            "",
        ]
    )


def _module_name(run) -> str:
    scope = str(run["scope"] or "").strip()
    return scope.splitlines()[0][:80] if scope else "站点入口"


def _module_key(run) -> str:
    return "site-entry"


def _safe_site_url(run) -> str:
    return str(run["environment_site_url"] if "environment_site_url" in run.keys() else "")


def _result_page_artifacts(result: dict) -> list[dict]:
    pages = result.get("structured_pages")
    if not isinstance(pages, list):
        raise ValueError("Playwright runner must return structured_pages")
    artifacts = []
    for index, page_artifact in enumerate(pages, start=1):
        if not isinstance(page_artifact, dict) or not isinstance(page_artifact.get("page"), dict):
            raise ValueError("structured_pages must contain page artifacts")
        page = dict(page_artifact["page"])
        if not page.get("url"):
            raise ValueError("structured page artifact missing page.url")
        page["id"] = str(page.get("id") or f"page-{index:03d}")
        page["title"] = str(page.get("title") or page["url"])
        page["normalized_url"] = str(page.get("normalized_url") or page["url"])
        page["module"] = str(page.get("module") or "未分组模块")
        page["depth"] = int(page.get("depth") or 0)
        page["status"] = str(page.get("status") or "explored")
        page["structure_summary"] = str(page.get("structure_summary") or "已生成结构化页面事实。")
        normalized = dict(page_artifact)
        normalized["page"] = page
        normalized.setdefault("accessibility_tree", [])
        normalized.setdefault("actions", [])
        normalized.setdefault("forms", [])
        normalized.setdefault("tables", [])
        normalized.setdefault("relations", {"incoming_edges": [], "outgoing_edges": []})
        normalized.setdefault("quality", {"confidence": "observed", "needs_confirmation": False, "blockers": []})
        artifacts.append(normalized)
    return artifacts


def _result_graph(result: dict) -> dict:
    graph = result.get("graph")
    if not isinstance(graph, dict):
        raise ValueError("Playwright runner must return graph")
    return graph


def _elements_from_page_artifacts(page_artifacts: list[dict], module_key: str, page_url: str) -> list[dict]:
    elements = []
    for page_artifact in page_artifacts:
        page_meta = page_artifact["page"]
        current_page_id = page_meta["id"]
        state_elements = _elements_from_v2_states(page_artifact, module_key, page_url)
        if state_elements:
            elements.extend(state_elements)
            continue
        for node in _flatten_yaml_nodes(page_artifact.get("accessibility_tree", [])):
            if not isinstance(node, dict):
                continue
            role = str(node.get("role") or "")
            name = str(node.get("name") or "")
            locator = str(node.get("locator_hint") or "")
            href = str(node.get("href") or node.get("fallback_locator") or "")
            if not role and not name and not locator:
                continue
            elements.append(
                {
                    "module_key": module_key,
                    "page_id": current_page_id,
                    "element_name": name or locator or "未命名元素",
                    "element_type": role or "element",
                    "recommended_locator": locator,
                    "fallback_locator": href,
                    "stability_note": f"来自页面 YAML 产物，定位置信度：{node.get('locator_confidence') or 'unknown'}。",
                    "source_ref": page_meta.get("url") or page_url,
                }
            )
    return elements


def _elements_from_v2_states(page_artifact: dict, module_key: str, page_url: str) -> list[dict]:
    page_meta = page_artifact["page"]
    page_id = str(page_meta.get("id") or "")
    source_ref = str(page_meta.get("url") or page_url)
    states = page_artifact.get("states") if isinstance(page_artifact.get("states"), list) else []
    elements = []
    for state in states:
        if not isinstance(state, dict):
            continue
        raw_elements = state.get("elements") if isinstance(state.get("elements"), list) else []
        for element in raw_elements:
            if not isinstance(element, dict):
                continue
            primary_selector = element.get("primary_selector") if isinstance(element.get("primary_selector"), dict) else {}
            fallback_selector = element.get("fallback_selector") if isinstance(element.get("fallback_selector"), dict) else {}
            primary_code = _selector_code(primary_selector)
            fallback_code = _selector_code(fallback_selector)
            name = str(element.get("name") or element.get("label") or primary_code or fallback_code or "未命名元素")
            element_type = str(element.get("role") or element.get("type") or "element")
            elements.append(
                {
                    "module_key": module_key,
                    "page_id": page_id,
                    "element_name": name,
                    "element_type": element_type,
                    "recommended_locator": primary_code,
                    "fallback_locator": fallback_code,
                    "stability_note": _selector_stability_note(primary_selector),
                    "source_ref": source_ref,
                    "primary_selector": primary_selector,
                    "fallback_selector": fallback_selector,
                }
            )
    return elements


def _selector_code(selector: dict) -> str:
    return str(selector.get("code") or "") if isinstance(selector, dict) else ""


def _selector_stability_note(selector: dict) -> str:
    verification = selector.get("verification") if isinstance(selector.get("verification"), dict) else {}
    if verification.get("checked") and verification.get("unique") and verification.get("visible"):
        return "主 selector 已通过唯一性和可见性校验。"
    if verification.get("checked"):
        return "主 selector 未通过唯一性或可见性校验，生成自动化前需复核。"
    return "主 selector 尚未完成唯一性和可见性校验。"


def _page_index_payload(page_artifact: dict, module_key: str) -> dict:
    page = page_artifact["page"]
    raw_steps = page_artifact.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raw_steps = page_artifact.get("actions", [])
    return {
        "id": page["id"],
        "module_key": module_key,
        "title": page["title"],
        "url": page["url"],
        "entry_path": page["normalized_url"],
        "structure_summary": page["structure_summary"],
        "status": page.get("status", "explored"),
        "steps": _normalize_steps(raw_steps),
    }


def _normalize_steps(raw_steps) -> list[dict]:
    if not isinstance(raw_steps, list):
        return []
    steps = []
    for index, raw_step in enumerate(raw_steps, start=1):
        if not isinstance(raw_step, dict):
            continue
        steps.append(
            {
                "id": str(raw_step.get("id") or f"step-{index:03d}"),
                "type": str(raw_step.get("type") or "event"),
                "title": str(raw_step.get("title") or raw_step.get("target") or raw_step.get("detail") or "探索步骤"),
                "detail": str(raw_step.get("detail") or raw_step.get("result") or ""),
                "status": str(raw_step.get("status") or "completed"),
                "occurred_at": raw_step.get("occurred_at") if raw_step.get("occurred_at") else None,
                "artifact_path": str(raw_step.get("artifact_path") or ""),
                "source": str(raw_step.get("source") or ""),
            }
        )
    return steps


def _flatten_yaml_nodes(nodes: list[dict]) -> list[dict]:
    flattened = []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        flattened.append(node)
        flattened.extend(_flatten_yaml_nodes(node.get("children", [])))
    return flattened


def _id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"
