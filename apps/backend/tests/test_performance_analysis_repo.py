from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings
from app.core.db import connect
from app.repositories import performance_analysis_repo
from app.seed.init_db import init_db


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db_core, "DB_PATH", tmp_path / "test.db")
    init_db()


def _seed_run() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "项目-1", "u-admin"),
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
        db.execute(
            """
            INSERT INTO performance_test_runs (
              id, project_id, performance_test_id, script_id, status, created_by
            ) VALUES (?, ?, ?, ?, 'stopped', ?)
            """,
            ("perfrun-1", "project-1", "perftest-1", "perfscript-1", "u-admin"),
        )


def test_analysis_repository_persists_and_serializes_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run()

    with connect() as db:
        performance_analysis_repo.create_analysis_session(
            db,
            analysis_id="perfanalysis-1",
            project_id="project-1",
            run_id="perfrun-1",
            analysis_version=1,
            created_by="u-admin",
        )
        performance_analysis_repo.update_analysis_session(
            db,
            "perfanalysis-1",
            status="waiting_approval",
            category="performance_config",
            summary="请求体为空",
            direct_cause="业务请求缺少必填字段",
            root_cause="性能测试保存了空请求体",
            confidence=0.96,
            evidence=[{"source": "performance_config", "level": "observed", "title": "请求体", "detail": "null"}],
            missing_evidence=["目标服务日志"],
            proposal={"changes": []},
            model_name="test-model",
        )
        row = performance_analysis_repo.find_analysis_session(db, "perfanalysis-1")
        result = performance_analysis_repo.serialize_analysis_session(row)

    assert result["status"] == "waiting_approval"
    assert result["category"] == "performance_config"
    assert result["confidence"] == 0.96
    assert result["evidence"][0]["level"] == "observed"
    assert result["missing_evidence"] == ["目标服务日志"]
    assert result["proposal"] == {"changes": []}


def test_analysis_repository_versions_sessions_and_finds_active_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_run()

    with connect() as db:
        assert performance_analysis_repo.next_analysis_version(db, "perfrun-1") == 1
        performance_analysis_repo.create_analysis_session(
            db,
            analysis_id="perfanalysis-1",
            project_id="project-1",
            run_id="perfrun-1",
            analysis_version=1,
            created_by="u-admin",
        )
        active = performance_analysis_repo.find_active_analysis_for_run(db, "perfrun-1")
        assert active["id"] == "perfanalysis-1"
        performance_analysis_repo.update_analysis_session(db, "perfanalysis-1", status="failed")
        assert performance_analysis_repo.find_active_analysis_for_run(db, "perfrun-1") is None
        assert performance_analysis_repo.next_analysis_version(db, "perfrun-1") == 2

        performance_analysis_repo.create_analysis_session(
            db,
            analysis_id="perfanalysis-2",
            project_id="project-1",
            run_id="perfrun-1",
            analysis_version=2,
            created_by="u-admin",
        )
        rows = performance_analysis_repo.list_analysis_sessions(db, "project-1", "perfrun-1")

    assert [row["id"] for row in rows] == ["perfanalysis-2", "perfanalysis-1"]
