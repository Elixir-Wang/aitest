from pathlib import Path

import pytest

from app.core import settings
from app.services.performance_testing import headless_worker


def test_build_headless_command_uses_load_configuration(tmp_path: Path) -> None:
    command = headless_worker.build_headless_command(
        run_dir=tmp_path,
        users=20,
        spawn_rate=5,
        duration_seconds=120,
    )

    assert command[:4] == [headless_worker.sys.executable, "-m", "locust", "-f"]
    assert "--headless" in command
    assert "--users" in command
    assert command[command.index("--users") + 1] == "20"
    assert command[command.index("--spawn-rate") + 1] == "5"
    assert command[command.index("--run-time") + 1] == "120s"
    assert command[command.index("--stop-timeout") + 1] == "5"
    assert command[command.index("-f") + 1] == "locustfile.py"


def test_headless_worker_never_adds_a_locust_web_port(tmp_path: Path) -> None:
    command = headless_worker.build_headless_command(
        run_dir=tmp_path,
        users=1,
        spawn_rate=1,
        duration_seconds=1,
    )

    assert "--web-port" not in command
    assert "--web-host" not in command
    assert "--headless" in command


def test_headless_command_enables_full_history_for_realtime_sampling(tmp_path: Path) -> None:
    command = headless_worker.build_headless_command(
        run_dir=tmp_path, users=5, spawn_rate=2, duration_seconds=10,
    )

    assert "--csv-full-history" in command


def test_scenario_graceful_stop_timeout_covers_all_remaining_steps() -> None:
    script = """import json
PLAN = json.loads('{"target_type":"scenario","steps":[{"step_type":"api_request","request":{"transport":"http","timeout_seconds":30}},{"step_type":"wait","control_config":{"duration_ms":1500}},{"step_type":"api_request","request":{"transport":"sse","timeout_seconds":30,"sse":{"max_stream_seconds":60}}}]}')
"""

    assert headless_worker.graceful_stop_timeout_seconds(script) == 97


def test_endpoint_graceful_stop_timeout_uses_longer_sse_stream_limit() -> None:
    script = """import json
PLAN = json.loads('{"target_type":"endpoint","request":{"transport":"sse","timeout_seconds":30,"sse":{"max_stream_seconds":60}}}')
"""

    assert headless_worker.graceful_stop_timeout_seconds(script) == 65


def test_graceful_stop_timeout_accepts_native_python_plan() -> None:
    script = """
PLAN = {
    'target_type': 'endpoint',
    'request': {'transport': 'http', 'timeout_seconds': 12},
}
"""

    assert headless_worker.graceful_stop_timeout_seconds(script) == 17


def test_force_kill_only_after_grace_timeout() -> None:
    calls = []

    class Process:
        def wait(self, timeout):
            calls.append(("wait", timeout))
            raise headless_worker.subprocess.TimeoutExpired("locust", timeout)

        def kill(self):
            calls.append(("kill",))

    headless_worker._force_kill_after_grace(Process(), 12)

    assert calls == [("wait", 12), ("kill",)]


def test_stop_headless_run_uses_locust_grace_period_before_force_kill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    class Process:
        def terminate(self):
            calls.append(("terminate",))

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class Thread:
        def __init__(self, *, target, args, daemon):
            calls.append(("thread", target, args, daemon))

        def start(self):
            calls.append(("thread_start",))

    process = Process()
    headless_worker._PROCESSES["perfrun-1"] = process
    headless_worker._STOP_TIMEOUTS["perfrun-1"] = 65
    monkeypatch.setattr(headless_worker, "connect", FakeConnection)
    monkeypatch.setattr(headless_worker.run_repo, "get_run", lambda db, run_id: {"status": "running"})
    monkeypatch.setattr(
        headless_worker.run_repo,
        "update_run_status",
        lambda db, run_id, status: calls.append(("status", run_id, status)),
    )
    monkeypatch.setattr(headless_worker.threading, "Thread", Thread)
    try:
        assert headless_worker.stop_headless_run("perfrun-1") is True
    finally:
        headless_worker._PROCESSES.pop("perfrun-1", None)
        headless_worker._STOP_TIMEOUTS.pop("perfrun-1", None)
        headless_worker._STOP_REQUESTED.discard("perfrun-1")

    assert calls == [
        ("status", "perfrun-1", "stopping"),
        ("terminate",),
        (
            "thread",
            headless_worker._force_kill_after_grace,
            (process, 70),
            True,
        ),
        ("thread_start",),
    ]


def test_stop_headless_run_and_wait_waits_for_monitor_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    finished = headless_worker.threading.Event()
    headless_worker._MONITOR_FINISHED["perfrun-1"] = finished

    def stop_run(run_id: str) -> bool:
        assert run_id == "perfrun-1"
        finished.set()
        return True

    monkeypatch.setattr(headless_worker, "stop_headless_run", stop_run)
    try:
        assert headless_worker.stop_headless_run_and_wait("perfrun-1", timeout=0.1) is True
    finally:
        headless_worker._MONITOR_FINISHED.pop("perfrun-1", None)


def test_prune_run_history_removes_old_run_directories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-old"
    run_dir.mkdir(parents=True)
    (run_dir / "result_stats.csv").write_text("old", encoding="utf-8")
    monkeypatch.setattr(
        headless_worker.run_repo,
        "prune_run_history",
        lambda db, project_id, performance_test_id, limit=10: ["perfrun-old"],
    )

    headless_worker._prune_run_history(object(), "project-1", "perftest-1")

    assert not run_dir.exists()


def test_create_run_session_prunes_history_after_creating_ready_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(headless_worker, "connect", FakeConnection)
    monkeypatch.setattr(headless_worker.secrets, "token_hex", lambda _length: "new")
    monkeypatch.setattr(headless_worker.run_repo, "create_run", lambda db, **values: calls.append(("create", values["run_id"])))
    monkeypatch.setattr(headless_worker.run_repo, "append_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        headless_worker,
        "_prune_run_history",
        lambda db, project_id, performance_test_id: calls.append(("prune", project_id, performance_test_id)),
    )

    run_id = headless_worker.create_run_session(
        project_id="project-1",
        test_id="perftest-1",
        script_id="perfscript-1",
        script_code="from locust import HttpUser",
        runtime_payload={},
        load_config={},
        created_by="u-admin",
    )

    assert run_id == "perfrun-new"
    assert calls == [("create", "perfrun-new"), ("prune", "project-1", "perftest-1")]


def test_parse_locust_stats_history_returns_latest_aggregate_sample() -> None:
    sample = headless_worker.parse_locust_stats_history(
        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,Total Request Count,Total Failure Count,Total Average Response Time,50%,95%,99%\n"
        "100,3,Aggregated,,12.5,1.0,20,2,42.0,30,80,100\n"
    )

    assert sample == {
        "sampled_at": "100",
        "user_count": 3,
        "request_count": 20,
        "failure_count": 2,
        "requests_per_second": 12.5,
        "failures_per_second": 1.0,
        "failure_rate": 0.1,
        "average_response_time_ms": 42.0,
        "p50_response_time_ms": 30.0,
        "p95_response_time_ms": 80.0,
        "p99_response_time_ms": 100.0,
        "source": "locust_csv_history",
    }


def test_parse_locust_stats_history_ignores_non_aggregate_rows() -> None:
    content = (
        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,Total Request Count,Total Failure Count,Total Average Response Time,50%,95%,99%\n"
        "100,3,GET,/health,10,0,10,0,20,20,40,50\n"
    )

    assert headless_worker.parse_locust_stats_history(content) is None


def test_parse_locust_stats_history_supports_locust_245_aggregate_rows() -> None:
    sample = headless_worker.parse_locust_stats_history(
        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,50%,95%,99%,Total Request Count,Total Failure Count,Total Average Response Time\n"
        "1784782681,2,POST,POST /api/items,1.5,0.5,20,80,100,3,1,42.0\n"
        "1784782681,2,,Aggregated,1.5,0.5,20,80,100,3,1,42.0\n"
    )

    assert sample == {
        "sampled_at": "1784782681",
        "user_count": 2,
        "request_count": 3,
        "failure_count": 1,
        "requests_per_second": 1.5,
        "failures_per_second": 0.5,
        "failure_rate": 1 / 3,
        "average_response_time_ms": 42.0,
        "p50_response_time_ms": 20.0,
        "p95_response_time_ms": 80.0,
        "p99_response_time_ms": 100.0,
        "source": "locust_csv_history",
    }


def test_parse_locust_stats_history_treats_na_percentiles_as_zero() -> None:
    sample = headless_worker.parse_locust_stats_history(
        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,50%,95%,99%,Total Request Count,Total Failure Count,Total Average Response Time\n"
        "1784782680,0,,Aggregated,0,0,N/A,N/A,N/A,0,0,0\n"
    )

    assert sample is not None
    assert sample["p50_response_time_ms"] == 0
    assert sample["p95_response_time_ms"] == 0
    assert sample["p99_response_time_ms"] == 0


def test_parse_locust_stats_history_samples_returns_all_aggregate_rows() -> None:
    samples = headless_worker.parse_locust_stats_history_samples(
        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,50%,95%,99%,Total Request Count,Total Failure Count,Total Average Response Time\n"
        "100,0,,Aggregated,0,0,N/A,N/A,N/A,0,0,0\n"
        "101,2,POST,POST /api/items,1.5,0.5,20,80,100,3,1,42\n"
        "101,2,,Aggregated,1.5,0.5,20,80,100,3,1,42\n"
    )

    assert [sample["sampled_at"] for sample in samples] == ["100", "101"]
    assert samples[-1]["failures_per_second"] == 0.5


def test_parse_locust_stats_csv_returns_current_aggregate_row() -> None:
    sample = headless_worker.parse_locust_stats_csv(
        "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Requests/s,Failures/s,50%,95%,99%\n"
        "POST,/api/items,6,0,110,150,1.69,0,110,660,660\n"
        ",Aggregated,6,0,110,150,1.69,0,110,660,660\n",
        user_count=3,
    )

    assert sample == {
        "sampled_at": "",
        "user_count": 3,
        "request_count": 6,
        "failure_count": 0,
        "requests_per_second": 1.69,
        "failures_per_second": 0.0,
        "failure_rate": 0.0,
        "average_response_time_ms": 150.0,
        "p50_response_time_ms": 110.0,
        "p95_response_time_ms": 660.0,
        "p99_response_time_ms": 660.0,
        "source": "locust_csv_live",
    }


def test_parse_locust_stats_csv_can_select_scenario_transaction_row() -> None:
    sample = headless_worker.parse_locust_stats_csv(
        "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Requests/s,Failures/s,50%,95%,99%\n"
        "GET,01 GET /api/items,12,1,30,40,4,0.2,30,80,100\n"
        "SCENARIO,SCENARIO 查询条目场景,4,1,120,150,1.2,0.2,120,260,300\n"
        ",Aggregated,16,2,60,75,5.2,0.4,50,200,300\n",
        user_count=3,
        request_type="SCENARIO",
    )

    assert sample is not None
    assert sample["request_count"] == 4
    assert sample["failure_count"] == 1
    assert sample["requests_per_second"] == 1.2
    assert sample["average_response_time_ms"] == 150.0


def test_parse_locust_stats_csv_prefers_final_snapshot_counts() -> None:
    sample = headless_worker.parse_locust_stats_csv(
        "Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Requests/s,Failures/s,50%,95%,99%\n"
        "POST,01 POST /segment,84,0,80,90,1.29,0,80,110,230\n"
        "POST,02 POST /sse,83,0,29,31,1.28,0,29,44,52\n"
        "SCENARIO,SCENARIO 测试,83,0,4800,4949,1.28,0,4800,7400,8500\n"
        ",Aggregated,250,0,81,1682,3.88,0,82,6400,7600\n",
        user_count=10,
        request_type="SCENARIO",
        final_stats={
            "entries": [
                {"request_type": "POST", "name": "01 POST /segment", "request_count": 84, "failure_count": 0},
                {"request_type": "POST", "name": "02 POST /sse", "request_count": 84, "failure_count": 0},
                {"request_type": "SCENARIO", "name": "SCENARIO 测试", "request_count": 84, "failure_count": 0},
            ]
        },
    )

    assert sample is not None
    assert sample["request_count"] == 84


def test_read_realtime_sample_uses_current_stats_and_history_user_count(tmp_path: Path) -> None:
    (tmp_path / "result_stats.csv").write_text(
        "Type,Name,Request Count,Failure Count,Average Response Time,Requests/s,Failures/s,50%,95%,99%\n"
        ",Aggregated,6,1,150,1.69,0.2,110,660,700\n",
        encoding="utf-8",
    )
    (tmp_path / "result_stats_history.csv").write_text(
        "Timestamp,User Count,Type,Name,Requests/s,Failures/s,Total Request Count,Total Failure Count,Total Average Response Time,50%,95%,99%\n"
        "100,4,,Aggregated,0,0,0,0,0,0,0,0\n",
        encoding="utf-8",
    )

    sample = headless_worker.read_realtime_sample(tmp_path, configured_users=10)

    assert sample is not None
    assert sample["user_count"] == 4
    assert sample["request_count"] == 6
    assert sample["failure_count"] == 1
    assert sample["source"] == "locust_csv_live"
    assert sample["sampled_at"]
