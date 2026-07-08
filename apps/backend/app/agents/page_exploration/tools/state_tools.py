"""
探索状态管理工具

包含：
- update_explored_url_tool: 标记URL为已探索
"""

from langchain_core.tools import tool

from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService
from app.agents.page_exploration.utils.url_normalizer import normalize_url


@tool
def update_explored_url_tool(
    url: str, page_id: str, project_id: str, run_id: str
) -> dict:
    """
    Mark a URL as explored and associate it with a page artifact.

    Use this tool to:
    - Record that a page has been explored in this run
    - Update the timestamp if the page was explored again
    - Link a URL to its page artifact file

    This will:
    - Create or update the explored_urls.yaml file
    - Add/update the URL record with current timestamp
    - Associate the URL with a page_id and run_id

    Args:
        url: The full URL that was explored (will be normalized internally)
        page_id: The page identifier (e.g., "page-workspace-agents")
        project_id: The project ID
        run_id: The current exploration run ID

    Returns:
        A dictionary containing:
        - success: True if update succeeded
        - normalized_path: The normalized path that was recorded
        - page_id: The page ID that was recorded
        - run_id: The run ID that was recorded

    Example:
        result = update_explored_url_tool(
            url="https://test.example.com/workspace/agents",
            page_id="page-workspace-agents",
            project_id="proj-123",
            run_id="run-001"
        )
        # Returns: {"success": true, "normalized_path": "/workspace/agents", ...}
    """
    normalized_path = normalize_url(url)
    service = ExploredUrlsService(project_id)

    # Update the explored URLs file
    service.update(normalized_path, page_id, run_id)

    return {
        "success": True,
        "normalized_path": normalized_path,
        "page_id": page_id,
        "run_id": run_id,
    }


__all__ = [
    "update_explored_url_tool",
]
