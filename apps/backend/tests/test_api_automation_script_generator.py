from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    project_root = data_dir / "projects"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", project_root)
    monkeypatch.setattr(db_core, "DATA_DIR", data_dir)
    monkeypatch.setattr(db_core, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", project_root)
    init_db()


def _seed_ready_case(status: str = "ready") -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        api_automation_repo.create_api_test_case(
            db,
            case_id="apitc-1",
            project_id="project-1",
            endpoint_id=None,
            source_test_case_id=None,
            generation_run_id=None,
            title="登录成功",
            priority="P1",
            source="manual",
            status=status,
            tags=["login"],
            request={"method": "POST", "path": "/login", "body": {"username": "demo"}},
            expected={"status_code": 200},
            assertions=[{"type": "status_code", "expected": 200}],
            variables={},
            data_origin={},
            data_file_path="",
            notes="",
            created_by=ACTOR["id"],
        )


def test_generate_scripts_creates_pytest_project_without_hardcoded_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_ready_case()

    result = service.generate_scripts_from_api_test_cases("project-1", ["apitc-1"], ACTOR)

    script = result["scripts"][0]
    suite_path = Path(storage.resolve_stored_path(script["suite_path"]))
    test_file = Path(storage.resolve_stored_path(script["test_file_path"]))
    data_file = Path(storage.resolve_stored_path(script["data_file_path"]))

    assert (suite_path / "pytest.ini").exists()
    assert (suite_path / "pyproject.toml").exists()
    assert (suite_path / "support" / "client.py").exists()
    assert test_file.exists()
    assert data_file.exists()
    assert "API_BASE_URL" in (suite_path / "support" / "client.py").read_text(encoding="utf-8")
    test_content = test_file.read_text(encoding="utf-8")
    assert "https://api.example" not in test_content
    assert "plain-token" not in test_content


def test_generate_scripts_rejects_needs_input_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_ready_case(status="needs_input")

    with pytest.raises(HTTPException) as exc_info:
        service.generate_scripts_from_api_test_cases("project-1", ["apitc-1"], ACTOR)

    assert exc_info.value.status_code == 400
