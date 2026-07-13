import threading
from contextlib import contextmanager
from pathlib import Path

from app.agents.api_automation.pytest_requests.renderer import render_scenario_files, slugify
from app.agents.api_automation.pytest_requests.schemas import PytestRequestsGenerationResult
from app.core import storage


_project_locks: dict[str, threading.RLock] = {}
_project_locks_guard = threading.Lock()


def project_suite_path(project_id: str) -> Path:
    return storage.PROJECT_FILE_STORAGE_ROOT / project_id / "api_automation" / "pytest_requests"


def endpoint_file_key(*, endpoint_id: str, method: str, path: str) -> str:
    return slugify(f"{method}_{path}_{endpoint_id}")


def scenario_file_key(*, scenario_id: str, name: str) -> str:
    return slugify(f"{name}_{scenario_id}")


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


def materialize_generation_result(project_id: str, result: PytestRequestsGenerationResult) -> dict:
    suite_path = project_suite_path(project_id)
    written = {}
    for generated_file in result.files:
        target = resolve_suite_file(suite_path, generated_file.key)
        write_atomic(target, generated_file.content)
        written[generated_file.key] = target
    test_key = next(file.key for file in result.files if file.kind == "test")
    data_key = next(file.key for file in result.files if file.kind == "data")
    return {
        "endpoint_id": result.endpoint_id,
        "suite_path": suite_path,
        "test_file_path": written[test_key],
        "data_file_path": written[data_key],
        "script_name": result.endpoint_key,
    }


def snapshot_endpoint_artifacts(project_id: str, result: PytestRequestsGenerationResult) -> dict:
    suite_path = project_suite_path(project_id)
    files = {}
    for generated_file in result.files:
        if generated_file.kind not in {"test", "data"}:
            continue
        target = resolve_suite_file(suite_path, generated_file.key)
        files[target] = target.read_text(encoding="utf-8") if target.exists() else None
    return {"suite_path": suite_path, "files": files}


def restore_endpoint_artifacts(snapshot: dict) -> None:
    suite_path = Path(snapshot["suite_path"]).resolve()
    parents = set()
    for raw_path, content in snapshot["files"].items():
        path = Path(raw_path).resolve()
        path.relative_to(suite_path)
        parents.add(path.parent)
        if content is None:
            if path.exists() and path.is_file():
                path.unlink()
        else:
            write_atomic(path, content)
    endpoints_root = (suite_path / "endpoints").resolve()
    for parent in parents:
        if parent.parent == endpoints_root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()


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
