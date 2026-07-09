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
    playwright_press_tool,
)

from app.agents.page_exploration.tools.extraction_tools import (
    playwright_observe_overlays_tool,
    playwright_scoped_query_tool,
    playwright_screenshot_tool,
    playwright_snap_tool,
)

from app.agents.page_exploration.tools.state_tools import update_explored_url_tool

from app.agents.page_exploration.tools.artifact_tools import (
    make_artifact_tools,
    read_page_artifact,
    merge_page_artifact,
)
from app.agents.page_exploration.tools.url_tools import (
    make_check_explored_url_tool,
    check_explored_url,
)

# Lazy reference – artifacts need base_dir resolved at import time.
# agent.py already imports PROJECT_FILE_STORAGE_ROOT, so we import it here too.
from app.core.settings import PROJECT_FILE_STORAGE_ROOT


# ==================== 工具分类 ====================

check_explored_url_tool = make_check_explored_url_tool(PROJECT_FILE_STORAGE_ROOT)

NAVIGATION_TOOLS = [
    playwright_navigate_tool,
    playwright_click_tool,
    playwright_fill_tool,
    playwright_press_tool,
]

EXTRACTION_TOOLS = [
    playwright_snap_tool,
    playwright_scoped_query_tool,
    playwright_observe_overlays_tool,
    playwright_screenshot_tool,
]

STATE_TOOLS = [
    check_explored_url_tool,
    update_explored_url_tool,
]

# Empty list; replaced by get_artifact_tools() below so base_dir is resolved lazily.
ARTIFACT_TOOLS: list = []


def get_artifact_tools() -> list:
    """Return artifact tools instantiated with the default project storage root."""
    return make_artifact_tools(base_dir=PROJECT_FILE_STORAGE_ROOT)


# 所有工具（artifact tools 延迟加载）
ALL_PAGE_EXPLORATION_TOOLS = [
    *NAVIGATION_TOOLS,
    *EXTRACTION_TOOLS,
    *STATE_TOOLS,
    *get_artifact_tools(),
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


__all__ = [
    # 导航工具
    "playwright_navigate_tool",
    "playwright_click_tool",
    "playwright_fill_tool",
    "playwright_press_tool",
    # 提取工具
    "playwright_snap_tool",
    "playwright_scoped_query_tool",
    "playwright_observe_overlays_tool",
    "playwright_screenshot_tool",
    # 状态工具
    "check_explored_url_tool",
    "update_explored_url_tool",
    # 产物工具（工厂函数 + 核心函数）
    "make_artifact_tools",
    "read_page_artifact",
    "merge_page_artifact",
    # URL 工具（工厂函数 + 核心函数）
    "make_check_explored_url_tool",
    "check_explored_url",
    # 分类
    "NAVIGATION_TOOLS",
    "EXTRACTION_TOOLS",
    "STATE_TOOLS",
    "ARTIFACT_TOOLS",
    "ALL_PAGE_EXPLORATION_TOOLS",
    # 便捷函数
    "get_local_tools",
    "get_artifact_tools",
]
