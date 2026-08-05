import asyncio
import ast
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
    "sse-measurements.jsonl",
    "sse-measurements.meta.json",
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
    request_stats, sse_metrics = _request_stats_payload(project_id, run_id)
    with connect() as db:
        run = run_repo.get_run(db, run_id)
        return {
            "run": _run_payload(run),
            "stats": [_stat_payload(row) for row in run_repo.list_stats(db, run_id)],
            "request_stats": request_stats,
            "failures": [dict(row) for row in run_repo.list_failures(db, run_id)],
            "exceptions": [dict(row) for row in run_repo.list_exceptions(db, run_id)],
            "events": [dict(row) for row in run_repo.list_events(db, run_id)],
            "sse_metrics": sse_metrics,
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
        last_stat_signature = ""
        last_event_id = ""
        request_stats_mtime_ns = -1
        request_stats_cache: list[dict[str, object]] = []
        while True:
            with connect() as db:
                run = run_repo.get_run(db, run_id)
                if run is None:
                    return
                test = db.execute(
                    "SELECT target_type FROM performance_tests WHERE id = ?",
                    (run["performance_test_id"],),
                ).fetchone()
                latest_stat_row = run_repo.get_latest_stat(db, run_id)
                failures = run_repo.list_failures(db, run_id)
                exceptions = run_repo.list_exceptions(db, run_id)
                run_events = run_repo.list_events(db, run_id)
            run_signature = (run["status"], run["updated_at"], run["error_code"], run["error_message"])
            if run_signature != last_run_signature:
                last_run_signature = run_signature
                yield format_run_sse_event("run", _run_payload(run))
            load_config = json.loads(run["load_config_json"] or "{}")
            latest = headless_worker.read_realtime_sample(
                _run_report_directory(project_id, run_id),
                configured_users=int(load_config.get("users") or 0),
                request_type="SCENARIO" if test and test["target_type"] == "scenario" else None,
            )
            if latest is None and latest_stat_row is not None:
                latest = _stat_payload(latest_stat_row)
            stat_signature = json.dumps(latest, ensure_ascii=False, sort_keys=True) if latest else ""
            if latest and stat_signature != last_stat_signature:
                last_stat_signature = stat_signature
                request_stats_path = _run_report_directory(project_id, run_id) / "result_stats.csv"
                try:
                    current_request_stats_mtime_ns = request_stats_path.stat().st_mtime_ns
                except OSError:
                    current_request_stats_mtime_ns = -1
                if current_request_stats_mtime_ns != request_stats_mtime_ns:
                    request_stats_mtime_ns = current_request_stats_mtime_ns
                    request_stats_cache = _request_stats(project_id, run_id)
                yield format_run_sse_event(
                    "stats",
                    {
                        "run": _run_payload(run),
                        "latest": latest,
                        "request_stats": request_stats_cache,
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
        with connect() as db:
            run = run_repo.get_run(db, run_id)
            test = db.execute(
                "SELECT target_type FROM performance_tests WHERE id = ?",
                (run["performance_test_id"],),
            ).fetchone() if run else None
        return headless_worker.parse_locust_stats_history_samples(
            path.read_text(encoding="utf-8-sig"),
            request_type="SCENARIO" if test and test["target_type"] == "scenario" else None,
        )
    except (OSError, UnicodeDecodeError, ValueError):
        return []


def _request_stats(project_id: str, run_id: str) -> list[dict[str, object]]:
    return _request_stats_payload(project_id, run_id)[0]


def _request_stats_payload(project_id: str, run_id: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    run_dir = _run_report_directory(project_id, run_id)
    path = run_dir / "result_stats.csv"
    if not path.is_file():
        return [], headless_worker.summarize_sse_measurements(
            run_dir / "sse-measurements.jsonl", max_attempts=0
        )
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError):
        return [], headless_worker.summarize_sse_measurements(
            run_dir / "sse-measurements.jsonl", max_attempts=0
        )
    actual_rows: dict[tuple[str, str], dict[str, object]] = {}
    final_entries = {
        (str(entry.get("request_type") or ""), str(entry.get("name") or "")): entry
        for entry in headless_worker.read_locust_final_stats(run_dir).get("entries", [])
        if isinstance(entry, dict)
    }
    for row in rows:
        method = str(row.get("Type") or "")
        name = str(row.get("Name") or "")
        if method in {"Aggregated", "SCENARIO"} or name == "Aggregated":
            continue
        request_count = int(float(row.get("Request Count") or 0))
        failure_count = int(float(row.get("Failure Count") or 0))
        final_entry = final_entries.get((method, name))
        if final_entry:
            request_count = int(final_entry.get("request_count") or 0)
            failure_count = int(final_entry.get("failure_count") or 0)
        actual_rows[(method, name)] = {
            "name": name,
            "method": method,
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

    plan = _generated_performance_plan(run_dir)
    planned_requests = _planned_requests(plan)
    result = []
    completed_sse_requests = 0
    for request in planned_requests:
        key = (request["method"], request["name"])
        row = actual_rows.pop(
            key,
            _empty_request_stat(method=request["method"], name=request["name"]),
        )
        if request.get("transport") == "sse":
            row = {**row, "timing_semantics": "connection"}
            completed_sse_requests += int(row.get("request_count") or 0)
        result.append(row)
    result.extend(actual_rows.values())

    sse_summary = headless_worker.summarize_sse_measurements(
        run_dir / "sse-measurements.jsonl",
        max_attempts=completed_sse_requests,
    )
    summaries = {str(item.get("metric_id") or ""): item for item in sse_summary.get("metrics", [])}
    planned_sse_metrics = _planned_sse_metrics(plan)
    for metric in planned_sse_metrics:
        summary = summaries.get(metric["metric_id"], {})
        attempt_count = int(summary.get("attempt_count") or 0)
        missing_count = int(summary.get("missing_count") or 0)
        result.append(
            {
                "name": metric["name"],
                "method": "SSE",
                "request_count": attempt_count,
                "failure_count": missing_count,
                "failure_rate": missing_count / attempt_count if attempt_count else 0,
                "average_response_time_ms": summary.get("average_ms") or 0,
                "median_response_time_ms": summary.get("p50_ms") or 0,
                "p50_response_time_ms": summary.get("p50_ms") or 0,
                "p95_response_time_ms": summary.get("p95_ms") or 0,
                "p99_response_time_ms": summary.get("p99_ms") or 0,
                "min_response_time_ms": summary.get("min_ms") or 0,
                "max_response_time_ms": summary.get("max_ms") or 0,
                "requests_per_second": 0,
                "content_size": 0,
                "metric_id": metric["metric_id"],
                "timing_semantics": "request_to_event",
                "source_request_id": metric.get("source_request_id") or "",
                "source_request_name": metric.get("source_request_name") or "",
                "timing_formula": f"{metric['name']} - {metric.get('source_request_name') or '所属 SSE 接口'} 请求发起时间",
            }
        )
    return result, sse_summary


def _generated_performance_plan(run_dir: Path) -> dict[str, object]:
    path = run_dir / "generated_locustfile.py"
    if not path.is_file():
        return {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(isinstance(target, ast.Name) and target.id == "PLAN" for target in node.targets):
            continue
        if not isinstance(node.value, ast.Call) or not node.value.args:
            return {}
        try:
            payload = ast.literal_eval(node.value.args[0])
            plan = json.loads(payload)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {}
        return plan if isinstance(plan, dict) else {}
    return {}


def _planned_requests(plan: dict[str, object]) -> list[dict[str, str]]:
    requests = []
    candidates = plan.get("steps") if plan.get("target_type") == "scenario" else [plan]
    for candidate in candidates if isinstance(candidates, list) else []:
        request = candidate.get("request") if isinstance(candidate, dict) else None
        if not isinstance(request, dict):
            continue
        method = str(request.get("method") or "")
        name = str(request.get("name") or "")
        if method and name:
            requests.append(
                {
                    "method": method,
                    "name": name,
                    "transport": str(request.get("transport") or "http"),
                }
            )
    return requests


def _planned_sse_metrics(plan: dict[str, object]) -> list[dict[str, str]]:
    metrics = []
    candidates = plan.get("steps") if plan.get("target_type") == "scenario" else [plan]
    for candidate in candidates if isinstance(candidates, list) else []:
        request = candidate.get("request") if isinstance(candidate, dict) else None
        if not isinstance(request, dict) or request.get("transport") != "sse":
            continue
        config = request.get("sse")
        for metric in config.get("metrics", []) if isinstance(config, dict) else []:
            if not isinstance(metric, dict) or not metric.get("id"):
                continue
            timing = metric.get("timing") if isinstance(metric.get("timing"), dict) else {}
            metrics.append(
                {
                    "metric_id": str(metric["id"]),
                    "name": str(metric.get("name") or metric["id"]),
                    "category": str(metric.get("category") or "custom_event"),
                    "source_request_id": str(timing.get("source_request_id") or candidate.get("id") or ""),
                    "source_request_name": str(timing.get("source_request_name") or request.get("name") or ""),
                }
            )
    return metrics


def _empty_request_stat(*, method: str, name: str) -> dict[str, object]:
    return {
        "name": name,
        "method": method,
        "request_count": 0,
        "failure_count": 0,
        "failure_rate": 0,
        "average_response_time_ms": 0,
        "median_response_time_ms": 0,
        "p50_response_time_ms": 0,
        "p95_response_time_ms": 0,
        "p99_response_time_ms": 0,
        "min_response_time_ms": 0,
        "max_response_time_ms": 0,
        "requests_per_second": 0,
        "content_size": 0,
    }


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
        "created_at": _sqlite_utc_timestamp(row["created_at"]),
        "started_at": _sqlite_utc_timestamp(row["started_at"]),
        "finished_at": _sqlite_utc_timestamp(row["finished_at"]),
        "updated_at": _sqlite_utc_timestamp(row["updated_at"]),
    }


def _sqlite_utc_timestamp(value: str | None) -> str | None:
    if not value:
        return value
    if value.endswith("Z") or "+" in value[10:]:
        return value
    return f"{value.replace(' ', 'T', 1)}Z"


def _stat_payload(row) -> dict:
    payload = dict(row)
    raw_stats = api_automation_repo.loads_json(payload.pop("stats_json", "{}"), {})
    return {**payload, **raw_stats}


@contextmanager
def _script_lookup(project_id: str, test_id: str, script_id: str, actor):
    from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan
    from app.core.db import connect
    from app.core.exceptions import api_error
    from app.services.performance_testing.script_renderer import render_locust_script
    from app.services.performance_testing.validator import validate_locust_script

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
        validation_result = api_automation_repo.loads_json(script_row["validation_result_json"], {})
        if script_row["validation_status"] != "valid" or not validation_result.get("valid"):
            raise api_error(409, "PERFORMANCE_SCRIPT_INVALID", "脚本校验通过后才能启动正式压测。")
        try:
            plan = LocustScriptPlan.model_validate(
                api_automation_repo.loads_json(script_row["plan_json"], {})
            )
            script_code = render_locust_script(plan)
            current_validation = validate_locust_script(plan, script_code)
        except (TypeError, ValueError) as exc:
            raise api_error(409, "PERFORMANCE_SCRIPT_INVALID", "性能测试脚本计划无效，请重新生成脚本。") from exc
        if not current_validation.valid:
            raise api_error(409, "PERFORMANCE_SCRIPT_INVALID", "脚本按当前运行时重新校验失败，请重新生成脚本。")
        environment = api_automation_repo.find_api_environment(db, test_row["api_environment_id"])
        if not environment or environment["project_id"] != project_id:
            raise api_error(409, "PERFORMANCE_ENVIRONMENT_INVALID", "接口环境引用已失效。")
        yield {
            "script_code": script_code,
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
