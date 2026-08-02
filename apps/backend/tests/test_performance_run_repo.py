import json
from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.seed.init_db import init_db
from app.services.performance_testing import headless_worker
from app.services.performance_testing import run_repo
from app.services.performance_testing.locust_runtime import runtime_locustfile_source


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_run_dependencies() -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, description, status, created_by)
            VALUES (?, ?, '', 'active', 'u-admin')
            """,
            ("project-1", "项目-1"),
        )
        db.execute(
            """
            INSERT INTO performance_tests (
              id, project_id, name, target_type, endpoint_id, api_environment_id, created_by
            ) VALUES (?, ?, ?, 'endpoint', NULL, NULL, ?)
            """,
            ("perftest-1", "project-1", "性能测试-1", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO performance_test_scripts (
              id, performance_test_id, project_id, generation_source, code, validation_status
            ) VALUES (?, ?, ?, 'default_plan', 'code', 'valid')
            """,
            ("perfscript-1", "perftest-1", "project-1"),
        )


def test_runtime_locustfile_captures_redacted_response_evidence() -> None:
    source = runtime_locustfile_source()

    compile(source, "locustfile.py", "exec")
    assert '"response_excerpt": _response_excerpt(response)' in source
    assert '"response_headers": _trace_headers(response)' in source
    assert 'normalized.endswith("_key")' in source


def test_runtime_locustfile_uses_current_environment_headers() -> None:
    source = runtime_locustfile_source()

    plan_position = source.index('**dict(PLAN["request"].get("headers") or {})')
    environment_position = source.index('**dict(RUNTIME["environment"].get("headers") or {})')
    assert plan_position < environment_position


def test_runtime_locustfile_removes_trailing_slash_from_base_url() -> None:
    source = runtime_locustfile_source()

    assert 'PerformanceUser.host = str(RUNTIME["environment"]["api_base_url"]).rstrip("/")' in source


def test_run_repository_persists_status_stats_failures_and_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={"users": 10},
            runtime_config={"api_base_url": "https://example.test"},
            created_by="u-admin",
        )
        run_repo.update_run_status(db, "perfrun-1", "starting")
        run_repo.update_run_status(db, "perfrun-1", "running")
        run_repo.append_stats(
            db,
            run_id="perfrun-1",
            sample={"user_count": 10, "requests_per_second": 4.5, "failure_rate": 0.1},
        )
        run_repo.upsert_failure(
            db,
            run_id="perfrun-1",
            request_name="GET /items",
            method="GET",
            reason="500 Server Error",
            status_code=500,
        )
        run_repo.upsert_exception(
            db,
            run_id="perfrun-1",
            request_name="GET /items",
            exception_type="TimeoutError",
            message="request timed out",
        )
        run_repo.append_event(db, "perfrun-1", "stats_updated", "info", "统计已更新", {})

        run = run_repo.get_run(db, "perfrun-1")
        stats = run_repo.list_stats(db, "perfrun-1")
        failures = run_repo.list_failures(db, "perfrun-1")
        exceptions = run_repo.list_exceptions(db, "perfrun-1")
        events = run_repo.list_events(db, "perfrun-1")

    assert run["status"] == "running"
    assert stats[0]["requests_per_second"] == 4.5
    assert failures[0]["count"] == 1
    assert exceptions[0]["count"] == 1
    assert events[0]["event_type"] == "stats_updated"


def test_run_repository_rejects_illegal_status_transition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        with pytest.raises(ValueError, match="非法的性能测试运行状态迁移"):
            run_repo.update_run_status(db, "perfrun-1", "completed")


def test_prune_run_history_keeps_only_latest_ten_terminal_runs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        for index in range(11):
            run_id = f"perfrun-{index:02d}"
            run_repo.create_run(
                db,
                run_id=run_id,
                project_id="project-1",
                performance_test_id="perftest-1",
                script_id="perfscript-1",
                load_config={},
                runtime_config={},
                created_by="u-admin",
            )
            db.execute(
                "UPDATE performance_test_runs SET created_at = datetime('2026-07-01', '+' || ? || ' minutes'), finished_at = created_at WHERE id = ?",
                (index, run_id),
            )
            run_repo.update_run_status(db, run_id, "starting")
            run_repo.update_run_status(db, run_id, "running")
            run_repo.update_run_status(db, run_id, "completed")

        removed = run_repo.prune_run_history(db, "project-1", "perftest-1", limit=10)
        remaining = run_repo.list_runs(db, "project-1", "perftest-1")

    assert removed == ["perfrun-00"]
    assert [row["id"] for row in remaining] == [f"perfrun-{index:02d}" for index in range(10, 0, -1)]


def test_prune_run_history_counts_created_runs_toward_retention_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        for index in range(11):
            run_id = f"perfrun-{index:02d}"
            run_repo.create_run(
                db,
                run_id=run_id,
                project_id="project-1",
                performance_test_id="perftest-1",
                script_id="perfscript-1",
                load_config={},
                runtime_config={},
                created_by="u-admin",
            )
            db.execute(
                "UPDATE performance_test_runs SET created_at = datetime('2026-07-01', '+' || ? || ' minutes') WHERE id = ?",
                (index, run_id),
            )

        removed = run_repo.prune_run_history(db, "project-1", "perftest-1", limit=10)
        remaining = run_repo.list_runs(db, "project-1", "perftest-1")

    assert removed == ["perfrun-00"]
    assert [row["id"] for row in remaining] == [f"perfrun-{index:02d}" for index in range(10, 0, -1)]


def test_delete_run_removes_only_selected_history_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()

    with connect() as db:
        for run_id in ("perfrun-1", "perfrun-2"):
            run_repo.create_run(
                db,
                run_id=run_id,
                project_id="project-1",
                performance_test_id="perftest-1",
                script_id="perfscript-1",
                load_config={},
                runtime_config={},
                created_by="u-admin",
            )
        run_repo.append_stats(db, run_id="perfrun-1", sample={"request_count": 10})
        run_repo.append_event(db, "perfrun-1", "run_finished", "info", "done", {})

        run_repo.delete_run(db, "perfrun-1")

        assert run_repo.get_run(db, "perfrun-1") is None
        assert run_repo.get_run(db, "perfrun-2") is not None
        assert run_repo.list_stats(db, "perfrun-1") == []
        assert run_repo.list_events(db, "perfrun-1") == []


def test_collect_locust_results_imports_csv_counts_without_duplicate_event_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_failures.csv").write_text(
        "Method,Name,Error,Occurrences,First Seen,Last Seen\n"
        "POST,POST /items,404 Not Found,3,2026-07-23T00:00:00Z,2026-07-23T00:01:00Z\n",
        encoding="utf-8",
    )
    (run_dir / "locust-events.jsonl").write_text(
        '{"kind":"failure","request_type":"POST","name":"POST /items",'
        '"reason":"404 Not Found","status_code":404,'
        '"response_excerpt":"{\\"code\\":\\"400001\\",\\"message\\":\\"invalid key\\"}"}\n',
        encoding="utf-8",
    )

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        headless_worker._collect_locust_results(db, "perfrun-1", run_dir)
        failures = run_repo.list_failures(db, "perfrun-1")

    assert len(failures) == 1
    assert failures[0]["request_name"] == "POST /items"
    assert failures[0]["reason"] == "404 Not Found"
    assert failures[0]["count"] == 3
    assert failures[0]["sample_status_code"] == 404
    assert json.loads(failures[0]["sample_response_excerpt"])["code"] == "400001"


def test_collect_locust_results_replaces_stale_failures_and_normalizes_catch_response_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_failures.csv").write_text(
        "Method,Name,Error,Occurrences,First Seen,Last Seen\n"
        "POST,POST /items,CatchResponseError('unexpected status code: 404'),120,2026-07-23T00:00:00Z,2026-07-23T00:01:00Z\n",
        encoding="utf-8",
    )
    (run_dir / "locust-events.jsonl").write_text(
        '{"kind":"failure","request_type":"POST","name":"POST /items",'
        '"reason":"unexpected status code: 404","status_code":404}\n',
        encoding="utf-8",
    )

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        run_repo.upsert_failure(
            db,
            run_id="perfrun-1",
            request_name="POST /items",
            method="POST",
            reason="unexpected status code: 404",
            count=120,
            status_code=404,
        )
        headless_worker._collect_locust_results(db, "perfrun-1", run_dir)
        failures = run_repo.list_failures(db, "perfrun-1")

    assert len(failures) == 1
    assert failures[0]["reason"] == "unexpected status code: 404"
    assert failures[0]["count"] == 120
    assert failures[0]["sample_status_code"] == 404


def test_collect_locust_results_uses_configured_user_count_for_final_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_stats.csv").write_text(
        "Type,Name,Request Count,Failure Count,Average Response Time,Requests/s,50%,95%,99%\n"
        "Aggregated,,120,120,31.15,4.29,20,40,50\n",
        encoding="utf-8",
    )

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={"users": 10},
            runtime_config={},
            created_by="u-admin",
        )
        headless_worker._collect_locust_results(db, "perfrun-1", run_dir)
        stats = run_repo.list_stats(db, "perfrun-1")

    assert stats[0]["user_count"] == 10


def test_collect_locust_results_imports_exception_csv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run_dependencies()
    run_dir = tmp_path / "project-1" / "performance_testing" / "runs" / "perfrun-1"
    run_dir.mkdir(parents=True)
    (run_dir / "result_exceptions.csv").write_text(
        "Count,Message,Traceback,Nodes\n"
        "2,TimeoutError: timed out,traceback text,node-1\n",
        encoding="utf-8",
    )

    with connect() as db:
        run_repo.create_run(
            db,
            run_id="perfrun-1",
            project_id="project-1",
            performance_test_id="perftest-1",
            script_id="perfscript-1",
            load_config={},
            runtime_config={},
            created_by="u-admin",
        )
        headless_worker._collect_locust_results(db, "perfrun-1", run_dir)
        exceptions = run_repo.list_exceptions(db, "perfrun-1")

    assert len(exceptions) == 1
    assert exceptions[0]["message"] == "TimeoutError: timed out"
    assert exceptions[0]["count"] == 2
