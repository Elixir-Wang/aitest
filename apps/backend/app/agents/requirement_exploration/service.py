import asyncio

from app.agents.requirement_exploration.agent import requirement_exploration_agent
from app.agents.requirement_exploration.schemas import (
    RequirementExplorationInput,
    RequirementExplorationPlan,
)
from app.core.llm import get_model


async def generate_exploration_plan_from_requirement(
    input_data: RequirementExplorationInput,
) -> RequirementExplorationPlan:
    """
    从需求文档生成探索计划

    Args:
        input_data: 包含需求文档和项目上下文的输入

    Returns:
        RequirementExplorationPlan: 生成的探索计划
    """
    model = get_model()
    agent = requirement_exploration_agent(model)

    # 构造agent输入
    agent_input = {
        "requirement_markdown": input_data.requirement_markdown,
        "project_context": input_data.project_context,
    }

    # 调用agent生成计划
    result = await agent.ainvoke(agent_input)

    # 提取输出
    if isinstance(result, dict) and "output" in result:
        output = result["output"]
    else:
        output = result

    # 确保返回正确的类型
    if isinstance(output, RequirementExplorationPlan):
        return output
    elif isinstance(output, dict):
        return RequirementExplorationPlan(**output)
    else:
        raise ValueError(f"Unexpected agent output type: {type(output)}")


def generate_exploration_plan_from_requirement_sync(
    input_data: RequirementExplorationInput,
) -> RequirementExplorationPlan:
    """同步版本的生成探索计划"""
    return asyncio.run(generate_exploration_plan_from_requirement(input_data))
