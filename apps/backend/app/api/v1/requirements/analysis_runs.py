"""需求 AI 分析运行生命周期。

- ``POST /projects/{project_id}/requirements/{document_id}/analysis-runs`` —— 启动 AI 分析运行
- ``POST /projects/{project_id}/requirements/{document_id}/analysis-runs/{run_id}/stop`` —— 停止分析运行
- ``GET /projects/{project_id}/requirements/{document_id}/analysis-runs`` —— 列出分析运行
"""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.dependencies.auth import current_user
from app.services.document import analysis_runs as document_analysis_runs

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.post("/{document_id}/analysis-runs")
def create_requirement_analysis_run(
    project_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    actor=Depends(current_user),
) -> dict:
    task = document_analysis_runs.start_requirement_review_run(project_id, document_id, actor)
    background_tasks.add_task(document_analysis_runs.execute_requirement_review_run, task["source_id"], dict(actor))
    return task


@router.post("/{document_id}/analysis-runs/{run_id}/stop")
def stop_requirement_analysis_run(
    project_id: str,
    document_id: str,
    run_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_analysis_runs.stop_requirement_analysis_run(project_id, document_id, run_id, actor)


@router.get("/{document_id}/analysis-runs")
def list_requirement_analysis_runs(project_id: str, document_id: str, actor=Depends(current_user)) -> list[dict]:
    return document_analysis_runs.list_requirement_analysis_runs(project_id, document_id, actor)
