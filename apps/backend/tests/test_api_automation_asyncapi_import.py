import json
from pathlib import Path

import pytest

from app.core import db as db_core
from app.core import settings, storage
from app.core.db import connect
from app.seed.init_db import init_db
from app.services.api_automation import service
from app.services.api_automation.interface_document_parser import parse_interface_document


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}

ASYNCAPI_JSON = """{
  "asyncapi": "3.0.0",
  "info": {"title": "Cybotstar Realtime API", "version": "1.0.0"},
  "servers": {
    "production": {
      "host": "www.cybotstar.cn",
      "pathname": "/openapi/v2/ws/dialog",
      "protocol": "wss"
    }
  },
  "channels": {
    "agentDialog": {
      "address": "/openapi/v2/ws/dialog",
      "title": "智能体多轮对话",
      "servers": [{"$ref": "#/servers/production"}],
      "messages": {
        "sendMessage": {"$ref": "#/components/messages/AgentDialogSend"},
        "receiveMessage": {"$ref": "#/components/messages/AgentDialogReceive"}
      },
      "x-source-doc-url": "http://docs.example.test/api-reference/conversation/ws/dialog_exec"
    }
  },
  "operations": {
    "sendAgentDialogMessage": {
      "action": "send",
      "channel": {"$ref": "#/channels/agentDialog"},
      "messages": [{"$ref": "#/channels/agentDialog/messages/sendMessage"}]
    },
    "receiveAgentDialogMessage": {
      "action": "receive",
      "channel": {"$ref": "#/channels/agentDialog"},
      "messages": [{"$ref": "#/channels/agentDialog/messages/receiveMessage"}]
    }
  },
  "components": {
    "messages": {
      "AgentDialogSend": {
        "payload": {
          "type": "object",
          "required": ["question"],
          "properties": {"question": {"type": "string"}}
        }
      },
      "AgentDialogReceive": {
        "payload": {
          "type": "object",
          "properties": {"answer": {"type": "string"}, "finish": {"type": "boolean"}}
        }
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


def test_parse_interface_document_normalizes_websocket_channel() -> None:
    result = parse_interface_document(ASYNCAPI_JSON, source_name="realtime.asyncapi.json")

    assert result["format"] == "asyncapi"
    assert result["endpoint_count"] == 1
    endpoint = result["endpoints"][0]
    assert endpoint["protocol"] == "websocket"
    assert endpoint["method"] == ""
    assert endpoint["path"] == "/openapi/v2/ws/dialog"
    assert endpoint["operation_action"] == "bidirectional"
    assert endpoint["connection_url"] == "wss://www.cybotstar.cn/openapi/v2/ws/dialog"
    assert endpoint["message_schemas"]["send"]["required"] == ["question"]
    assert endpoint["message_schemas"]["receive"]["properties"]["finish"]["type"] == "boolean"


def test_import_openapi_text_accepts_asyncapi_and_persists_websocket_asset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()

    result = service.import_openapi_text(
        "project-1",
        source_type="file",
        raw_content=ASYNCAPI_JSON,
        actor=ACTOR,
        name="Cybotstar Realtime API",
    )

    with connect() as db:
        document = db.execute("SELECT * FROM api_documents WHERE id = ?", (result["id"],)).fetchone()
        endpoint = db.execute("SELECT * FROM api_endpoints WHERE document_id = ?", (result["id"],)).fetchone()

    assert document["document_format"] == "asyncapi"
    assert endpoint["protocol"] == "websocket"
    assert endpoint["method"] == ""
    assert endpoint["operation_action"] == "bidirectional"
    assert Path(storage.resolve_stored_path(result["file_path"])).name == "asyncapi.json"


def test_import_preserves_websocket_channels_that_share_the_same_address(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _seed_project()
    document = json.loads(ASYNCAPI_JSON)
    document["channels"]["dialog"] = {
        **document["channels"]["agentDialog"],
        "title": "对话流多轮对话",
        "x-source-doc-url": "http://docs.example.test/api-reference/chatflow/ws/dialog_exec",
    }
    document["operations"]["sendDialogMessage"] = {
        **document["operations"]["sendAgentDialogMessage"],
        "channel": {"$ref": "#/channels/dialog"},
    }
    document["operations"]["receiveDialogMessage"] = {
        **document["operations"]["receiveAgentDialogMessage"],
        "channel": {"$ref": "#/channels/dialog"},
    }

    result = service.import_openapi_text(
        "project-1",
        source_type="file",
        raw_content=json.dumps(document),
        actor=ACTOR,
        name="Cybotstar Realtime API",
    )

    with connect() as db:
        endpoints = db.execute(
            "SELECT source_json FROM api_endpoints WHERE document_id = ? ORDER BY id",
            (result["id"],),
        ).fetchall()

    assert len(endpoints) == 2
    assert {json.loads(endpoint["source_json"])["channel_id"] for endpoint in endpoints} == {"agentDialog", "dialog"}
