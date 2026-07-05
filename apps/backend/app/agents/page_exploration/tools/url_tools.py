"""check_explored_url_tool: 返回 (explored, has_state_tree) 二维。"""
from __future__ import annotations

from pathlib import Path

import yaml


def check_explored_url(
    normalized_path: str,
    project_id: str,
    base_dir: Path,
) -> dict:
    project_root = Path(base_dir) / project_id / "page_exploration"
    pages_dir = project_root / "pages"
    if not pages_dir.exists():
        return {"explored": False, "has_state_tree": False}
    for yaml_path in pages_dir.glob("*.yaml"):
        try:
            obj = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        page = obj.get("page") or {}
        if (
            obj.get("schema_version") == "2.0"
            and page.get("normalized_path") == normalized_path
        ):
            return {"explored": True, "has_state_tree": True}
    return {"explored": False, "has_state_tree": False}


def make_check_explored_url_tool(base_dir: Path):
    """包装成 LangChain StructuredTool, 注入 base_dir."""
    from langchain_core.tools import tool

    @tool("check_explored_url_tool")
    def _impl(normalized_path: str, project_id: str) -> dict:
        """Check whether a normalized URL path has been explored.
        Returns: {explored: bool, has_state_tree: bool}"""
        return check_explored_url(normalized_path=normalized_path, project_id=project_id, base_dir=base_dir)
    return _impl
