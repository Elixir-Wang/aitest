import threading
from contextlib import contextmanager
from pathlib import Path

from app.core import storage


_project_locks: dict[str, threading.RLock] = {}
_project_locks_guard = threading.Lock()


def project_suite_path(project_id: str) -> Path:
    return storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "pytest_requests"


def endpoint_file_key(*, endpoint_id: str, method: str, path: str) -> str:
    from app.services.api_automation.script_generator import slugify

    return slugify(f"{method}_{path}_{endpoint_id}")


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


@contextmanager
def project_workspace_lock(project_id: str):
    with _project_locks_guard:
        lock = _project_locks.setdefault(project_id, threading.RLock())
    with lock:
        yield


def relative_file_key(suite_path: Path, file_path: Path) -> str:
    return file_path.resolve().relative_to(suite_path.resolve()).as_posix()


def resolve_suite_file(suite_path: Path, file_key: str) -> Path:
    candidate = (suite_path / file_key).resolve()
    candidate.relative_to(suite_path.resolve())
    return candidate
