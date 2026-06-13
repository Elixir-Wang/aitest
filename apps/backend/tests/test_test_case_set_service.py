from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import storage
from app.seed.init_db import init_db
from app.schemas.test_case import TestCaseSetCreateIn
from app.services import task_service, test_case_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
GUEST = {"id": "u-guest", "role": "guest", "nickname": "访客", "username": "guest", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()


def _seed_project_requirement_and_exploration() -> None:
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description, created_by) VALUES (?, ?, 'active', '', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_documents (id, project_id, name, document_type, current_version_id, status, created_by)
            VALUES (?, ?, ?, 'PRD', 'version-1', 'finalized', ?)
            """,
            ("doc-1", "project-1", "登录需求", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO source_document_versions
              (id, document_id, version_no, markdown_content, file_path, source_action, change_summary, created_by)
            VALUES (?, ?, 1, ?, ?, 'finalize_requirement_analysis', '确认最终需求', ?)
            """,
            ("version-1", "doc-1", "# 登录需求\n\n用户可以登录系统。", "project-1/requirements/doc-1/versions/v1.md", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO project_environments (id, project_id, name, site_url, login_strategy, created_by)
            VALUES (?, ?, ?, ?, 'skip_login', ?)
            """,
            ("env-1", "project-1", "测试环境", "https://example.test", ACTOR["id"]),
        )
        db.execute(
            """
            INSERT INTO exploration_runs
              (id, project_id, environment_id, requirement_doc_id, title, status, scope, goal, created_by, updated_at)
            VALUES (?, ?, ?, ?, ?, 'completed', '登录', '采集登录页面事实', ?, CURRENT_TIMESTAMP)
            """,
            ("explore-1", "project-1", "env-1", "doc-1", "登录探索", ACTOR["id"]),
        )


def test_create_test_case_set_defaults_company_knowledge_and_related_exploration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_requirement_and_exploration()

    created = test_case_service.create_test_case_set(
        "project-1",
        TestCaseSetCreateIn(
            name="登录需求测试用例集",
            requirement_doc_id="doc-1",
            generation_scope_type="all",
        ),
        ACTOR,
    )

    assert created["name"] == "登录需求测试用例集"
    assert created["requirement_doc_id"] == "doc-1"
    assert created["requirement_doc_title"] == "登录需求"
    assert created["exploration_run_id"] == "explore-1"
    assert created["exploration_run_title"] == "登录探索"
    assert created["include_company_knowledge"] is True
    assert created["generation_scope_type"] == "all"
    assert created["generation_scope_text"] == ""
    assert created["status"] == "generating"
    assert created["case_count"] == 0
    assert created["generation_run"]["status"] == "queued"
    assert created["generation_run"]["input_snapshot"]["company_knowledge_role"] == "testing_guidance_only"
