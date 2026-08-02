from __future__ import annotations

import json
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.tools import StructuredTool

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware

from .collection import collect_suite
from .renderer import initialize_suite, render_automation_plan
from .schemas import AutomationPlan
from .suite import ensure_suite_root, relative_suite_path


SYSTEM_PROMPT = """
你是业务项目专属 pytest + Playwright UI 自动化代码生成智能体。

当前 filesystem backend 根目录是当前业务项目的 pytest_playwright 工程目录。先检查现有工程，
不存在时补齐公共框架；只能写入后端提供的 project_key 命名空间，不得访问根目录之外的文件。

后端会提供单条测试用例、探索证据以及 artifacts.test_file、artifacts.data_file、artifacts.plan_file。
这些路径是本次任务唯一合法的输出路径。允许修改指定的派生测试数据文件，包括规范化、参数化和补充
执行辅助字段，但不得回写原始测试用例，不得写入账号、密码、Cookie、Token 或宿主机绝对路径。

必须只使用探索证据中存在的页面、操作路径和 locator；不得编造 locator。先形成严格 AutomationPlan，
调用 validate_automation_plan 校验，再调用 render_automation_plan 生成或更新 POM 与测试代码。
如果 case.parameters 声明了参数，AutomationPlan.parameters 必须包含对应参数名；使用参数值选择页面文本时，
使用 click_parameter_text 并通过 value_ref 引用参数，禁止把某个参数值固化成 locator。
每个自动化动作必须使用 business_step_id 显式引用原始用例步骤 ID，并填写一致的用户可读 title；
同一业务步骤拆出的 fill、click、wait 等动作必须共享 business_step_id，禁止用合成 ID 代替业务步骤映射。
发送聊天消息后等待助手回复时，必须使用 wait_for_response，并确保目标 locator 只匹配助手回复；
不得用 wait_visible 代替，也不得假设页面存在初始欢迎语。
不得绕过渲染工具直接写任意 Python 测试代码。完成后调用 run_pytest_collection；生成阶段不得执行真实 UI 用例。
""".strip()


def create_pytest_playwright_agent(*, model, suite_path: Path, max_actions: int = 100):
    resolved = ensure_suite_root(suite_path)
    initialize_suite(resolved)
    backend = FilesystemBackend(root_dir=str(resolved), virtual_mode=True)
    return create_deep_agent(
        model=model,
        backend=backend,
        tools=[
            _build_validate_tool(),
            _build_render_tool(resolved),
            _build_collection_tool(resolved),
        ],
        skills=[".deepagents/skills"],
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            InvalidToolCallRecoveryMiddleware(max_retries=2),
            ToolCallLimitMiddleware(thread_limit=max_actions, run_limit=max_actions),
        ],
    )


async def generate_pytest_playwright_case(
    *,
    model,
    suite_path: Path,
    case_payload: dict,
    evidence_payload: dict,
    artifacts: dict[str, str],
    max_actions: int = 100,
) -> dict:
    agent = create_pytest_playwright_agent(model=model, suite_path=suite_path, max_actions=max_actions)
    payload = {
        "case": case_payload,
        "evidence": evidence_payload,
        "artifacts": artifacts,
    }
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "为下面这一条已采纳 UI 测试用例生成或更新自动化代码。先读取当前项目框架和已有 POM。"
                        "artifacts.test_file、artifacts.data_file、artifacts.plan_file 是唯一合法目标；"
                        "可以调整 artifacts.data_file，但禁止修改原始用例事实。只能使用 evidence 中可追溯的 locator。"
                        "生成 AutomationPlan 后依次调用校验、渲染和 collection 工具。\n\n"
                        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                    ),
                }
            ]
        }
    )
    if not isinstance(result, dict):
        raise ValueError("pytest Playwright 生成 Agent 返回格式不正确。")
    return result


def _build_validate_tool() -> StructuredTool:
    def validate_automation_plan(plan: dict) -> dict:
        validated = AutomationPlan.model_validate(plan)
        return validated.model_dump(mode="json")

    return StructuredTool.from_function(
        func=validate_automation_plan,
        name="validate_automation_plan",
        description="Validate a complete AutomationPlan including explicit business-step mappings.",
    )


def _build_render_tool(suite_path: Path) -> StructuredTool:
    def render_plan(plan: dict) -> dict:
        validated = AutomationPlan.model_validate(plan)
        paths = render_automation_plan(suite_path, validated)
        return {
            "test_file": relative_suite_path(suite_path, paths["test_file"]),
            "plan_file": relative_suite_path(suite_path, paths["plan_file"]),
            "page_files": [relative_suite_path(suite_path, path) for path in paths["page_files"]],
        }

    return StructuredTool.from_function(
        func=render_plan,
        name="render_automation_plan",
        description="Deterministically render validated POM and pytest files inside the current suite.",
    )


def _build_collection_tool(suite_path: Path) -> StructuredTool:
    def run_pytest_collection(test_paths: list[str] | None = None) -> dict:
        return collect_suite(suite_path, test_paths=test_paths)

    return StructuredTool.from_function(
        func=run_pytest_collection,
        name="run_pytest_collection",
        description="Run pytest collection only; this tool never executes real UI tests.",
    )


__all__ = ["create_pytest_playwright_agent", "generate_pytest_playwright_case"]
