"""
LangGraph 工作流编排

使用 LangGraph 1.2+ 构建需求分析工作流
"""

import time
from datetime import datetime
from typing import Literal
from langgraph.graph import StateGraph, END, START

from app.agents.requirement_analysis.state import RequirementAnalysisState
from app.agents.requirement_analysis.nodes.understand_node import understand_node
from app.agents.requirement_analysis.nodes.quality_node import quality_node
from app.agents.requirement_analysis.nodes.clarify_node import clarify_node
from app.agents.requirement_analysis.nodes.enhance_node import enhance_node
from app.agents.requirement_analysis.schemas import (
    ClarificationOutput,
    ClarificationSummary,
    RequirementAnalysisInputV2,
    RequirementAnalysisResultV2,
)


def should_skip_clarification(state: RequirementAnalysisState) -> Literal["clarify", "enhance"]:
    """
    条件路由：决定是否跳过澄清阶段

    条件：质量评分 >= 95 且决策为 approved
    """
    quality = state.get("quality")
    if quality and \
       quality.scores.overall >= 95 and \
       quality.decision.result == "approved":
        return "enhance"  # 跳过澄清
    return "clarify"  # 需要澄清


def prepare_empty_clarification(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """为跳过澄清的高质量需求生成稳定的空澄清结果。"""
    state["clarification"] = ClarificationOutput(
        items=[],
        summary=ClarificationSummary(
            total=0,
            auto_resolved=0,
            has_suggestions=0,
            needs_manual=0,
        ),
        clarification_summary_text="需求质量已通过，无需补充澄清。",
    )
    return state


def build_requirement_analysis_workflow() -> StateGraph:
    """
    构建需求分析工作流（LangGraph 1.2+）

    流程：
    1. 需求理解
    2. 质量评估
    3. 条件路由：
       - 高质量（overall >= 95 且 approved）→ 跳过澄清，直接增强
       - 其他 → 澄清（Agentic Search）
    4. 增强和报告生成
    """
    # 使用 StateGraph
    workflow = StateGraph(RequirementAnalysisState)

    # 添加节点
    workflow.add_node("understand", understand_node)
    workflow.add_node("assess_quality", quality_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("prepare_empty_clarification", prepare_empty_clarification)
    workflow.add_node("enhance", enhance_node)

    # 设置边
    workflow.add_edge(START, "understand")
    workflow.add_edge("understand", "assess_quality")

    # 条件路由
    workflow.add_conditional_edges(
        "assess_quality",
        should_skip_clarification,
        {
            "clarify": "clarify",
            "enhance": "prepare_empty_clarification"
        }
    )

    # 串行连接
    workflow.add_edge("clarify", "enhance")
    workflow.add_edge("prepare_empty_clarification", "enhance")
    workflow.add_edge("enhance", END)

    return workflow


async def run_requirement_analysis(
    input_data: RequirementAnalysisInputV2
) -> RequirementAnalysisResultV2:
    """
    运行需求分析（LangGraph + Agentic Search）

    Args:
        input_data: 需求分析输入

    Returns:
        RequirementAnalysisResultV2: 完整的分析结果
    """
    start_time = time.time()

    # 构建工作流
    workflow = build_requirement_analysis_workflow()
    app = workflow.compile()

    # 准备初始状态
    initial_state: RequirementAnalysisState = {
        # 输入
        "primary_content": input_data.primary_markdown_content,
        "auxiliary_docs": [
            {
                "mapping_id": doc.mapping_id,
                "filename": doc.filename,
                "markdown_content": doc.markdown_content
            }
            for doc in input_data.auxiliary_documents
        ],
        "config": input_data.config,

        # 项目信息
        "project_id": input_data.project_id,
        "document_id": input_data.document_id,
        "document_name": input_data.document_name,
        "run_id": input_data.run_id or f"run-{int(time.time())}",

        # 中间状态
        "understanding": None,
        "quality": None,
        "clarification": None,

        # 输出
        "enhanced_requirement": None,
        "analysis_report": None,
        "status": None,

        # 元数据
        "metadata": {}
    }

    # 执行工作流
    final_state = await app.ainvoke(initial_state)

    # 计算执行时间
    execution_time_ms = int((time.time() - start_time) * 1000)

    # 构建最终结果
    result = RequirementAnalysisResultV2(
        status=final_state["status"],
        understanding=final_state["understanding"],
        quality_assessment=final_state["quality"],
        clarification=final_state["clarification"],
        analysis_report_markdown=final_state["analysis_report"],
        enhanced_requirement_markdown=final_state["enhanced_requirement"],
        metadata={
            "version": "3.0",
            "engine": "langchain_langgraph",
            "project_id": input_data.project_id,
            "document_id": input_data.document_id,
            "document_name": input_data.document_name,
            "run_id": final_state["run_id"],
            "execution_time_ms": execution_time_ms,
            "execution_timestamp": datetime.now().isoformat(),
            "config": input_data.config,
        }
    )

    return result


__all__ = [
    "run_requirement_analysis",
    "build_requirement_analysis_workflow",
    "prepare_empty_clarification",
]
