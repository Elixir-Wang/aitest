from pathlib import Path

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
