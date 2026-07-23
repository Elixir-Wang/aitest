from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.api_automation.self_healing.schemas import FailureDiagnosis, RepairResult


SYSTEM_PROMPT = """
你是 pytest + requests 测试项目修复智能体。当前 filesystem root 是唯一允许修改的临时 workspace。
可以修复测试代码、公共工具、配置和用例数据；不得修改业务系统代码，不得访问 workspace 外路径。
禁止删除失败用例、添加 skip/xfail、吞掉异常、移除关键断言或硬编码实际响应。
修改后必须调用受控验证工具。最终将结构化结果写入 .repair-result.json。
""".strip()


def create_repair_agent(*, model, workspace: Path, tools: list[Any] | None = None, max_actions: int = 80):
    return create_deep_agent(
        model=model,
        tools=tools or [],
        system_prompt=SYSTEM_PROMPT,
        backend=FilesystemBackend(root_dir=str(workspace.resolve()), virtual_mode=True),
        skills=[".deepagents/skills"],
        middleware=[
            InvalidToolCallRecoveryMiddleware(max_retries=2),
            ToolCallLimitMiddleware(thread_limit=max_actions, run_limit=max_actions),
        ],
    )


async def repair_failure(
    *,
    model,
    workspace: Path,
    diagnosis: FailureDiagnosis,
    context: dict[str, Any],
    tools: list[Any] | None = None,
) -> RepairResult:
    result_path = workspace / ".repair-result.json"
    agent = create_repair_agent(model=model, workspace=workspace, tools=tools)
    await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "根据诊断和上下文修复当前测试项目。完成后把 RepairResult JSON 写入 .repair-result.json。\n\n"
                        f"诊断:\n{diagnosis.model_dump_json(indent=2)}\n\n"
                        f"上下文:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
                    ),
                }
            ]
        }
    )
    if not result_path.exists():
        raise ValueError("接口自动化修复智能体未生成 .repair-result.json。")
    return RepairResult.model_validate_json(result_path.read_text(encoding="utf-8"))
