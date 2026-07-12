"""Persistent asynchronous replay run lifecycle."""

import json
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.settings import PROJECT_FILE_STORAGE_ROOT

from .service import ReplayService


_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ui-replay")
_lock = threading.Lock()
_stop_flags: set[str] = set()


class ReplayRunService:
    def __init__(self, storage_root: Path | None = None) -> None:
        self._storage_root = Path(storage_root or PROJECT_FILE_STORAGE_ROOT)

    def start(
        self,
        *,
        project_id: str,
        environment_id: str,
        operation_key: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict:
        run_id = f"replay-{secrets.token_hex(8)}"
        run = {
            "id": run_id,
            "project_id": project_id,
            "environment_id": environment_id,
            "operation_key": operation_key,
            "parameters": parameters or {},
            "status": "pending",
            "steps": [],
            "error": "",
            "created_at": self._now(),
            "started_at": None,
            "finished_at": None,
        }
        self._write(run)
        _executor.submit(self._execute, run_id)
        return run

    def get(self, project_id: str, run_id: str) -> dict:
        run = self._read(project_id, run_id)
        if run is None:
            raise ValueError("Replay run 不存在。")
        return run

    def stop(self, project_id: str, run_id: str) -> dict:
        run = self.get(project_id, run_id)
        if run["status"] in {"passed", "failed", "cancelled"}:
            return run
        with _lock:
            _stop_flags.add(run_id)
        run["status"] = "stopping"
        self._write(run)
        return run

    def retry(self, project_id: str, run_id: str) -> dict:
        previous = self.get(project_id, run_id)
        return self.start(
            project_id=project_id,
            environment_id=previous["environment_id"],
            operation_key=previous["operation_key"],
            parameters=previous.get("parameters") or {},
        )

    def _execute(self, run_id: str) -> None:
        run = self._find_run(run_id)
        if run is None:
            return
        run["status"] = "running"
        run["started_at"] = self._now()
        self._write(run)
        try:
            result = ReplayService(storage_root=self._storage_root).execute(
                project_id=run["project_id"],
                environment_id=run["environment_id"],
                operation_key=run["operation_key"],
                parameters=run.get("parameters") or {},
                should_stop=lambda: self._should_stop(run_id),
                on_step=lambda step: self._record_step(run, step.model_dump(mode="json")),
            )
            run = self.get(run["project_id"], run_id)
            run["status"] = "cancelled" if self._should_stop(run_id) else ("passed" if result.success else "failed")
        except Exception as exc:
            run = self.get(run["project_id"], run_id)
            run["status"] = "cancelled" if self._should_stop(run_id) else "failed"
            run["error"] = str(exc)
        finally:
            run["finished_at"] = self._now()
            self._write(run)
            with _lock:
                _stop_flags.discard(run_id)

    def _record_step(self, run: dict, step: dict) -> None:
        latest = self.get(run["project_id"], run["id"])
        latest["steps"].append(step)
        self._write(latest)

    def _should_stop(self, run_id: str) -> bool:
        with _lock:
            return run_id in _stop_flags

    def _find_run(self, run_id: str) -> dict | None:
        for path in self._storage_root.glob(f"*/page_exploration/replay-runs/{run_id}.json"):
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _read(self, project_id: str, run_id: str) -> dict | None:
        path = self._path(project_id, run_id)
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def _write(self, run: dict) -> None:
        path = self._path(run["project_id"], run["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def _path(self, project_id: str, run_id: str) -> Path:
        return self._storage_root / project_id / "page_exploration" / "replay-runs" / f"{run_id}.json"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
