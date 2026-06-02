import pytest
from fastapi import HTTPException

from app.agents.model_selection import resolve_model_selection
from app.core import db as core_db
from app.repositories import model_repo
from app.schemas.model import ModelAssignmentIn
from app.seed.init_db import init_db
from app.services import model_service


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _create_provider(provider_id: str = "mp-openai", *, status: str = "enabled", api_key: str = "sk-test") -> None:
    with core_db.connect() as db:
        model_repo.create_provider(
            db,
            provider_id=provider_id,
            provider="openai",
            model="gpt-5.5",
            base_url="https://api.openai.com/v1",
            api_key=api_key,
            description="test",
            status=status,
            created_by="u-admin",
        )


def test_model_assignment_update_and_selection_resolves_model_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider()

    result = model_service.update_model_assignment(
        "document_editor",
        payload=ModelAssignmentIn(model_provider_id="mp-openai"),
        actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
    )

    assert result["capability_id"] == "document_editor"
    assert "capability_kind" not in result

    selection = resolve_model_selection("document_editor")
    assert selection.model == "gpt-5.5"
    assert selection.api_key == "sk-test"


def test_model_assignment_rejects_unknown_capability(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider()

    with pytest.raises(HTTPException) as exc_info:
        model_service.update_model_assignment(
            "unknown_capability",
            payload=ModelAssignmentIn(model_provider_id="mp-openai"),
            actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "AI_CAPABILITY_NOT_FOUND"


def test_model_assignment_rejects_disabled_provider(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    _create_provider(status="disabled")

    with pytest.raises(HTTPException) as exc_info:
        model_service.update_model_assignment(
            "document_editor",
            payload=ModelAssignmentIn(model_provider_id="mp-openai"),
            actor={"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin"},
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "MODEL_PROVIDER_DISABLED"


def test_resolve_model_selection_rejects_missing_assignment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="未分配可用模型配置"):
        resolve_model_selection("document_editor")
