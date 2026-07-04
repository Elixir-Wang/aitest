"""
产物管理工具

包含：
- write_page_artifact_tool: 保存项目级页面产物
"""

from datetime import datetime, UTC
from typing import List, Dict, Optional

from langchain_core.tools import tool

from app.agents.page_exploration.services.explored_urls_service import ExploredUrlsService
from app.agents.page_exploration.utils.url_normalizer import normalize_url
from app.core.settings import PROJECT_FILE_STORAGE_ROOT
from app.services.page_exploration import ProjectPagesService


@tool
def write_page_artifact_tool(
    url: str,
    title: str,
    elements: List[Dict],
    project_id: str,
    page_id: Optional[str] = None,
) -> dict:
    """DEPRECATED: 由 T6 删除。新入口请用 `PageArtifactWriter.merge_states`。
    本函数暂留以避免破坏外部 import。

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

    # 幂等性保护：同 normalized_path 已探索过则直接返回已有 page_id，
    # 避免 LLM 在循环中反复 write 同一页面产生重复 yaml 产物。
    base_dir = PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration"
    explored = ExploredUrlsService(project_id, base_dir=base_dir).check(normalized_path)
    if explored.get("explored"):
        return {
            "success": True,
            "page_id": explored.get("page_id", page_id),
            "file_path": explored.get("page_file", ""),
            "normalized_path": normalized_path,
            "element_count": len(elements),
            "skipped": True,
            "reason": "url_already_explored",
        }

    pages_service = ProjectPagesService(project_id, base_dir=base_dir)
    breadcrumb = _breadcrumb_from_path(normalized_path)
    display_name = breadcrumb[-1]
    page_data = {
        "title": title,
        "display_name": display_name,
        "breadcrumb": breadcrumb,
        "structure_summary": f"自动保存页面快照，发现 {len(elements)} 个元素。",
        "elements": elements,
        "metadata": {
            "explored_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    }
    saved = pages_service.save_page(
        page_id=page_id,
        page_data=page_data,
        run_id="manual-tool",
        url=url,
        normalized_path=normalized_path,
    )
    if not saved:
        return {
            "success": False,
            "page_id": page_id,
            "normalized_path": normalized_path,
            "element_count": len(elements),
        }
    resolved_page_id = pages_service.find_page_by_path(normalized_path) or page_id
    page_id = resolved_page_id
    file_path = pages_service.pages_dir / f"{page_id}.yaml"
    pages_service.update_cache_index(
        normalized_path=normalized_path,
        page_id=page_id,
        run_id="manual-tool",
        page_signature={
            "title": title,
            "display_name": display_name,
            "element_count": len(elements),
        },
        env_urls={"test": url},
    )

    doc_path = file_path.with_suffix(".md")
    doc_path.write_text(
        _render_human_page_doc(
            title=title,
            url=url,
            normalized_path=normalized_path,
            elements=elements,
        ),
        encoding="utf-8",
    )

    return {
        "success": True,
        "page_id": page_id,
        "file_path": str(file_path),
        "doc_path": str(doc_path),
        "normalized_path": normalized_path,
        "element_count": len(elements),
    }


def _breadcrumb_from_path(normalized_path: str) -> List[str]:
    segments = [segment for segment in normalized_path.strip("/").split("/") if segment]
    return segments or ["首页"]


def _render_human_page_doc(
    *,
    title: str,
    url: str,
    normalized_path: str,
    elements: List[Dict],
) -> str:
    page_title = title.strip() or normalized_path or url
    lines = [
        f"# {page_title}",
        "",
        "## 页面用途",
        "",
        f"该页面位于 `{normalized_path}`，本产物基于页面探索事实生成，用于帮助人工理解页面内容和后续测试范围。",
        "",
        "## 页面内容",
        "",
        f"- 页面地址：`{url}`",
        f"- 归一化路径：`{normalized_path}`",
        f"- 已记录元素数：{len(elements)}",
        "",
        "## 页面功能",
        "",
    ]
    if elements:
        for element in elements:
            name = str(element.get("name") or element.get("id") or "未命名元素")
            role = str(element.get("role") or "element")
            lines.append(f"- {name}（{role}）")
    else:
        lines.append("- 本次探索未记录可交互元素。")

    lines.extend([
        "",
        "## 关键元素",
        "",
        "| 名称 | 类型 | 作用 | 推荐定位器 |",
        "|---|---|---|---|",
    ])
    if elements:
        for element in elements:
            name = str(element.get("name") or element.get("id") or "")
            role = str(element.get("role") or "")
            locator = _first_locator_code(element)
            purpose = str(element.get("description") or element.get("purpose") or "页面交互元素")
            lines.append(f"| {name} | {role} | {purpose} | `{locator}` |")
    else:
        lines.append("| 无 |  |  |  |")

    lines.extend([
        "",
        "## 已探索交互",
        "",
        "| 操作 | 结果 | 状态 |",
        "|---|---|---|",
        "| 页面结构采集 | 已生成页面机器可读产物和人工说明文档 | completed |",
        "",
        "## 跳过和阻塞",
        "",
        "- 当前产物未记录跳过操作或阻塞项。",
        "",
        "## 测试建议",
        "",
    ])
    if elements:
        lines.append("- 基于关键元素补充可见性、可点击性和主要交互流程测试。")
    else:
        lines.append("- 页面暂无可交互元素记录，建议先补充页面快照或人工确认页面加载状态。")
    lines.append("")
    return "\n".join(lines)


def _first_locator_code(element: Dict) -> str:
    locators = element.get("locators")
    if not isinstance(locators, list):
        return ""
    for locator in locators:
        if isinstance(locator, dict) and locator.get("code"):
            return str(locator["code"])
    return ""


__all__ = [
    "write_page_artifact_tool",
]
