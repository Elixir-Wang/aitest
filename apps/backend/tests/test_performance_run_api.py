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


def test_run_payload_marks_sqlite_timestamps_as_utc() -> None:
    payload = performance_runs._run_payload(
        {
            "id": "perfrun-1",
            "project_id": "project-1",
            "performance_test_id": "perftest-1",
            "script_id": "perfscript-1",
            "status": "running",
            "load_config_json": "{}",
            "runtime_config_json": "{}",
            "latest_summary_json": "{}",
            "error_code": "",
            "error_message": "",
            "trace_id": "",
            "created_at": "2026-08-03 11:23:45",
            "started_at": "2026-08-03 11:23:50",
            "finished_at": None,
            "updated_at": "2026-08-03 11:24:50",
        }
    )

    assert payload["created_at"] == "2026-08-03T11:23:45Z"
    assert payload["started_at"] == "2026-08-03T11:23:50Z"
    assert payload["finished_at"] is None
    assert payload["updated_at"] == "2026-08-03T11:24:50Z"


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


def test_request_stats_returns_scenario_endpoints_and_sse_metrics_as_four_business_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_stats.csv").write_text(
        "Type,Name,Request Count,Failure Count,Average Response Time,Median Response Time,50%,95%,99%,Min Response Time,Max Response Time,Requests/s,Average Content Size\n"
        "POST,01 POST /segment-code,12,12,25,23,23,40,45,18,50,4.2,64\n"
        "POST,02 POST /chat/sse,2,0,34,32,32,40,45,20,50,1.0,0\n"
        "SCENARIO,SCENARIO 测试,12,12,27,25,25,42,48,20,52,4.2,0\n"
        ",Aggregated,24,24,26,24,24,41,47,18,52,8.4,32\n",
        encoding="utf-8",
    )
    plan = {
        "target_type": "scenario",
        "steps": [
            {
                "step_type": "api_request",
                "request": {"method": "POST", "name": "01 POST /segment-code", "transport": "http"},
            },
            {
                "step_type": "api_request",
                "request": {
                    "method": "POST",
                    "name": "02 POST /chat/sse",
                    "transport": "sse",
                    "sse": {
                        "metrics": [
                            {
                                "id": "first_output",
                                "name": "首次有效内容时间",
                                "match": {"source": "data_json", "path": "$.data.answer", "operator": "non_empty"},
                            },
                            {
                                "id": "llm_started",
                                "name": "LLM 开始时间",
                                "match": {
                                    "source": "data_json",
                                    "path": "$.data.event_type",
                                    "operator": "equals",
                                    "expected": "call_llm_start",
                                },
                            },
                        ]
                    },
                },
            },
        ],
    }
    (run_dir / "generated_locustfile.py").write_text(
        f"import json\nPLAN = json.loads({json.dumps(json.dumps(plan, ensure_ascii=False))})\n",
        encoding="utf-8",
    )
    (run_dir / "sse-measurements.jsonl").write_text(
        "\n".join(
            [
                '{"metrics":{"first_output":100,"llm_started":40},"derived_metrics":{"llm_start_to_first_content_ms":60},"missing_metric_ids":[],"failure_reason":""}',
                '{"metrics":{"first_output":200,"llm_started":100},"derived_metrics":{"llm_start_to_first_content_ms":100},"missing_metric_ids":[],"failure_reason":""}',
                '{"metrics":{"first_output":900,"llm_started":300},"derived_metrics":{"llm_start_to_first_content_ms":600},"missing_metric_ids":[],"failure_reason":""}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(performance_runs.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    rows = performance_runs._request_stats("project-1", "perfrun-1")

    assert [(row["method"], row["name"]) for row in rows] == [
        ("POST", "01 POST /segment-code"),
        ("POST", "02 POST /chat/sse"),
        ("SSE", "首次有效内容时间"),
        ("SSE", "LLM 开始时间"),
        ("SSE", "LLM 启动到首次有效内容"),
    ]
    assert rows[0]["request_count"] == 12
    assert rows[1]["request_count"] == 2
    assert rows[1]["timing_semantics"] == "connection"
    assert rows[2]["request_count"] == 2
    assert rows[4]["request_count"] == 2
    assert rows[4]["average_response_time_ms"] == 80
    assert all(row["method"] != "SCENARIO" for row in rows)
