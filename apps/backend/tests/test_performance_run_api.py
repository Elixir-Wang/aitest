import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import BackgroundTasks
from fastapi import HTTPException

from app.api.v1 import performance_runs
from app.api.v1.performance_runs import format_run_sse_event


def test_format_run_sse_event_emits_json_payload() -> None:
    assert format_run_sse_event("stats", {"request_count": 10}) == (
        "event: stats\n"
        "data: " + json.dumps({"request_count": 10}, ensure_ascii=False, separators=(",", ":")) + "\n\n"
    )


def test_create_performance_analysis_schedules_background_execution(monkeypatch) -> None:
    created = {"id": "perfanalysis-1", "status": "collecting"}
    calls = []
    monkeypatch.setattr(performance_runs.analysis_service, "create_analysis", lambda project_id, run_id, actor: created)
    monkeypatch.setattr(performance_runs.analysis_service, "execute_analysis", lambda analysis_id: calls.append(analysis_id))
    background_tasks = BackgroundTasks()

    result = performance_runs.create_performance_analysis(
        "project-1",
        "perfrun-1",
        background_tasks,
        {"id": "u-admin", "role": "admin", "project_scope": "全部项目"},
    )

    assert result == created
    assert len(background_tasks.tasks) == 1
    background_tasks.tasks[0].func(*background_tasks.tasks[0].args, **background_tasks.tasks[0].kwargs)
    assert calls == ["perfanalysis-1"]


def test_performance_analysis_routes_delegate_to_service(monkeypatch) -> None:
    actor = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}
    monkeypatch.setattr(performance_runs.analysis_service, "get_analysis", lambda project_id, analysis_id, current: {"id": analysis_id})
    monkeypatch.setattr(performance_runs.analysis_service, "list_run_analyses", lambda project_id, run_id, current: [{"run_id": run_id}])
    monkeypatch.setattr(performance_runs.analysis_service, "reject_analysis", lambda project_id, analysis_id, current: {"id": analysis_id, "status": "rejected"})

    assert performance_runs.get_performance_analysis("project-1", "perfanalysis-1", actor) == {"id": "perfanalysis-1"}
    assert performance_runs.list_performance_run_analyses("project-1", "perfrun-1", actor) == [{"run_id": "perfrun-1"}]
    assert performance_runs.reject_performance_analysis("project-1", "perfanalysis-1", actor) == {
        "id": "perfanalysis-1",
        "status": "rejected",
    }


def test_delete_performance_run_rejects_active_history(monkeypatch) -> None:
    monkeypatch.setattr(
        performance_runs,
        "_require_run",
        lambda project_id, run_id, actor: {"id": run_id, "status": "running"},
    )

    with pytest.raises(HTTPException) as exc_info:
        performance_runs.delete_performance_run(
            "project-1",
            "perfrun-1",
            {"id": "u-admin", "role": "admin", "project_scope": "全部项目"},
        )

    assert exc_info.value.detail["code"] == "PERFORMANCE_RUN_ACTIVE"


@pytest.mark.parametrize("status", ["created", "completed"])
def test_delete_performance_run_removes_deletable_record_and_directory(monkeypatch, tmp_path: Path, status: str) -> None:
    calls = []

    @contextmanager
    def fake_connect():
        yield object()

    monkeypatch.setattr(
        performance_runs,
        "_require_run",
        lambda project_id, run_id, actor: {"id": run_id, "status": status},
    )
    monkeypatch.setattr(performance_runs, "connect", fake_connect)
    monkeypatch.setattr(performance_runs.run_repo, "delete_run", lambda db, run_id: calls.append(("db", run_id)))
    monkeypatch.setattr(
        performance_runs.shutil,
        "rmtree",
        lambda path, ignore_errors: calls.append(("files", path, ignore_errors)),
    )
    monkeypatch.setattr(performance_runs.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    performance_runs.delete_performance_run(
        "project-1",
        "perfrun-1",
        {"id": "u-admin", "role": "admin", "project_scope": "全部项目"},
    )

    assert calls == [
        ("db", "perfrun-1"),
        ("files", tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1", True),
    ]


def test_request_stats_ignores_locust_245_aggregate_row_with_zero_requests(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_stats.csv").write_text(
        "Type,Name,Request Count,Failure Count,Average Response Time,Median Response Time,50%,95%,99%,Min Response Time,Max Response Time,Requests/s,Average Content Size\n"
        ",Aggregated,0,0,0,0,0,0,0,0,0,0,0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(performance_runs.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    assert performance_runs._request_stats("project-1", "perfrun-1") == []
