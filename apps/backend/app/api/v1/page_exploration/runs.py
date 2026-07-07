"""探索任务（runs）的生命周期与列表/详情端点。"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.page_exploration.schemas import (
    CreateExplorationRunRequest,
    ExplorationRunDetailResponse,
    UpdateExplorationRunRequest,
)
from app.dependencies.auth import current_user
from app.services.page_exploration import page_exploration_service

router = APIRouter()


@router.post("/runs", response_model=dict)
def create_exploration_run(
    request: CreateExplorationRunRequest,
    actor=Depends(current_user),
) -> dict:
    """创建页面探索任务

    创建一个新的页面探索任务（不自动启动）。
    """
    try:
        return page_exploration_service.create_exploration_run(
            actor,
            project_id=request.project_id,
            environment_id=request.environment_id,
            title=request.title,
            exploration_mode=request.exploration_mode,
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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/runs/{run_id}/start", response_model=dict)
def start_exploration_run(run_id: str, actor=Depends(current_user)) -> dict:
    """启动/重新启动探索任务"""
    try:
        return page_exploration_service.start_exploration_async(actor, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/runs/{run_id}/stop", response_model=dict)
def stop_exploration_run(run_id: str, actor=Depends(current_user)) -> dict:
    """停止探索任务"""
    try:
        return page_exploration_service.stop_exploration_async(actor, run_id)
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
    """更新探索任务配置"""
    try:
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}
        if not update_data:
            raise ValueError("没有提供要更新的字段")
        return page_exploration_service.update_exploration_run(actor, run_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/{run_id}", response_model=ExplorationRunDetailResponse)
def get_exploration_run(run_id: str, actor=Depends(current_user)) -> dict:
    """获取探索任务详情"""
    try:
        return page_exploration_service.get_exploration_run(actor, run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/runs/{run_id}")
def delete_exploration_run(run_id: str, actor=Depends(current_user)) -> dict:
    """删除探索任务"""
    try:
        page_exploration_service.delete_exploration_run(actor, run_id)
        return {"message": "探索任务已删除", "run_id": run_id}
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
    """列出项目的探索任务"""
    try:
        return page_exploration_service.list_exploration_runs(actor, project_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs-all", response_model=list[dict])
def list_all_runs(
    project_id: str | None = Query(default=None, description="项目ID（可选）"),
    limit: int = Query(default=100, ge=1, le=500, description="返回数量限制"),
    actor=Depends(current_user),
) -> list[dict]:
    """列出所有探索任务（不传 project_id 时跨项目）"""
    try:
        return page_exploration_service.list_all_runs(actor, project_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))