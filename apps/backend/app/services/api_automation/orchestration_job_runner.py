from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable


class OrchestrationJobRunner:
    def __init__(self, *, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="api-scenario-plan")
        self._lock = threading.Lock()
        self._futures: dict[str, Future[Any]] = {}

    def submit(self, plan_id: str, work: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        with self._lock:
            current = self._futures.get(plan_id)
            if current is not None and not current.done():
                return False
            future = self._executor.submit(work, *args, **kwargs)
            self._futures[plan_id] = future
            future.add_done_callback(lambda _future: self._forget(plan_id, _future))
            return True

    def cancel(self, plan_id: str) -> bool:
        with self._lock:
            future = self._futures.get(plan_id)
            return bool(future and future.cancel())

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _forget(self, plan_id: str, future: Future[Any]) -> None:
        with self._lock:
            if self._futures.get(plan_id) is future:
                self._futures.pop(plan_id, None)


job_runner = OrchestrationJobRunner()


__all__ = ["OrchestrationJobRunner", "job_runner"]
