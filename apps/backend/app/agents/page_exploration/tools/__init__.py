"""
页面探索Agent工具模块

按功能分类组织所有工具：
- Navigation Tools: 页面导航和交互
- Extraction Tools: 页面信息提取
- State Tools: 探索状态管理
- Artifact Tools: 产物管理
"""

from app.agents.page_exploration.tools.navigation_tools import (
    playwright_navigate_tool,
    playwright_click_tool,
    playwright_fill_tool,
)

from app.agents.page_exploration.tools.extraction_tools import (
    playwright_snap_tool,
)

from app.agents.page_exploration.tools.state_tools import (
    check_explored_url_tool,
    update_explored_url_tool,
)

from app.agents.page_exploration.tools.artifact_tools import (
    write_page_artifact_tool,
)


# ==================== 工具分类 ====================


NAVIGATION_TOOLS = [
    playwright_navigate_tool,
    playwright_click_tool,
    playwright_fill_tool,
]

EXTRACTION_TOOLS = [
    playwright_snap_tool,
]

STATE_TOOLS = [
    check_explored_url_tool,
    update_explored_url_tool,
]

ARTIFACT_TOOLS = [
    write_page_artifact_tool,
]

# 所有工具
ALL_PAGE_EXPLORATION_TOOLS = [
    *NAVIGATION_TOOLS,
    *EXTRACTION_TOOLS,
    *STATE_TOOLS,
    *ARTIFACT_TOOLS,
]


# ==================== 便捷函数 ====================


def get_local_tools() -> list:
    """
    获取所有页面探索工具

    注意：工具需要的project_id和run_id参数由agent在调用时传递，
    不需要在加载时绑定。

    Returns:
        工具列表
    """
    return list(ALL_PAGE_EXPLORATION_TOOLS)


def get_exploration_tools() -> list:
    """获取探索工具（向后兼容别名）"""
    return get_local_tools()


__all__ = [
    # 导航工具
    "playwright_navigate_tool",
    "playwright_click_tool",
    "playwright_fill_tool",
    # 提取工具
    "playwright_snap_tool",
    # 状态工具
    "check_explored_url_tool",
    "update_explored_url_tool",
    # 产物工具
    "write_page_artifact_tool",
    # 分类
    "NAVIGATION_TOOLS",
    "EXTRACTION_TOOLS",
    "STATE_TOOLS",
    "ARTIFACT_TOOLS",
    "ALL_PAGE_EXPLORATION_TOOLS",
    # 便捷函数
    "get_local_tools",
    "get_exploration_tools",
]
