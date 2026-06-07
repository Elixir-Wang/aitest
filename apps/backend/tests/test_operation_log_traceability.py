import pytest
from fastapi.testclient import TestClient

from app.core import db as core_db
from app.core.logging import set_trace_id
from app.schemas.operation_log import ClientErrorReport, OperationLogQuery
from app.seed.init_db import init_db
from app.services import operation_log_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    set_trace_id("-")
    init_db()


def test_record_success_defaults_request_id_to_current_trace(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    set_trace_id("trace_test123")

    log_id = operation_log_service.record_success(
        log_type="audit",
        module="requirement",
        action="upload",
        object_type="requirement_document",
        object_id="doc-1",
        object_name="登录需求",
        actor_id="u-admin",
        actor_name="管理员",
        source="web",
        summary="上传需求文件。",
    )

    assert log_id
    with core_db.connect() as db:
        row = db.execute("SELECT request_id FROM operation_logs WHERE id = ?", (log_id,)).fetchone()
    assert row["request_id"] == "trace_test123"


def test_operation_log_keyword_search_includes_trace_task_and_object_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    operation_log_service.record_task_event(
        module="requirement",
        action="run",
        object_type="requirement_analysis_run",
        object_id="reqrun-1",
        object_name="需求评审",
        actor_id="u-admin",
        actor_name="管理员",
        source="web",
        summary="需求评审已提交。",
        task_id="reqrun-1",
        request_id="trace_search123",
    )

    by_trace = operation_log_service.list_logs(OperationLogQuery(keyword="trace_search123"), ACTOR)
    by_task = operation_log_service.list_logs(OperationLogQuery(keyword="reqrun-1"), ACTOR)
    detail = operation_log_service.get_log(by_trace["items"][0]["id"], ACTOR)

    assert by_trace["total"] == 1
    assert detail["request_id"] == "trace_search123"
    assert by_task["total"] == 1
    assert by_task["items"][0]["object_id"] == "reqrun-1"


def test_record_client_error_writes_failed_frontend_log_with_trace_and_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    with core_db.connect() as db:
        db.execute(
            "INSERT INTO projects (id, name, status, description) VALUES ('project-1', '测试项目', 'active', '')"
        )

    result = operation_log_service.record_client_error(
        ClientErrorReport(
            title="需求保存失败",
            message="保存失败：password=secret123 token=abc123",
            code="SAVE_FAILED",
            status=500,
            trace_id="trace_client123",
            method="POST",
            path="/projects/project-1/requirements/doc-1?token=abc123",
            page_url="http://localhost:3000/projects/project-1/requirements/doc-1?password=secret123",
            action_label="保存标准文件",
            occurred_at="2026-06-07T10:00:00.000Z",
        ),
        ACTOR,
        ip_address="127.0.0.1",
        user_agent="pytest token=abc123",
    )

    assert result["log_id"]
    detail = operation_log_service.get_log(result["log_id"], ACTOR)

    assert detail["module"] == "frontend"
    assert detail["action"] == "client_error"
    assert detail["result"] == "failed"
    assert detail["project_id"] == "project-1"
    assert detail["request_id"] == "trace_client123"
    assert detail["object_id"] == "trace_client123"
    assert detail["actor_id"] == "u-admin"
    assert detail["ip_address"] == "127.0.0.1"
    assert "password=secret123" not in detail["failure_reason"]
    assert "token=abc123" not in detail["failure_reason"]
    assert "token=abc123" not in str(detail["before"])
    assert "password=secret123" not in str(detail["before"])
    assert "token=abc123" not in detail["user_agent"]


def test_record_client_error_without_actor_creates_system_level_anonymous_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    result = operation_log_service.record_client_error(
        ClientErrorReport(
            title="登录页请求失败",
            message="账号或密码不正确",
            status=401,
            trace_id="trace_login123",
            method="POST",
            path="/auth/login",
            page_url="http://localhost:3000/auth/v1/login",
            action_label="登录",
        ),
        None,
    )

    assert result["log_id"]
    detail = operation_log_service.get_log(result["log_id"], ACTOR)

    assert detail["module"] == "frontend"
    assert detail["action"] == "client_error"
    assert detail["project_id"] is None
    assert detail["actor_id"] == "anonymous"
    assert detail["actor_name"] == "匿名用户"


def test_client_error_api_requires_auth_and_writes_log(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        unauthorized = client.post(
            "/api/v1/operation-logs/client-errors",
            json={"title": "前端错误", "message": "网络错误"},
        )
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        token = login.json()["data"]["access_token"]
        response = client.post(
            "/api/v1/operation-logs/client-errors",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "保存失败",
                "message": "请求失败 token=abc123",
                "status": 500,
                "trace_id": "trace_api_client123",
                "method": "POST",
                "path": "/settings/models",
                "page_url": "http://localhost:3000/settings/models",
                "action_label": "保存模型",
            },
        )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["log_id"]
    detail = operation_log_service.get_log(data["log_id"], ACTOR)
    assert detail["module"] == "frontend"
    assert detail["action"] == "client_error"
    assert detail["request_id"] == "trace_api_client123"
    assert "token=abc123" not in detail["failure_reason"]
