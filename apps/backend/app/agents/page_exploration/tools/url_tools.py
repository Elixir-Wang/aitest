"""Schema 4.0 page and shared-coverage lookup tools."""
from __future__ import annotations

from pathlib import Path

import yaml

from app.services.page_exploration.coverage_registry import load_coverage


def check_explored_url(
    normalized_path: str,
    project_id: str,
    base_dir: Path,
    force_reexplore: bool = False,
) -> dict:
    project_root = Path(base_dir) / project_id / "page_exploration"
    pages_dir = project_root / "pages"
    result = {
        "explored": False,
        "page_id": "",
        "page_completed": False,
        "completed_states": 0,
        "completed_operations": 0,
        "pending_operations": 0,
    }
    if pages_dir.exists():
        for yaml_path in pages_dir.glob("*.yaml"):
            try:
                obj = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(obj, dict) or str(obj.get("schema_version")) != "4.0":
                continue
            page = obj.get("page") or {}
            if page.get("normalized_path") == normalized_path:
                result["page_id"] = str(page.get("id") or "")
                break
    if not result["page_id"]:
        return result

    coverage = load_coverage(Path(base_dir), project_id)
    pages = coverage.get("pages") if isinstance(coverage.get("pages"), dict) else {}
    page_coverage = pages.get(result["page_id"], {})
    if not isinstance(page_coverage, dict):
        return result
    states = page_coverage.get("states") if isinstance(page_coverage.get("states"), dict) else {}
    actions = page_coverage.get("actions") if isinstance(page_coverage.get("actions"), dict) else {}
    result["page_completed"] = page_coverage.get("status") == "complete"
    result["completed_states"] = sum(
        isinstance(entry, dict) and entry.get("status") == "completed" for entry in states.values()
    )
    result["completed_operations"] = sum(
        isinstance(entry, dict) and entry.get("status") == "completed" for entry in actions.values()
    )
    result["pending_operations"] = sum(
        not isinstance(entry, dict) or entry.get("status") != "completed" for entry in actions.values()
    )
    result["explored"] = not force_reexplore and result["page_completed"]
    return result


def make_check_explored_url_tool():
    """包装成 LangChain StructuredTool，运行身份由服务端上下文注入。"""
    from langchain_core.tools import tool

    from app.agents.page_exploration.tools.runtime_context import require_exploration_runtime

    @tool("check_explored_url_tool")
    def _impl(normalized_path: str) -> dict:
        """Check whether a normalized URL path has been explored.

        Returns:
          - explored: bool
          - page_id: stable Schema 4.0 page id
          - page_completed: bool
          - completed_states/completed_operations/pending_operations: shared coverage counts
        """
        runtime = require_exploration_runtime()
        return check_explored_url(
            normalized_path=normalized_path,
            project_id=runtime.project_id,
            base_dir=runtime.storage_root,
        )
    return _impl
