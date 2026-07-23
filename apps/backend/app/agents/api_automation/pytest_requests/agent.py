from __future__ import annotations

import json
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.api_automation.pytest_requests.collection import build_collection_tool
from app.agents.api_automation.pytest_requests.suite import ensure_suite_root


SYSTEM_PROMPT = """
你是一个项目级 pytest + requests 自动化测试智能体。

你只能操作当前 filesystem backend 的根目录，它就是当前业务项目的 pytest_requests 项目目录。
先检查现有目录和文件，再执行初始化或接口增量生成；不要创建第二个测试项目。

初始化阶段必须先确保公共框架存在，包括 AGENTS.md、pytest.ini、conftest.py、
api/client.py、testcases/conftest.py、utils/__init__.py、utils/data_loader.py、utils/assertions.py、
utils/assert_utils.py、support/__init__.py、config/__init__.py 和 data/__init__.py。

接口生成阶段只处理后端提供的 endpoint 和 cases，保留未选中的接口文件。不得把 base URL、Token、Cookie、
密码或宿主机绝对路径写入源代码；运行时值必须通过环境变量读取。

每个 endpoint 的 artifacts.directory、artifacts.test_file 和 artifacts.data_file 由后端确定，是该接口唯一合法的
输出目录、测试文件和数据文件。必须严格写入这些相对路径，不得自行改成 test_agent.py、test_v1.py 或其他目录。
后端会在调用前写好 artifacts.data_file；该文件是数据库用例快照，只能读取，不得重写、追加、包装 cases 键、
修改 id/endpoint_id 或复制已有用例。只创建或更新 artifacts.test_file，并复用当前项目已有公共代码。
对于 oracle_status 为 inferred 或 needs_confirmation 的用例，测试文件必须先调用 utils.observations.record_observation(case, response)
记录脱敏实际响应，再执行数据文件中的当前最佳断言。断言失败必须正常计入 failed，供 AI 修复流程根据观察证据判断测试数据、
Oracle、测试代码或接口实现问题；禁止使用 pytest.skip 或跳过断言制造假通过。

完成文件修改后执行 pytest --collect-only。collection 失败时，读取 traceback 和相关文件，修复后重试；
collection 不得发送真实 API 请求。只有整个项目 collection 成功后，才报告生成成功。
""".strip()


def create_pytest_requests_agent(*, model, suite_path: Path, max_actions: int = 80):
    resolved_suite_path = ensure_suite_root(suite_path)
    backend = FilesystemBackend(root_dir=str(resolved_suite_path), virtual_mode=True)
    middleware = [
        InvalidToolCallRecoveryMiddleware(max_retries=2),
        ToolCallLimitMiddleware(thread_limit=max_actions, run_limit=max_actions),
    ]
    tools = [build_collection_tool(suite_path=resolved_suite_path)]
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        skills=[".deepagents/skills"],
        middleware=middleware,
    )


async def initialize_pytest_requests_suite(*, model, suite_path: Path, max_actions: int = 80) -> dict:
    agent = create_pytest_requests_agent(model=model, suite_path=suite_path, max_actions=max_actions)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "初始化当前 pytest_requests 项目。先检查现有目录，补齐缺失的公共框架文件（包括 AGENTS.md），"
                        "不要删除已有 endpoint 测试。完成后调用 run_pytest_collection 验证整个项目；"
                        "如果 collection 失败，读取错误并修复，直到成功或达到工具调用上限。"
                    ),
                }
            ]
        }
    )
    if not isinstance(result, dict):
        raise ValueError("pytest 项目初始化 Agent 返回格式不正确。")
    return result


async def generate_pytest_requests_endpoints(
    *,
    model,
    suite_path: Path,
    endpoints: list[dict],
    cases_by_endpoint: dict[str, list[dict]],
    max_actions: int = 120,
) -> dict:
    agent = create_pytest_requests_agent(model=model, suite_path=suite_path, max_actions=max_actions)
    payload = {
        "endpoints": endpoints,
        "cases_by_endpoint": cases_by_endpoint,
    }
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "在当前 pytest_requests 项目中生成或更新选中的接口测试。先读取现有项目结构和 AGENTS.md，"
                        "只处理下面 JSON 中的 endpoint 及其 cases，保留未选中的 endpoint 文件。复用已有公共 client、"
                        "fixture、loader 和 assertions；不要创建第二个测试项目。每个 endpoint 的 artifacts.test_file 和 "
                        "artifacts.data_file 是唯一合法输出文件，必须创建或更新这些精确路径，不得自行选择其他文件名或目录。"
                        "artifacts.data_file 已由后端根据数据库快照写入，只允许读取，禁止覆盖、追加或改变其 YAML 结构；"
                        "仅生成或更新 artifacts.test_file。"
                        "修改后先收集变更测试，再收集整个项目，"
                        "collection 失败时读取错误并修复。\n\n"
                        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                    ),
                }
            ]
        }
    )
    if not isinstance(result, dict):
        raise ValueError("pytest 接口脚本生成 Agent 返回格式不正确。")
    return result
