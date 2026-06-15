"""
澄清节点 v3.0（纯测试驱动）

调用 clarification_agent_v3 生成待澄清内容
"""

from app.agents.requirement_analysis.state import RequirementAnalysisState


async def clarify_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    澄清节点 v3.0（纯测试驱动）

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 clarification 结果）
    """
    # 获取 LLM 模型
    from app.agents.model_selection import build_agent_model, resolve_model_selection
    from app.agents.requirement_analysis.agents.clarification import run_clarification_agent_v3

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    # 🔥 使用 clarification_agent_v3 生成澄清内容
    # 转换辅助文档格式
    auxiliary_documents = []
    for doc in state["auxiliary_docs"]:
        # 创建一个简单对象来模拟辅助文档
        aux_doc = type('AuxiliaryDocument', (), {
            'mapping_id': doc.get('mapping_id', ''),
            'filename': doc.get('filename', ''),
            'markdown_content': doc.get('markdown_content', ''),
            'document_type': doc.get('document_type', 'other')
        })()
        auxiliary_documents.append(aux_doc)

    clarification_output = await run_clarification_agent_v3(
        model=model,
        understanding_result=state["understanding"],
        quality_assessment_result=state["quality"],
        auxiliary_documents=auxiliary_documents
    )

    # 更新状态
    state["clarification"] = clarification_output

    return state


__all__ = ["clarify_node"]
