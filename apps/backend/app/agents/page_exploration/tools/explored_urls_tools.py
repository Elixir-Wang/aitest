"""LangChain tools for explored URLs management"""

from langchain_core.tools import tool

from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService
from app.agents.page_exploration.utils.url_normalizer import normalize_url


@tool
def check_explored_url_tool(url: str, project_id: str) -> dict:
    """
    Check if a URL has been explored before in this project.

    Use this tool to:
    - Avoid exploring the same page multiple times in one run
    - Check if a page artifact already exists
    - Get information about when a page was last explored

    This tool uses URL normalization to match URLs across different environments:
    - https://test.example.com/workspace/agents → /workspace/agents
    - https://prod.example.com/workspace/agents → /workspace/agents
    - Both are considered the same page

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

    Example:
        result = check_explored_url_tool(
            url="https://test.example.com/workspace/agents",
            project_id="proj-123"
        )
        # Returns:
        # {
        #   "explored": true,
        #   "page_id": "page-workspace-agents",
        #   "page_file": "pages/page-workspace-agents.yaml",
        #   "last_explored_at": "2026-06-27T10:00:00Z",
        #   "last_run_id": "run-001",
        #   "normalized_path": "/workspace/agents"
        # }
    """
    normalized_path = normalize_url(url)
    service = ExploredUrlsService(project_id)
    result = service.check(normalized_path)

    # Always include the normalized_path in the result
    result["normalized_path"] = normalized_path

    return result


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
        # Returns:
        # {
        #   "success": true,
        #   "normalized_path": "/workspace/agents",
        #   "page_id": "page-workspace-agents",
        #   "run_id": "run-001"
        # }
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
