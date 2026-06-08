import json

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.site_exploration.plan_agent import exploration_plan_agent
from app.agents.site_exploration.plan_schemas import ExplorationPlanInput, ExplorationPlanOutput


CAPABILITY_ID = "site_exploration"


async def generate_exploration_plan(input_data: ExplorationPlanInput) -> ExplorationPlanOutput:
    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = exploration_plan_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_plan_prompt(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("探索计划智能体未返回结构化结果。")
    return output


def _build_plan_prompt(input_data: ExplorationPlanInput) -> str:
    return json.dumps(input_data.model_dump(), ensure_ascii=False, indent=2)
