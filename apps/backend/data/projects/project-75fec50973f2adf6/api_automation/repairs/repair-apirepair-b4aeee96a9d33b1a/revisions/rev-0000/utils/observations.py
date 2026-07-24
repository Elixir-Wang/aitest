"""Oracle 观察证据的脱敏与并发安全持久化。"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "cybertron-robot-key",
    "cybertron-robot-token",
}
_SENSITIVE_BODY_PARTS = (
    "token",
    "password",
    "secret",
    "cookie",
    "authorization",
    "api_key",
    "apikey",
)
_MAX_TEXT_LENGTH = 4096


def record_observation(case: dict, response) -> None:
    """将 inferred/needs_confirmation 响应追加到指定 JSON 文件。"""
    target = os.environ.get("API_OBSERVATION_RESULT_PATH", "")
    if not target:
        return

    path = Path(target).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    observation = {
        "case_id": case.get("case_id", ""),
        "test_point_key": case.get("test_point_key", ""),
        "status_code": getattr(response, "status_code", None),
        "response_headers": _sanitize_headers(getattr(response, "headers", {})),
        "response_body": _sanitize_body(response),
    }
    _merge_observation(path, observation)


def _sanitize_headers(headers) -> dict:
    return {
        str(name): value
        for name, value in dict(headers or {}).items()
        if str(name).lower() not in _SENSITIVE_HEADERS
    }


def _sanitize_body(response):
    content = getattr(response, "content", b"") or b""
    content_type = str(getattr(response, "headers", {}).get("Content-Type", "")).lower()
    try:
        return _redact(response.json())
    except Exception:
        if _is_textual(content_type, content):
            text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
            return {
                "type": "text",
                "content": text[:_MAX_TEXT_LENGTH],
                "truncated": len(text) > _MAX_TEXT_LENGTH,
            }
        raw = content if isinstance(content, bytes) else str(content).encode("utf-8", errors="replace")
        return {
            "type": "binary",
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }


def _is_textual(content_type: str, content) -> bool:
    if content_type.startswith("text/") or "json" in content_type or "xml" in content_type:
        return True
    if not isinstance(content, bytes):
        return True
    try:
        content[:_MAX_TEXT_LENGTH].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _redact(value):
    if isinstance(value, dict):
        return {
            key: "***" if _is_sensitive_name(key) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _is_sensitive_name(name) -> bool:
    normalized = str(name).lower()
    return any(part in normalized for part in _SENSITIVE_BODY_PARTS)


def _merge_observation(path: Path, observation: dict) -> None:
    lock_path = path.with_name(f"{path.name}.lock")
    with _locked_file(lock_path):
        existing = _read_observations(path)
        key = (observation["case_id"], observation["test_point_key"])
        merged = [
            item
            for item in existing
            if (item.get("case_id"), item.get("test_point_key")) != key
        ]
        merged.append(observation)
        _atomic_write(path, {"observations": merged})


def _read_observations(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict) and isinstance(payload.get("observations"), list):
        return payload["observations"]
    if isinstance(payload, list):
        return payload
    return []


def _atomic_write(path: Path, payload: dict) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


@contextmanager
def _locked_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if handle.tell() == 0 and handle.read(1) == b"":
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
