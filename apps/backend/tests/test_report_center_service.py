import json

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services import report_center_service


ADMIN = {"id": "u-admin", "role": "admin", "project_scope": "全部项目"}
PROJECT_ACTOR = {"id": "u-tester", "role": "tester", "project_scope": "项目A"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _seed_report(
    db,
    *,
    project_id: str,
    project_name: str,
    suffix: str,
    verdict: str = "fail",
    generation_mode: str = "ai_primary",
) -> None:
    db.execute(
        "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', 'u-admin')",
        (project_id, project_name),
    )
    api_automation_repo.upsert_endpoint(
        db,
        endpoint_id=f"endpoint-{suffix}",
        project_id=project_id,
        document_id=None,
        method="GET",
        path="/health",
        normalized_path="/health",
        summary="健康检查",
        description="",
        tags=[],
        parameters=[],
        request_body={},
        responses={"200": {"description": "ok"}},
        auth={},
        source={},
        created_by="u-admin",
    )
    db.execute(
        """
        INSERT INTO performance_tests (id, project_id, name, target_type, endpoint_id, created_by)
        VALUES (?, ?, ?, 'endpoint', ?, 'u-admin')
        """,
        (f"test-{suffix}", project_id, f"压测-{suffix}", f"endpoint-{suffix}"),
    )
    db.execute(
        """
        INSERT INTO performance_test_scripts (
          id, performance_test_id, project_id, generation_source, code, validation_status
        ) VALUES (?, ?, ?, 'default_plan', 'pass', 'valid')
        """,
        (f"script-{suffix}", f"test-{suffix}", project_id),
    )
    db.execute(
        """
        INSERT INTO performance_test_runs (
          id, project_id, performance_test_id, script_id, status, created_by
        ) VALUES (?, ?, ?, ?, 'completed', 'u-admin')
        """,
        (f"run-{suffix}", project_id, f"test-{suffix}", f"script-{suffix}"),
    )
    db.execute(
        """
        INSERT INTO performance_analysis_sessions (
          id, project_id, run_id, status, analysis_status, analysis_stage,
          analysis_version, report_snapshot_json, metric_snapshot_json, generation_mode, created_by
        ) VALUES (?, ?, ?, 'waiting_approval', 'completed', 'completed', 1, ?, ?, ?, 'u-admin')
        """,
        (
            f"analysis-{suffix}",
            project_id,
            f"run-{suffix}",
            json.dumps({"verdict": verdict, "generation_mode": generation_mode}),
            json.dumps({"quality": {"status": "complete"}}),
            generation_mode,
        ),
    )


def _seed_api_batch_report(db) -> None:
    db.execute(
        "INSERT INTO projects (id, name, status, description, created_by) VALUES ('project-api', '接口项目', 'active', '', 'u-admin')"
    )
    db.execute(
        """
        INSERT INTO api_test_environments (
          id, project_id, name, api_base_url, auth_type, created_by
        ) VALUES ('apienv-report', 'project-api', '回归环境', 'https://api.example.test', 'none', 'u-admin')
        """
    )
    api_automation_repo.create_api_batch_run(
        db,
        batch_run_id="apibatch-report",
        project_id="project-api",
        api_environment_id="apienv-report",
        name="接口批量运行",
        created_by="u-admin",
    )
    api_automation_repo.update_api_batch_run(
        db,
        "apibatch-report",
        status="completed",
        result="failed",
        started=True,
        finished=True,
    )
    for position, (run_id, scenario_name, status) in enumerate(
        (("apirun-pass", "登录", "passed"), ("apirun-fail", "下单", "failed"))
    ):
        api_automation_repo.create_api_run(
            db,
            run_id=run_id,
            task_id=f"api_automation_run:{run_id}",
            project_id="project-api",
            api_environment_id="apienv-report",
            script_ids=[],
            target_type="scenario",
            target_ids=[f"apiscn-{position}"],
            execution_snapshot={"scenario": {"id": f"apiscn-{position}", "name": scenario_name, "step_count": 2}},
            command_summary="python -m pytest scenario.py --json-report",
            created_by="u-admin",
            status=status,
            batch_run_id="apibatch-report",
            batch_position=position,
        )


def test_report_center_lists_frozen_performance_reports(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_report(db, project_id="project-a", project_name="项目A", suffix="a")

    reports = report_center_service.list_reports("performance", "all", ADMIN)

    assert len(reports) == 1
    assert reports[0]["name"] == "压测-a - 性能智能分析报告"
    assert reports[0]["verdict"] == "fail"
    assert reports[0]["quality_status"] == "complete"
    assert reports[0]["generation_mode"] == "ai_primary"
    assert reports[0]["generation_status"] == "generated"
    assert reports[0]["href"] == "/projects/project-a/performance-tests/test-a/runs/run-a/analysis/analysis-a"


def test_report_center_marks_deterministic_fallback_as_degraded(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_report(
            db,
            project_id="project-a",
            project_name="项目A",
            suffix="a",
            verdict="pass",
            generation_mode="deterministic_fallback",
        )

    reports = report_center_service.list_reports("performance", "all", ADMIN)

    assert reports[0]["status"] == "completed"
    assert reports[0]["generation_mode"] == "deterministic_fallback"
    assert reports[0]["generation_status"] == "degraded"


def test_report_center_limits_rows_to_visible_projects(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_report(db, project_id="project-a", project_name="项目A", suffix="a")
        _seed_report(db, project_id="project-b", project_name="项目B", suffix="b", verdict="pass")

    reports = report_center_service.list_reports("performance", "all", PROJECT_ACTOR)

    assert [report["project_id"] for report in reports] == ["project-a"]


def test_report_center_rejects_invisible_project_filter(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_report(db, project_id="project-a", project_name="项目A", suffix="a")
        _seed_report(db, project_id="project-b", project_name="项目B", suffix="b")

    with pytest.raises(HTTPException) as exc_info:
        report_center_service.list_reports("performance", "project-b", PROJECT_ACTOR)

    assert getattr(exc_info.value, "status_code", None) == 404


def test_report_center_deletes_visible_report(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_report(db, project_id="project-a", project_name="项目A", suffix="a")

    report_center_service.delete_report("performance", "analysis-a", ADMIN)

    assert report_center_service.list_reports("performance", "all", ADMIN) == []


def test_report_center_rejects_deleting_invisible_report(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_report(db, project_id="project-b", project_name="项目B", suffix="b")

    with pytest.raises(HTTPException) as exc_info:
        report_center_service.delete_report("performance", "analysis-b", PROJECT_ACTOR)

    assert getattr(exc_info.value, "status_code", None) == 404


def test_report_center_lists_completed_api_batches_as_reports(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_api_batch_report(db)

    reports = report_center_service.list_reports("api", "all", ADMIN)

    assert len(reports) == 1
    assert reports[0]["id"] == "apibatch-report"
    assert reports[0]["report_type"] == "api"
    assert reports[0]["environment_name"] == "回归环境"
    assert reports[0]["scenario_count"] == 2
    assert reports[0]["passed_count"] == 1
    assert reports[0]["pass_rate"] == 0.5
    assert reports[0]["href"] == "/reports/api/apibatch-report"


def test_report_center_returns_api_batch_report_detail(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_api_batch_report(db)

    report = report_center_service.get_api_report("apibatch-report", ADMIN)

    assert report["result"] == "failed"
    assert report["counts"]["total"] == 2
    assert [run["scenario_name"] for run in report["runs"]] == ["登录", "下单"]


def test_deleting_api_report_hides_report_but_keeps_child_runs(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        _seed_api_batch_report(db)

    report_center_service.delete_report("api", "apibatch-report", ADMIN)

    assert report_center_service.list_reports("api", "all", ADMIN) == []
    with core_db.connect() as db:
        child_count = db.execute(
            "SELECT COUNT(*) FROM api_automation_runs WHERE batch_run_id = 'apibatch-report'"
        ).fetchone()[0]
    assert child_count == 2
