"""需求 AI 分析产物端点。

- ``GET /projects/{project_id}/requirements/{document_id}/analysis`` —— 取最新分析结果
- ``POST /projects/{project_id}/requirements/{document_id}/analysis/finalize`` —— 最终化分析
- ``PUT /projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/preliminary`` —— 更新初步文档
- ``GET /projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/clarification-answers`` —— 列出问答
- ``POST /projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/clarification-answers`` —— 提交问答
"""

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.logging import logger
from app.dependencies.auth import current_user
from app.schemas.document import RequirementAnalysisFinalizeIn, RequirementClarificationAnswerIn, RequirementPreliminaryUpdateIn
from app.services.document import analysis as document_analysis
from app.services.document import analysis_runs as document_analysis_runs
from app.services import test_point_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("/{document_id}/analysis")
def get_requirement_analysis(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_analysis_runs.get_latest_requirement_analysis(project_id, document_id, actor)


@router.post("/{document_id}/analysis/finalize")
async def finalize_requirement_analysis(
    project_id: str,
    document_id: str,
    payload: RequirementAnalysisFinalizeIn,
    background_tasks: BackgroundTasks,
    actor=Depends(current_user),
) -> dict:
    logger.info("finalize_requirement_analysis: project={}, document={}, actor={}", project_id, document_id, actor["id"])
    try:
        result = await document_analysis.finalize_requirement_analysis(project_id, document_id, payload, actor)
        logger.info("finalize_requirement_analysis: success, document_id={}", document_id)
    except Exception as e:
        logger.exception("finalize_requirement_analysis: failed before enqueue, error={}", str(e))
        raise

    try:
        run = test_point_service.enqueue_generation(project_id, document_id, actor)
        logger.info("enqueue_generation: project={}, document={}, run={}", project_id, document_id, run)
    except Exception as e:
        logger.exception("enqueue_generation: failed, error={}", str(e))
        result["test_point_generation_run"] = None
        result["test_point_generation_error"] = str(e)
        return result

    if run and run["status"] == "queued":
        logger.info("enqueue_generation: adding background task for run_id={}", run["id"])
        background_tasks.add_task(test_point_service.execute_generation_run, run["id"])
    else:
        logger.info("enqueue_generation: run status is {}, not adding background task", run.get("status") if run else "None")

    result["test_point_generation_run"] = run
    return result


@router.put("/{document_id}/analysis/{analysis_id}/preliminary")
def update_requirement_preliminary_markdown(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementPreliminaryUpdateIn,
    actor=Depends(current_user),
) -> dict:
    return document_analysis.update_requirement_preliminary_markdown(project_id, document_id, analysis_id, payload, actor)


@router.get("/{document_id}/analysis/{analysis_id}/clarification-answers")
def list_requirement_clarification_answers(
    project_id: str,
    document_id: str,
    analysis_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_analysis_runs.list_requirement_clarification_answers(project_id, document_id, analysis_id, actor)


@router.post("/{document_id}/analysis/{analysis_id}/clarification-answers")
def save_requirement_clarification_answer(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementClarificationAnswerIn,
    actor=Depends(current_user),
) -> dict:
    return document_analysis.save_requirement_clarification_answer(project_id, document_id, analysis_id, payload, actor)
