"""页面探索API路由"""

import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.dependencies.auth import current_user
from app.services.exploration import event_bus
from app.services.exploration import page_exploration_service


router = APIRouter(prefix="/page-exploration", tags=["page-exploration"])


# ==================== Request/Response Models ====================


class CreateExplorationRunRequest(BaseModel):
    """创建探索任务请求"""

    project_id: str = Field(..., description="项目ID")
    environment_id: str = Field(..., description="环境ID")
    title: str = Field(..., description="任务标题")
    scope: str = Field(..., description="探索范围（起始URL）")
    goal: str = Field(default="", description="探索目标")
    forbidden_paths: str = Field(default="", description="禁止路径（每行一个）")
    max_pages: int = Field(default=50, ge=1, le=500, description="最大页面数")
    max_actions: int = Field(default=1000, ge=1, le=10000, description="最大操作数")
    timeout_minutes: int = Field(default=120, ge=1, le=1440, description="超时时间（分钟）")
    login_strategy: str = Field(default="skip_login", description="登录策略")
    requirement_doc_id: str = Field(default="", description="需求文档ID")
    notes: str = Field(default="", description="备注")


class UpdateExplorationRunRequest(BaseModel):
    """更新探索任务请求"""

    title: str | None = Field(None, description="任务标题")
    environment_id: str | None = Field(None, description="环境ID")
    requirement_doc_id: str | None = Field(None, description="需求文档ID")
    scope: str | None = Field(None, description="探索范围")
    forbidden_paths: str | None = Field(None, description="禁止路径")
    goal: str | None = Field(None, description="探索目标")
    notes: str | None = Field(None, description="备注")
    max_pages: int | None = Field(None, ge=1, le=500, description="最大页面数")
    max_actions: int | None = Field(None, ge=1, le=10000, description="最大操作数")
    timeout_minutes: int | None = Field(None, ge=1, le=1440, description="超时时间（分钟）")


class ExplorationRunResponse(BaseModel):
    """探索任务响应"""

    id: str
    project_id: str
    environment_id: str
    title: str
    status: str
    scope: str
    goal: str
    forbidden_paths: str
    max_pages: int
    max_actions: int
    timeout_minutes: int
    created_at: str
    created_by: str
    started_at: str | None = None
    finished_at: str | None = None
    result_summary: str = ""


class ExplorationRunDetailResponse(BaseModel):
    """探索任务详情响应"""

    run: dict
    artifact_schema_version: int
    unsupported_artifact: bool
    unsupported_reason: str
    modules: list[dict]


# ==================== API Endpoints ====================


@router.post("/runs", response_model=dict)
def create_exploration_run(
    request: CreateExplorationRunRequest,
    actor=Depends(current_user),
) -> dict:
    """创建页面探索任务

    创建一个新的页面探索任务（不自动启动）。

    Args:
        request: 创建请求
        actor: 当前用户

    Returns:
        创建的任务信息
    """
    try:
        run = page_exploration_service.create_exploration_run(
            actor,
            project_id=request.project_id,
            environment_id=request.environment_id,
            title=request.title,
            scope=request.scope,
            goal=request.goal,
            forbidden_paths=request.forbidden_paths,
            max_pages=request.max_pages,
            max_actions=request.max_actions,
            timeout_minutes=request.timeout_minutes,
            login_strategy=request.login_strategy,
            requirement_doc_id=request.requirement_doc_id,
            notes=request.notes,
        )

        return run

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/start", response_model=dict)
def start_exploration_run(
    run_id: str,
    actor=Depends(current_user),
) -> dict:
    """启动/重新启动探索任务

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        更新后的任务信息
    """
    try:
        run = page_exploration_service.start_exploration_async(actor, run_id)
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/stop", response_model=dict)
def stop_exploration_run(
    run_id: str,
    actor=Depends(current_user),
) -> dict:
    """停止探索任务

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        更新后的任务信息
    """
    try:
        run = page_exploration_service.stop_exploration_async(actor, run_id)
        return run
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/runs/{run_id}", response_model=dict)
def update_exploration_run(
    run_id: str,
    request: UpdateExplorationRunRequest,
    actor=Depends(current_user),
) -> dict:
    """更新探索任务配置

    Args:
        run_id: 任务ID
        request: 更新请求
        actor: 当前用户

    Returns:
        更新后的任务信息
    """
    try:
        # 过滤掉None值
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise ValueError("没有提供要更新的字段")

        run = page_exploration_service.update_exploration_run(actor, run_id, update_data)
        return run
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}", response_model=ExplorationRunDetailResponse)
def get_exploration_run(run_id: str, actor=Depends(current_user)) -> dict:
    """获取探索任务详情

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        任务详情，包含页面、产物等信息
    """
    try:
        return page_exploration_service.get_exploration_run(actor, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/stream")
async def stream_exploration_progress(
    run_id: str,
    actor=Depends(current_user),
) -> StreamingResponse:
    """SSE流式推送探索进度

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        SSE事件流
    """
    import asyncio

    async def event_generator() -> AsyncGenerator[str, None]:
        """生成SSE事件"""
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
            terminal_statuses = {"completed", "partial", "cancelled", "interrupted", "blocked", "failed"}
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
            subscription = event_bus.subscribe(run_id)

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


@router.get("/runs/{run_id}/artifacts", response_model=dict)
def get_exploration_artifacts(
    run_id: str,
    actor=Depends(current_user),
) -> dict:
    """获取探索报告

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        探索报告内容
    """
    try:
        return page_exploration_service.get_exploration_report(actor, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs", response_model=list[dict])
def list_exploration_runs(
    project_id: str = Query(..., description="项目ID"),
    limit: int = Query(default=100, ge=1, le=500, description="返回数量限制"),
    actor=Depends(current_user),
) -> list[dict]:
    """列出项目的探索任务

    Args:
        project_id: 项目ID
        limit: 返回数量限制
        actor: 当前用户

    Returns:
        探索任务列表
    """
    try:
        return page_exploration_service.list_exploration_runs(actor, project_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs-running", response_model=list[dict])
def list_running_runs(
    project_id: str | None = Query(default=None, description="项目ID（可选）"),
    actor=Depends(current_user),
) -> list[dict]:
    """列出运行中的探索任务

    Args:
        project_id: 项目ID（可选，不传则返回所有项目）
        actor: 当前用户

    Returns:
        运行中的任务列表
    """
    try:
        return page_exploration_service.list_running_runs(actor, project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs-all", response_model=list[dict])
def list_all_runs(
    project_id: str | None = Query(default=None, description="项目ID（可选）"),
    limit: int = Query(default=100, ge=1, le=500, description="返回数量限制"),
    actor=Depends(current_user),
) -> list[dict]:
    """列出所有探索任务

    Args:
        project_id: 项目ID（可选，不传则返回所有项目的任务）
        limit: 返回数量限制
        actor: 当前用户

    Returns:
        所有探索任务列表
    """
    try:
        return page_exploration_service.list_all_runs(actor, project_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}/pages", response_model=list[dict])
def list_run_pages(run_id: str, actor=Depends(current_user)) -> list[dict]:
    """列出探索任务的页面

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        页面列表
    """
    try:
        return page_exploration_service.list_run_pages(actor, run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts/{artifact_id}/content", response_model=dict)
def get_artifact_content(artifact_id: str, actor=Depends(current_user)) -> dict:
    """获取产物内容

    Args:
        artifact_id: 产物ID
        actor: 当前用户

    Returns:
        产物内容
    """
    try:
        content = page_exploration_service.get_artifact_content(actor, artifact_id)
        return {"content": content}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/runs/{run_id}")
def delete_exploration_run(run_id: str, actor=Depends(current_user)) -> dict:
    """删除探索任务

    Args:
        run_id: 任务ID
        actor: 当前用户

    Returns:
        删除结果
    """
    try:
        page_exploration_service.delete_exploration_run(actor, run_id)
        return {"message": "探索任务已删除", "run_id": run_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts", response_model=list[dict])
def list_all_artifacts(
    project_id: str | None = Query(default=None, description="项目ID（可选）"),
    run_id: str | None = Query(default=None, description="探索任务ID（可选）"),
    actor=Depends(current_user),
) -> list[dict]:
    """列出所有探索产物

    Args:
        project_id: 项目ID（可选）
        run_id: 探索任务ID（可选）
        actor: 当前用户

    Returns:
        产物列表
    """
    try:
        return page_exploration_service.list_all_artifacts(actor, project_id, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts-tree", response_model=dict)
def get_artifacts_tree(
    project_id: str | None = Query(default=None, description="项目ID（可选）"),
    actor=Depends(current_user),
) -> dict:
    """获取探索产物树结构

    Args:
        project_id: 项目ID（可选）
        actor: 当前用户

    Returns:
        产物树结构
    """
    try:
        return page_exploration_service.build_artifact_tree(actor, project_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
