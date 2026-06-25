import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.site_exploration.execution_decision.agent import agentic_exploration_agent
from app.agents.site_exploration.execution_decision.schemas import AgenticDecisionOutput, AgenticExplorationInput


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


def _build_decision_prompt(input_data: AgenticExplorationInput) -> str:
    return json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2)
