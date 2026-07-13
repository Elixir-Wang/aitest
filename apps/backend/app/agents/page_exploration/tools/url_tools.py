"""check_explored_url_tool: 返回 (explored, has_state_tree, remaining_subgoals) 三元组。

remaining_subgoals 来自本 run 写出的 subgoals.yaml（由 service 在收到 LLM
write_todos 事件时落盘），方便 LLM 在每次 check 之后知道"还有几个子目标没完成"。
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def _read_subgoals(project_dir: Path) -> dict[str, Any]:
    """读取本项目下的 subgoals.yaml（service 落盘），不依赖 LLM 显式写入。"""
    path = project_dir / "subgoals.yaml"
    if not path.exists():
        return {"total": 0, "completed": 0, "pending": 0, "items": []}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"total": 0, "completed": 0, "pending": 0, "items": []}
    items = loaded.get("items") if isinstance(loaded.get("items"), list) else []
    total = len(items)
    completed = sum(1 for it in items if isinstance(it, dict) and it.get("status") == "completed")
    pending = total - completed
    return {"total": total, "completed": completed, "pending": pending, "items": items}


def check_explored_url(
    normalized_path: str,
    project_id: str,
    base_dir: Path,
) -> dict:
    project_root = Path(base_dir) / project_id / "page_exploration"
    pages_dir = project_root / "pages"
    result: dict[str, Any] = {"explored": False, "has_state_tree": False}
    if pages_dir.exists():
        for yaml_path in pages_dir.glob("*.yaml"):
            try:
                obj = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            page = obj.get("page") or {}
            if (
                obj.get("schema_version") in {"2.0", "3.0"}
                and page.get("normalized_path") == normalized_path
            ):
                result["explored"] = True
                result["has_state_tree"] = True
                break

    # 注入"剩余子目标"信息：让 LLM 一眼看到自己离目标完成还差几步
    subgoals = _read_subgoals(project_root)
    result["subgoals"] = {
        "total": subgoals["total"],
        "completed": subgoals["completed"],
        "pending": subgoals["pending"],
    }
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
          - has_state_tree: bool
          - subgoals: {total, completed, pending}  # 来自 service 落盘的 subgoals.yaml
        """
        runtime = require_exploration_runtime()
        return check_explored_url(
            normalized_path=normalized_path,
            project_id=runtime.project_id,
            base_dir=runtime.storage_root,
        )
    return _impl


def write_subgoals_snapshot(
    *,
    project_id: str,
    run_id: str,
    base_dir: Path,
    todos: list[dict],
) -> dict:
    """把当前 write_todos 状态落盘到 {base_dir}/{project_id}/page_exploration/subgoals.yaml。

    todos: LLM 调用 write_todos 时传进来的 todos 列表，每条 {id, content, status, ...}
    返回新文件的写入结果摘要。
    """
    project_root = Path(base_dir) / project_id / "page_exploration"
    project_root.mkdir(parents=True, exist_ok=True)
    items = []
    for todo in todos or []:
        if not isinstance(todo, dict):
            continue
        items.append({
            "id": str(todo.get("id") or ""),
            "content": str(todo.get("content") or ""),
            "status": str(todo.get("status") or "pending"),
        })
    payload = {
        "run_id": run_id,
        "project_id": project_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    path = project_root / "subgoals.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {
        "path": str(path),
        "total": len(items),
        "completed": sum(1 for it in items if it["status"] == "completed"),
        "pending": sum(1 for it in items if it["status"] != "completed"),
    }
