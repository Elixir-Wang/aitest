"""FastAPI routes for page exploration

Provides HTTP API for creating and monitoring page exploration runs.
"""

from typing import Optional, AsyncIterator
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import asyncio
from datetime import datetime, UTC

from app.agents.page_exploration.orchestrator import ExplorationOrchestrator
from app.agents.page_exploration.event_emitter import EventEmitter

router = APIRouter(prefix="/api/exploration", tags=["page_exploration"])

# In-memory storage for active runs (replace with DB in production)
active_runs: dict[str, dict] = {}
event_emitters: dict[str, EventEmitter] = {}


class CreateExplorationRequest(BaseModel):
    """Request model for creating exploration run"""

    project_id: str = Field(..., description="Project identifier")
    start_url: str = Field(..., description="Starting URL for exploration")
    scope: Optional[str] = Field(None, description="URL scope (optional)")
    max_depth: int = Field(3, ge=1, le=10, description="Maximum exploration depth")
    max_pages: int = Field(50, ge=1, le=500, description="Maximum pages to explore")
    max_duration_seconds: int = Field(
        3600, ge=60, le=7200, description="Maximum duration in seconds"
    )


class ExplorationRunResponse(BaseModel):
    """Response model for exploration run"""

    run_id: str
    project_id: str
    start_url: str
    status: str  # "running", "completed", "failed"
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    pages_discovered: int = 0
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


@router.post("/runs", response_model=ExplorationRunResponse)
async def create_exploration_run(
    request: CreateExplorationRequest, background_tasks: BackgroundTasks
):
    """
    Create and start a new exploration run.

    The exploration runs in the background. Use the SSE endpoint to
    monitor progress in real-time.
    """
    # Generate run ID
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_id = f"run-{timestamp}"

    # Create orchestrator
    orchestrator = ExplorationOrchestrator(
        project_id=request.project_id,
        run_id=run_id,
        start_url=request.start_url,
        scope=request.scope,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
        max_duration_seconds=request.max_duration_seconds,
    )

    # Create event emitter
    emitter = EventEmitter()
    event_emitters[run_id] = emitter

    # Store run info
    created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    active_runs[run_id] = {
        "run_id": run_id,
        "project_id": request.project_id,
        "start_url": request.start_url,
        "status": "pending",
        "created_at": created_at,
        "started_at": None,
        "completed_at": None,
        "pages_discovered": 0,
        "duration_seconds": None,
        "error": None,
        "orchestrator": orchestrator,
    }

    # Start exploration in background
    background_tasks.add_task(run_exploration, run_id, orchestrator, emitter)

    return ExplorationRunResponse(**active_runs[run_id])


@router.get("/runs/{run_id}", response_model=ExplorationRunResponse)
async def get_exploration_run(run_id: str):
    """Get exploration run status and results"""
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found")

    run_data = active_runs[run_id].copy()
    # Remove internal objects
    run_data.pop("orchestrator", None)

    return ExplorationRunResponse(**run_data)


@router.get("/runs/{run_id}/events")
async def stream_exploration_events(run_id: str):
    """
    Stream exploration events via SSE.

    Events:
    - exploration.started
    - exploration.progress
    - exploration.page_discovered
    - exploration.page_completed
    - exploration.page_failed
    - exploration.error
    - exploration.completed
    - exploration.failed
    """
    if run_id not in active_runs:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events"""
        # Get or create event emitter
        if run_id not in event_emitters:
            event_emitters[run_id] = EventEmitter()

        emitter = event_emitters[run_id]
        queue: asyncio.Queue = asyncio.Queue()

        # Event listener that puts events in queue
        def listener(event: dict):
            asyncio.create_task(queue.put(event))

        emitter.on(listener)

        try:
            # Send initial connection event
            yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"

            # Stream events
            while True:
                try:
                    # Wait for next event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Format as SSE
                    event_type = event["type"]
                    event_data = json.dumps(event)
                    yield f"event: {event_type}\ndata: {event_data}\n\n"

                    # Stop streaming after completion or failure
                    if event_type in [
                        "exploration.completed",
                        "exploration.failed",
                    ]:
                        break

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f": keepalive\n\n"

        finally:
            emitter.off(listener)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def run_exploration(
    run_id: str, orchestrator: ExplorationOrchestrator, emitter: EventEmitter
):
    """
    Background task to run exploration.

    This is a placeholder that emits events. The actual exploration
    logic will be integrated with the LangChain agent in the next phase.
    """
    try:
        # Update status
        active_runs[run_id]["status"] = "running"
        started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        active_runs[run_id]["started_at"] = started_at

        # Emit started event
        emitter.emit_started(
            run_id=run_id,
            start_url=orchestrator.start_url,
            max_pages=orchestrator.max_pages,
            max_depth=orchestrator.max_depth,
        )

        # Start exploration
        orchestrator.start_exploration()

        # TODO: Integrate with LangChain agent for actual exploration
        # For now, simulate exploration with mock data
        await simulate_exploration(run_id, orchestrator, emitter)

        # Finalize exploration
        result = orchestrator.finalize_exploration()

        # Update status
        completed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        active_runs[run_id]["status"] = "completed"
        active_runs[run_id]["completed_at"] = completed_at
        active_runs[run_id]["pages_discovered"] = result["pages_discovered"]
        active_runs[run_id]["duration_seconds"] = result["duration_seconds"]

        # Emit completed event
        emitter.emit_completed(
            run_id=run_id,
            pages_explored=result["pages_discovered"],
            elements_found=result["elements_found"],
            duration_seconds=result["duration_seconds"],
            artifacts=result["artifacts"],
        )

    except Exception as e:
        # Update status
        completed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        active_runs[run_id]["status"] = "failed"
        active_runs[run_id]["completed_at"] = completed_at
        active_runs[run_id]["error"] = str(e)

        # Emit failed event
        emitter.emit_failed(
            run_id=run_id,
            error=str(e),
            pages_explored=orchestrator.queue.explored_count(),
            duration_seconds=orchestrator.get_statistics()["elapsed_seconds"],
        )


async def simulate_exploration(
    run_id: str, orchestrator: ExplorationOrchestrator, emitter: EventEmitter
):
    """
    Simulate exploration for testing (will be replaced with actual LangChain agent).
    """
    # Get first URL
    url_data = orchestrator.get_next_url()
    if not url_data:
        return

    url, depth = url_data

    # Mark as explored
    orchestrator.mark_page_explored(url)

    # Simulate page discovery
    page_id = "page-start"
    normalized_path = "/start"

    emitter.emit_page_discovered(
        run_id=run_id, page_id=page_id, normalized_path=normalized_path, depth=depth
    )

    # Simulate processing
    await asyncio.sleep(1)

    # Simulate page completion
    orchestrator.add_discovered_page(
        page_id=page_id,
        page_file=f"../../pages/{page_id}.yaml",
        normalized_path=normalized_path,
        status="new",
        elements_count=10,
        exploration_status="completed",
    )

    emitter.emit_page_completed(
        run_id=run_id,
        page_id=page_id,
        normalized_path=normalized_path,
        elements_count=10,
        duration_seconds=1.0,
    )

    # Emit progress
    stats = orchestrator.get_statistics()
    emitter.emit_progress(
        run_id=run_id,
        current_url=url,
        pages_explored=stats["explored_count"],
        queue_size=stats["queue_size"],
        progress_percentage=100.0,
        message="Exploration completed",
    )
