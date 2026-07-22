from pathlib import Path

import pytest

from app.core import db as core_db
from app.core import storage
from app.repositories import test_point_repo
from app.seed.init_db import init_db


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()


def _seed_requirement_version() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-1", "测试项目", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'version-1', 'finalized', ?)
            """,
            ("doc-1", "project-1", "最终需求", "u-admin"),
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, created_by)
            VALUES (?, ?, 1, ?, '', 'requirement_analysis_finalize', '确认最终需求', ?)
            """,
            ("version-1", "doc-1", "# 最终需求", "u-admin"),
        )
        test_point_repo.create_run(
            db,
            run_id="run-1",
            project_id="project-1",
            document_id="doc-1",
            version_id="version-1",
            task_id="test_point_generation:run-1",
            input_json="{}",
            created_by="u-admin",
        )


def _obligation() -> dict:
    return {
        "obligation_key": "REQ-001",
        "source_section": "改造方案",
        "statement": "超过10000字符时完整文本存入数据库",
        "obligation_type": "business_rule",
        "modules": ["输出节点"],
        "thresholds": ["10000"],
        "explicit": True,
        "test_required": True,
    }


def test_replace_obligations_and_links_round_trip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_requirement_version()

    with core_db.connect() as db:
        test_point_repo.replace_obligations(
            db,
            project_id="project-1",
            document_id="doc-1",
            version_id="version-1",
            obligations=[_obligation()],
        )
        db.execute(
            """
            INSERT INTO test_points (
              id, project_id, document_id, requirement_version_id, generation_run_id,
              point_key, title, category
            ) VALUES ('point-1', 'project-1', 'doc-1', 'version-1', 'run-1', 'point-1', '测试点', '功能')
            """
        )
        test_point_repo.replace_point_obligation_links(
            db,
            version_id="version-1",
            links={"point-1": ["REQ-001"]},
        )

        obligations = test_point_repo.list_obligations(db, "doc-1", "version-1")
        links = test_point_repo.list_point_obligation_links(db, "version-1")

    assert obligations[0]["obligation_key"] == "REQ-001"
    assert obligations[0]["modules"] == ["输出节点"]
    assert links == {"point-1": ["REQ-001"]}


def test_requeue_preserves_previous_coverage_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _use_temp_db(monkeypatch, tmp_path)
    _seed_requirement_version()

    with core_db.connect() as db:
        test_point_repo.replace_obligations(
            db,
            project_id="project-1",
            document_id="doc-1",
            version_id="version-1",
            obligations=[_obligation()],
        )
        test_point_repo.requeue_run(db, "run-1")

        assert len(test_point_repo.list_obligations(db, "doc-1", "version-1")) == 1
        assert test_point_repo.list_point_obligation_links(db, "version-1") == {}
