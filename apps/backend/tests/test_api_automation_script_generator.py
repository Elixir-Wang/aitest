from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import requests
from fastapi import HTTPException

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.agents.api_automation.pytest_requests import renderer
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
    monkeypatch.setattr(
        service,
        "collect_script_suite",
        lambda **kwargs: {"ok": True, "exitcode": 0, "stdout": "", "stderr": ""},
        raising=False,
    )
    init_db()


def _seed_case(
    *,
    endpoint_id: str = "apiend-1",
    case_id: str = "apitc-1",
    method: str = "POST",
    path: str = "/login",
    title: str = "登录成功",
) -> None:
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id=endpoint_id,
            project_id="project-1",
            document_id=None,
            method=method,
            path=path,
            normalized_path=path,
            summary=title,
            description="",
            tags=[],
            parameters=[],
            request_body={},
            responses={"200": {"description": "success"}},
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )
        api_automation_repo.create_api_test_case(
            db,
            case_id=case_id,
            project_id="project-1",
            endpoint_id=endpoint_id,
            source_test_case_id=None,
            generation_run_id=None,
            title=title,
            priority="P1",
            coverage="positive",
            source="manual",
            preconditions=[],
            request={"method": method, "path": path, "body": {"username": "demo"}},
            test_data={},
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
    _seed_case()

    result = service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)

    script = result["scripts"][0]
    suite_path = Path(storage.resolve_stored_path(script["suite_path"]))
    test_file = Path(storage.resolve_stored_path(script["test_file_path"]))
    data_file = Path(storage.resolve_stored_path(script["data_file_path"]))

    assert (suite_path / "pytest.ini").exists()
    assert (suite_path / "pyproject.toml").exists()
    assert (suite_path / "support" / "client.py").exists()
    assert test_file.exists()
    assert data_file.exists()
    assert test_file.name == "test_api.py"
    assert data_file.name == "cases.json"
    assert test_file.parent == data_file.parent
    assert test_file.parent.parent.name == "endpoints"
    assert script["name"] == "post_login_apiend_1"
    assert "API_BASE_URL" in (suite_path / "support" / "client.py").read_text(encoding="utf-8")
    test_content = test_file.read_text(encoding="utf-8")
    assert "https://api.example" not in test_content
    assert "plain-token" not in test_content

    repeated = service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)
    listed = service.list_project_scripts("project-1", ACTOR)
    files = service.get_api_script_files("project-1", script["id"], ACTOR)

    assert repeated["summary"] == {"created": 0, "updated": 0, "unchanged": 1}
    assert len(listed) == 1
    assert listed[0]["endpoint_id"] == "apiend-1"
    assert listed[0]["case_count"] == 1
    assert {item["kind"] for item in files["files"]} == {"test", "data"}


def test_delete_script_removes_record_and_generated_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_case()

    result = service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)
    script = result["scripts"][0]
    suite_path = Path(storage.resolve_stored_path(script["suite_path"]))
    test_file = Path(storage.resolve_stored_path(script["test_file_path"]))
    data_file = Path(storage.resolve_stored_path(script["data_file_path"]))
    endpoint_dir = test_file.parent
    unrelated_endpoint_dir = suite_path / "endpoints" / "get_users_apiend_2"
    unrelated_endpoint_dir.mkdir(parents=True)
    (unrelated_endpoint_dir / "test_api.py").write_text("def test_other(): pass\n", encoding="utf-8")

    service.delete_api_script("project-1", script["id"], ACTOR)

    assert service.list_project_scripts("project-1", ACTOR) == []
    assert not test_file.exists()
    assert not data_file.exists()
    assert not endpoint_dir.exists()
    assert unrelated_endpoint_dir.exists()
    assert suite_path.exists()
    assert (suite_path / "support" / "client.py").exists()


def test_generation_collection_failure_rolls_back_selected_endpoint_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_case()
    _seed_case(
        endpoint_id="apiend-2",
        case_id="apitc-2",
        method="GET",
        path="/users",
        title="用户列表",
    )
    existing = service.generate_project_scripts("project-1", ["apiend-2"], ACTOR)["scripts"][0]
    existing_test_file = Path(storage.resolve_stored_path(existing["test_file_path"]))
    existing_data_file = Path(storage.resolve_stored_path(existing["data_file_path"]))
    monkeypatch.setattr(
        service,
        "collect_script_suite",
        lambda **kwargs: {
            "ok": False,
            "exitcode": 4,
            "stdout": "",
            "stderr": "ModuleNotFoundError: support",
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)

    assert exc_info.value.detail["code"] == "API_SCRIPT_COLLECTION_FAILED"
    assert "ModuleNotFoundError: support" in exc_info.value.detail["message"]
    assert [script["endpoint_id"] for script in service.list_project_scripts("project-1", ACTOR)] == ["apiend-2"]
    failed_endpoint_dir = (
        storage.PROJECT_FILE_STORAGE_ROOT
        / "project-1"
        / "api_automation"
        / "pytest_requests"
        / "endpoints"
        / "post_login_apiend_1"
    )
    assert not failed_endpoint_dir.exists()
    assert existing_test_file.exists()
    assert existing_data_file.exists()


def test_generation_collection_failure_restores_existing_endpoint_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_case()
    existing = service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)["scripts"][0]
    test_file = Path(storage.resolve_stored_path(existing["test_file_path"]))
    data_file = Path(storage.resolve_stored_path(existing["data_file_path"]))
    test_file.write_text("old test content\n", encoding="utf-8")
    data_file.write_text('{"cases": ["old data"]}\n', encoding="utf-8")
    monkeypatch.setattr(
        service,
        "collect_script_suite",
        lambda **kwargs: {"ok": False, "exitcode": 4, "stdout": "", "stderr": "collection failed"},
    )

    with pytest.raises(HTTPException):
        service.generate_project_scripts("project-1", ["apiend-1"], ACTOR, force=True)

    scripts = service.list_project_scripts("project-1", ACTOR)
    assert [script["id"] for script in scripts] == [existing["id"]]
    assert test_file.read_text(encoding="utf-8") == "old test content\n"
    assert data_file.read_text(encoding="utf-8") == '{"cases": ["old data"]}\n'


def test_generation_collection_exception_rolls_back_new_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_case()

    def raise_collection_error(**kwargs):
        raise RuntimeError("uv is unavailable")

    monkeypatch.setattr(service, "collect_script_suite", raise_collection_error)

    with pytest.raises(HTTPException) as exc_info:
        service.generate_project_scripts("project-1", ["apiend-1"], ACTOR)

    assert exc_info.value.detail["code"] == "API_SCRIPT_COLLECTION_FAILED"
    assert service.list_project_scripts("project-1", ACTOR) == []
    endpoint_dir = (
        storage.PROJECT_FILE_STORAGE_ROOT
        / "project-1"
        / "api_automation"
        / "pytest_requests"
        / "endpoints"
        / "post_login_apiend_1"
    )
    assert not endpoint_dir.exists()


def test_generated_client_sends_multipart_upload_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    upload_file = tmp_path / "sample.txt"
    upload_file.write_text("upload-content", encoding="utf-8")
    monkeypatch.setenv("API_UPLOAD_FILE_PATH", str(upload_file))

    support_module = ModuleType("support")
    auth_module = ModuleType("support.auth")
    auth_module.build_auth_headers = lambda: {}
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.auth", auth_module)

    captured = {}

    class FakeSession:
        def __init__(self):
            self.headers = {}

        def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            captured["file_content"] = kwargs["files"][0][1][1].read()
            captured["file_handle"] = kwargs["files"][0][1][1]
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(requests, "Session", FakeSession)
    namespace = {}
    exec(renderer._client_py(), namespace)
    client = namespace["ApiClient"]("https://api.example")

    client.request(
        {
            "method": "POST",
            "path": "/files",
            "body": {"description": "sample"},
            "files": {
                "file": {
                    "path": "${API_UPLOAD_FILE_PATH}",
                    "filename": "sample.txt",
                    "content_type": "text/plain",
                }
            },
        }
    )

    assert captured["method"] == "POST"
    assert captured["data"] == {"description": "sample"}
    assert captured["json"] is None
    assert captured["files"][0][0] == "file"
    assert captured["files"][0][1][0] == "sample.txt"
    assert captured["file_content"] == b"upload-content"
    assert captured["file_handle"].closed is True


def test_generated_client_expands_path_parameters_from_case_test_data(monkeypatch: pytest.MonkeyPatch) -> None:
    support_module = ModuleType("support")
    auth_module = ModuleType("support.auth")
    auth_module.build_auth_headers = lambda: {}
    monkeypatch.setitem(sys.modules, "support", support_module)
    monkeypatch.setitem(sys.modules, "support.auth", auth_module)
    captured = {}

    class FakeSession:
        def __init__(self):
            self.headers = {}

        def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, **kwargs)
            return SimpleNamespace(status_code=200)

    monkeypatch.setattr(requests, "Session", FakeSession)
    namespace = {}
    exec(renderer._client_py(), namespace)

    namespace["ApiClient"]("https://api.example").request(
        {"method": "GET", "path": "/profiles/{profile_id}"},
        {"profile_id": {"value": "profile-123"}},
    )

    assert captured["url"] == "https://api.example/profiles/profile-123"


def test_generated_assertions_validate_download_response() -> None:
    namespace = {}
    exec(renderer._assertions_py(), namespace)
    response = SimpleNamespace(
        status_code=200,
        headers={
            "Content-Type": "application/octet-stream; charset=binary",
            "Content-Disposition": 'attachment; filename="sample.bin"',
        },
        content=b"download-content",
    )

    namespace["assert_response_assertions"](
        response,
        [
            {"type": "status_code", "expected": 200},
            {"type": "content_type", "expected": "application/octet-stream"},
            {"type": "header_exists", "path": "Content-Disposition"},
            {"type": "body_not_empty", "expected": True},
            {
                "type": "body_sha256",
                "expected": "9534888cc67113243c47c085e1389a8e429e0238e6ed6b15eab9342573e53d28",
            },
        ],
    )
