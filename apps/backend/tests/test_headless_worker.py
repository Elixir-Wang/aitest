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
