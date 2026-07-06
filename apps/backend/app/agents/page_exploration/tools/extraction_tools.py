"""
页面信息提取工具。
"""
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from app.agents.page_exploration.tools.runtime_context import snapshot_with_runtime_context


def _semantic_selector_code(selector: Optional[Dict[str, Any]]) -> str:
    """把 snap 端 primary_selector 结构化对象还原成可读 locator 字符串（用作 source.code）。"""
    if not isinstance(selector, dict):
        return ""
    kind = selector.get("kind")
    if kind == "playwright_api" and isinstance(selector.get("code"), str):
        return selector["code"]
    if kind == "role":
        name = (selector.get("name") or "").replace("'", "\\'")
        role = (selector.get("role") or "").replace("'", "\\'")
        return f"page.getByRole('{role}', {{ name: '{name}' }})"
    if kind == "label":
        return f"page.getByLabel('{selector.get('label', '')}')"
    if kind == "placeholder":
        return f"page.getByPlaceholder('{selector.get('placeholder', '')}')"
    if kind == "testid":
        return f"page.getByTestId('{selector.get('testId', '')}')"
    if kind == "text":
        return f"page.getByText('{selector.get('text', '')}')"
    if kind == "css" and isinstance(selector.get("css"), str):
        return f"page.locator('{selector['css']}')"
    return ""


def _dom_signature_for_url_title(url: str, title: str, sample: str) -> str:
    """生成确定性 dom_signature（避免 LLM 写占位符）。

    用 URL + title + 前 160 字 body 作为指纹来源（Playwright 不会泄漏到这里，
    用我们自己的 hash 即可）。"""
    digest_source = f"{normalize_url_for_sig(url)}|{title}|{sample[:160]}"
    return f"sha256-{hashlib.sha256(digest_source.encode('utf-8')).hexdigest()[:16]}"


def normalize_url_for_sig(url: str) -> str:
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url or "")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        return path
    except Exception:
        return url or ""


@tool
def playwright_snap_tool(
    url: Optional[str] = None,
    focus_keywords: Optional[List[str]] = None,
) -> dict:
    """
    Capture a semantic snapshot of the current page.

    Use this tool to:
    - Get compact accessibility-tree page state for model reasoning
    - Extract verified executable elements for browser actions
    - Get visible text blocks as a fallback for popovers and custom UI
    - Focus on goal-relevant areas to reduce token usage

    Args:
        url: Optional URL to navigate before capture. Omit it to snapshot the current page.
        focus_keywords: Optional keywords to focus the snapshot on. When provided,
            the snapshot will prioritize elements and accessibility nodes whose
            name or text contains any of these keywords. This is useful for
            goal-oriented exploration to reduce token usage while keeping
            relevant page context.

    Returns:
        A dictionary containing:
        - url: The actual URL of the page
        - title: Page title
        - page_text_summary: One-line summary of the page
        - elements: List of element info with verified reusable selectors
        - accessibility_tree: Compact accessibility nodes (id, role, name, state)
        - visible_text_blocks: Compact visible text blocks from the page
            Only included when focus_keywords is provided.
        - error: Error message if snapshot failed
        - state_observation_hint: Pre-shaped v2.0 state observation (use as
            observed_states argument for merge_page_artifact_tool to avoid
            manual construction errors like 'sha256:unknown' placeholder)

    Example:
        result = playwright_snap_tool(url="https://app.example.com/workspace")
        # Returns elements like:
        # {
        #   "url": "https://...",
        #   "title": "Workspace",
        #   "page_text_summary": "标题：Workspace。可交互元素：12...",
        #   "elements": [
        #     {
        #       "role": "button",
        #       "name": "Create Agent",
        #       "primary_selector": {"kind": "role", "code": "page.getByRole('button', { name: 'Create Agent' })"}
        #     }
        #   ],
        #   "accessibility_tree": [
        #     {"id": "ax-1", "role": "button", "name": "Create Agent"}
        #   ]
        # }

        focused = playwright_snap_tool(
            url="https://app.example.com/workspace",
            focus_keywords=["agent", "create"]
        )
        # Returns a smaller snapshot focused on agent-related elements.
    """
    result = snapshot_with_runtime_context(url)
    keywords = [kw.strip() for kw in (focus_keywords or []) if str(kw).strip()]
    elements = [
        {
            "role": elem.role,
            "role_source": elem.role_source,
            "name": elem.name,
            "text": elem.text,
            "action_type": elem.action_type,
            "primary_selector": elem.primary_selector,
            "fallback_selector": elem.fallback_selector,
            "visible": elem.visible,
            "dialog_id": elem.dialog_id,
        }
        for elem in result.elements
    ]
    # 给每个 element 标 sibling_count（页面级，同 name+role 全页面出现次数），
    # 让 LLM 看到 ambiguous 元素，避免写 getByRole 触发严格模式多匹配。
    _annotate_ambiguity(elements)
    accessibility_tree = [node.model_dump() for node in result.accessibility_tree]
    visible_text_blocks = result.visible_text_blocks
    if keywords:
        elements = _focus_elements(elements, keywords)
        accessibility_tree = _focus_accessibility_tree(accessibility_tree, keywords)
        visible_text_blocks = _focus_visible_text_blocks(visible_text_blocks, keywords)

    state_observation_hint = _build_state_observation_hint(
        url=result.url,
        title=result.title,
        page_text=result.page_text_summary,
        elements=elements,
    )

    match_groups = _build_match_groups(elements)

    return {
        "url": result.url,
        "title": result.title,
        "page_text_summary": result.page_text_summary,
        "elements": elements,
        "accessibility_tree": accessibility_tree,
        "visible_text_blocks": visible_text_blocks,
        "dialogs": [d.model_dump() for d in result.dialogs],
        "active_dialog_id": result.active_dialog_id,
        "match_groups": match_groups,
        "error": result.error,
        "state_observation_hint": state_observation_hint,
    }


def _annotate_ambiguity(elements: list) -> None:
    """给每个 element 加 sibling_count（同 name+role 全页面出现次数）+ is_ambiguous 布尔。

    why: verification.unique 只验证"这个 element 的 selector 在 DOM 中唯一指向它"，
    但严格模式下 getByRole 跨整个 DOM 匹配——同 name+role 有多元素时还是多匹配。
    LLM 看到 sibling_count > 1 就该用 chain 容器而不是裸 getByRole。
    """
    counts: dict[tuple[str, str], int] = {}
    for el in elements:
        if not isinstance(el, dict):
            continue
        key = (str(el.get("name") or ""), str(el.get("role") or ""))
        counts[key] = counts.get(key, 0) + 1

    for el in elements:
        if not isinstance(el, dict):
            continue
        key = (str(el.get("name") or ""), str(el.get("role") or ""))
        sibling_count = counts.get(key, 1)
        el["sibling_count"] = sibling_count
        el["is_ambiguous"] = sibling_count > 1


def _build_match_groups(elements: list) -> list[dict]:
    """按 (name, role) 分组聚合所有候选，让 LLM 一次性看到同 name 全部元素的位置。

    每组结构：
    {
        "name": "创建",
        "role": "button",
        "count": 3,
        "candidates": [
            {
                "index": 0,
                "dialog_id": None,
                "primary_selector_code": "page.getByRole('button', { name: '创建' })",
                "context_hint": "弹窗内 / 主页面 ...",
            },
            ...
        ]
    }

    LLM 在 click 失败时能直接对照 candidates 列表选择正确的 chain。
    """
    groups: dict[tuple[str, str], list[int]] = {}
    for idx, el in enumerate(elements):
        if not isinstance(el, dict):
            continue
        key = (str(el.get("name") or ""), str(el.get("role") or ""))
        groups.setdefault(key, []).append(idx)

    out: list[dict] = []
    for (name, role), indexes in groups.items():
        if not name or not role:
            continue
        if len(indexes) <= 1:
            # 唯一匹配的不进 groups（避免信息过载），用空 filter 时还能看到全页
            continue
        candidates: list[dict] = []
        for order, idx in enumerate(indexes, start=1):
            el = elements[idx]
            primary = el.get("primary_selector") if isinstance(el.get("primary_selector"), dict) else None
            primary_code = primary.get("code") if primary else ""
            candidates.append({
                "ordinal": order,
                "element_index": idx,
                "dialog_id": el.get("dialog_id") or None,
                "primary_selector_code": primary_code,
                "context_hint": "弹窗内" if el.get("dialog_id") else "主页面",
            })
        out.append({
            "name": name,
            "role": role,
            "count": len(indexes),
            "candidates": candidates,
        })
    return out


def _build_state_observation_hint(
    *,
    url: str,
    title: str,
    page_text: str,
    elements: list[dict],
) -> dict:
    """把 snap 结果直接转成 v2.0 NewStateObservation 候选。

    关键设计：
    - **禁止 LLM 手工填 dom_signature**：由 snap 自动从 url+title+page_text 算
    - **禁止 LLM 手工填 triggered_by**：root state 留空，其它 state 由 service
      根据前序 state 推断
    - element.source 优先用 verified primary_selector（已包含 is_semantic 标记）
    - 纯文本猜测 / role 不可信时标 inferred=true
    """
    normalized_path = normalize_url_for_sig(url)
    now = datetime.now(timezone.utc).isoformat()
    dom_signature = _dom_signature_for_url_title(url, title, page_text)

    children: list[dict] = []
    for index, element in enumerate(elements, start=1):
        if not isinstance(element, dict):
            continue
        primary = element.get("primary_selector") if isinstance(element.get("primary_selector"), dict) else None
        role = str(element.get("role") or "").strip()
        name = str(element.get("name") or "").strip()
        role_source = str(element.get("role_source") or "")
        action_type = str(element.get("action_type") or "click")
        is_semantic = bool(primary) and primary.get("kind") != "css" and role_source != "inferred"
        # 仅在 role/name 至少一项可定位时保留 element_key；纯文本/无 role 的丢
        if not (primary or (role and name)):
            continue
        source_code = _semantic_selector_code(primary)
        element_key = _stable_element_key(role or action_type, name or element.get("text") or "", index)
        children.append({
            "key": element_key,
            "source": {
                "kind": primary.get("kind") if primary else "inferred",
                "code": source_code,
                "role": role,
                "name": name,
                "label": element.get("label") or "",
                "placeholder": element.get("placeholder") or "",
                "test_id": element.get("testId") or "",
            },
            "inferred": not is_semantic,
            "children": [],
        })

    return {
        "page_id": _snapshot_page_id_hint(normalized_path),
        "page_title": title or url or "探索页面",
        "normalized_path": normalized_path,
        "observed_url": url,
        "observed_at": now,
        "state_type": "page",
        "title": title or "页面初始状态",
        "dom_signature": dom_signature,
        "triggered_by": None,  # 根 state 始终不填；非根 state 由 service 推断
        "parent_state_id": None,
        "elements": children,
    }


def _snapshot_page_id_hint(normalized_path: str) -> str:
    value = (normalized_path or "").strip("/") or "home"
    for char in ("?", "&", "=", "#", "%", ":"):
        value = value.replace(char, "-")
    value = value.replace("/", "-")
    value = "-".join(part for part in value.split("-") if part)
    return f"page-{value or 'home'}"


def _stable_element_key(role: str, name: str, index: int) -> str:
    base = (name or role or f"element-{index}").strip().lower()
    # 仅保留字母数字和中文，其余转 -
    cleaned = "".join(
        ch if (ch.isalnum() or "\u4e00" <= ch <= "\u9fff") else "-"
        for ch in base
    )
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    if not cleaned:
        cleaned = f"element-{index}"
    return f"{role or 'el'}-{cleaned[:48]}-{index:03d}"[:80]


def _matches_keywords(text: Optional[str], keywords: List[str]) -> bool:
    value = str(text or "").lower()
    return any(keyword.lower() in value for keyword in keywords)


def _focus_elements(elements: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
    if not keywords:
        return elements
    matched = []
    for element in elements:
        if _matches_keywords(element.get("name"), keywords) or _matches_keywords(element.get("text"), keywords):
            matched.append(element)
    return matched or elements


def _focus_accessibility_tree(
    tree: List[Dict[str, Any]],
    keywords: List[str],
) -> List[Dict[str, Any]]:
    if not tree or not keywords:
        return tree

    matched_ids = set()
    for node in tree:
        if _matches_keywords(node.get("name"), keywords):
            matched_ids.add(node.get("id"))

    if not matched_ids:
        return tree

    keep = set()
    for node in tree:
        node_id = node.get("id")
        if node_id in matched_ids:
            keep.add(node_id)
            _add_ancestors(tree, node_id, keep)

    return [node for node in tree if node.get("id") in keep]


def _add_ancestors(tree: List[Dict[str, Any]], target_id: str, keep: set) -> None:
    for node in tree:
        children = node.get("children") or []
        if any(child.get("id") == target_id for child in children):
            keep.add(node.get("id"))
            _add_ancestors(tree, node.get("id"), keep)
            return


def _focus_visible_text_blocks(blocks: List[str], keywords: List[str], max_blocks: int = 60) -> List[str]:
    if not blocks or not keywords:
        return []
    matched = [block for block in blocks if _matches_keywords(block, keywords)]
    return matched[:max_blocks]


__all__ = [
    "playwright_snap_tool",
    "build_state_observation_hint",
    "normalize_url_for_sig",
]
