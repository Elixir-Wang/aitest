from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.api_automation.orchestration.schemas import ScenarioPlanResult
from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware


def api_scenario_orchestration_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=(
            "你是接口自动化编排规划器。只能从用户提供的当前项目接口资产中选择 endpoint_id，"
            "不得生成 URL、脚本或调用接口。输出必须是增强线性场景计划，按依赖顺序排列节点。"
            "每个接口请求尽量生成状态码断言；无法确定字段时写入 unresolved_items，不要猜测。"
        ),
        middleware=[InvalidToolCallRecoveryMiddleware()],
        response_format=ToolStrategy(ScenarioPlanResult),
    )
