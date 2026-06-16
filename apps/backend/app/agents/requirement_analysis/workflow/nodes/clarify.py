"""Clarification node for requirement analysis workflow."""

from app.agents.requirement_analysis.core.state import RequirementAnalysisState
from app.agents.requirement_analysis.utils.timing import record_step_timing, start_step_timer


async def clarify_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    澄清节点（纯测试驱动）

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 clarification 结果）
    """
    from app.agents.model_selection import build_agent_model, resolve_model_selection
    from app.agents.requirement_analysis.agents.clarification import run_clarification_agent

    run_id = state.get("run_id", "")
    started_at = start_step_timer()

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    # 转换辅助文档格式
    auxiliary_documents = []
    for doc in state["auxiliary_docs"]:
        aux_doc = type('AuxiliaryDocument', (), {
            'mapping_id': doc.get('mapping_id', ''),
            'filename': doc.get('filename', ''),
            'markdown_content': doc.get('markdown_content', ''),
            'document_type': doc.get('document_type', 'other')
        })()
        auxiliary_documents.append(aux_doc)

    clarification_output = await run_clarification_agent(
        model=model,
        understanding_result=state["understanding"],
        quality_assessment_result=state["quality"],
        auxiliary_documents=auxiliary_documents
    )

    state["clarification"] = clarification_output

    record_step_timing(
        state["metadata"],
        run_id=run_id,
        step="clarify",
        started_at=started_at,
    )

    return state
