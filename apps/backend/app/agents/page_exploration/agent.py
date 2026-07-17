"""
页面探索智能体

该智能体负责页面探索的全生命周期管理：
- 页面分析与元素识别
- 页面快照生成
- 元素定位器提取
- 探索报告生成

架构设计：
- Agent: 使用 deepagents 框架，工作流编排与用户交互
- Skills: 领域知识与最佳实践指导（自动加载 SKILL.md）
- Tools: 原子操作（Playwright CLI、数据库、存储）
- Middleware: deepagents自动管理（通过backend和skills自动添加汇总等中间件）
"""

from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware

from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.page_exploration.tools import get_local_tools
from app.agents.page_exploration.prompts.autonomous_system_prompt import AUTONOMOUS_SYSTEM_PROMPT
from app.agents.page_exploration.prompts.system_prompt import SYSTEM_PROMPT


def page_exploration_agent(
    model,
    tools=None,
    skill_names=None,
    max_actions: int = 80,
    exploration_mode: str = "goal",
):
    """
    创建页面探索智能体

    架构：
    - 单一 Agent
    - 无结构化输出约束（自由探索）
    - 自动加载 Skills（page-explorer, locator-best-practices）
    - deepagents 自动管理中间件（包括汇总和技能注入）
    - 硬截断：单次 run 内最多 max_actions 次工具调用

    Args:
        model: LLM 模型实例
        tools: 可选的额外工具列表
        skill_names: 可选的技能名称列表
        max_actions: 单次 run 的工具调用上限（默认 80）。即便 LLM
            陷入循环也会被 ToolCallLimitMiddleware 硬截断。

    Returns:
        配置好的页面探索 Agent
    """
    # 1. 创建Backend（用于加载Skills和汇总中间件的历史存储）
    backend_root = Path(__file__).parent.parent.parent.parent  # apps/backend/
    backend = FilesystemBackend(
        root_dir=str(backend_root),
        virtual_mode=True,
    )

    # 2. 加载工具
    all_tools = list(get_local_tools())
    if tools:
        all_tools.extend(tools)

    # 3. 处理技能名称
    if exploration_mode not in {"goal", "autonomous"}:
        raise ValueError(f"不支持的页面探索模式: {exploration_mode}")

    skills = [
        "app/agents/page_exploration/skills/page-explorer/"
        if exploration_mode == "goal"
        else "app/agents/page_exploration/skills/autonomous-explorer/",
        "app/agents/page_exploration/skills/locator-best-practices/",
    ]
    if skill_names:
        skills.extend(skill_names)

    # 4. 硬截断：防止 LLM 陷入物理死循环
    middleware = [
        InvalidToolCallRecoveryMiddleware(max_retries=2),
        ToolCallLimitMiddleware(
            thread_limit=max_actions,
            run_limit=max_actions,
        ),
    ]

    # 5. 创建Agent - deepagents 会自动添加汇总中间件和技能加载
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT if exploration_mode == "goal" else AUTONOMOUS_SYSTEM_PROMPT,
        backend=backend,
        skills=skills,  # 自动发现子技能
        middleware=middleware,
    )
