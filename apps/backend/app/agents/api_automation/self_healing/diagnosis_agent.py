from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.api_automation.self_healing.schemas import FailureDiagnosis
from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.skill_middleware import SkillMiddleware


SYSTEM_PROMPT = """
你是接口自动化失败诊断智能体。只分析，不修改文件。
必须把失败分类为 test_code_issue、test_data_issue、environment_issue、interface_bug、contract_ambiguity 或 unknown。
优先使用用户确认规则、已审批用例、正式接口契约、实际请求响应、历史稳定结果，最后才使用常见约定推断。
接口缺陷只输出证据和定位建议，不修改业务代码。不得为了让测试通过而删除用例、跳过用例或弱化断言。
只有 classification 为 test_code_issue 时才生成 proposal，且 proposal.target 必须为 test_script、script_repair_allowed 必须为 true。proposal.proposed_changes 只填写明确的文件路径、函数/代码位置和修改内容，保持简短。
interface_bug、contract_ambiguity、test_data_issue、environment_issue 或 unknown 只输出简短诊断结论，不生成 proposal、风险清单或问题清单，也不引导修改测试脚本。
不要为了完整而重复输出状态码、证据、影响用例等信息；只有它们直接决定测试代码修改时才保留。
""".strip()


def create_diagnosis_agent(*, model):
    middleware = [
        SkillMiddleware(
            skill_path=Path(__file__).parent / "skills" / "api-failure-diagnosis",
            load_references=True,
        ),
        InvalidToolCallRecoveryMiddleware(),
    ]
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        response_format=ToolStrategy(FailureDiagnosis),
    )


async def diagnose_failure(*, model, context: dict[str, Any]) -> FailureDiagnosis:
    result = await create_diagnosis_agent(model=model).ainvoke(
        {"messages": [{"role": "user", "content": json.dumps(context, ensure_ascii=False)}]}
    )
    if not isinstance(result, dict) or not result.get("structured_response"):
        raise ValueError("接口自动化失败诊断智能体未返回结构化结果。")
    structured = result["structured_response"]
    if isinstance(structured, FailureDiagnosis):
        return structured
    return FailureDiagnosis.model_validate(structured)
