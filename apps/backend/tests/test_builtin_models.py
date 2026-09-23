from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.core import settings
from app.seed.init_db import init_db
from app.services import builtin_model_service

ADMIN_ACTOR = {"id": "u-admin", "username": "admin", "nickname": "平台管理员", "role": "admin"}


@pytest.fixture()
def isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()


def _provider_rows() -> list[dict]:
    with core_db.connect() as db:
        rows = db.execute(
            "SELECT provider, model, base_url, api_key, status, created_by FROM model_providers ORDER BY provider ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def _expected_key(provider: str) -> str:
    for entry in builtin_model_service.BUILTIN_MODELS:
        if entry["provider"] == provider:
            return builtin_model_service.decrypt_api_key(
                settings.BUILTIN_MODEL_PASSWORD, entry["api_key_encrypted"]
            )
    raise AssertionError(f"未找到内置模型 {provider}")


def test_default_password_is_aitest() -> None:
    assert settings.BUILTIN_MODEL_PASSWORD == "aitest"


def test_rejects_wrong_password(isolated_db) -> None:
    with pytest.raises(HTTPException) as exc_info:
        builtin_model_service.load_builtin_models("wrong-password", ADMIN_ACTOR)

    assert exc_info.value.status_code == 403
    assert _provider_rows() == []


def test_encrypt_decrypt_roundtrip() -> None:
    encrypted = builtin_model_service.encrypt_api_key("aitest", "sk-unit-test-key")

    assert builtin_model_service.decrypt_api_key("aitest", encrypted) == "sk-unit-test-key"


def test_decrypt_fails_with_wrong_password() -> None:
    encrypted = builtin_model_service.encrypt_api_key("aitest", "sk-unit-test-key")

    assert builtin_model_service.decrypt_api_key("other-password", encrypted) is None


def test_all_builtin_ciphers_are_readable() -> None:
    for entry in builtin_model_service.BUILTIN_MODELS:
        assert builtin_model_service.decrypt_api_key("aitest", entry["api_key_encrypted"])


def test_creates_builtin_models_with_decrypted_keys(isolated_db) -> None:
    result = builtin_model_service.load_builtin_models("aitest", ADMIN_ACTOR)

    assert result == {"created": 2, "updated": 0, "unchanged": 0}
    rows = _provider_rows()
    assert [(row["provider"], row["model"]) for row in rows] == [
        ("DeepSeek", "deepseek-v4-flash"),
        ("sensenova", "deepseek-v4-flash"),
    ]
    for row in rows:
        assert row["api_key"] == _expected_key(row["provider"])
        assert row["api_key"]
        assert row["status"] == "enabled"
        assert row["created_by"] == "u-admin"


def test_reloading_does_not_duplicate_or_clear_keys(isolated_db) -> None:
    builtin_model_service.load_builtin_models("aitest", ADMIN_ACTOR)

    again = builtin_model_service.load_builtin_models("aitest", ADMIN_ACTOR)

    assert again == {"created": 0, "updated": 0, "unchanged": 2}
    assert len(_provider_rows()) == 2


def test_reloading_restores_cleared_keys(isolated_db) -> None:
    builtin_model_service.load_builtin_models("aitest", ADMIN_ACTOR)
    with core_db.connect() as db:
        db.execute("UPDATE model_providers SET api_key = ''")

    again = builtin_model_service.load_builtin_models("aitest", ADMIN_ACTOR)

    assert again == {"created": 0, "updated": 2, "unchanged": 0}
    assert all(row["api_key"] for row in _provider_rows())
