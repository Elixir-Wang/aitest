import queue
import threading
from collections import deque
from collections.abc import Iterator
from typing import Any

_TERMINAL_EVENT = object()
_MAX_RECENT_EVENTS = 200
_subscribers: dict[str, set[queue.Queue[dict[str, Any] | object]]] = {}
_recent_events: dict[str, deque[dict[str, Any]]] = {}
_event_sequences: dict[str, int] = {}
_lock = threading.Lock()


def publish(run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    with _lock:
        event_id = _event_sequences.get(run_id, 0) + 1
        _event_sequences[run_id] = event_id
        event = {
            "event_id": event_id,
            "type": event_type,
            "run_id": run_id,
            "payload": payload or {},
        }
        _recent_events.setdefault(run_id, deque(maxlen=_MAX_RECENT_EVENTS)).append(event)
        subscribers = list(_subscribers.get(run_id, set()))
    for subscriber in subscribers:
        subscriber.put(event)


def close(run_id: str) -> None:
    with _lock:
        subscribers = list(_subscribers.pop(run_id, set()))
    for subscriber in subscribers:
        subscriber.put(_TERMINAL_EVENT)


def recent_events(run_id: str, *, after_event_id: int = 0) -> list[dict[str, Any]]:
    with _lock:
        events = list(_recent_events.get(run_id, ()))
    if after_event_id <= 0:
        return events
    return [event for event in events if int(event.get("event_id") or 0) > after_event_id]


def latest_event_id(run_id: str) -> int:
    with _lock:
        return _event_sequences.get(run_id, 0)


def reset_run(run_id: str) -> None:
    with _lock:
        subscribers = list(_subscribers.pop(run_id, set()))
        _recent_events.pop(run_id, None)
        _event_sequences.pop(run_id, None)
    for subscriber in subscribers:
        subscriber.put(_TERMINAL_EVENT)


def subscribe(
    run_id: str,
    *,
    heartbeat_seconds: float = 15.0,
    after_event_id: int = 0,
) -> Iterator[dict[str, Any] | None]:
    subscriber: queue.Queue[dict[str, Any] | object] = queue.Queue()
    with _lock:
        _subscribers.setdefault(run_id, set()).add(subscriber)
        replay_events = [
            event
            for event in _recent_events.get(run_id, ())
            if int(event.get("event_id") or 0) > after_event_id
        ]
    try:
        for event in replay_events:
            yield event
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
        _recent_events.clear()
        _event_sequences.clear()
    for subscriber in subscribers:
        subscriber.put(_TERMINAL_EVENT)
