"""需求 AI 分析产物端点。

- ``GET /projects/{project_id}/requirements/{document_id}/analysis`` —— 取最新分析结果
- ``POST /projects/{project_id}/requirements/{document_id}/analysis/finalize`` —— 最终化分析
- ``PUT /projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/preliminary`` —— 更新初步文档
- ``GET /projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/clarification-answers`` —— 列出问答
- ``POST /projects/{project_id}/requirements/{document_id}/analysis/{analysis_id}/clarification-answers`` —— 提交问答
"""

from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user
from app.schemas.document import RequirementAnalysisFinalizeIn, RequirementClarificationAnswerIn, RequirementPreliminaryUpdateIn
from app.services.document import service as document_service

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["requirements"])


@router.get("/{document_id}/analysis")
def get_requirement_analysis(project_id: str, document_id: str, actor=Depends(current_user)) -> dict:
    return document_service.get_latest_requirement_analysis(project_id, document_id, actor)


@router.post("/{document_id}/analysis/finalize")
async def finalize_requirement_analysis(
    project_id: str,
    document_id: str,
    payload: RequirementAnalysisFinalizeIn,
    actor=Depends(current_user),
) -> dict:
    return await document_service.finalize_requirement_analysis(project_id, document_id, payload, actor)


@router.put("/{document_id}/analysis/{analysis_id}/preliminary")
def update_requirement_preliminary_markdown(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementPreliminaryUpdateIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.update_requirement_preliminary_markdown(project_id, document_id, analysis_id, payload, actor)


@router.get("/{document_id}/analysis/{analysis_id}/clarification-answers")
def list_requirement_clarification_answers(
    project_id: str,
    document_id: str,
    analysis_id: str,
    actor=Depends(current_user),
) -> dict:
    return document_service.list_requirement_clarification_answers(project_id, document_id, analysis_id, actor)


@router.post("/{document_id}/analysis/{analysis_id}/clarification-answers")
def save_requirement_clarification_answer(
    project_id: str,
    document_id: str,
    analysis_id: str,
    payload: RequirementClarificationAnswerIn,
    actor=Depends(current_user),
) -> dict:
    return document_service.save_requirement_clarification_answer(project_id, document_id, analysis_id, payload, actor)