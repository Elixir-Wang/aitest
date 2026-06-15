"""
需求理解节点（重构版）

使用深度分析架构：业务分析 → 领域建模 → 风险识别
"""

from app.agents.requirement_analysis.state import RequirementAnalysisState
from app.agents.requirement_analysis.orchestrator import DeepUnderstandingOrchestrator


async def understand_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    需求理解节点（深度分析）

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 understanding 结果）
    """
    # 获取 LLM 模型
    from app.agents.model_selection import build_agent_model, resolve_model_selection

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    # 使用深度分析编排器
    orchestrator = DeepUnderstandingOrchestrator(model)
    deep_result = await orchestrator.analyze(state["primary_content"])

    # 将深度分析结果转换为原有的 RequirementUnderstandingOutput 格式
    # 这样可以保持与后续节点的兼容性
    from app.agents.requirement_analysis.schemas import (
        RequirementUnderstandingOutput,
        RequirementModule,
        BusinessObject,
        BusinessRule,
        StateFlow,
        StateTransition,
        Dependency,
        Risk,
        Assumption,
    )

    # 从领域模型提取模块信息
    modules = []
    for entity in deep_result.domain_model.entities:
        module = RequirementModule(
            module_key=entity.name.lower().replace(" ", "_"),
            module_name=entity.name,
            summary=entity.essence,
            capabilities=entity.key_attributes,
            business_objects=[
                BusinessObject(
                    name=entity.name,
                    description=entity.why_exists,
                    fields=entity.key_attributes,
                    relationships=entity.relationships
                )
            ],
            business_rules=[],
            state_flows=[],
            dependencies=[]
        )
        modules.append(module)

    # 从状态机提取状态流转
    state_flows = []
    for sm in deep_result.domain_model.state_machines:
        transitions = []
        for trans in sm.transitions:
            transitions.append(StateTransition(
                from_state=trans.get("from", ""),
                to_state=trans.get("to", ""),
                trigger=trans.get("trigger", ""),
                condition=trans.get("condition", "")
            ))

        state_flows.append(StateFlow(
            object_name=sm.entity_name,
            states=sm.states,
            transitions=transitions
        ))

    # 从风险识别提取风险
    risks = []
    for root_cause in deep_result.risk_profile.root_causes:
        risks.append(Risk(
            risk_id=f"RISK-{len(risks)+1}",
            category="business" if "业务" in root_cause.risk_description else "technical",
            description=root_cause.risk_description,
            impact="high" if root_cause.likelihood == "high" else "medium",
            likelihood=root_cause.likelihood,
            mitigation=root_cause.root_cause
        ))

    # 从业务分析提取假设（如果有的话）
    assumptions = []

    # 构建兼容的理解结果
    understanding_result = RequirementUnderstandingOutput(
        modules=modules,
        dependencies=[],
        risks=risks,
        assumptions=assumptions,
        understanding_summary=deep_result.business_insight.summary
    )

    # 更新状态
    state["understanding"] = understanding_result

    # 同时保存深度分析结果到metadata，供后续使用
    state["metadata"]["deep_understanding"] = {
        "business_insight": deep_result.business_insight.model_dump(),
        "domain_model": deep_result.domain_model.model_dump(),
        "risk_profile": deep_result.risk_profile.model_dump(),
        "explanation_markdown": deep_result.explanation_markdown
    }

    return state


__all__ = ["understand_node"]
