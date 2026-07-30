import json

import pytest
from fastapi import HTTPException

from app.core import db as core_db
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
    db.execute(
        """
        INSERT INTO performance_tests (id, project_id, name, created_by)
        VALUES (?, ?, ?, 'u-admin')
        """,
        (f"test-{suffix}", project_id, f"压测-{suffix}"),
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
