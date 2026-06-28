"""Event emitter for exploration progress

Emits events during exploration for SSE streaming to frontend.
"""

from typing import Optional, Callable, Dict, Any
from datetime import datetime, UTC
from enum import Enum


class EventType(str, Enum):
    """Event types for exploration progress"""

    STARTED = "exploration.started"
    PROGRESS = "exploration.progress"
    PAGE_DISCOVERED = "exploration.page_discovered"
    PAGE_COMPLETED = "exploration.page_completed"
    PAGE_FAILED = "exploration.page_failed"
    ERROR = "exploration.error"
    COMPLETED = "exploration.completed"
    FAILED = "exploration.failed"


class EventEmitter:
    """Emits events during exploration process"""

    def __init__(self):
        self._listeners: list[Callable[[Dict[Any, Any]], None]] = []

    def on(self, listener: Callable[[Dict[Any, Any]], None]) -> None:
        """
        Register an event listener.

        Args:
            listener: Callback function that receives event data
        """
        self._listeners.append(listener)

    def off(self, listener: Callable[[Dict[Any, Any]], None]) -> None:
        """
        Unregister an event listener.

        Args:
            listener: Callback function to remove
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """
        Emit an event to all listeners.

        Args:
            event_type: Type of event
            data: Event data
        """
        event = {
            "type": event_type.value,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "data": data,
        }

        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                # Log error but don't stop other listeners
                print(f"Error in event listener: {e}")

    def emit_started(
        self, run_id: str, start_url: str, max_pages: int, max_depth: int
    ) -> None:
        """Emit exploration started event"""
        self.emit(
            EventType.STARTED,
            {
                "run_id": run_id,
                "start_url": start_url,
                "max_pages": max_pages,
                "max_depth": max_depth,
            },
        )

    def emit_progress(
        self,
        run_id: str,
        current_url: str,
        pages_explored: int,
        queue_size: int,
        progress_percentage: float,
        message: Optional[str] = None,
    ) -> None:
        """Emit exploration progress event"""
        self.emit(
            EventType.PROGRESS,
            {
                "run_id": run_id,
                "current_url": current_url,
                "pages_explored": pages_explored,
                "queue_size": queue_size,
                "progress_percentage": round(progress_percentage, 2),
                "message": message or f"Exploring {current_url}",
            },
        )

    def emit_page_discovered(
        self, run_id: str, page_id: str, normalized_path: str, depth: int
    ) -> None:
        """Emit page discovered event"""
        self.emit(
            EventType.PAGE_DISCOVERED,
            {
                "run_id": run_id,
                "page_id": page_id,
                "normalized_path": normalized_path,
                "depth": depth,
            },
        )

    def emit_page_completed(
        self,
        run_id: str,
        page_id: str,
        normalized_path: str,
        elements_count: int,
        duration_seconds: float,
    ) -> None:
        """Emit page exploration completed event"""
        self.emit(
            EventType.PAGE_COMPLETED,
            {
                "run_id": run_id,
                "page_id": page_id,
                "normalized_path": normalized_path,
                "elements_count": elements_count,
                "duration_seconds": round(duration_seconds, 2),
            },
        )

    def emit_page_failed(
        self, run_id: str, page_id: str, normalized_path: str, error: str
    ) -> None:
        """Emit page exploration failed event"""
        self.emit(
            EventType.PAGE_FAILED,
            {
                "run_id": run_id,
                "page_id": page_id,
                "normalized_path": normalized_path,
                "error": error,
            },
        )

    def emit_error(self, run_id: str, error: str, context: Optional[Dict] = None) -> None:
        """Emit error event"""
        self.emit(
            EventType.ERROR,
            {
                "run_id": run_id,
                "error": error,
                "context": context or {},
            },
        )

    def emit_completed(
        self,
        run_id: str,
        pages_explored: int,
        elements_found: int,
        duration_seconds: float,
        artifacts: Dict[str, str],
    ) -> None:
        """Emit exploration completed event"""
        self.emit(
            EventType.COMPLETED,
            {
                "run_id": run_id,
                "pages_explored": pages_explored,
                "elements_found": elements_found,
                "duration_seconds": round(duration_seconds, 2),
                "artifacts": artifacts,
            },
        )

    def emit_failed(
        self, run_id: str, error: str, pages_explored: int, duration_seconds: float
    ) -> None:
        """Emit exploration failed event"""
        self.emit(
            EventType.FAILED,
            {
                "run_id": run_id,
                "error": error,
                "pages_explored": pages_explored,
                "duration_seconds": round(duration_seconds, 2),
            },
        )

    def clear(self) -> None:
        """Clear all event listeners"""
        self._listeners.clear()
