from __future__ import annotations

from urllib.parse import urlparse


LOGIN_PATTERNS = (
    "login",
    "signin",
    "sign-in",
    "auth",
    "passport",
    "account/login",
    "user/login",
    "登录",
    "登陆",
    "验证码",
    "401",
    "403",
)

UNSAFE_BUTTON_KEYWORDS = (
    "删除",
    "移除",
    "提交",
    "支付",
    "付款",
    "确认",
    "确定",
    "发布",
    "保存",
    "创建",
    "新增",
    "修改",
    "编辑",
    "上传",
    "发送",
)


def validate_goal(goal: str, page_artifacts: list[dict], graph: dict | None = None) -> dict:
    goal_text = str(goal or "").strip()
    if not goal_text:
        return _result("", "skipped", "未设置探索目标。", _empty_stats(), [])
    if not _supports_article_link_button_login_goal(goal_text):
        return _result(
            goal_text,
            "pending",
            "当前探索目标尚未解析成可执行验收规则。",
            _empty_stats(page_count=len(page_artifacts)),
            [],
        )

    items: list[dict] = []
    graph_edges = _graph_edges(graph)
    for page_artifact in page_artifacts:
        page = page_artifact.get("page") if isinstance(page_artifact.get("page"), dict) else {}
        page_id = str(page.get("id") or "")
        page_url = str(page.get("url") or page.get("normalized_url") or "")
        page_title = str(page.get("title") or "")

        for link in _links_for_page(page_artifact, graph_edges, page_id, page_url):
            target_url = str(link.get("target_url") or "")
            result = "failed" if _looks_like_login_page(target_url) else "passed"
            reason = "链接目标命中登录/鉴权页特征。" if result == "failed" else "链接目标未命中登录页特征。"
            items.append(
                {
                    "page_id": page_id,
                    "page_title": page_title,
                    "page_url": page_url,
                    "element_type": "link",
                    "element_name": str(link.get("name") or target_url or "LINK"),
                    "action": "href_check",
                    "before_url": page_url,
                    "after_url": target_url,
                    "result": result,
                    "reason": reason,
                }
            )

        for button in _buttons_for_page(page_artifact):
            name = str(button.get("name") or "").strip()
            locator = str(button.get("locator_hint") or "")
            validation = button.get("validation") if isinstance(button.get("validation"), dict) else {}
            validation_result = str(validation.get("result") or validation.get("status") or "").strip()
            validation_reason = str(validation.get("reason") or "").strip()
            item = {
                "page_id": page_id,
                "page_title": page_title,
                "page_url": page_url,
                "element_type": "button",
                "element_name": name or "BUTTON",
                "action": "click",
                "before_url": page_url,
                "after_url": str(validation.get("after_url") or ""),
                "result": validation_result or "unverified",
                "reason": "按钮尚无点击后 URL、标题或正文证据，不能判定是否跳转登录页。",
            }
            if validation_result == "passed":
                item["reason"] = validation_reason or "按钮点击后页面未命中登录页特征。"
            elif validation_result == "failed":
                item["reason"] = validation_reason or "按钮点击后页面命中登录/鉴权页特征。"
            if _is_low_quality_button_name(name):
                item["reason"] = "按钮名称不可识别，未执行点击验证。"
            elif _is_unsafe_button(name):
                item["reason"] = "按钮疑似会修改业务数据，跳过真实点击验证。"
            elif validation_result in {"passed", "failed"}:
                item["reason"] = validation_reason or item["reason"]
            elif locator:
                item["reason"] = "已定位按钮，但当前探索产物没有点击后页面证据。"
            items.append(item)

    stats = _stats(page_artifacts, items)
    status = _status_from_items(items)
    summary = _summary_from_stats(stats, status)
    return _result(goal_text, status, summary, stats, items)


def terminal_status_for_goal_validation(current_status: str, validation: dict) -> str:
    if current_status != "completed":
        return current_status
    validation_status = str(validation.get("status") or "")
    if validation_status in {"skipped", "passed"}:
        return current_status
    if validation_status == "failed":
        return "blocked"
    return "waiting_human"


def _supports_article_link_button_login_goal(goal: str) -> bool:
    has_link = "链接" in goal or "超链接" in goal or "link" in goal.lower()
    has_button = "按钮" in goal or "button" in goal.lower()
    has_login = any(pattern in goal.lower() for pattern in ("login", "signin", "登录", "登陆", "验证码", "401", "403"))
    return has_login and (has_link or has_button)


def _links_for_page(page_artifact: dict, graph_edges: list[dict], page_id: str, page_url: str) -> list[dict]:
    links: list[dict] = []
    seen: set[tuple[str, str]] = set()

    relations = page_artifact.get("relations") if isinstance(page_artifact.get("relations"), dict) else {}
    for edge in relations.get("outgoing_edges") if isinstance(relations.get("outgoing_edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        target_url = str(edge.get("to_url") or edge.get("target_url") or edge.get("url") or edge.get("to") or "")
        if _add_link(links, seen, target_url, str(edge.get("label") or edge.get("action") or edge.get("name") or "")):
            continue

    for edge in graph_edges:
        source = str(edge.get("from") or edge.get("source") or edge.get("source_id") or "")
        source_url = str(edge.get("from_url") or edge.get("source_url") or "")
        if source not in {page_id, page_url} and source_url != page_url:
            continue
        target_url = str(edge.get("to_url") or edge.get("target_url") or edge.get("url") or edge.get("to") or edge.get("target") or "")
        _add_link(links, seen, target_url, str(edge.get("label") or edge.get("action") or edge.get("name") or ""))

    for node in _flatten_accessibility(page_artifact.get("accessibility_tree")):
        if str(node.get("role") or "").lower() != "link":
            continue
        target_url = str(node.get("href") or node.get("url") or "")
        _add_link(links, seen, target_url, str(node.get("name") or ""))

    return links


def _add_link(links: list[dict], seen: set[tuple[str, str]], target_url: str, name: str) -> bool:
    target_url = target_url.strip()
    if not target_url:
        return False
    key = (target_url, name)
    if key in seen:
        return False
    seen.add(key)
    links.append({"target_url": target_url, "name": name})
    return True


def _buttons_for_page(page_artifact: dict) -> list[dict]:
    buttons: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for action in page_artifact.get("actions") if isinstance(page_artifact.get("actions"), list) else []:
        if not isinstance(action, dict):
            continue
        role = str(action.get("role") or action.get("element_type") or "").lower()
        action_type = str(action.get("action_type") or action.get("action") or "").lower()
        if role != "button" and action_type != "click":
            continue
        _add_button(buttons, seen, action)

    for node in _flatten_accessibility(page_artifact.get("accessibility_tree")):
        if str(node.get("role") or "").lower() != "button":
            continue
        _add_button(buttons, seen, node)
    return buttons


def _add_button(buttons: list[dict], seen: set[tuple[str, str]], item: dict) -> None:
    name = str(item.get("name") or item.get("label") or "").strip()
    locator = str(item.get("locator_hint") or item.get("selector") or "").strip()
    key = (name, locator)
    if key in seen:
        return
    seen.add(key)
    button = {"name": name, "locator_hint": locator}
    if isinstance(item.get("validation"), dict):
        button["validation"] = item["validation"]
    buttons.append(button)


def _flatten_accessibility(raw_tree) -> list[dict]:
    if not isinstance(raw_tree, list):
        return []
    nodes: list[dict] = []
    stack = [node for node in raw_tree if isinstance(node, dict)]
    while stack:
        node = stack.pop(0)
        nodes.append(node)
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
    return nodes


def _looks_like_login_page(text: str) -> bool:
    value = text.lower()
    parsed = urlparse(text)
    candidates = " ".join(part for part in (value, parsed.path.lower(), parsed.query.lower()) if part)
    return any(pattern.lower() in candidates for pattern in LOGIN_PATTERNS)


def _is_low_quality_button_name(name: str) -> bool:
    return not name.strip() or name.strip().upper() == "BUTTON"


def _is_unsafe_button(name: str) -> bool:
    return any(keyword in name for keyword in UNSAFE_BUTTON_KEYWORDS)


def _graph_edges(graph: dict | None) -> list[dict]:
    if not isinstance(graph, dict) or not isinstance(graph.get("edges"), list):
        return []
    return [edge for edge in graph["edges"] if isinstance(edge, dict)]


def _status_from_items(items: list[dict]) -> str:
    if any(item.get("result") == "failed" for item in items):
        return "failed"
    if any(item.get("result") in {"unverified", "skipped"} for item in items):
        return "partial"
    if items and all(item.get("result") == "passed" for item in items):
        return "passed"
    return "partial"


def _stats(page_artifacts: list[dict], items: list[dict]) -> dict:
    stats = _empty_stats(page_count=len(page_artifacts))
    for item in items:
        result = str(item.get("result") or "")
        element_type = str(item.get("element_type") or "")
        if element_type == "link":
            stats["link_total_count"] += 1
            if result == "passed":
                stats["link_passed_count"] += 1
            if result == "failed":
                stats["link_failed_count"] += 1
        if element_type == "button":
            stats["button_total_count"] += 1
            if result == "passed":
                stats["button_passed_count"] += 1
            if result == "failed":
                stats["button_failed_count"] += 1
            if result == "unverified":
                stats["button_unverified_count"] += 1
            if result == "skipped":
                stats["button_skipped_count"] += 1
        if result == "failed":
            stats["failed_count"] += 1
        if result == "unverified":
            stats["unverified_count"] += 1
        if result == "passed":
            stats["passed_count"] += 1
    stats["link_checked_count"] = stats["link_passed_count"] + stats["link_failed_count"]
    stats["button_checked_count"] = stats["button_passed_count"] + stats["button_failed_count"]
    return stats


def _empty_stats(page_count: int = 0) -> dict:
    return {
        "page_count": page_count,
        "link_total_count": 0,
        "link_checked_count": 0,
        "link_passed_count": 0,
        "link_failed_count": 0,
        "button_total_count": 0,
        "button_checked_count": 0,
        "button_passed_count": 0,
        "button_failed_count": 0,
        "button_unverified_count": 0,
        "button_skipped_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "unverified_count": 0,
    }


def _summary_from_stats(stats: dict, status: str) -> str:
    conclusion = {
        "passed": "目标验证通过",
        "partial": "目标验证部分完成",
        "failed": "目标验证未通过",
    }.get(status, "目标验证待处理")
    return (
        f"{conclusion}：已覆盖 {stats['page_count']} 个页面，"
        f"链接已验证 {stats['link_checked_count']}/{stats['link_total_count']} 个，"
        f"按钮已验证 {stats['button_checked_count']}/{stats['button_total_count']} 个，"
        f"失败 {stats['failed_count']} 个，未验证 {stats['unverified_count']} 个。"
    )


def _result(goal: str, status: str, summary: str, stats: dict, items: list[dict]) -> dict:
    return {
        "goal": goal,
        "status": status,
        "summary": summary,
        "stats": stats,
        "items": items,
    }
