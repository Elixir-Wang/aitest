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

from app.agents.page_exploration.tools import get_local_tools
from app.agents.page_exploration.prompts.system_prompt import SYSTEM_PROMPT


def page_exploration_agent(
    model,
    project_id: str,
    run_id: str,
):
    """
    创建页面探索智能体

    架构：
    - 单一 Agent
    - 无结构化输出约束（自由探索）
    - 自动加载 Skills（page_explorer, locator_best_practices）
    - deepagents 自动管理中间件（包括汇总和技能注入）

    Args:
        model: LLM 模型实例
        project_id: 项目ID（用于工具调用时指定存储路径）
        run_id: 探索任务ID（用于工具调用时指定运行标识）

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

    # 3. 创建Agent - deepagents 会自动添加汇总中间件和技能加载
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        skills=["app/agents/page_exploration/skills/"],  # 自动发现子技能
    )


__all__ = ["page_exploration_agent"]


__all__ = ["page_exploration_agent"]
