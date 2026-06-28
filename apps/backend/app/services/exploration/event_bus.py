"""In-memory event bus for page exploration realtime updates."""

from __future__ import annotations

import asyncio
import itertools
import threading
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Any, AsyncGenerator


_MAX_HISTORY = 200
_STOP = object()

_lock = threading.Lock()
_event_counter = itertools.count(1)
_subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
_history: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=_MAX_HISTORY))


def publish(run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Publish a realtime exploration event to current subscribers."""
    event = {
        "event_id": next(_event_counter),
        "type": event_type,
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": payload or {},
    }
    with _lock:
        _history[run_id].append(event)
        subscribers = list(_subscribers.get(run_id, set()))

    for queue in subscribers:
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
    return event


async def subscribe(run_id: str, after_event_id: int | None = None) -> AsyncGenerator[dict[str, Any], None]:
    """Subscribe to run events, replaying recent history before live updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    with _lock:
        _subscribers[run_id].add(queue)
        replay = list(_history.get(run_id, ()))

    try:
        for event in replay:
            event_id = int(event.get("event_id") or 0)
            if after_event_id is None or event_id > after_event_id:
                yield event
        while True:
            event = await queue.get()
            if event is _STOP:
                break
            yield event
    finally:
        with _lock:
            subscribers = _subscribers.get(run_id)
            if subscribers is not None:
                subscribers.discard(queue)
                if not subscribers:
                    _subscribers.pop(run_id, None)


def close(run_id: str) -> None:
    """Wake active subscribers so completed streams can exit promptly."""
    with _lock:
        subscribers = list(_subscribers.get(run_id, set()))
    for queue in subscribers:
        try:
            queue.put_nowait(_STOP)
        except asyncio.QueueFull:
            pass


def clear(run_id: str | None = None) -> None:
    """Clear event history. Intended for tests and run restarts."""
    with _lock:
        if run_id is None:
            _history.clear()
            _subscribers.clear()
            return
        _history.pop(run_id, None)
