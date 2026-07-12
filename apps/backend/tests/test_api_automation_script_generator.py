from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest
import requests

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import service
from app.services.api_automation import script_generator


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


def _seed_case() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-1",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/login",
            normalized_path="/login",
            summary="登录",
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
            case_id="apitc-1",
            project_id="project-1",
            endpoint_id="apiend-1",
            source_test_case_id=None,
            generation_run_id=None,
            title="登录成功",
            priority="P1",
            coverage="positive",
            source="manual",
            preconditions=[],
            request={"method": "POST", "path": "/login", "body": {"username": "demo"}},
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


def test_generator_incrementally_updates_one_project_suite_by_endpoint(tmp_path: Path) -> None:
    login_case = {
        "id": "case-login-1",
        "endpoint_id": "endpoint-login",
        "title": "登录成功",
        "request": {"method": "POST", "path": "/login", "body": {"username": "demo"}},
        "assertions": [{"type": "status_code", "expected": 200}],
    }
    profile_case = {
        "id": "case-profile-1",
        "endpoint_id": "endpoint-profile",
        "title": "查询资料成功",
        "request": {"method": "GET", "path": "/profiles/{id}"},
        "assertions": [{"type": "status_code", "expected": 200}],
    }

    first = script_generator.generate_pytest_suite(
        project_id="project-1", suite_id="first-run", cases=[login_case], output_root=tmp_path
    )
    login_artifact = first["artifacts"][0]
    original_login_content = login_artifact["test_file_path"].read_text(encoding="utf-8")

    second = script_generator.generate_pytest_suite(
        project_id="project-1", suite_id="second-run", cases=[profile_case], output_root=tmp_path
    )

    assert first["suite_path"] == second["suite_path"]
    assert login_artifact["test_file_path"].exists()
    assert login_artifact["test_file_path"].read_text(encoding="utf-8") == original_login_content
    assert second["artifacts"][0]["test_file_path"].exists()
    assert len(list((first["suite_path"] / "tests").glob("test_*.py"))) == 2


def test_generated_endpoint_module_parametrizes_cases_independently(tmp_path: Path) -> None:
    cases = [
        {
            "id": f"case-{index}",
            "endpoint_id": "endpoint-login",
            "title": title,
            "request": {"method": "POST", "path": "/login"},
            "assertions": [{"type": "status_code", "expected": 200}],
        }
        for index, title in enumerate(["登录成功", "登录失败"], start=1)
    ]

    generated = script_generator.generate_pytest_suite(
        project_id="project-1", suite_id="run", cases=cases, output_root=tmp_path
    )
    test_content = generated["artifacts"][0]["test_file_path"].read_text(encoding="utf-8")

    assert '@pytest.mark.parametrize("case_data", CASES' in test_content
    assert "for case_data in case_dataset" not in test_content


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
    exec(script_generator._client_py(), namespace)
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
    exec(script_generator._client_py(), namespace)

    namespace["ApiClient"]("https://api.example").request(
        {"method": "GET", "path": "/profiles/{profile_id}"},
        {"profile_id": {"value": "profile-123"}},
    )

    assert captured["url"] == "https://api.example/profiles/profile-123"


def test_generated_assertions_validate_download_response() -> None:
    namespace = {}
    exec(script_generator._assertions_py(), namespace)
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
