import threading
import re
from contextlib import contextmanager
from pathlib import Path

from app.core import storage


_project_locks: dict[str, threading.RLock] = {}
_project_locks_guard = threading.Lock()


def project_suite_path(project_id: str) -> Path:
    return storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "pytest_requests"


def scenario_file_key(*, scenario_id: str, name: str) -> str:
    return _slugify(f"{name}_{scenario_id}")


def materialize_scenario_snapshot(project_id: str, snapshot: dict) -> dict:
    suite_path = project_suite_path(project_id)
    scenario_key = scenario_file_key(scenario_id=snapshot["id"], name=snapshot["name"])
    files = render_scenario_files(scenario_key, snapshot)
    written = {}
    for file_key, content in files.items():
        target = resolve_suite_file(suite_path, file_key)
        write_atomic(target, content)
        written[file_key] = target
    scenario_dir = f"scenarios/{scenario_key}"
    return {
        "suite_path": suite_path,
        "test_file_path": written[f"{scenario_dir}/test_scenario.py"],
        "data_file_path": written[f"{scenario_dir}/scenario.json"],
        "scenario_key": scenario_key,
    }


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


def resolve_suite_file(suite_path: Path, file_key: str) -> Path:
    candidate = (suite_path / file_key).resolve()
    candidate.relative_to(suite_path.resolve())
    return candidate


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    return re.sub(r"_+", "_", slug) or "generated"
