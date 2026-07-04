"""
探索状态管理工具

包含：
- check_explored_url_tool: 检查URL是否已探索（v2.0，支持 has_state_tree）
- update_explored_url_tool: 标记URL为已探索
"""

from langchain_core.tools import tool

from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService
from app.agents.page_exploration.utils.url_normalizer import normalize_url


def _check_explored_url_impl(url: str, project_id: str, base_dir=None):
    """Shared logic: accepts raw url, normalizes, checks explored_urls.yaml and state tree."""
    normalized_path = normalize_url(url)

    # 1. Check explored_urls.yaml (old behavior)
    service = ExploredUrlsService(project_id)
    result = service.check(normalized_path)

    # 2. Enhance with has_state_tree if pages exist
    if base_dir:
        from pathlib import Path
        pages_dir = Path(base_dir) / project_id / "page_exploration" / "pages"
        if pages_dir.exists():
            for yaml_path in pages_dir.glob("*.yaml"):
                try:
                    text = yaml_path.read_text(encoding="utf-8")
                except Exception:
                    continue
                if 'schema_version: "2.0"' in text or "schema_version: '2.0'" in text:
                    result["has_state_tree"] = True
                    return result
        result["has_state_tree"] = False

    result["normalized_path"] = normalized_path
    return result


@tool
def check_explored_url_tool(url: str, project_id: str) -> dict:
    """
    Check if a URL has been explored and whether it has a v2.0 state tree.

    Use this tool to:
    - Avoid exploring the same page multiple times in one run
    - Check if a page artifact already exists
    - Determine if the page has a complete state tree

    This tool uses URL normalization to match URLs across different environments:
    - https://test.example.com/workspace/agents → /workspace/agents
    - https://prod.example.com/workspace/agents → /workspace/agents

    Args:
        url: The full URL to check (will be normalized internally)
        project_id: The project ID to check against

    Returns:
        A dictionary containing:
        - explored: True if URL was explored before, False otherwise
        - page_id: Page identifier (if explored)
        - page_file: Path to the page artifact YAML file (if explored)
        - last_explored_at: ISO timestamp of last exploration (if explored)
        - last_run_id: The run ID that last explored this page (if explored)
        - normalized_path: The normalized path used for matching
        - has_state_tree: True if the page has a v2.0 state tree

    Example:
        result = check_explored_url_tool(
            url="https://test.example.com/workspace/agents",
            project_id="proj-123"
        )
        # Returns: {"explored": True, "has_state_tree": True, ...}
    """
    return _check_explored_url_impl(url=url, project_id=project_id)


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
    "check_explored_url_tool",
    "update_explored_url_tool",
]
