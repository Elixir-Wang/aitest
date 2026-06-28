"""
产物管理工具

包含：
- write_page_artifact_tool: 保存页面产物
- save_page_snapshot_tool: 保存页面快照
"""

from pathlib import Path
from datetime import datetime, UTC
from typing import List, Dict, Optional
import yaml

from langchain_core.tools import tool

from app.agents.page_exploration.utils.url_normalizer import normalize_url
from app.core.settings import PROJECT_FILE_STORAGE_ROOT


@tool
def write_page_artifact_tool(
    url: str,
    title: str,
    elements: List[Dict],
    project_id: str,
    page_id: Optional[str] = None,
) -> dict:
    """
    Write or update a page artifact YAML file.

    Use this tool to:
    - Save page exploration results
    - Create a reusable page object model
    - Store element locators for test case generation

    The artifact will be saved to:
    data/projects/{project_id}/page_exploration/pages/{page_id}.yaml

    Each element should have:
    - id: Element identifier (e.g., "create_agent_btn")
    - name: Human-readable name (e.g., "创建智能体")
    - role: Element role (e.g., "button", "link", "textbox")
    - locators: List of locator strategies, each with:
      - kind: Locator type (e.g., "role", "label", "testid", "text")
      - code: Playwright locator code (e.g., "getByRole('button', { name: '创建' })")
      - priority: Priority order (1 = highest)

    Args:
        url: The full URL of the page (will be normalized)
        title: Page title
        elements: List of element dictionaries with id, name, role, locators
        project_id: The project ID
        page_id: Optional page identifier (auto-generated if not provided)

    Returns:
        A dictionary containing:
        - success: True if write succeeded
        - page_id: The page identifier
        - file_path: Path to the written YAML file
        - normalized_path: The normalized URL path
        - element_count: Number of elements written

    Example:
        result = write_page_artifact_tool(
            url="https://test.example.com/workspace/agents",
            title="Agent Workspace",
            elements=[
                {
                    "id": "create_agent_btn",
                    "name": "创建智能体",
                    "role": "button",
                    "locators": [
                        {
                            "kind": "role",
                            "code": "getByRole('button', { name: '创建智能体' })",
                            "priority": 1
                        }
                    ]
                }
            ],
            project_id="proj-123"
        )
    """
    normalized_path = normalize_url(url)

    # Auto-generate page_id if not provided
    if not page_id:
        # Convert path to page_id: /workspace/agents → page-workspace-agents
        page_id = "page-" + normalized_path.strip("/").replace("/", "-")

    # Prepare the page artifact structure
    artifact = {
        "page": {
            "id": page_id,
            "title": title,
            "normalized_path": normalized_path,
            "explored_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "elements": elements,
        }
    }

    # Determine file path
    pages_dir = PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration" / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    file_path = pages_dir / f"{page_id}.yaml"

    # Write to file
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(artifact, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    return {
        "success": True,
        "page_id": page_id,
        "file_path": str(file_path),
        "normalized_path": normalized_path,
        "element_count": len(elements),
    }


@tool
def save_page_snapshot_tool(
    url: str,
    title: str,
    page_data: Dict,
    project_id: str,
    run_id: str,
) -> dict:
    """
    Save a page snapshot for this exploration run.

    Use this tool to:
    - Record pages discovered during exploration
    - Track exploration history
    - Generate exploration reports

    The snapshot will be saved to:
    data/projects/{project_id}/page_exploration/runs/{run_id}/discovered_pages.yaml

    Args:
        url: The full URL of the page
        title: Page title
        page_data: Dictionary containing page information (elements, links, etc.)
        project_id: The project ID
        run_id: The exploration run ID

    Returns:
        A dictionary containing:
        - success: True if save succeeded
        - run_id: The run identifier
        - file_path: Path to the snapshot file

    Example:
        result = save_page_snapshot_tool(
            url="https://test.example.com/workspace",
            title="Workspace",
            page_data={"elements_count": 15, "links": [...]},
            project_id="proj-123",
            run_id="run-001"
        )
    """
    normalized_path = normalize_url(url)

    # Prepare snapshot structure
    snapshot = {
        "url": url,
        "normalized_path": normalized_path,
        "title": title,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "data": page_data,
    }

    # Determine file path
    run_dir = PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    file_path = run_dir / "discovered_pages.yaml"

    # Append to or create discovered_pages.yaml
    pages = []
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f)
            if existing and "pages" in existing:
                pages = existing["pages"]

    pages.append(snapshot)

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump({"pages": pages}, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    return {
        "success": True,
        "run_id": run_id,
        "file_path": str(file_path),
        "pages_count": len(pages),
    }


__all__ = [
    "write_page_artifact_tool",
    "save_page_snapshot_tool",
]
