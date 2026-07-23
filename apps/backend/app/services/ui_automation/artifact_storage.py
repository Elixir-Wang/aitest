from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path

import yaml


_shared_lock = threading.RLock()


@contextmanager
def project_workspace_lock(project_id: str):
    del project_id
    with _shared_lock:
        yield


def write_yaml_atomic(path: Path, payload: dict, *, suite_path: Path) -> None:
    _ensure_in_suite(path, suite_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.replace(path)


def _ensure_in_suite(path: Path, suite_path: Path) -> None:
    try:
        path.resolve().relative_to(suite_path.resolve())
    except ValueError as exc:
        raise ValueError("目标文件必须位于 pytest_playwright 工程目录内。") from exc


__all__ = ["project_workspace_lock", "write_yaml_atomic"]
