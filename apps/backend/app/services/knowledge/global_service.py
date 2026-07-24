import secrets
import shutil
import os
import tempfile
import threading
from contextlib import contextmanager

from fastapi import UploadFile

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import (
    global_knowledge_base_dir,
    global_knowledge_folder_dir,
    resolve_stored_path,
    store_path,
)
from app.repositories import global_knowledge_repo
from app.services.document.file_service import file_format_for_filename, safe_filename_for_storage

BASE_STATUSES = {
    "processing": "处理中",
    "available": "可用",
    "conversion_failed": "转换失败",
}

VAULT_UPLOAD_ALLOWED_TYPES = {"md"}
_FILE_LOCKS: dict[str, threading.Lock] = {}
_FILE_LOCKS_GUARD = threading.Lock()


def list_bases(*, actor, keyword: str = "") -> dict:
    with connect() as db:
        rows = global_knowledge_repo.list_bases(db, keyword)
        return {"items": [_serialize_base(row, actor["role"]) for row in rows]}


def create_base(*, name: str, description: str = "", actor) -> dict:
    _require_admin(actor)
    name = _clean_required_name(name, "GLOBAL_KNOWLEDGE_BASE_NAME_REQUIRED", "请填写知识库名称。")
    description = description.strip()
    base_id = f"gkb-{secrets.token_hex(8)}"
    root_folder_id = f"gkfld-{secrets.token_hex(8)}"
    with connect() as db:
        if global_knowledge_repo.find_base_by_name(db, name):
            raise api_error(422, "GLOBAL_KNOWLEDGE_BASE_NAME_EXISTS", "已存在同名公司知识库。")
        global_knowledge_repo.create_base(
            db,
            base_id=base_id,
            name=name,
            description=description,
            root_folder_id=root_folder_id,
            created_by=actor["id"],
        )
        global_knowledge_repo.create_folder(
            db,
            folder_id=root_folder_id,
            base_id=base_id,
            parent_id=None,
            name=name,
        )
        row = global_knowledge_repo.find_base(db, base_id)
    return _serialize_base(row, actor["role"])


def update_base(base_id: str, *, name: str, description: str = "", actor) -> dict:
    _require_admin(actor)
    name = _clean_required_name(name, "GLOBAL_KNOWLEDGE_BASE_NAME_REQUIRED", "请填写知识库名称。")
    description = description.strip()
    with connect() as db:
        base = _require_base(db, base_id)
        if global_knowledge_repo.find_base_by_name(db, name, exclude_id=base_id):
            raise api_error(422, "GLOBAL_KNOWLEDGE_BASE_NAME_EXISTS", "已存在同名公司知识库。")
        global_knowledge_repo.update_base(db, base_id, name=name, description=description)
        global_knowledge_repo.update_folder_name(db, base["root_folder_id"], name)
        row = global_knowledge_repo.find_base(db, base_id)
    return _serialize_base(row, actor["role"])


def get_base_tree(base_id: str, actor) -> dict:
    with connect() as db:
        base = global_knowledge_repo.find_base(db, base_id)
        if not base:
            raise api_error(404, "GLOBAL_KNOWLEDGE_BASE_NOT_FOUND", "公司知识库不存在。")
        folders = global_knowledge_repo.list_folders_by_base(db, base_id)
        files = global_knowledge_repo.list_files_by_base(db, base_id)
    folder_nodes = {
        row["id"]: {
            "id": row["id"],
            "type": "folder",
            "name": row["name"],
            "parent_id": row["parent_id"],
            "is_root": row["id"] == base["root_folder_id"],
            "sort_order": int(row["sort_order"] if row["sort_order"] is not None else 0),
            "children": [],
        }
        for row in folders
    }
    root = folder_nodes.get(base["root_folder_id"])
    if root is None:
        raise api_error(500, "GLOBAL_KNOWLEDGE_ROOT_FOLDER_MISSING", "公司知识库根文件夹缺失。")
    for row in folders:
        parent_id = row["parent_id"]
        if parent_id and parent_id in folder_nodes:
            folder_nodes[parent_id]["children"].append(folder_nodes[row["id"]])
    for row in files:
        folder = folder_nodes.get(row["folder_id"])
        if folder is None:
            continue
        folder["children"].append(_serialize_vault_file(row, include_content=False))
    _sort_tree(root)
    return {"base": _serialize_base(base, actor["role"]), "root": root}


def create_folder(base_id: str, *, parent_id: str, name: str, actor) -> dict:
    _require_admin(actor)
    name = _clean_folder_name(name)
    folder_id = f"gkfld-{secrets.token_hex(8)}"
    with connect() as db:
        base = _require_base(db, base_id)
        parent = global_knowledge_repo.find_folder_in_base(db, base_id, parent_id)
        if not parent:
            raise api_error(404, "GLOBAL_KNOWLEDGE_FOLDER_NOT_FOUND", "目标文件夹不存在。")
        try:
            global_knowledge_repo.create_folder(
                db,
                folder_id=folder_id,
                base_id=base_id,
                parent_id=parent_id,
                name=name,
            )
        except Exception as exc:
            if "UNIQUE" in str(exc):
                raise api_error(422, "GLOBAL_KNOWLEDGE_FOLDER_NAME_EXISTS", "同级目录下已存在同名文件夹。") from exc
            raise
        global_knowledge_repo.touch_base(db, base_id)
        row = global_knowledge_repo.find_folder(db, folder_id)
    global_knowledge_folder_dir(base["id"], folder_id).mkdir(parents=True, exist_ok=True)
    return _serialize_folder(row, is_root=False)


async def upload_files_to_folder(base_id: str, folder_id: str, files: list[UploadFile], actor) -> dict:
    _require_admin(actor)
    if not files:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FILE_REQUIRED", "请至少上传一个公司知识文件。")
    with connect() as db:
        _require_base(db, base_id)
        folder = global_knowledge_repo.find_folder_in_base(db, base_id, folder_id)
        if not folder:
            raise api_error(404, "GLOBAL_KNOWLEDGE_FOLDER_NOT_FOUND", "目标文件夹不存在。")

    created: list[dict] = []
    for index, upload in enumerate(files, start=1):
        created.append(await _save_vault_file(base_id, folder_id, upload, index))
    with connect() as db:
        global_knowledge_repo.touch_base(db, base_id)
        rows = [global_knowledge_repo.find_vault_file(db, base_id, item["id"]) for item in created]
    return {"files": [_serialize_vault_file(row, include_content=False) for row in rows if row]}


def upsert_markdown_file(
    base_id: str,
    folder_id: str,
    *,
    display_name: str,
    markdown_content: str,
    actor,
) -> dict:
    """Create or atomically replace a registered Markdown knowledge file."""
    _require_admin(actor)
    safe_name = safe_filename_for_storage(display_name)
    _validate_vault_upload_filename(safe_name)
    if not markdown_content.strip():
        raise api_error(400, "GLOBAL_KNOWLEDGE_FILE_EMPTY", "知识文件内容不能为空。")

    lock_key = f"{base_id}/{folder_id}/{safe_name}"
    with _file_lock(lock_key):
        with connect() as db:
            _require_base(db, base_id)
            folder = global_knowledge_repo.find_folder_in_base(db, base_id, folder_id)
            if not folder:
                raise api_error(404, "GLOBAL_KNOWLEDGE_FOLDER_NOT_FOUND", "目标文件夹不存在。")
            existing = global_knowledge_repo.find_vault_file_by_folder_and_name(db, folder_id, safe_name)

        file_id = existing["id"] if existing else f"gkfile-{secrets.token_hex(8)}"
        folder_dir = global_knowledge_folder_dir(base_id, folder_id)
        raw_dir = folder_dir / "raw"
        markdown_dir = folder_dir / "markdown"
        raw_path = raw_dir / f"{file_id}-{safe_name}"
        markdown_path = markdown_dir / f"{file_id}.md"
        raw_bytes = markdown_content.encode("utf-8")

        raw_dir.mkdir(parents=True, exist_ok=True)
        markdown_dir.mkdir(parents=True, exist_ok=True)
        raw_tmp = _write_temp_file(raw_dir, raw_bytes)
        markdown_tmp = _write_temp_file(markdown_dir, raw_bytes)
        old_raw = raw_path.read_bytes() if raw_path.exists() else None
        old_markdown = markdown_path.read_bytes() if markdown_path.exists() else None
        try:
            os.replace(raw_tmp, raw_path)
            os.replace(markdown_tmp, markdown_path)
            with connect() as db:
                if existing:
                    global_knowledge_repo.update_vault_file_content(
                        db,
                        file_id,
                        original_filename=safe_name,
                        display_name=safe_name,
                        file_size=len(raw_bytes),
                        raw_path=store_path(raw_path) or str(raw_path),
                        markdown_path=store_path(markdown_path) or str(markdown_path),
                        markdown_content=markdown_content,
                    )
                else:
                    global_knowledge_repo.create_vault_file(
                        db,
                        file_id=file_id,
                        base_id=base_id,
                        folder_id=folder_id,
                        original_filename=safe_name,
                        display_name=safe_name,
                        file_type="md",
                        file_size=len(raw_bytes),
                        raw_path=store_path(raw_path) or str(raw_path),
                        markdown_path=store_path(markdown_path) or str(markdown_path),
                        markdown_content=markdown_content,
                        conversion_status="success",
                        conversion_summary="文件已作为 Markdown 内容保存。",
                    )
                global_knowledge_repo.touch_base(db, base_id)
        except Exception:
            _restore_file(raw_path, old_raw)
            _restore_file(markdown_path, old_markdown)
            raise
        finally:
            for temp_path in (raw_tmp, markdown_tmp):
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass

        with connect() as db:
            row = global_knowledge_repo.find_vault_file(db, base_id, file_id)
        return _serialize_vault_file(row, include_content=True)


def get_vault_file(base_id: str, file_id: str, actor) -> dict:
    with connect() as db:
        _require_base(db, base_id)
        row = global_knowledge_repo.find_vault_file(db, base_id, file_id)
        if not row:
            raise api_error(404, "GLOBAL_KNOWLEDGE_FILE_NOT_FOUND", "文件不存在。")
        return _serialize_vault_file(row, include_content=True)


def delete_vault_file(base_id: str, file_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_base(db, base_id)
        row = global_knowledge_repo.find_vault_file(db, base_id, file_id)
        if not row:
            raise api_error(404, "GLOBAL_KNOWLEDGE_FILE_NOT_FOUND", "文件不存在。")
        snapshot = dict(row)
    _delete_file_paths(snapshot)
    with connect() as db:
        _require_base(db, base_id)
        if not global_knowledge_repo.find_vault_file(db, base_id, file_id):
            raise api_error(404, "GLOBAL_KNOWLEDGE_FILE_NOT_FOUND", "文件不存在。")
        global_knowledge_repo.delete_vault_file(db, file_id)
        global_knowledge_repo.touch_base(db, base_id)
    return {"deleted": True, "id": file_id}


def delete_base(base_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        _require_base(db, base_id)
    base_dir = global_knowledge_base_dir(base_id)
    if base_dir.exists():
        shutil.rmtree(base_dir)
    with connect() as db:
        _require_base(db, base_id)
        global_knowledge_repo.delete_base(db, base_id)
    return {"deleted": True, "id": base_id}


def delete_folder(base_id: str, folder_id: str, actor) -> dict:
    _require_admin(actor)
    with connect() as db:
        base = _require_base(db, base_id)
        folder = global_knowledge_repo.find_folder_in_base(db, base_id, folder_id)
        if not folder:
            raise api_error(404, "GLOBAL_KNOWLEDGE_FOLDER_NOT_FOUND", "目标文件夹不存在。")
        if folder_id == base["root_folder_id"]:
            raise api_error(400, "GLOBAL_KNOWLEDGE_ROOT_FOLDER_DELETE_FORBIDDEN", "根文件夹不允许删除。")
        folder_ids = global_knowledge_repo.descendant_folder_ids(db, base_id, folder_id)
    for descendant_id in folder_ids:
        folder_dir = global_knowledge_folder_dir(base_id, descendant_id)
        if folder_dir.exists():
            shutil.rmtree(folder_dir)
    with connect() as db:
        _require_base(db, base_id)
        if not global_knowledge_repo.find_folder_in_base(db, base_id, folder_id):
            raise api_error(404, "GLOBAL_KNOWLEDGE_FOLDER_NOT_FOUND", "目标文件夹不存在。")
        global_knowledge_repo.delete_folders(db, folder_ids)
        global_knowledge_repo.touch_base(db, base_id)
    return {"deleted": True, "id": folder_id, "deleted_folder_ids": folder_ids}


def _validate_vault_upload_filename(filename: str) -> None:
    file_type = file_format_for_filename(filename)
    if file_type not in VAULT_UPLOAD_ALLOWED_TYPES:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FILE_TYPE_NOT_ALLOWED", "仅支持上传 Markdown（.md）文件。")


@contextmanager
def _file_lock(key: str):
    with _FILE_LOCKS_GUARD:
        lock = _FILE_LOCKS.setdefault(key, threading.Lock())
    with lock:
        yield


def _write_temp_file(directory, content: bytes):
    descriptor, temp_name = tempfile.mkstemp(prefix=".knowledge-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    return directory / temp_name.rsplit("/", 1)[-1]


def _restore_file(path, content: bytes | None) -> None:
    if content is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    restore_tmp = _write_temp_file(path.parent, content)
    os.replace(restore_tmp, path)


async def _save_vault_file(base_id: str, folder_id: str, upload: UploadFile, index: int) -> dict:
    raw_bytes = await upload.read()
    if not raw_bytes:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FILE_EMPTY", "上传文件不能为空。")
    safe_name = safe_filename_for_storage(upload.filename or f"global-knowledge-{index}")
    _validate_vault_upload_filename(safe_name)
    file_type = file_format_for_filename(safe_name)
    file_id = f"gkfile-{secrets.token_hex(8)}"
    folder_dir = global_knowledge_folder_dir(base_id, folder_id)
    raw_dir = folder_dir / "raw"
    markdown_dir = folder_dir / "markdown"
    raw_path = raw_dir / f"{file_id}-{safe_name}"
    markdown_content = raw_bytes.decode("utf-8", errors="ignore")
    conversion_status = "success"
    conversion_summary = "文件已作为 Markdown 内容保存。"
    markdown_path = markdown_dir / f"{file_id}.md"

    try:
        raw_dir.mkdir(parents=True, exist_ok=True)
        markdown_dir.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw_bytes)
        markdown_path.write_text(markdown_content, encoding="utf-8")
        with connect() as db:
            global_knowledge_repo.create_vault_file(
                db,
                file_id=file_id,
                base_id=base_id,
                folder_id=folder_id,
                original_filename=safe_name,
                display_name=safe_name,
                file_type=file_type,
                file_size=len(raw_bytes),
                raw_path=store_path(raw_path) or str(raw_path),
                markdown_path=store_path(markdown_path) or str(markdown_path),
                markdown_content=markdown_content,
                conversion_status=conversion_status,
                conversion_summary=conversion_summary,
            )
    except Exception as exc:
        _cleanup_failed_vault_upload(base_id, raw_path, markdown_path)
        if "UNIQUE" in str(exc):
            raise api_error(422, "GLOBAL_KNOWLEDGE_FILE_NAME_EXISTS", "当前文件夹下已存在同名文件。") from exc
        raise
    return {"id": file_id}


def _require_base(db, base_id: str):
    base = global_knowledge_repo.find_base(db, base_id)
    if not base:
        raise api_error(404, "GLOBAL_KNOWLEDGE_BASE_NOT_FOUND", "公司知识库不存在。")
    return base


def _clean_required_name(value: str, code: str, message: str) -> str:
    name = value.strip()
    if not name:
        raise api_error(400, code, message)
    return name


def _clean_folder_name(value: str) -> str:
    name = _clean_required_name(value, "GLOBAL_KNOWLEDGE_FOLDER_NAME_REQUIRED", "请填写文件夹名称。")
    if "/" in name or "\\" in name:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FOLDER_NAME_INVALID", "文件夹名称不能包含路径分隔符。")
    if set(name) == {"."}:
        raise api_error(400, "GLOBAL_KNOWLEDGE_FOLDER_NAME_INVALID", "文件夹名称不能只包含点号。")
    return name


def _serialize_base(row, role: str) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "status": row["status"],
        "status_label": BASE_STATUSES.get(row["status"], row["status"]),
        "root_folder_id": row["root_folder_id"],
        "file_count": row["file_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "available_actions": _base_available_actions(role),
    }


def _serialize_folder(row, *, is_root: bool) -> dict:
    return {
        "id": row["id"],
        "type": "folder",
        "name": row["name"],
        "parent_id": row["parent_id"],
        "is_root": is_root,
        "sort_order": int(row["sort_order"] if row["sort_order"] is not None else 0),
        "children": [],
    }


def _serialize_vault_file(row, *, include_content: bool) -> dict:
    raw_path = resolve_stored_path(row["raw_path"])
    markdown_path = resolve_stored_path(row["markdown_path"])
    result = {
        "id": row["id"],
        "type": "file",
        "knowledge_base_id": row["knowledge_base_id"],
        "folder_id": row["folder_id"],
        "name": row["display_name"],
        "original_filename": row["original_filename"],
        "display_name": row["display_name"],
        "file_type": row["file_type"],
        "file_size": row["file_size"],
        "conversion_status": row["conversion_status"],
        "conversion_summary": row["conversion_summary"],
        "sort_order": int(row["sort_order"] if row["sort_order"] is not None else 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if include_content:
        result.update(
            {
                "markdown_content": row["markdown_content"],
                "raw_path": str(raw_path) if raw_path else "",
                "markdown_path": str(markdown_path) if markdown_path else "",
            }
        )
    return result


def _sort_tree(node: dict) -> None:
    node["children"].sort(key=lambda item: (item.get("sort_order", 0), item["name"]))
    for child in node["children"]:
        if child["type"] == "folder":
            _sort_tree(child)


def _delete_file_paths(row: dict) -> None:
    base_root = global_knowledge_base_dir(row["knowledge_base_id"]).resolve()
    for key in ("raw_path", "markdown_path"):
        path = resolve_stored_path(row.get(key))
        if not path:
            continue
        try:
            resolved = path.resolve()
            resolved.relative_to(base_root)
        except ValueError:
            continue
        if resolved.exists() and resolved.is_file():
            resolved.unlink()


def _cleanup_failed_vault_upload(base_id: str, raw_path, markdown_path) -> None:
    base_root = global_knowledge_base_dir(base_id).resolve()
    for path in (raw_path, markdown_path):
        resolved = path.resolve()
        try:
            resolved.relative_to(base_root)
        except ValueError:
            continue
        if resolved.exists() and resolved.is_file():
            resolved.unlink()

    candidate_dirs = {
        raw_path.parent,
        markdown_path.parent,
        raw_path.parent.parent,
        raw_path.parent.parent.parent,
        base_root,
    }
    for directory in sorted(candidate_dirs, key=lambda item: len(item.parts), reverse=True):
        try:
            directory.resolve().relative_to(base_root.parent)
            directory.rmdir()
        except (FileNotFoundError, OSError, ValueError):
            continue


def _base_available_actions(role: str) -> list[dict]:
    can_write = role == "admin"
    return [
        {
            "key": "open_company_knowledge_base",
            "label": "查看",
            "enabled": True,
            "disabled_reason": "",
            "risk_level": "normal",
            "confirm_required": False,
        },
        {
            "key": "delete_company_knowledge_base",
            "label": "删除",
            "enabled": can_write,
            "disabled_reason": "" if can_write else "仅管理员可删除公司知识库。",
            "risk_level": "warning",
            "confirm_required": True,
        },
    ]


def _require_admin(actor) -> None:
    if actor["role"] != "admin":
        raise api_error(403, "PERMISSION_DENIED", "仅管理员可维护公司知识库。")
