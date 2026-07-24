from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import shutil
import time
from pathlib import Path

from fastapi import UploadFile

from app.core import settings
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import document_repo
from app.schemas.requirement_upload import RequirementUploadSessionCreateIn

from . import file_service


SUPPORTED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"}


def upload_config() -> dict:
    return {
        "max_files": settings.REQUIREMENT_UPLOAD_MAX_FILES,
        "max_file_size_bytes": settings.REQUIREMENT_UPLOAD_MAX_FILE_SIZE_BYTES,
        "max_batch_size_bytes": settings.REQUIREMENT_UPLOAD_MAX_BATCH_SIZE_BYTES,
        "chunk_size_bytes": settings.REQUIREMENT_UPLOAD_CHUNK_SIZE_BYTES,
        "concurrency": settings.REQUIREMENT_UPLOAD_CONCURRENCY,
        "session_ttl_hours": settings.REQUIREMENT_UPLOAD_SESSION_TTL_HOURS,
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
    }


def create_session(project_id: str, payload: RequirementUploadSessionCreateIn, actor) -> dict:
    cleanup_expired_sessions()
    _validate_session_request(project_id, payload)
    _enforce_active_session_limit(actor["id"])

    upload_id = f"requpload-{secrets.token_hex(12)}"
    session_dir = _session_root() / upload_id
    session_dir.mkdir(parents=True, exist_ok=False)
    now = time.time()
    chunk_size_bytes = settings.REQUIREMENT_UPLOAD_CHUNK_SIZE_BYTES
    files = []
    for index, item in enumerate(payload.files, start=1):
        file_id = f"file-{index:03d}-{secrets.token_hex(4)}"
        file_dir = session_dir / file_id
        file_dir.mkdir()
        files.append(
            {
                "id": file_id,
                "filename": item.filename,
                "size": item.size,
                "sha256": item.sha256,
                "chunk_size_bytes": chunk_size_bytes,
                "chunk_count": math.ceil(item.size / chunk_size_bytes),
            }
        )

    metadata = {
        "id": upload_id,
        "project_id": project_id,
        "actor_id": actor["id"],
        "mode": payload.mode,
        "document_name": payload.document_name.strip(),
        "existing_document_id": payload.existing_document_id.strip(),
        "created_at": now,
        "expires_at": now + settings.REQUIREMENT_UPLOAD_SESSION_TTL_HOURS * 3600,
        "chunk_size_bytes": chunk_size_bytes,
        "files": files,
    }
    _metadata_path(session_dir).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return _serialize_session(metadata, session_dir)


def get_session(project_id: str, upload_id: str, actor) -> dict:
    metadata, session_dir = _load_owned_session(project_id, upload_id, actor)
    return _serialize_session(metadata, session_dir)


def cancel_session(project_id: str, upload_id: str, actor) -> dict:
    _, session_dir = _load_owned_session(project_id, upload_id, actor)
    shutil.rmtree(session_dir, ignore_errors=True)
    return {"success": True}


async def save_chunk(
    project_id: str,
    upload_id: str,
    file_id: str,
    part_number: int,
    body_stream,
    actor,
    *,
    expected_sha256: str = "",
) -> dict:
    metadata, session_dir = _load_owned_session(project_id, upload_id, actor)
    file_meta = _find_file(metadata, file_id)
    if part_number < 0 or part_number >= file_meta["chunk_count"]:
        raise api_error(404, "UPLOAD_PART_NOT_FOUND", "上传分片不存在。")

    expected_size = _expected_part_size(file_meta, part_number)
    part_path = _part_path(session_dir, file_id, part_number)
    normalized_hash = expected_sha256.strip().lower()
    if normalized_hash and (len(normalized_hash) != 64 or any(char not in "0123456789abcdef" for char in normalized_hash)):
        raise api_error(422, "UPLOAD_CHUNK_HASH_INVALID", "上传分片校验值格式不正确。")

    if part_path.exists() and part_path.stat().st_size == expected_size:
        if not normalized_hash or _sha256_path(part_path) == normalized_hash:
            return {"part_number": part_number, "size": expected_size, "completed": True}

    temporary_path = part_path.with_suffix(f".tmp-{secrets.token_hex(4)}")
    received = 0
    digest = hashlib.sha256()
    try:
        with temporary_path.open("wb") as target:
            async for chunk in body_stream:
                if not chunk:
                    continue
                received += len(chunk)
                if received > expected_size:
                    raise api_error(413, "UPLOAD_CHUNK_TOO_LARGE", "上传分片超过允许大小。")
                digest.update(chunk)
                target.write(chunk)
        if received != expected_size:
            raise api_error(422, "UPLOAD_CHUNK_SIZE_MISMATCH", "上传分片大小不正确。")
        if normalized_hash and digest.hexdigest() != normalized_hash:
            raise api_error(409, "UPLOAD_CHUNK_HASH_MISMATCH", "上传分片校验失败，请重新上传。")
        os.replace(temporary_path, part_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return {"part_number": part_number, "size": received, "completed": True}


async def complete_session(project_id: str, upload_id: str, actor) -> dict:
    metadata, session_dir = _load_owned_session(project_id, upload_id, actor)
    lock_path = session_dir / ".completing"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(lock_fd)
    except FileExistsError as exc:
        raise api_error(409, "UPLOAD_SESSION_COMPLETING", "上传会话正在完成，请勿重复提交。") from exc

    handles = []
    uploads: list[UploadFile] = []
    try:
        for file_meta in metadata["files"]:
            missing_parts = _missing_parts(session_dir, file_meta)
            if missing_parts:
                raise api_error(409, "UPLOAD_SESSION_INCOMPLETE", "仍有文件分片未上传完成。")
            assembled_path = session_dir / file_meta["id"] / "assembled.upload"
            digest = hashlib.sha256()
            total_size = 0
            with assembled_path.open("wb") as target:
                for part_number in range(file_meta["chunk_count"]):
                    with _part_path(session_dir, file_meta["id"], part_number).open("rb") as source:
                        while chunk := source.read(1024 * 1024):
                            digest.update(chunk)
                            total_size += len(chunk)
                            target.write(chunk)
            if total_size != file_meta["size"]:
                raise api_error(409, "UPLOAD_FILE_SIZE_MISMATCH", "合并后的文件大小校验失败。")
            if file_meta["sha256"] and digest.hexdigest() != file_meta["sha256"]:
                raise api_error(409, "UPLOAD_FILE_HASH_MISMATCH", "合并后的文件校验失败。")
            handle = assembled_path.open("rb")
            handles.append(handle)
            uploads.append(UploadFile(filename=file_meta["filename"], file=handle, size=file_meta["size"]))

        result = await file_service.upload_documents(
            project_id,
            uploads,
            actor,
            mode=metadata["mode"],
            document_name=metadata["document_name"],
            existing_document_id=metadata["existing_document_id"],
        )
        result["_upload_mode"] = metadata["mode"]
    except Exception:
        lock_path.unlink(missing_ok=True)
        raise
    finally:
        for handle in handles:
            handle.close()

    shutil.rmtree(session_dir, ignore_errors=True)
    return result


def cleanup_expired_sessions() -> None:
    root = _session_root()
    if not root.exists():
        return
    now = time.time()
    for session_dir in root.iterdir():
        if not session_dir.is_dir():
            continue
        try:
            metadata = json.loads(_metadata_path(session_dir).read_text(encoding="utf-8"))
            expired = float(metadata["expires_at"]) <= now
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            expired = session_dir.stat().st_mtime + settings.REQUIREMENT_UPLOAD_SESSION_TTL_HOURS * 3600 <= now
        if expired:
            shutil.rmtree(session_dir, ignore_errors=True)


def _validate_session_request(project_id: str, payload: RequirementUploadSessionCreateIn) -> None:
    if len(payload.files) > settings.REQUIREMENT_UPLOAD_MAX_FILES:
        raise api_error(422, "UPLOAD_FILE_COUNT_EXCEEDED", f"单次最多上传 {settings.REQUIREMENT_UPLOAD_MAX_FILES} 个文件。")
    total_size = sum(item.size for item in payload.files)
    if total_size > settings.REQUIREMENT_UPLOAD_MAX_BATCH_SIZE_BYTES:
        raise api_error(413, "UPLOAD_BATCH_TOO_LARGE", "单次上传文件总大小超过限制。")
    for item in payload.files:
        if item.size > settings.REQUIREMENT_UPLOAD_MAX_FILE_SIZE_BYTES:
            raise api_error(413, "UPLOAD_FILE_TOO_LARGE", f"单文件不能超过 {_max_file_size_mb()}MB：{item.filename}")
        if Path(item.filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise api_error(422, "UPLOAD_FILE_TYPE_UNSUPPORTED", f"不支持该文件类型：{item.filename}")

    with connect() as db:
        file_service.ensure_project_accepts_upload(db, project_id)
        if payload.mode == "new":
            name = payload.document_name.strip()
            if not name:
                raise api_error(400, "DOCUMENT_NAME_REQUIRED", "请填写需求名称。")
            if document_repo.find_by_project_and_name(db, project_id, name):
                raise api_error(422, "DOCUMENT_NAME_EXISTS", "该需求名称已存在。")
        else:
            document_id = payload.existing_document_id.strip()
            if not document_id:
                raise api_error(400, "DOCUMENT_ID_REQUIRED", "请选择已有需求。")
            if not document_repo.find_by_project_and_id(db, project_id, document_id):
                raise api_error(404, "DOCUMENT_NOT_FOUND", "需求文档不存在。")


def _enforce_active_session_limit(actor_id: str) -> None:
    root = _session_root()
    if not root.exists():
        return
    active = 0
    for session_dir in root.iterdir():
        try:
            metadata = json.loads(_metadata_path(session_dir).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("actor_id") == actor_id and float(metadata.get("expires_at", 0)) > time.time():
            active += 1
    if active >= settings.REQUIREMENT_UPLOAD_MAX_ACTIVE_SESSIONS_PER_USER:
        raise api_error(429, "UPLOAD_ACTIVE_SESSION_LIMIT", "进行中的上传任务过多，请完成或等待已有任务过期。")


def _load_owned_session(project_id: str, upload_id: str, actor) -> tuple[dict, Path]:
    if not upload_id.startswith("requpload-") or any(char in upload_id for char in "/\\"):
        raise api_error(404, "UPLOAD_SESSION_NOT_FOUND", "上传会话不存在。")
    session_dir = _session_root() / upload_id
    try:
        metadata = json.loads(_metadata_path(session_dir).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise api_error(404, "UPLOAD_SESSION_NOT_FOUND", "上传会话不存在。") from exc
    if metadata.get("project_id") != project_id or metadata.get("actor_id") != actor["id"]:
        raise api_error(404, "UPLOAD_SESSION_NOT_FOUND", "上传会话不存在。")
    if float(metadata.get("expires_at", 0)) <= time.time():
        shutil.rmtree(session_dir, ignore_errors=True)
        raise api_error(410, "UPLOAD_SESSION_EXPIRED", "上传会话已过期，请重新开始上传。")
    return metadata, session_dir


def _serialize_session(metadata: dict, session_dir: Path) -> dict:
    return {
        "id": metadata["id"],
        "project_id": metadata["project_id"],
        "expires_at": metadata["expires_at"],
        "chunk_size_bytes": metadata["chunk_size_bytes"],
        "concurrency": settings.REQUIREMENT_UPLOAD_CONCURRENCY,
        "files": [
            {
                **file_meta,
                "uploaded_parts": _uploaded_parts(session_dir, file_meta),
            }
            for file_meta in metadata["files"]
        ],
    }


def _uploaded_parts(session_dir: Path, file_meta: dict) -> list[int]:
    return [
        part_number
        for part_number in range(file_meta["chunk_count"])
        if _part_path(session_dir, file_meta["id"], part_number).exists()
        and _part_path(session_dir, file_meta["id"], part_number).stat().st_size
        == _expected_part_size(file_meta, part_number)
    ]


def _missing_parts(session_dir: Path, file_meta: dict) -> list[int]:
    uploaded = set(_uploaded_parts(session_dir, file_meta))
    return [part_number for part_number in range(file_meta["chunk_count"]) if part_number not in uploaded]


def _find_file(metadata: dict, file_id: str) -> dict:
    file_meta = next((item for item in metadata["files"] if item["id"] == file_id), None)
    if file_meta is None:
        raise api_error(404, "UPLOAD_FILE_NOT_FOUND", "上传文件不存在。")
    return file_meta


def _expected_part_size(file_meta: dict, part_number: int) -> int:
    chunk_size_bytes = file_meta["chunk_size_bytes"]
    offset = part_number * chunk_size_bytes
    return min(chunk_size_bytes, file_meta["size"] - offset)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _part_path(session_dir: Path, file_id: str, part_number: int) -> Path:
    return session_dir / file_id / f"part-{part_number:05d}"


def _metadata_path(session_dir: Path) -> Path:
    return session_dir / "session.json"


def _session_root() -> Path:
    return settings.DATA_DIR / ".uploads" / "requirements"


def _max_file_size_mb() -> int:
    return settings.REQUIREMENT_UPLOAD_MAX_FILE_SIZE_BYTES // 1024 // 1024
