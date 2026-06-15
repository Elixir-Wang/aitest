from io import BytesIO
from pathlib import Path
import asyncio

import pytest
from fastapi import HTTPException, UploadFile

from app.core import db as core_db
from app.core import storage
from app.seed.init_db import init_db
from app.services.knowledge import global_service


ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    monkeypatch.setattr(storage, "PROJECT_FILE_STORAGE_ROOT", data_dir / "projects")
    init_db()
    return data_dir


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=name)


def test_company_knowledge_vault_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = _use_temp_db(monkeypatch, tmp_path)

    base = global_service.create_base(name="申请操作库", description="申请相关页面和规则说明", actor=ACTOR)

    assert base["name"] == "申请操作库"
    assert base["file_count"] == 0
    assert base["root_folder_id"]

    tree = global_service.get_base_tree(base["id"], ACTOR)
    assert tree["root"]["type"] == "folder"
    assert tree["root"]["name"] == "申请操作库"
    assert tree["root"]["children"] == []

    child = global_service.create_folder(base["id"], parent_id=base["root_folder_id"], name="01-基础配置", actor=ACTOR)
    assert child["name"] == "01-基础配置"

    uploaded = asyncio.run(
        global_service.upload_files_to_folder(
            base["id"],
            child["id"],
            [_upload("rules.md", b"# Rules\n\n- One\n")],
            actor=ACTOR,
        )
    )
    file_item = uploaded["files"][0]
    assert file_item["display_name"] == "rules.md"

    content = global_service.get_vault_file(base["id"], file_item["id"], ACTOR)
    assert content["markdown_content"] == "# Rules\n\n- One\n"
    assert Path(content["raw_path"]).exists()
    assert Path(content["markdown_path"]).exists()

    tree = global_service.get_base_tree(base["id"], ACTOR)
    assert tree["root"]["children"][0]["children"][0]["id"] == file_item["id"]

    global_service.delete_vault_file(base["id"], file_item["id"], ACTOR)
    assert not Path(content["raw_path"]).exists()
    assert not Path(content["markdown_path"]).exists()
    assert global_service.list_bases(actor=ACTOR)["items"][0]["file_count"] == 0

    nested = global_service.create_folder(base["id"], parent_id=child["id"], name="子目录", actor=ACTOR)
    second_upload = asyncio.run(
        global_service.upload_files_to_folder(
            base["id"],
            nested["id"],
            [_upload("note.txt", b"hello")],
            actor=ACTOR,
        )
    )
    second_content = global_service.get_vault_file(base["id"], second_upload["files"][0]["id"], ACTOR)
    global_service.delete_folder(base["id"], child["id"], ACTOR)

    assert not Path(second_content["raw_path"]).exists()
    assert not (data_dir / "global-knowledge" / "bases" / base["id"] / "folders" / nested["id"]).exists()
    assert global_service.get_base_tree(base["id"], ACTOR)["root"]["children"] == []


def test_company_knowledge_root_folder_cannot_be_deleted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    base = global_service.create_base(name="申请操作库", description="", actor=ACTOR)

    with pytest.raises(HTTPException) as exc_info:
        global_service.delete_folder(base["id"], base["root_folder_id"], ACTOR)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "GLOBAL_KNOWLEDGE_ROOT_FOLDER_DELETE_FORBIDDEN"


def test_company_knowledge_base_delete_removes_entry_and_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_dir = _use_temp_db(monkeypatch, tmp_path)
    base = global_service.create_base(name="申请操作库", description="", actor=ACTOR)
    base_dir = data_dir / "global-knowledge" / "bases" / base["id"]
    base_dir.mkdir(parents=True)

    global_service.delete_base(base["id"], ACTOR)

    assert global_service.list_bases(actor=ACTOR)["items"] == []
    assert not base_dir.exists()
