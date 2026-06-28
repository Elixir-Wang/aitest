"""Tests for EventEmitter"""

import pytest
from app.agents.page_exploration.event_emitter import EventEmitter, EventType


def test_event_emitter_initialization():
    """Test event emitter initialization"""
    emitter = EventEmitter()
    assert len(emitter._listeners) == 0


def test_register_listener():
    """Test registering event listener"""
    emitter = EventEmitter()
    events = []

    def listener(event):
        events.append(event)

    emitter.on(listener)
    assert len(emitter._listeners) == 1


def test_unregister_listener():
    """Test unregistering event listener"""
    emitter = EventEmitter()

    def listener(event):
        pass

    emitter.on(listener)
    assert len(emitter._listeners) == 1

    emitter.off(listener)
    assert len(emitter._listeners) == 0


def test_emit_event():
    """Test emitting event to listeners"""
    emitter = EventEmitter()
    events = []

    def listener(event):
        events.append(event)

    emitter.on(listener)
    emitter.emit(EventType.STARTED, {"run_id": "run-001"})

    assert len(events) == 1
    assert events[0]["type"] == "exploration.started"
    assert events[0]["data"]["run_id"] == "run-001"
    assert "timestamp" in events[0]


def test_emit_to_multiple_listeners():
    """Test emitting to multiple listeners"""
    emitter = EventEmitter()
    events1 = []
    events2 = []

    def listener1(event):
        events1.append(event)

    def listener2(event):
        events2.append(event)

    emitter.on(listener1)
    emitter.on(listener2)

    emitter.emit(EventType.PROGRESS, {"pages_explored": 5})

    assert len(events1) == 1
    assert len(events2) == 1
    assert events1[0] == events2[0]


def test_emit_started():
    """Test emit_started convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_started(
        run_id="run-001",
        start_url="https://test.com/start",
        max_pages=50,
        max_depth=3,
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.started"
    assert events[0]["data"]["run_id"] == "run-001"
    assert events[0]["data"]["start_url"] == "https://test.com/start"
    assert events[0]["data"]["max_pages"] == 50
    assert events[0]["data"]["max_depth"] == 3


def test_emit_progress():
    """Test emit_progress convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_progress(
        run_id="run-001",
        current_url="https://test.com/page1",
        pages_explored=5,
        queue_size=10,
        progress_percentage=33.33,
        message="Exploring page 1",
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.progress"
    assert events[0]["data"]["pages_explored"] == 5
    assert events[0]["data"]["queue_size"] == 10
    assert events[0]["data"]["progress_percentage"] == 33.33
    assert events[0]["data"]["message"] == "Exploring page 1"


def test_emit_page_discovered():
    """Test emit_page_discovered convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_page_discovered(
        run_id="run-001",
        page_id="page-workspace-agents",
        normalized_path="/workspace/agents",
        depth=1,
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.page_discovered"
    assert events[0]["data"]["page_id"] == "page-workspace-agents"
    assert events[0]["data"]["depth"] == 1


def test_emit_page_completed():
    """Test emit_page_completed convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_page_completed(
        run_id="run-001",
        page_id="page-workspace-agents",
        normalized_path="/workspace/agents",
        elements_count=15,
        duration_seconds=2.5,
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.page_completed"
    assert events[0]["data"]["elements_count"] == 15
    assert events[0]["data"]["duration_seconds"] == 2.5


def test_emit_page_failed():
    """Test emit_page_failed convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_page_failed(
        run_id="run-001",
        page_id="page-not-found",
        normalized_path="/not-found",
        error="Page not found",
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.page_failed"
    assert events[0]["data"]["error"] == "Page not found"


def test_emit_error():
    """Test emit_error convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_error(
        run_id="run-001", error="Timeout", context={"url": "https://test.com/slow"}
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.error"
    assert events[0]["data"]["error"] == "Timeout"
    assert events[0]["data"]["context"]["url"] == "https://test.com/slow"


def test_emit_completed():
    """Test emit_completed convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_completed(
        run_id="run-001",
        pages_explored=10,
        elements_found=150,
        duration_seconds=30.5,
        artifacts={"report": "path/to/report.md"},
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.completed"
    assert events[0]["data"]["pages_explored"] == 10
    assert events[0]["data"]["elements_found"] == 150
    assert events[0]["data"]["duration_seconds"] == 30.5


def test_emit_failed():
    """Test emit_failed convenience method"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit_failed(
        run_id="run-001",
        error="Authentication failed",
        pages_explored=5,
        duration_seconds=10.0,
    )

    assert len(events) == 1
    assert events[0]["type"] == "exploration.failed"
    assert events[0]["data"]["error"] == "Authentication failed"


def test_listener_exception_handling():
    """Test that listener exceptions don't break other listeners"""
    emitter = EventEmitter()
    events = []

    def bad_listener(event):
        raise Exception("Listener error")

    def good_listener(event):
        events.append(event)

    emitter.on(bad_listener)
    emitter.on(good_listener)

    emitter.emit(EventType.PROGRESS, {"test": "data"})

    # Good listener should still receive the event
    assert len(events) == 1


def test_clear_listeners():
    """Test clearing all listeners"""
    emitter = EventEmitter()

    emitter.on(lambda e: None)
    emitter.on(lambda e: None)
    assert len(emitter._listeners) == 2

    emitter.clear()
    assert len(emitter._listeners) == 0


def test_event_timestamp_format():
    """Test that event timestamp is in correct ISO format"""
    emitter = EventEmitter()
    events = []

    emitter.on(lambda e: events.append(e))
    emitter.emit(EventType.STARTED, {})

    timestamp = events[0]["timestamp"]
    assert timestamp.endswith("Z")
    # Verify it's a valid datetime
    from datetime import datetime

    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
