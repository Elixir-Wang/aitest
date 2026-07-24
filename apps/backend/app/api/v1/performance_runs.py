import asyncio
import csv
import json
import shutil
from contextlib import contextmanager
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse, StreamingResponse

from app.core import settings
from app.core.db import connect
from app.dependencies.auth import current_user
from app.repositories import api_automation_repo, performance_script_repo, project_repo
from app.services.performance_testing import analysis_service, headless_worker, run_repo, service
from app.services.performance_testing import repair_service
from app.schemas.performance_analysis import PerformanceAnalysisApplyIn


test_router = APIRouter(prefix="/projects/{project_id}/performance-tests/{test_id}", tags=["performance-tests"])
run_router = APIRouter(prefix="/projects/{project_id}/performance-test-runs", tags=["performance-test-runs"])
analysis_router = APIRouter(prefix="/projects/{project_id}/performance-analysis", tags=["performance-analysis"])
REPORT_FILES = {
    "result.html",
    "result_stats.csv",
    "result_stats_history.csv",
    "result_failures.csv",
    "result_exceptions.csv",
    "result_tasks.csv",
    "stdout.log",
    "stderr.log",
}
TERMINAL_STATUSES = {"completed", "stopped", "failed", "cancelled"}
ACTIVE_STATUSES = {"starting", "running", "stopping"}


@test_router.post("/runs")
def create_performance_run(
    project_id: str,
    test_id: str,
    payload: dict,
    actor=Depends(current_user),
) -> dict[str, str]:
    script_id = str(payload.get("script_id") or "")
    if not script_id:
        from app.core.exceptions import api_error
        raise api_error(400, "PERFORMANCE_RUN_INVALID", "必须提供 script_id。")
    with _script_lookup(project_id, test_id, script_id, actor) as context:
        run_id = headless_worker.create_run_session(
            project_id=project_id,
            test_id=test_id,
            script_id=script_id,
            script_code=context["script_code"],
            runtime_payload=context["runtime_environment"],
            load_config=context["load_config"],
            created_by=str(actor["id"]),
        )
    return {"id": run_id, "status": "created"}


@test_router.post("/runs/{run_id}/start")
def start_performance_run(
    project_id: str,
    test_id: str,
    run_id: str,
    payload: dict | None = None,
    actor=Depends(current_user),
) -> dict[str, str | bool]:
    run = _require_run(project_id, run_id, actor)
    if run["performance_test_id"] != test_id:
        from app.core.exceptions import api_error
        raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "性能测试运行不存在。")
    try:
        accepted = headless_worker.start_headless_run(run_id, payload or {})
    except (FileNotFoundError, KeyError, ValueError) as exc:
        from app.core.exceptions import api_error
        raise api_error(409, "PERFORMANCE_RUN_START_INVALID", str(exc)) from exc
    return {"id": run_id, "accepted": accepted}


@test_router.get("/runs/history")
def list_performance_run_history(project_id: str, test_id: str, actor=Depends(current_user)) -> dict:
    _ensure_project_visible(project_id, actor)
    with connect() as db:
        runs = run_repo.list_runs(db, project_id, test_id)[:10]
        return {"performance_test_id": test_id, "retention_limit": 10, "runs": [_run_payload(row) for row in runs]}


@run_router.get("/{run_id}")
def get_performance_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return _run_payload(_require_run(project_id, run_id, actor))


@run_router.delete("/{run_id}", status_code=204)
def delete_performance_run(project_id: str, run_id: str, actor=Depends(current_user)) -> None:
    from app.core.exceptions import api_error

    run = _require_run(project_id, run_id, actor)
    if run["status"] in ACTIVE_STATUSES:
        raise api_error(409, "PERFORMANCE_RUN_ACTIVE", "运行中的压测记录不能删除。")
    with connect() as db:
        run_repo.delete_run(db, run_id)
    shutil.rmtree(_run_report_directory(project_id, run_id), ignore_errors=True)


@run_router.post("/{run_id}/ai-analysis", status_code=202)
def create_performance_analysis(
    project_id: str,
    run_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(current_user),
) -> dict:
    created = analysis_service.create_analysis(project_id, run_id, actor)
    background_tasks.add_task(analysis_service.execute_analysis, created["id"])
    return created


@run_router.get("/{run_id}/ai-analysis")
def list_performance_run_analyses(project_id: str, run_id: str, actor=Depends(current_user)) -> list[dict]:
    return analysis_service.list_run_analyses(project_id, run_id, actor)


@analysis_router.get("/{analysis_id}")
def get_performance_analysis(project_id: str, analysis_id: str, actor=Depends(current_user)) -> dict:
    return analysis_service.get_analysis(project_id, analysis_id, actor)


@analysis_router.post("/{analysis_id}/reject")
def reject_performance_analysis(project_id: str, analysis_id: str, actor=Depends(current_user)) -> dict:
    return analysis_service.reject_analysis(project_id, analysis_id, actor)


@analysis_router.post("/{analysis_id}/apply-and-rerun")
def apply_performance_analysis(
    project_id: str,
    analysis_id: str,
    payload: PerformanceAnalysisApplyIn,
    actor=Depends(current_user),
) -> dict:
    return repair_service.apply_and_rerun(project_id, analysis_id, payload.change_ids, actor)


@run_router.get("/{run_id}/stats")
def get_performance_run_stats(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _require_run(project_id, run_id, actor)
    with connect() as db:
        run = run_repo.get_run(db, run_id)
        return {
            "run": _run_payload(run),
            "stats": [_stat_payload(row) for row in run_repo.list_stats(db, run_id)],
            "request_stats": _request_stats(project_id, run_id),
            "failures": [dict(row) for row in run_repo.list_failures(db, run_id)],
            "exceptions": [dict(row) for row in run_repo.list_exceptions(db, run_id)],
            "events": [dict(row) for row in run_repo.list_events(db, run_id)],
        }


@run_router.get("/{run_id}/state")
def get_performance_run_state(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return {"run": _run_payload(_require_run(project_id, run_id, actor))}


@run_router.get("/{run_id}/charts")
def get_performance_run_charts(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _require_run(project_id, run_id, actor)
    with connect() as db:
        samples = [_stat_payload(row) for row in run_repo.list_stats(db, run_id)]
    history_samples = _history_samples(project_id, run_id)
    if len(history_samples) > len(samples):
        samples = history_samples
    return {"run_id": run_id, "samples": samples}


@run_router.get("/{run_id}/failures")
def get_performance_run_failures(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _require_run(project_id, run_id, actor)
    with connect() as db:
        return {"run_id": run_id, "failures": [dict(row) for row in run_repo.list_failures(db, run_id)]}


@run_router.get("/{run_id}/exceptions")
def get_performance_run_exceptions(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _require_run(project_id, run_id, actor)
    with connect() as db:
        return {"run_id": run_id, "exceptions": [dict(row) for row in run_repo.list_exceptions(db, run_id)]}


@run_router.post("/{run_id}/stop")
def stop_performance_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict[str, str | bool]:
    _require_run(project_id, run_id, actor)
    return {"id": run_id, "accepted": headless_worker.stop_headless_run(run_id)}


@run_router.post("/{run_id}/reset-stats")
def reset_performance_run_stats(project_id: str, run_id: str, actor=Depends(current_user)) -> dict[str, str | bool]:
    run = _require_run(project_id, run_id, actor)
    if run["status"] in {"created", "stopping"}:
        from app.core.exceptions import api_error
        raise api_error(409, "PERFORMANCE_STATS_RESET_INVALID", "当前运行状态不支持重置统计。")
    headless_worker.reset_headless_stats(run_id)
    with connect() as db:
        run_repo.reset_stats(db, run_id)
        run_repo.append_event(db, run_id, "stats_reset", "info", "已重置运行统计", {})
    return {"id": run_id, "reset": True}


@run_router.get("/{run_id}/reports")
def list_performance_run_reports(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    _require_run(project_id, run_id, actor)
    directory = _run_report_directory(project_id, run_id)
    reports = []
    if directory.exists():
        reports = [
            {"name": item.name, "size": item.stat().st_size}
            for item in sorted(directory.iterdir())
            if item.is_file() and item.name in REPORT_FILES
        ]
    return {"run_id": run_id, "reports": reports}


@run_router.get("/{run_id}/reports/{filename}")
def download_performance_run_report(
    project_id: str,
    run_id: str,
    filename: str,
    actor=Depends(current_user),
):
    _require_run(project_id, run_id, actor)
    if Path(filename).name != filename or filename not in REPORT_FILES:
        from app.core.exceptions import api_error
        raise api_error(400, "PERFORMANCE_REPORT_INVALID", "不支持的报告文件。")
    directory = _run_report_directory(project_id, run_id)
    report = (directory / filename).resolve()
    if directory not in report.parents or not report.is_file():
        from app.core.exceptions import api_error
        raise api_error(404, "PERFORMANCE_REPORT_NOT_FOUND", "报告文件不存在。")
    return FileResponse(report, filename=filename)


def format_run_sse_event(event: str, payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event}\ndata: {encoded}\n\n"


@run_router.get("/{run_id}/stream")
async def stream_performance_run(project_id: str, run_id: str, actor=Depends(current_user)):
    _require_run(project_id, run_id, actor)

    async def events():
        last_run_signature = None
        last_stat_id = ""
        last_event_id = ""
        while True:
            with connect() as db:
                run = run_repo.get_run(db, run_id)
                if run is None:
                    return
                stats = run_repo.list_stats(db, run_id)
                failures = run_repo.list_failures(db, run_id)
                exceptions = run_repo.list_exceptions(db, run_id)
                run_events = run_repo.list_events(db, run_id)
            run_signature = (run["status"], run["updated_at"], run["error_code"], run["error_message"])
            if run_signature != last_run_signature:
                last_run_signature = run_signature
                yield format_run_sse_event("run", _run_payload(run))
            if stats and stats[-1]["id"] != last_stat_id:
                last_stat_id = stats[-1]["id"]
                yield format_run_sse_event(
                    "stats",
                    {
                        "run": _run_payload(run),
                        "latest": _stat_payload(stats[-1]),
                        "failures": [dict(row) for row in failures],
                        "exceptions": [dict(row) for row in exceptions],
                    },
                )
            if run_events and run_events[-1]["id"] != last_event_id:
                last_event_id = run_events[-1]["id"]
                yield format_run_sse_event("log", dict(run_events[-1]))
            if run["status"] in TERMINAL_STATUSES:
                yield format_run_sse_event("done", {"status": run["status"]})
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _require_run(project_id: str, run_id: str, actor):
    _ensure_project_visible(project_id, actor)
    with connect() as db:
        run = run_repo.get_run(db, run_id)
        if not run or run["project_id"] != project_id:
            from app.core.exceptions import api_error
            raise api_error(404, "PERFORMANCE_RUN_NOT_FOUND", "性能测试运行不存在。")
        return run


def _run_report_directory(project_id: str, run_id: str) -> Path:
    return (settings.PROJECT_FILE_STORAGE_ROOT / project_id / "performance_testing" / "runs" / run_id).resolve()


def _history_samples(project_id: str, run_id: str) -> list[dict[str, object]]:
    path = _run_report_directory(project_id, run_id) / "result_stats_history.csv"
    if not path.is_file():
        return []
    try:
        return headless_worker.parse_locust_stats_history_samples(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, ValueError):
        return []


def _request_stats(project_id: str, run_id: str) -> list[dict[str, object]]:
    path = _run_report_directory(project_id, run_id) / "result_stats.csv"
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError):
        return []
    result = []
    for row in rows:
        if row.get("Type") == "Aggregated" or row.get("Name") == "Aggregated":
            continue
        request_count = int(float(row.get("Request Count") or 0))
        failure_count = int(float(row.get("Failure Count") or 0))
        result.append(
            {
                "name": row.get("Name", ""),
                "method": row.get("Type", ""),
                "request_count": request_count,
                "failure_count": failure_count,
                "failure_rate": failure_count / request_count if request_count else 0,
                "average_response_time_ms": float(row.get("Average Response Time") or 0),
                "median_response_time_ms": float(row.get("Median Response Time") or row.get("50%") or 0),
                "p50_response_time_ms": float(row.get("50%") or 0),
                "p95_response_time_ms": float(row.get("95%") or 0),
                "p99_response_time_ms": float(row.get("99%") or 0),
                "min_response_time_ms": float(row.get("Min Response Time") or 0),
                "max_response_time_ms": float(row.get("Max Response Time") or 0),
                "requests_per_second": float(row.get("Requests/s") or 0),
                "content_size": int(float(row.get("Average Content Size") or 0)),
            }
        )
    return result


def _run_payload(row) -> dict:
    runtime_config = api_automation_repo.loads_json(row["runtime_config_json"], {})
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "performance_test_id": row["performance_test_id"],
        "script_id": row["script_id"],
        "status": row["status"],
        "load_config": api_automation_repo.loads_json(row["load_config_json"], {}),
        "target_host": runtime_config.get("api_base_url", ""),
        "latest_summary": api_automation_repo.loads_json(row["latest_summary_json"], {}),
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "trace_id": row["trace_id"],
        "created_at": row["created_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
        "updated_at": row["updated_at"],
    }


def _stat_payload(row) -> dict:
    payload = dict(row)
    raw_stats = api_automation_repo.loads_json(payload.pop("stats_json", "{}"), {})
    return {**payload, **raw_stats}


@contextmanager
def _script_lookup(project_id: str, test_id: str, script_id: str, actor):
    from app.core.db import connect
    from app.core.exceptions import api_error

    with connect() as db:
        _ensure_project_visible_db(db, project_id, actor)
        test_row = db.execute(
            "SELECT * FROM performance_tests WHERE id = ? AND project_id = ?",
            (test_id, project_id),
        ).fetchone()
        if not test_row:
            raise api_error(404, "PERFORMANCE_TEST_NOT_FOUND", "性能测试不存在。")
        script_row = performance_script_repo.find_script(db, script_id)
        if (
            not script_row
            or script_row["project_id"] != project_id
            or script_row["performance_test_id"] != test_id
        ):
            raise api_error(404, "PERFORMANCE_SCRIPT_NOT_FOUND", "性能测试脚本不存在。")
        if script_row["validation_status"] != "confirmed":
            raise api_error(409, "PERFORMANCE_SCRIPT_NOT_CONFIRMED", "只有已确认脚本可以启动正式压测。")
        endpoint = api_automation_repo.find_endpoint(db, test_row["endpoint_id"])
        environment = api_automation_repo.find_api_environment(db, test_row["api_environment_id"])
        if not endpoint or endpoint["project_id"] != project_id:
            raise api_error(409, "PERFORMANCE_ENDPOINT_INVALID", "接口引用已失效。")
        if not environment or environment["project_id"] != project_id:
            raise api_error(409, "PERFORMANCE_ENVIRONMENT_INVALID", "接口环境引用已失效。")
        yield {
            "script_code": script_row["code"],
            "runtime_environment": _build_runtime_environment(environment),
            "load_config": api_automation_repo.loads_json(test_row["load_config_json"], {}),
        }


def _ensure_project_visible(project_id: str, actor) -> None:
    from app.core.db import connect
    from app.core.exceptions import api_error

    with connect() as db:
        _ensure_project_visible_db(db, project_id, actor)
        if not project_repo.find_by_id(db, project_id):  # noqa: F841 — silence unused
            raise api_error(404, "NOT_FOUND", "项目不存在。")


def _ensure_project_visible_db(db, project_id: str, actor) -> None:
    from app.core.exceptions import api_error

    project = project_repo.find_by_id(db, project_id)
    if not project:
        raise api_error(404, "NOT_FOUND", "项目不存在。")
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        return
    if project["name"] == actor["project_scope"]:
        return
    raise api_error(403, "PERMISSION_DENIED", "无权访问该项目。")


def _build_runtime_environment(row) -> dict:
    from app.core.environment_credentials import decrypt_api_environment_secret

    auth_config = api_automation_repo.loads_json(row["auth_config_json"], {})
    headers: dict[str, str] = {
        str(key): str(value)
        for key, value in api_automation_repo.loads_json(row["default_headers_json"], {}).items()
    }
    if row["auth_type"] == "static_bearer" and auth_config.get("token_encrypted"):
        token = decrypt_api_environment_secret(auth_config["token_encrypted"]) or ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
    if row["auth_type"] == "static_headers":
        for key, encrypted in auth_config.get("headers_encrypted", {}).items():
            headers[str(key)] = decrypt_api_environment_secret(str(encrypted)) or ""
    if row["auth_type"] == "cookie" and auth_config.get("cookie_name"):
        cookie_value = decrypt_api_environment_secret(auth_config.get("cookie_value_encrypted", "")) or ""
        if cookie_value:
            headers["Cookie"] = f"{auth_config['cookie_name']}={cookie_value}"
    if row["auth_type"] == "cybertron_agent":
        if auth_config.get("username"):
            headers["username"] = str(auth_config["username"])
        robot_key = decrypt_api_environment_secret(auth_config.get("cybertron_robot_key_encrypted", "")) or ""
        robot_token = decrypt_api_environment_secret(auth_config.get("cybertron_robot_token_encrypted", "")) or ""
        if robot_key:
            headers["cybertron-robot-key"] = robot_key
        if robot_token:
            headers["cybertron-robot-token"] = robot_token
    return {
        "api_base_url": row["api_base_url"],
        "headers": headers,
        "managed_header_names": sorted(service._environment_managed_header_names(row)),
        "variables": api_automation_repo.loads_json(row["variables_json"], {}),
        "verify_ssl": bool(row["verify_ssl"]),
    }
