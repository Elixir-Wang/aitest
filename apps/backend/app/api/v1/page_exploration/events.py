"""探索任务进度 SSE 流端点（与 runs 拆开避免混入生命周期端点）。"""

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.dependencies.auth import current_user
from app.services.page_exploration import event_bus, page_exploration_service

router = APIRouter()


@router.get("/runs/{run_id}/stream")
async def stream_exploration_progress(
    run_id: str,
    actor=Depends(current_user),
) -> StreamingResponse:
    """SSE 流式推送探索进度"""

    async def event_generator() -> AsyncGenerator[str, None]:
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            status = page_exploration_service.get_exploration_status(run_id)
            if not status:
                yield sse({
                    "type": "error",
                    "run_id": run_id,
                    "payload": {"message": "探索任务不存在"},
                })
                return

            yield sse({
                "type": "run_snapshot",
                "run_id": run_id,
                "payload": page_exploration_service.get_exploration_run(actor, run_id),
            })

            last_status = status.get("status")
            last_updated = status.get("updated_at")
            terminal_statuses = {"completed", "cancelled", "interrupted", "blocked", "failed"}
            if last_status in terminal_statuses:
                yield sse({
                    "type": "run_completed",
                    "run_id": run_id,
                    "payload": {
                        "status": last_status,
                        "result_summary": status.get("result_summary", ""),
                        "finished_at": status.get("finished_at"),
                    },
                })
                return

            event_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)
            subscription = event_bus.subscribe(run_id, replay=False)

            async def pump_events() -> None:
                async for event in subscription:
                    await event_queue.put(event)

            pump_task = asyncio.create_task(pump_events())
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=1)
                    except asyncio.TimeoutError:
                        event = None

                    if event is not None:
                        yield sse(event)
                        if event.get("type") in {"run_completed", "run_failed", "run_cancelled"}:
                            break
                        continue

                    status = page_exploration_service.get_exploration_status(run_id)
                    if not status:
                        yield sse({
                            "type": "error",
                            "run_id": run_id,
                            "payload": {"message": "探索任务不存在"},
                        })
                        break
                    current_status = status.get("status")
                    current_updated = status.get("updated_at")
                    if current_status != last_status or current_updated != last_updated:
                        yield sse({
                            "type": "run_snapshot",
                            "run_id": run_id,
                            "payload": page_exploration_service.get_exploration_run(actor, run_id),
                        })
                        last_status = current_status
                        last_updated = current_updated
                    if current_status in terminal_statuses:
                        yield sse({
                            "type": "run_completed" if current_status not in {"blocked", "failed"} else "run_failed",
                            "run_id": run_id,
                            "payload": {
                                "status": current_status,
                                "result_summary": status.get("result_summary", ""),
                                "finished_at": status.get("finished_at"),
                            },
                        })
                        break
            finally:
                pump_task.cancel()
                await asyncio.gather(pump_task, return_exceptions=True)
                await subscription.aclose()

        except Exception as e:
            yield sse({
                "type": "error",
                "run_id": run_id,
                "payload": {"message": str(e)}
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )