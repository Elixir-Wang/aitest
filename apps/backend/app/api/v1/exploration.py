import json
import threading

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies.auth import current_user, require_admin
from app.schemas.exploration import (
    ExplorationGoalOptimizeIn,
    ExplorationGoalOptimizeOut,
    ExplorationLogOut,
    ExplorationReportOut,
    ExplorationRunCreateIn,
    ExplorationRunDetailOut,
    ExplorationRunOut,
    ExplorationRunUpdateIn,
)
from app.services.exploration import event_bus as exploration_event_bus
from app.services.exploration import goal_optimizer
from app.services.exploration import service as exploration_service
from app.services.exploration import site_orchestrator as site_exploration_orchestrator

router = APIRouter(prefix="/projects", tags=["exploration"])
global_router = APIRouter(prefix="/exploration-runs", tags=["exploration"])


@global_router.get("", response_model=list[ExplorationRunOut])
def list_visible_runs(actor=Depends(current_user)) -> list[dict]:
    return exploration_service.list_visible_runs(actor)


@router.get("/{project_id}/exploration-runs", response_model=list[ExplorationRunOut])
def list_project_runs(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return exploration_service.list_project_runs(project_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}", response_model=ExplorationRunOut)
def get_project_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run(project_id, run_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}/detail", response_model=ExplorationRunDetailOut)
def get_project_run_detail(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run_detail(project_id, run_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}/report", response_model=ExplorationReportOut)
def get_project_run_report(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return exploration_service.get_project_run_report(project_id, run_id, actor)


@router.get("/{project_id}/exploration-runs/{run_id}/log", response_model=ExplorationLogOut)
def get_project_run_log(
    project_id: str,
    run_id: str,
    page: int = 1,
    page_size: int = 10,
    keyword: str = "",
    type: str = "",
    level: str = "",
    page_ref: str = "",
    include_raw_content: bool = False,
    actor=Depends(current_user),
) -> dict:
    return exploration_service.get_project_run_log(
        project_id,
        run_id,
        actor,
        page=page,
        page_size=page_size,
        keyword=keyword,
        type_filter=type,
        level=level,
        page_ref=page_ref,
        include_raw_content=include_raw_content,
    )


@router.get("/{project_id}/exploration-runs/{run_id}/stream")
def stream_project_run(project_id: str, run_id: str, actor=Depends(current_user)) -> StreamingResponse:
    run = exploration_service.get_project_run(project_id, run_id, actor)
    detail = exploration_service.get_project_run_detail(project_id, run_id, actor)
    snapshot_event_id = exploration_event_bus.latest_event_id(run_id)
    snapshot_event = {
        "event_id": snapshot_event_id,
        "type": "run_snapshot",
        "run_id": run_id,
        "payload": detail,
    }
    if run["status"] in {"completed", "partial", "blocked", "cancelled", "interrupted"}:
        event_type = _terminal_stream_event_type(run["status"])

        def terminal_event_stream():
            yield _format_sse_event(snapshot_event)
            data = json.dumps(
                {
                    "event_id": snapshot_event_id,
                    "type": event_type,
                    "run_id": run_id,
                    "payload": run,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"event: {event_type}\ndata: {data}\n\n"

        return StreamingResponse(terminal_event_stream(), media_type="text/event-stream")

    def event_stream():
        yield _format_sse_event(snapshot_event)
        replay_event_id = exploration_event_bus.latest_event_id(run_id)
        for event in exploration_event_bus.recent_events(run_id):
            yield _format_sse_event(event)
        for event in exploration_event_bus.subscribe(run_id, after_event_id=replay_event_id):
            if event is None:
                yield ": keep-alive\n\n"
                continue
            yield _format_sse_event(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _format_sse_event(event: dict) -> str:
    event_type = str(event.get("type") or "message")
    data = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"event: {event_type}\ndata: {data}\n\n"


def _terminal_stream_event_type(status: str) -> str:
    if status == "completed":
        return "run_completed"
    if status == "cancelled":
        return "run_cancelled"
    return "run_failed"


@router.post("/{project_id}/exploration-runs", response_model=ExplorationRunOut)
def create_project_run(
    project_id: str,
    payload: ExplorationRunCreateIn,
    actor=Depends(require_admin),
) -> dict:
    return exploration_service.create_project_run(project_id, payload, actor)


@router.patch("/{project_id}/exploration-runs/{run_id}", response_model=ExplorationRunOut)
def update_project_run(
    project_id: str,
    run_id: str,
    payload: ExplorationRunUpdateIn,
    actor=Depends(require_admin),
) -> dict:
    return exploration_service.update_project_run(project_id, run_id, payload, actor)


@router.post("/{project_id}/exploration-goal/optimize", response_model=ExplorationGoalOptimizeOut)
def optimize_exploration_goal(
    project_id: str,
    payload: ExplorationGoalOptimizeIn,
    actor=Depends(require_admin),
) -> dict:
    return goal_optimizer.optimize_exploration_goal(project_id, payload, actor)


@router.post("/{project_id}/exploration-runs/{run_id}/start", response_model=ExplorationRunOut)
def start_project_run(
    project_id: str,
    run_id: str,
    actor=Depends(require_admin),
) -> dict:
    run = exploration_service.start_project_run(project_id, run_id, actor)
    _dispatch_exploration_run(run_id)
    return run


def _dispatch_exploration_run(run_id: str) -> None:
    thread = threading.Thread(
        target=site_exploration_orchestrator.run_exploration,
        args=(run_id,),
        daemon=True,
    )
    thread.start()


@router.post("/{project_id}/exploration-runs/{run_id}/stop", response_model=ExplorationRunOut)
def stop_project_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> dict:
    return exploration_service.stop_project_run(project_id, run_id, actor)


@router.delete("/{project_id}/exploration-runs/{run_id}")
def delete_project_run(project_id: str, run_id: str, actor=Depends(require_admin)) -> dict:
    return exploration_service.delete_project_run(project_id, run_id, actor)
