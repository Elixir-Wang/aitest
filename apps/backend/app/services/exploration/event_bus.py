import queue
import threading
from collections.abc import Iterator
from typing import Any

_TERMINAL_EVENT = object()
_subscribers: dict[str, set[queue.Queue[dict[str, Any] | object]]] = {}
_lock = threading.Lock()


def publish(run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    event = {
        "type": event_type,
        "run_id": run_id,
        "payload": payload or {},
    }
    with _lock:
        subscribers = list(_subscribers.get(run_id, set()))
    for subscriber in subscribers:
        subscriber.put(event)


def close(run_id: str) -> None:
    with _lock:
        subscribers = list(_subscribers.pop(run_id, set()))
    for subscriber in subscribers:
        subscriber.put(_TERMINAL_EVENT)


def subscribe(run_id: str, *, heartbeat_seconds: float = 15.0) -> Iterator[dict[str, Any] | None]:
    subscriber: queue.Queue[dict[str, Any] | object] = queue.Queue()
    with _lock:
        _subscribers.setdefault(run_id, set()).add(subscriber)
    try:
        while True:
            try:
                event = subscriber.get(timeout=heartbeat_seconds)
            except queue.Empty:
                yield None
                continue
            if event is _TERMINAL_EVENT:
                return
            yield event  # type: ignore[misc]
    finally:
        with _lock:
            subscribers = _subscribers.get(run_id)
            if subscribers is not None:
                subscribers.discard(subscriber)
                if not subscribers:
                    _subscribers.pop(run_id, None)


def reset_for_tests() -> None:
    with _lock:
        subscribers = [subscriber for group in _subscribers.values() for subscriber in group]
        _subscribers.clear()
    for subscriber in subscribers:
        subscriber.put(_TERMINAL_EVENT)
