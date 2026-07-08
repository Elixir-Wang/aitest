from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.repositories import api_automation_repo
from app.seed.init_db import init_db
from app.services.api_automation import openapi_parser, service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}
GUEST = {"id": "u-guest", "role": "guest", "nickname": "访客", "username": "guest", "project_scope": "全部项目"}


OPENAPI_JSON = """{
  "openapi": "3.0.3",
  "info": {"title": "Petstore", "version": "1.0.0"},
  "paths": {
    "/pets/{petId}": {
      "get": {
        "summary": "Get pet",
        "description": "Read one pet",
        "tags": ["pet"],
        "parameters": [{"name": "petId", "in": "path", "required": true, "schema": {"type": "string"}}],
        "responses": {"200": {"description": "ok"}}
      }
    }
  }
}"""


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


def _seed_project() -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, description, status, created_by) VALUES (?, ?, '', 'active', ?)",
            ("project-1", "测试项目", ACTOR["id"]),
        )


def test_parse_openapi_document_extracts_endpoint() -> None:
    result = openapi_parser.parse_openapi_document(OPENAPI_JSON, source_name="petstore.json")

    assert result["title"] == "Petstore"
    assert result["version"] == "1.0.0"
    assert result["endpoint_count"] == 1
    endpoint = result["endpoints"][0]
    assert endpoint["method"] == "GET"
    assert endpoint["path"] == "/pets/{petId}"
    assert endpoint["tags"] == ["pet"]
    assert endpoint["parameters"][0]["name"] == "petId"
    assert endpoint["responses"]["200"]["description"] == "ok"


def test_parse_openapi_document_resolves_local_schema_refs() -> None:
    result = openapi_parser.parse_openapi_document(
        """{
          "openapi": "3.0.3",
          "info": {"title": "Operation Logs", "version": "1.0.0"},
          "paths": {
            "/operation-logs/retention-policy": {
              "put": {
                "summary": "Update Retention Policy",
                "parameters": [
                  {"name": "authorization", "in": "header", "schema": {"$ref": "#/components/schemas/AuthHeader"}}
                ],
                "requestBody": {
                  "required": true,
                  "content": {
                    "application/json": {
                      "schema": {"$ref": "#/components/schemas/OperationLogRetentionPolicyUpdate"}
                    }
                  }
                },
                "responses": {
                  "200": {
                    "description": "ok",
                    "content": {
                      "application/json": {
                        "schema": {"$ref": "#/components/schemas/OperationLogRetentionPolicyOut"}
                      }
                    }
                  }
                }
              }
            }
          },
          "components": {
            "schemas": {
              "AuthHeader": {"type": "object", "properties": {"token": {"type": "string"}}},
              "OperationLogRetentionPolicyUpdate": {
                "type": "object",
                "required": ["retention_days"],
                "properties": {
                  "retention_days": {"type": "integer", "description": "保留天数"}
                }
              },
              "OperationLogRetentionPolicyOut": {
                "type": "object",
                "properties": {
                  "retention_days": {"type": "integer"}
                }
              }
            }
          }
        }""",
        source_name="operation-logs.json",
    )

    endpoint = result["endpoints"][0]
    assert endpoint["parameters"][0]["schema"]["properties"]["token"]["type"] == "string"
    request_schema = endpoint["request_body"]["content"]["application/json"]["schema"]
    assert request_schema["properties"]["retention_days"]["description"] == "保留天数"
    response_schema = endpoint["responses"]["200"]["content"]["application/json"]["schema"]
    assert response_schema["properties"]["retention_days"]["type"] == "integer"


def test_parse_openapi_document_rejects_missing_paths() -> None:
    with pytest.raises(openapi_parser.OpenAPIParseError, match="paths"):
        openapi_parser.parse_openapi_document('{"openapi":"3.0.3","info":{"title":"Bad"}}')


def test_import_openapi_text_saves_document_file_and_upserts_endpoints(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    first = service.import_openapi_text(
        "project-1",
        source_type="file",
        raw_content=OPENAPI_JSON,
        actor=ACTOR,
        name="Petstore",
    )
    second = service.import_openapi_text(
        "project-1",
        source_type="file",
        raw_content=OPENAPI_JSON.replace("Get pet", "Get pet updated"),
        actor=ACTOR,
        name="Petstore Again",
    )

    with connect() as db:
        endpoints = api_automation_repo.list_endpoints(db, "project-1")
        documents = db.execute("SELECT * FROM api_documents ORDER BY created_at ASC").fetchall()

    assert first["endpoint_count"] == 1
    assert second["endpoint_count"] == 1
    assert len(documents) == 2
    assert len(endpoints) == 1
    assert endpoints[0]["summary"] == "Get pet updated"
    assert Path(storage.resolve_stored_path(first["file_path"])).read_text(encoding="utf-8") == OPENAPI_JSON


def test_import_openapi_url_uses_requests_get(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    calls = []

    class Response:
        text = OPENAPI_JSON

        def raise_for_status(self) -> None:
            pass

    def fake_get(url: str, *, timeout: float, allow_redirects: bool) -> Response:
        calls.append({"url": url, "timeout": timeout, "allow_redirects": allow_redirects})
        return Response()

    monkeypatch.setattr(service.requests, "get", fake_get)

    result = service.import_openapi_url(
        "project-1",
        url="http://localhost:8000/openapi.json",
        actor=ACTOR,
        name="Petstore URL",
    )

    assert calls == [{"url": "http://localhost:8000/openapi.json", "timeout": 15.0, "allow_redirects": True}]
    assert result["name"] == "Petstore URL"
    assert result["source_type"] == "url"
    assert result["source_url"] == "http://localhost:8000/openapi.json"


def test_guest_cannot_import_openapi(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    with pytest.raises(HTTPException) as exc_info:
        service.import_openapi_text(
            "project-1",
            source_type="file",
            raw_content=OPENAPI_JSON,
            actor=GUEST,
            name="Petstore",
        )

    assert exc_info.value.status_code == 403
