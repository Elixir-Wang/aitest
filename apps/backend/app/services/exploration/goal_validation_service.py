from urllib.parse import urlparse


LOGIN_PATTERNS = {
    # 中文模式
    "zh": (
        "登录", "登陆", "注册", "验证码", "captcha",
    ),
    # 英文模式
    "en": (
        "login", "signin", "sign-in", "sign_in",
        "signup", "sign-up", "register", "authentication",
        "sso", "oauth", "saml",
    ),
    # 路径模式（更精确）
    "path": (
        "/login", "/signin", "/sign-in", "/auth/login",
        "/user/login", "/account/login", "/passport",
        "/register", "/signup",
    ),
    # HTTP 状态码（应该检查实际状态码，这里仅作为 URL 中出现的标记）
    "status": (
        "401", "403", "unauthorized", "forbidden",
    ),
}


def _looks_like_login_page(text: str) -> bool:
    """
    判断 URL 或文本是否像登录页

    改进逻辑：
    1. 移除过于宽泛的 "auth" 模式
    2. 添加更多语言支持
    3. 区分路径模式和状态码模式
    4. 更精确的匹配规则
    """
    if not text:
        return False

    value = text.lower()
    from urllib.parse import urlparse

    try:
        parsed = urlparse(text)
        path = parsed.path.lower()
        query = parsed.query.lower()
    except Exception:
        path = ""
        query = ""

    # 检查路径模式（精确匹配）
    for pattern in LOGIN_PATTERNS["path"]:
        if pattern in path:
            return True

    # 检查中英文关键词（在 URL、路径或查询参数中）
    candidates = " ".join(part for part in (value, path, query) if part)

    for pattern in LOGIN_PATTERNS["zh"] + LOGIN_PATTERNS["en"]:
        if pattern in candidates:
            return True

    # 检查状态码模式（需要更谨慎）
    # "401" 和 "403" 只在特定上下文中才算登录页标记
    for pattern in LOGIN_PATTERNS["status"]:
        if pattern in path or pattern in query:
            return True

    return False


UNSAFE_BUTTON_KEYWORDS = {
    # 中文关键词
    "zh": (
        "删除", "移除", "提交", "支付", "付款", "确认", "确定",
        "发布", "保存", "创建", "新增", "修改", "编辑", "上传", "发送",
    ),
    # 英文关键词
    "en": (
        "delete", "remove", "submit", "pay", "payment", "confirm", "approve",
        "publish", "save", "create", "add", "update", "edit", "upload", "send",
        "execute", "run", "apply", "commit",
    ),
}

# 高危关键词 - 完全匹配才算不安全
HIGH_RISK_KEYWORDS = {
    "zh": ("删除", "支付", "付款", "发布"),
    "en": ("delete", "pay", "payment", "publish", "execute", "run"),
}


def validate_goal(goal: str, page_artifacts: list[dict], graph: dict | None = None) -> dict:
    goal_text = str(goal or "").strip()
    if not goal_text:
        return _result("", "skipped", "未设置探索目标。", _empty_stats(), [])

    # 检查是否支持特定的登录页验证目标格式
    supports_login_validation = _supports_article_link_button_login_goal(goal_text)

    items: list[dict] = []
    graph_edges = _graph_edges(graph)
    # 如果目标支持登录页验证，执行详细的链接和按钮验证
    if supports_login_validation:
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

    # 对于不支持特定格式的目标，执行基础验证
    else:
        return _validate_generic_goal(goal_text, page_artifacts, graph_edges)


def terminal_status_for_goal_validation(current_status: str, validation: dict) -> str:
    if current_status != "completed":
        return current_status
    validation_status = str(validation.get("status") or "")
    if validation_status in {"skipped", "passed"}:
        return current_status
    if validation_status == "failed":
        return "blocked"
    if validation_status == "partial":
        return "partial"
    return "partial"


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


def _is_low_quality_button_name(name: str) -> bool:
    return not name.strip() or name.strip().upper() == "BUTTON"


def _is_unsafe_button(name: str) -> bool:
    """
    判断按钮是否不安全（可能修改数据）

    改进逻辑：
    1. 支持中英文
    2. 高危关键词需要完全匹配
    3. 一般关键词支持子字符串匹配
    4. 考虑上下文（如"查看确认"不算不安全）
    """
    if not name or not name.strip():
        return False

    name_lower = name.lower().strip()

    # 白名单：包含这些词的按钮认为是安全的
    safe_patterns = (
        "查看", "view", "显示", "show", "详情", "detail",
        "取消", "cancel", "关闭", "close", "返回", "back",
        "搜索", "search", "查询", "query", "筛选", "filter",
    )
    if any(pattern in name_lower for pattern in safe_patterns):
        return False

    # 高危关键词：完全匹配（或作为独立词出现）
    for keyword in HIGH_RISK_KEYWORDS["zh"] + HIGH_RISK_KEYWORDS["en"]:
        # 完全匹配
        if name_lower == keyword:
            return True
        # 作为独立词出现（前后有分隔符或边界）
        import re
        if re.search(rf'\b{re.escape(keyword)}\b', name_lower):
            return True

    # 一般关键词：子字符串匹配
    all_keywords = UNSAFE_BUTTON_KEYWORDS["zh"] + UNSAFE_BUTTON_KEYWORDS["en"]
    return any(keyword in name_lower for keyword in all_keywords)


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


def _validate_generic_goal(goal_text: str, page_artifacts: list[dict], graph_edges: list[dict]) -> dict:
    """
    对通用探索目标执行基础验证

    不执行特定的登录页检测，但不能把“发现页面/按钮”等同于“目标完成”。
    结构化或动作型目标必须有真实动作证据，否则只能返回 partial。
    """
    items: list[dict] = []
    page_count = len(page_artifacts)

    # 收集基本的探索统计信息
    total_links = 0
    total_buttons = 0

    for page_artifact in page_artifacts:
        page = page_artifact.get("page") if isinstance(page_artifact.get("page"), dict) else {}
        page_id = str(page.get("id") or "")
        page_url = str(page.get("url") or page.get("normalized_url") or "")
        page_title = str(page.get("title") or "")

        # 统计链接
        links = _links_for_page(page_artifact, graph_edges, page_id, page_url)
        total_links += len(links)

        # 添加链接发现项。discovered 只是事实记录，不代表目标已验证通过。
        for link in links[:5]:  # 只记录前5个作为示例
            items.append({
                "page_id": page_id,
                "page_title": page_title,
                "page_url": page_url,
                "element_type": "link",
                "element_name": str(link.get("name") or link.get("target_url") or "LINK"),
                "action": "discovered",
                "before_url": page_url,
                "after_url": str(link.get("target_url") or ""),
                "result": "unverified",
                "reason": "已发现链接，但未形成目标步骤执行证据。",
            })

        # 统计按钮
        buttons = _buttons_for_page(page_artifact)
        total_buttons += len(buttons)

        # 添加按钮发现项。discovered 只是事实记录，不代表目标已验证通过。
        for button in buttons[:5]:  # 只记录前5个作为示例
            items.append({
                "page_id": page_id,
                "page_title": page_title,
                "page_url": page_url,
                "element_type": "button",
                "element_name": str(button.get("name") or "BUTTON"),
                "action": "discovered",
                "before_url": page_url,
                "after_url": "",
                "result": "unverified",
                "reason": "已发现按钮，但未形成目标步骤执行证据。",
            })

    # 构建统计信息
    stats = {
        "page_count": page_count,
        "link_total_count": total_links,
        "link_checked_count": min(total_links, len([i for i in items if i["element_type"] == "link"])),
        "link_passed_count": len([i for i in items if i["element_type"] == "link" and i["result"] == "passed"]),
        "link_failed_count": 0,
        "button_total_count": total_buttons,
        "button_checked_count": min(total_buttons, len([i for i in items if i["element_type"] == "button"])),
        "button_passed_count": len([i for i in items if i["element_type"] == "button" and i["result"] == "passed"]),
        "button_failed_count": 0,
        "button_unverified_count": max(0, total_buttons - len([i for i in items if i["element_type"] == "button"])),
        "button_skipped_count": 0,
        "passed_count": len([i for i in items if i["result"] == "passed"]),
        "failed_count": 0,
        "unverified_count": len([i for i in items if i["result"] == "unverified"]),
    }

    # 确定验证状态
    if page_count == 0:
        status = "partial"
        summary = f"目标验证部分完成：未探索到页面，无法验证目标「{goal_text}」。"
    elif _requires_step_execution(goal_text) and not _has_goal_action_evidence(page_artifacts):
        status = "partial"
        summary = (
            f"目标验证部分完成：已覆盖 {page_count} 个页面，"
            f"但未找到点击、填写、选择、发送、发布、返回等目标步骤执行证据，"
            f"不能判定探索目标「{goal_text}」已完成。"
        )
    elif page_count > 0 and _has_goal_action_evidence(page_artifacts):
        status = "passed"
        summary = (
            f"目标验证通过：已覆盖 {page_count} 个页面，"
            f"并存在目标步骤执行证据，"
            f"探索目标「{goal_text}」已完成基础验证。"
        )
    else:
        status = "partial"
        summary = f"目标验证部分完成：已覆盖 {page_count} 个页面，但缺少目标步骤执行证据。"

    return _result(goal_text, status, summary, stats, items)


def _requires_step_execution(goal_text: str) -> bool:
    normalized = str(goal_text or "").lower()
    markers = (
        "模块一", "模块二", "模块三", "步骤", "点击", "输入", "填写", "选择", "发送", "发布", "返回",
        "新建", "会话", "对话", "使用", "卡片", "模型", "click", "fill", "select", "send", "publish",
    )
    return any(marker in normalized for marker in markers)


def _has_goal_action_evidence(page_artifacts: list[dict]) -> bool:
    evidence_types = {
        "click",
        "fill",
        "select_option",
        "press",
        "navigate",
        "go_back",
        "close_modal",
        "action_result",
        "agent_decision",
    }
    for page_artifact in page_artifacts:
        for action in page_artifact.get("actions", []) if isinstance(page_artifact.get("actions"), list) else []:
            if not isinstance(action, dict):
                continue
            status = str(action.get("status") or "")
            action_type = str(action.get("type") or action.get("action_type") or "")
            if action_type in evidence_types and status in {"passed", "completed", "unverified"}:
                return True
        for step in page_artifact.get("steps", []) if isinstance(page_artifact.get("steps"), list) else []:
            if not isinstance(step, dict):
                continue
            step_type = str(step.get("type") or "")
            title = str(step.get("title") or "")
            detail = str(step.get("detail") or "")
            status = str(step.get("status") or "")
            if status not in {"passed", "completed", "unverified"}:
                continue
            if step_type in evidence_types:
                return True
            if any(keyword in f"{title} {detail}".lower() for keyword in ("点击", "填写", "输入", "选择", "发送", "发布", "返回", "click", "fill")):
                return True
    return False


def _result(goal: str, status: str, summary: str, stats: dict, items: list[dict]) -> dict:
    return {
        "goal": goal,
        "status": status,
        "summary": summary,
        "stats": stats,
        "items": items,
    }
