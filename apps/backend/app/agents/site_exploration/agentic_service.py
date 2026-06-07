import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.site_exploration.agentic_agent import agentic_exploration_agent
from app.agents.site_exploration.agentic_schemas import AgenticAction, AgenticDecisionOutput, AgenticExplorationInput, AgenticRisk


CAPABILITY_ID = "site_exploration"


async def decide_next_action(input_data: AgenticExplorationInput) -> AgenticDecisionOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = agentic_exploration_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_decision_prompt(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("站点探索执行智能体未返回结构化决策。")
    return output


def fallback_decision(input_data: AgenticExplorationInput) -> AgenticDecisionOutput:
    observation = input_data.current_observation if isinstance(input_data.current_observation, dict) else {}
    elements = observation.get("elements") if isinstance(observation.get("elements"), list) else []
    for element in elements:
        if not isinstance(element, dict) or element.get("enabled") is False or element.get("visible") is False:
            continue
        if element.get("already_attempted"):
            continue
        action_type = str(element.get("action_type") or "")
        risk_level = _element_risk_level(element)
        if action_type == "click":
            return AgenticDecisionOutput(
                decision_type="act",
                action=AgenticAction(type="click", target_element_id=str(element.get("id") or "")),
                reason="模型不可用时采用确定性策略：选择当前页面第一个可点击元素继续探索。",
                expected_result="进入新页面、打开弹窗或改变页面状态。",
                risk=AgenticRisk(level=risk_level, reason=f"元素由浏览器观察标记为 {risk_level}，探索允许完整 CRUD。"),
            )
        if action_type == "fill":
            return AgenticDecisionOutput(
                decision_type="act",
                action=AgenticAction(
                    type="fill",
                    target_element_id=str(element.get("id") or ""),
                    value=_fallback_fill_value(risk_level),
                    intent="search" if risk_level == "safe" else "crud_input",
                ),
                reason="模型不可用时采用确定性策略：填写当前页面第一个可执行输入框。",
                expected_result="触发搜索、筛选、校验或表单状态变化。",
                risk=AgenticRisk(level=risk_level, reason=f"元素由浏览器观察标记为 {risk_level}，探索允许完整 CRUD。"),
            )
    return AgenticDecisionOutput(
        decision_type="finish",
        action=None,
        reason="当前观察中没有可执行动作。",
        expected_result="结束 Agentic 探索。",
        risk=AgenticRisk(level="safe", reason="结束探索不会修改页面数据。"),
    )


def _build_decision_prompt(input_data: AgenticExplorationInput) -> str:
    return json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2)


def _element_risk_level(element: dict) -> str:
    risk_level = str(element.get("risk_hint") or "safe")
    if risk_level in {"safe", "guarded", "destructive"}:
        return risk_level
    return "safe"


def _fallback_fill_value(risk_level: str) -> str:
    if risk_level == "safe":
        return "AI_TEST_search"
    return "AI_TEST_input"
