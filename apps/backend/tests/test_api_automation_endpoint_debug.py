import io
from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.schemas.api_automation import ApiEndpointDebugIn, ApiEnvironmentIn, parse_api_endpoint_debug_form
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


def _seed_project_endpoint() -> None:
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
            method="PUT",
            path="/knowledge/{conversation_id}",
            normalized_path="/knowledge/{conversation_id}",
            summary="更新对话",
            description="",
            tags=["knowledge"],
            parameters=[],
            request_body={"content": {"application/json": {"schema": {"type": "object"}}}},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )


def test_debug_project_endpoint_sends_request_through_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    environment = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test/openapi/v2",
            auth_type="cybertron_agent",
            auth_config={
                "cybertron_robot_key": "robot-key",
                "cybertron_robot_token": "robot-token",
                "username": "robot-user",
            },
            default_headers={"X-Env": "env"},
        ),
        ACTOR,
    )
    captured = {}

    class FakeResponse:
        status_code = 201
        headers = {"Content-Type": "application/json"}
        text = '{"ok": true}'

        class elapsed:
            @staticmethod
            def total_seconds() -> float:
                return 0.012

        @staticmethod
        def json() -> dict:
            return {"ok": True}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(service.requests, "request", fake_request)

    result = service.debug_project_endpoint(
        "project-1",
        "apiend-1",
        ApiEndpointDebugIn(
            api_environment_id=environment["id"],
            path_params={"conversation_id": "conv-1"},
            query_params={"verbose": "1"},
            headers={"X-Request": "debug"},
            body={"question": "你好"},
        ),
        ACTOR,
    )

    assert captured["method"] == "PUT"
    assert captured["url"] == "https://api.example.test/openapi/v2/knowledge/conv-1"
    assert captured["params"] == {"verbose": "1"}
    assert captured["headers"]["X-Env"] == "env"
    assert captured["headers"]["X-Request"] == "debug"
    assert captured["headers"]["Content-Type"] == "application/json"
    assert captured["headers"]["cybertron-robot-key"] == "robot-key"
    assert captured["headers"]["cybertron-robot-token"] == "robot-token"
    assert captured["headers"]["username"] == "robot-user"
    assert "cookies" not in captured
    assert captured["json"] == {"question": "你好"}
    assert result["status_code"] == 201
    assert result["body_json"] == {"ok": True}
    assert result["request"]["headers"]["cybertron-robot-key"] == "******"
    assert result["request"]["headers"]["cybertron-robot-token"] == "******"
    assert "cookies" not in result["request"]


def test_debug_project_endpoint_uses_request_body_content_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    with connect() as db:
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-form",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/upload",
            normalized_path="/upload",
            summary="上传",
            description="",
            tags=["knowledge"],
            parameters=[],
            request_body={"content": {"application/x-www-form-urlencoded": {"schema": {"type": "object"}}}},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )
    environment = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(name="测试环境", api_base_url="https://api.example.test", default_headers={}),
        ACTOR,
    )
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {}
        text = "{}"

        class elapsed:
            @staticmethod
            def total_seconds() -> float:
                return 0.001

        @staticmethod
        def json() -> dict:
            return {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(service.requests, "request", fake_request)

    service.debug_project_endpoint(
        "project-1",
        "apiend-form",
        ApiEndpointDebugIn(api_environment_id=environment["id"], body={"name": "demo"}),
        ACTOR,
    )

    assert captured["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert captured["data"] == {"name": "demo"}
    assert captured["json"] is None


def test_debug_project_endpoint_sends_multipart_fields_and_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    with connect() as db:
        api_automation_repo.upsert_endpoint(
            db,
            endpoint_id="apiend-multipart",
            project_id="project-1",
            document_id=None,
            method="POST",
            path="/upload",
            normalized_path="/upload",
            summary="上传",
            description="",
            tags=["knowledge"],
            parameters=[],
            request_body={"content": {"multipart/form-data": {"schema": {"type": "object"}}}},
            responses={"200": {"description": "ok"}},
            auth={},
            source={"source_type": "manual"},
            created_by=ACTOR["id"],
        )
    environment = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(name="测试环境", api_base_url="https://api.example.test", default_headers={}),
        ACTOR,
    )
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {}
        text = "{}"

        class elapsed:
            @staticmethod
            def total_seconds() -> float:
                return 0.001

        @staticmethod
        def json() -> dict:
            return {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(service.requests, "request", fake_request)

    result = service.debug_project_endpoint(
        "project-1",
        "apiend-multipart",
        ApiEndpointDebugIn(api_environment_id=environment["id"], body={"username": "tester"}),
        ACTOR,
        files={"file": ("demo.txt", io.BytesIO(b"hello"), "text/plain", 5)},
    )

    assert captured["data"] == {"username": "tester"}
    assert captured["json"] is None
    assert captured["files"]["file"][:3] == ("demo.txt", captured["files"]["file"][1], "text/plain")
    assert captured["files"]["file"][1].read() == b"hello"
    assert all(key.lower() != "content-type" for key in captured["headers"])
    assert result["request"]["files"] == {
        "file": {"filename": "demo.txt", "content_type": "text/plain", "size": 5}
    }


def test_parse_api_endpoint_debug_form_restores_payload_and_files() -> None:
    class FakeUpload:
        filename = "demo.txt"
        file = io.BytesIO(b"hello")
        content_type = "text/plain"
        size = 5

    class FakeForm:
        @staticmethod
        def get(key):
            if key == "payload":
                return '{"api_environment_id":"apienv-1","body":{"username":"tester"}}'
            return None

        @staticmethod
        def multi_items():
            return [("payload", FakeForm.get("payload")), ("file::file", FakeUpload())]

    payload, files = parse_api_endpoint_debug_form(FakeForm())

    assert payload.api_environment_id == "apienv-1"
    assert payload.body == {"username": "tester"}
    assert files["file"][0] == "demo.txt"
    assert files["file"][1].read() == b"hello"
    assert files["file"][2:] == ("text/plain", 5)


def test_debug_project_endpoint_preserves_explicit_content_type(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project_endpoint()
    environment = service.create_api_environment(
        "project-1",
        ApiEnvironmentIn(
            name="测试环境",
            api_base_url="https://api.example.test",
            default_headers={"content-type": "text/plain"},
        ),
        ACTOR,
    )
    captured = {}

    class FakeResponse:
        status_code = 200
        headers = {}
        text = "{}"

        class elapsed:
            @staticmethod
            def total_seconds() -> float:
                return 0.001

        @staticmethod
        def json() -> dict:
            return {}

    def fake_request(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(service.requests, "request", fake_request)

    service.debug_project_endpoint(
        "project-1",
        "apiend-1",
        ApiEndpointDebugIn(api_environment_id=environment["id"], body={"question": "你好"}),
        ACTOR,
    )

    assert captured["headers"]["content-type"] == "text/plain"
    assert "Content-Type" not in captured["headers"]
