"""Tests for FastAPI page exploration routes"""

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import json

from app.api.routes.page_exploration import router, active_runs, event_emitters


@pytest.fixture
def app():
    """Create FastAPI app with router"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup after each test"""
    yield
    active_runs.clear()
    event_emitters.clear()


def test_create_exploration_run(client):
    """Test creating exploration run"""
    request_data = {
        "project_id": "proj-test",
        "start_url": "https://test.com/start",
        "max_depth": 3,
        "max_pages": 50,
        "max_duration_seconds": 3600,
    }

    response = client.post("/api/exploration/runs", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert "run_id" in data
    assert data["project_id"] == "proj-test"
    assert data["start_url"] == "https://test.com/start"
    assert data["status"] == "pending"
    assert "created_at" in data


def test_create_exploration_run_with_scope(client):
    """Test creating exploration run with custom scope"""
    request_data = {
        "project_id": "proj-test",
        "start_url": "https://test.com/workspace/start",
        "scope": "https://test.com/workspace",
        "max_depth": 2,
        "max_pages": 20,
        "max_duration_seconds": 1800,
    }

    response = client.post("/api/exploration/runs", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"


def test_create_exploration_run_validation(client):
    """Test request validation"""
    # Missing required field
    request_data = {
        "project_id": "proj-test",
        # Missing start_url
    }

    response = client.post("/api/exploration/runs", json=request_data)
    assert response.status_code == 422  # Validation error


def test_create_exploration_run_depth_validation(client):
    """Test max_depth validation"""
    request_data = {
        "project_id": "proj-test",
        "start_url": "https://test.com/start",
        "max_depth": 0,  # Invalid: must be >= 1
    }

    response = client.post("/api/exploration/runs", json=request_data)
    assert response.status_code == 422


def test_get_exploration_run(client):
    """Test getting exploration run status"""
    # Create a run first
    create_response = client.post(
        "/api/exploration/runs",
        json={
            "project_id": "proj-test",
            "start_url": "https://test.com/start",
        },
    )
    run_id = create_response.json()["run_id"]

    # Get the run
    response = client.get(f"/api/exploration/runs/{run_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert data["project_id"] == "proj-test"


def test_get_exploration_run_not_found(client):
    """Test getting non-existent run"""
    response = client.get("/api/exploration/runs/non-existent-run")
    assert response.status_code == 404


def test_stream_exploration_events(client):
    """Test SSE event streaming"""
    # Create a run first
    create_response = client.post(
        "/api/exploration/runs",
        json={
            "project_id": "proj-test",
            "start_url": "https://test.com/start",
        },
    )
    run_id = create_response.json()["run_id"]

    # Stream events (this will test the endpoint exists and returns SSE)
    with client.stream("GET", f"/api/exploration/runs/{run_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read first event (connected event)
        first_chunk = next(response.iter_lines())
        assert b"event: connected" in first_chunk or b"exploration.started" in first_chunk


def test_stream_exploration_events_not_found(client):
    """Test streaming events for non-existent run"""
    response = client.get("/api/exploration/runs/non-existent-run/events")
    assert response.status_code == 404


def test_exploration_run_response_model():
    """Test ExplorationRunResponse model"""
    from app.api.routes.page_exploration import ExplorationRunResponse

    response = ExplorationRunResponse(
        run_id="run-001",
        project_id="proj-test",
        start_url="https://test.com",
        status="completed",
        created_at="2026-06-27T10:00:00Z",
        started_at="2026-06-27T10:00:01Z",
        completed_at="2026-06-27T10:05:00Z",
        pages_discovered=10,
        duration_seconds=299.5,
    )

    assert response.run_id == "run-001"
    assert response.status == "completed"
    assert response.pages_discovered == 10


def test_create_exploration_request_model():
    """Test CreateExplorationRequest model"""
    from app.api.routes.page_exploration import CreateExplorationRequest

    request = CreateExplorationRequest(
        project_id="proj-test",
        start_url="https://test.com/start",
        max_depth=3,
        max_pages=50,
    )

    assert request.project_id == "proj-test"
    assert request.max_depth == 3
    assert request.max_pages == 50
    assert request.max_duration_seconds == 3600  # Default value


def test_multiple_concurrent_runs(client):
    """Test creating multiple concurrent runs"""
    run_ids = []

    for i in range(3):
        response = client.post(
            "/api/exploration/runs",
            json={
                "project_id": f"proj-{i}",
                "start_url": f"https://test{i}.com/start",
            },
        )
        assert response.status_code == 200
        run_ids.append(response.json()["run_id"])

    # All runs should be different
    assert len(set(run_ids)) == 3

    # All runs should be retrievable
    for run_id in run_ids:
        response = client.get(f"/api/exploration/runs/{run_id}")
        assert response.status_code == 200
