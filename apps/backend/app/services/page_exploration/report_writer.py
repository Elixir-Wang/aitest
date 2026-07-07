# apps/backend/app/services/page_exploration/report_writer.py

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def _string(value) -> str:
    return "" if value is None else str(value)


def _write_yaml_file(path: Path, payload: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _exploration_mode_label(exploration_mode: str) -> str:
    return {
        "autonomous": "自主探索",
        "goal": "目标探索",
        "regression": "回归检查",
    }.get(exploration_mode, exploration_mode or "自主探索")




def _compact_url_for_display(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''}"
    except Exception:
        pass
    return value[:96]


def _locator_label(locator: str) -> str:
    if not locator:
        return ""
    import re

    match = re.match(r"^[a-zA-Z]+-(.+?)-\d+$", locator)
    if match:
        return " / ".join(part for part in match.group(1).split("-") if part)
    return locator[:64]


def _write_exploration_summary(
    *,
    run_dir: Path,
    run_id: str,
    start_url: str,
    scope: str,
    exploration_mode: str,
    max_pages: int,
    page_artifacts: list[tuple[Path, dict]],
    completion_status: str = "completed",
) -> None:
    module_counts: dict[str, int] = {}
    for _, artifact in page_artifacts:
        page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
        module_key = _string(page.get("module_key") or page.get("module") or scope or "主探索模块")
        module_counts[module_key] = module_counts.get(module_key, 0) + 1
    modules = [
        {
            "module_key": module_key,
            "module_name": module_key,
            "status": completion_status,
            "entry_path": scope or start_url,
            "planned_page_count": max_pages,
            "explored_page_count": count,
        }
        for module_key, count in module_counts.items()
    ]
    if not modules:
        module_key = scope or "主探索模块"
        modules = [
            {
                "module_key": module_key,
                "module_name": module_key,
                "status": completion_status,
                "entry_path": scope or start_url,
                "planned_page_count": max_pages,
                "explored_page_count": 0,
            }
        ]
    _write_yaml_file(
        run_dir / "summary.yaml",
        {
            "run_id": run_id,
            "artifact_schema_version": 2,
            "start_url": start_url,
            "exploration_mode": exploration_mode,
            "scope": scope,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "modules": modules,
        },
    )


def _read_timeline_events_from_run_dir(run_dir: Path) -> list[dict]:
    events_path = run_dir / "timeline_events.jsonl"
    if not events_path.exists():
        return []
    events: list[dict] = []
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _latest_plan_steps_from_timeline(timeline_events: list[dict]) -> list[dict]:
    for event in reversed(timeline_events):
        if event.get("type") != "agent_plan_updated":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        steps = payload.get("plan_steps")
        if isinstance(steps, list):
            return [step for step in steps if isinstance(step, dict)]
    return []


def _extract_url_from_event(event: dict) -> str:
    """从事件中提取 URL，支持多种格式。

    - navigate_completed: display.fields[label="目标 URL"].value
    - snap_completed:       display.fields[label="URL"].value
    - tool output:          payload.output.url / payload.url
    """
    if not isinstance(event, dict):
        return ""
    display = event.get("display", {})
    if isinstance(display, dict):
        fields = display.get("fields", [])
        if isinstance(fields, list):
            for field in fields:
                if isinstance(field, dict):
                    if field.get("label") == "目标 URL":
                        return _string(field.get("value", "")).strip()
                    if field.get("label") == "URL":
                        return _string(field.get("value", "")).strip()
    return ""


def _build_page_topology(timeline_events: list[dict]) -> list[dict]:
    """从 timeline 事件中解析 URL 跳转拓扑关系。

    URL 信息从 display.fields 中提取（navigate: label="目标 URL", snap: label="URL"）。
    Returns:
        list of {from_url, to_url, action_summary, occurred_at} dicts.
    """
    nodes: list[dict] = []
    last_url: str | None = None
    current_locator: str | None = None

    for event in timeline_events:
        if not isinstance(event, dict):
            continue

        event_type = event.get("type", "")
        payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
        occurred_at = event.get("occurred_at", "")

        if event_type == "agent_tool_started":
            tool_name = payload.get("tool_name", "")
            if tool_name in ("playwright_click_tool", "playwright_fill_tool"):
                current_locator = payload.get("locator", "")

        elif event_type == "agent_tool_completed":
            tool_name = payload.get("tool_name", "")
            if tool_name in ("playwright_navigate_tool", "playwright_snap_tool"):
                to_url = _extract_url_from_event(event)
                if to_url and to_url != last_url:
                    if to_url.startswith("/"):
                        to_url = f"https://www.cybotstar.cn{to_url}"
                    if last_url is None:
                        last_url = to_url
                    else:
                        action = f"点击 {current_locator}" if current_locator else "导航"
                        nodes.append({
                            "from_url": last_url or "入口",
                            "to_url": to_url,
                            "action_summary": action,
                            "tool_name": tool_name,
                            "occurred_at": occurred_at,
                        })
                        last_url = to_url
                    current_locator = None

    return nodes


def _topology_node_id(url_or_label: str) -> str:
    """将 URL 或标签转换为合法的 Mermaid 节点 ID（去协议、去参数、简化）。"""
    if url_or_label == "入口":
        return "node_entry"
    try:
        parsed = urlparse(url_or_label if "://" in url_or_label else f"https://{url_or_label}")
        path = parsed.path.strip("/") or "root"
        params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        if "id" in params:
            path = f"{path}?id={params['id'][:8]}"
        return f"node_{hashlib.md5(path.encode()).hexdigest()[:6]}"
    except Exception:
        return f"node_{hashlib.md5(url_or_label.encode()).hexdigest()[:6]}"


def _topology_node_label(url_or_label: str) -> str:
    """将 URL 转换为人类可读的节点标签。"""
    if url_or_label == "入口":
        return "入口页面"
    try:
        parsed = urlparse(url_or_label if "://" in url_or_label else f"https://{url_or_label}")
        path = parsed.path.strip("/") or "/"
        params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        label = path
        if "id" in params:
            label = f"{path}?id={params['id']}"
        elif "agentId" in params:
            label = f"{path}?agentId={params['agentId']}"
        if len(label) > 40:
            label = label[:37] + "..."
        return label
    except Exception:
        return url_or_label[:40]


def _render_mermaid_topology(edges: list[dict]) -> str:
    """将拓扑边列表渲染为 Mermaid flowchart 代码。"""
    if not edges:
        return ""

    lines = ["```mermaid", "flowchart LR"]
    seen_nodes: set[str] = set()
    seen_edge_keys: set[str] = set()

    for edge in edges:
        from_id = _topology_node_id(edge.get("from_url", ""))
        to_id = _topology_node_id(edge.get("to_url", ""))
        action = edge.get("action_summary", "跳转")
        from_label = _topology_node_label(edge.get("from_url", ""))
        to_label = _topology_node_label(edge.get("to_url", ""))

        if from_id not in seen_nodes:
            lines.append(f'    {from_id}["{from_label}"]')
            seen_nodes.add(from_id)
        if to_id not in seen_nodes:
            lines.append(f'    {to_id}["{to_label}"]')
            seen_nodes.add(to_id)

        edge_key = f"{from_id}-->{to_id}"
        edge_label = f"|{action}|"
        if edge_key not in seen_edge_keys:
            lines.append(f"    {from_id} -->{edge_label} {to_id}")
            seen_edge_keys.add(edge_key)

    lines.append("```")
    return "\n".join(lines)


def _display_field_value(event: dict, label: str) -> str:
    display = event.get("display") if isinstance(event.get("display"), dict) else {}
    fields = display.get("fields") if isinstance(display.get("fields"), list) else []
    for field in fields:
        if isinstance(field, dict) and field.get("label") == label:
            return _string(field.get("value")).strip()
    return ""


def _event_summary(event: dict) -> str:
    display = event.get("display") if isinstance(event.get("display"), dict) else {}
    return _string(display.get("summary")).strip()


def _failure_summary_from_event(event: dict) -> str:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    failure = payload.get("failure") if isinstance(payload.get("failure"), dict) else {}
    output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
    if not failure and isinstance(output.get("failure"), dict):
        failure = output.get("failure")
    return (
        _string(failure.get("summary")).strip()
        or _string(output.get("error")).strip()
        or _string(payload.get("error_summary")).strip()
        or "操作未完成。"
    )


def _clean_mermaid_label(value: str, *, max_len: int = 52) -> str:
    label = " ".join(_string(value).replace("|", "/").replace('"', "'").split())
    if len(label) > max_len:
        label = label[: max_len - 3] + "..."
    return label or "未命名步骤"


def _build_exploration_path_steps(timeline_events: list[dict], start_url: str) -> list[dict]:
    """从 timeline 压缩出给人看的探索路径节点。"""
    steps: list[dict] = []

    def append_step(kind: str, label: str, detail: str = "", status: str = "completed") -> None:
        label = _clean_mermaid_label(label)
        detail = _clean_mermaid_label(detail, max_len=44) if detail else ""
        key = (kind, label, detail, status)
        if steps and (steps[-1]["kind"], steps[-1]["label"], steps[-1].get("detail", ""), steps[-1]["status"]) == key:
            return
        steps.append({"kind": kind, "label": label, "detail": detail, "status": status})

    if start_url:
        append_step("page", "入口页面", _compact_url_for_display(start_url))

    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type", "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        tool_name = _string(payload.get("tool_name"))

        if event_type == "agent_tool_completed" and tool_name in {"playwright_navigate_tool", "playwright_snap_tool"}:
            page_label = _display_field_value(event, "页面") or _event_summary(event) or "页面快照"
            url = _extract_url_from_event(event)
            if url:
                append_step("page", page_label, _compact_url_for_display(url))
            else:
                append_step("page", page_label)
            continue

        if event_type == "agent_tool_started" and tool_name in {"playwright_click_tool", "playwright_fill_tool"}:
            action_label = _event_summary(event)
            if not action_label:
                locator = _string(payload.get("locator"))
                verb = "输入" if tool_name == "playwright_fill_tool" else "点击"
                action_label = f"{verb} {_locator_label(locator) or '页面元素'}"
            append_step("action", action_label)
            continue

        if event_type == "agent_tool_failed":
            append_step("blocked", "阻塞/未完成", _failure_summary_from_event(event), "failed")

    return steps[:18]


def _render_exploration_path_flowchart(steps: list[dict]) -> str:
    """渲染本次探索的步骤路径图。"""
    if len(steps) < 2:
        return ""

    lines = [
        "```mermaid",
        "flowchart TD",
        "    classDef page fill:#e8f2ff,stroke:#2563eb,color:#111827",
        "    classDef action fill:#f7fee7,stroke:#65a30d,color:#111827",
        "    classDef blocked fill:#fef2f2,stroke:#dc2626,color:#111827",
    ]
    for index, step in enumerate(steps, start=1):
        node_id = f"N{index}"
        detail = step.get("detail", "")
        label = step["label"] if not detail else f"{step['label']}<br/>{detail}"
        if step["status"] == "failed":
            lines.append(f'    {node_id}{{"{label}"}}')
        else:
            lines.append(f'    {node_id}["{label}"]')
        lines.append(f"    class {node_id} {step['kind'] if step['kind'] in {'page', 'action'} else 'blocked'}")
        if index > 1:
            lines.append(f"    N{index - 1} --> {node_id}")
    lines.append("```")
    return "\n".join(lines)


def _render_mermaid_gantt(timeline_events: list[dict], run_start: str) -> str:
    """将 timeline 事件渲染为 Mermaid gantt 时间线图。"""
    if not timeline_events:
        return ""

    try:
        from datetime import datetime as dt
        start = dt.fromisoformat(run_start.replace("Z", "+00:00")) if run_start else dt.now(timezone.utc)
    except Exception:
        start = dt.now(timezone.utc)

    lines = ["```mermaid", "gantt", "    title 探索执行时间线", "    dateFormat X", "    axisFormat %H:%M:%S", ""]

    tool_events: list[dict] = []
    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type", "")
        if event_type not in ("agent_tool_started", "agent_tool_completed", "agent_tool_failed"):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        tool_name = payload.get("tool_name", "unknown")
        occurred_at = event.get("occurred_at", "")
        try:
            ts = dt.fromisoformat(occurred_at.replace("Z", "+00:00"))
            seconds = int((ts - start).total_seconds())
        except Exception:
            seconds = 0
        tool_events.append({
            "type": event_type,
            "tool": tool_name,
            "seconds": seconds,
            "locator": payload.get("locator", ""),
        })

    if not tool_events:
        lines.append("    section 工具调用")
        lines.append("    (无记录)")
        lines.append("```")
        return "\n".join(lines)

    lines.append("    section 工具调用")
    last_tool: str | None = None
    for ev in tool_events:
        tool_short = ev["tool"].replace("playwright_", "pw.")
        label = tool_short
        if ev["type"] == "agent_tool_started":
            last_tool = f"{tool_short}_{ev['seconds']}"
            lines.append(f"    {ev['seconds']}: done, {last_tool}, 0s")
        elif ev["type"] == "agent_tool_completed" and last_tool:
            duration = max(ev["seconds"] - int(last_tool.split("_")[-1]), 1)
            lines.append(f"    : {duration}s")
            last_tool = None
        elif ev["type"] == "agent_tool_failed" and last_tool:
            duration = max(ev["seconds"] - int(last_tool.split("_")[-1]), 1)
            lines.append(f"    : crit, {duration}s, 失败")
            last_tool = None

    lines.append("```")
    return "\n".join(lines)


def _build_goal_action_mapping(timeline_events: list[dict]) -> list[dict]:
    """将子目标（todo）与实际工具调用关联，返回 [{goal, status, attempts, tools}]。

    通过事件顺序追踪：按顺序扫描 timeline，维护当前活跃的 plan step，
    遇到 tool_started/tool_failed 时计入对应 step 的尝试次数。
    """
    plan_steps: list[dict] = []
    # 当前活跃 step index（0-based）
    current_step_idx: int = -1
    # 每个 step 的工具调用计数和失败计数
    step_stats: list[dict] = []

    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type", "")
        payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}

        if event_type == "agent_plan_updated":
            steps = payload.get("plan_steps")
            if isinstance(steps, list):
                plan_steps = [s for s in steps if isinstance(s, dict)]
                step_stats = [{"attempts": 0, "failed_attempts": 0} for _ in plan_steps]
                # 重置当前 step：优先找 in_progress，否则找第一个 pending，否则用最后一个
                current_step_idx = 0
                found = -1
                for idx, step in enumerate(plan_steps):
                    if step.get("status") in ("in_progress", "running"):
                        current_step_idx = idx
                        found = idx
                        break
                if found < 0:
                    # 没有 in_progress，找第一个 pending
                    for idx, step in enumerate(plan_steps):
                        if step.get("status") == "pending":
                            current_step_idx = idx
                            break

        elif event_type in ("agent_tool_started", "agent_tool_failed"):
            tool_name = payload.get("tool_name", "")
            if not tool_name or "write_todos" in tool_name:
                continue
            if current_step_idx < len(step_stats):
                step_stats[current_step_idx]["attempts"] += 1
                if event_type == "agent_tool_failed":
                    step_stats[current_step_idx]["failed_attempts"] += 1

        elif event_type == "agent_thought":
            display = event.get("display", {}) if isinstance(event.get("display"), dict) else {}
            summary: str = display.get("summary", "")
            if not summary:
                continue
            # 当 thought 表明进入下一步时，更新 current_step_idx
            for idx in range(current_step_idx + 1, len(plan_steps)):
                step = plan_steps[idx]
                desc_short = (step.get("description") or "")[:20]
                if any(kw in summary for kw in ["第", "进入第", "步完成", "步完成"]):
                    if str(idx + 1) in summary or f"agent-todo-{idx + 1}" in summary:
                        current_step_idx = idx
                        break

    if not plan_steps:
        return []

    mapping: list[dict] = []
    for idx, step in enumerate(plan_steps):
        stats = step_stats[idx] if idx < len(step_stats) else {"attempts": 0, "failed_attempts": 0}
        mapping.append({
            "step_id": step.get("step_id", ""),
            "description": step.get("description", ""),
            "status": step.get("status", "unknown"),
            "attempts": max(stats["attempts"], 1),  # 至少有 1 次尝试
            "failed_attempts": stats["failed_attempts"],
            "locators": [],
        })
    return mapping


def _extract_key_insights(timeline_events: list[dict], failed_actions: list[dict]) -> list[str]:
    """从 agent_thought 事件和失败记录中提取关键发现。"""
    insights: list[str] = []
    seen_urls: set[str] = set()
    error_patterns: dict[str, int] = {}

    for action in failed_actions:
        err = action.get("error_type", "unknown")
        error_patterns[err] = error_patterns.get(err, 0) + 1

    if error_patterns:
        top_error = max(error_patterns, key=error_patterns.get)
        counts = error_patterns[top_error]
        error_labels = {
            "locator_not_unique": "定位器匹配多个元素",
            "not_visible": "定位器对应元素不可见",
            "action_failed": "工具执行失败",
            "locator_timeout": "定位器超时",
            "pointer_intercepted": "元素被遮挡",
        }
        insights.append(
            f"**定位挑战**：共遇到 {counts} 次 `{top_error}` 问题。"
            f"原因：{error_labels.get(top_error, top_error)}。"
            f"Agent 通过重试和切换选择器策略最终解决。"
        )

    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        if event.get("type") != "agent_thought":
            continue
        display = event.get("display", {}) if isinstance(event.get("display"), dict) else {}
        summary: str = display.get("summary", "")
        if not summary:
            continue
        clue_keywords = ["发现", "找到", "成功", "完成", "探索到", "识别到", "注意到"]
        for kw in clue_keywords:
            if kw in summary and len(summary) > 15 and len(summary) < 500:
                clean = summary.strip().replace("\n", " ")[:200]
                if clean not in [i[:200] for i in insights]:
                    insights.append(f"**观察**：{clean}")
                    break

    return insights[:5]


def _summarize_failed_actions(failed_actions: list[dict], timeline_events: list[dict]) -> dict[str, list[dict]]:
    """将失败动作按页面 URL 分组聚合。URL 从 display.fields 或 payload 中提取。"""
    page_failures: dict[str, list[dict]] = {}
    current_page_url = "未知页面"

    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type", "")
        payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}

        if event_type == "agent_tool_completed":
            tool_name = payload.get("tool_name", "")
            if tool_name in ("playwright_navigate_tool", "playwright_snap_tool"):
                url = _extract_url_from_event(event)
                if url:
                    if url.startswith("/"):
                        url = f"https://www.cybotstar.cn{url}"
                    current_page_url = url
        elif event_type == "agent_tool_failed":
            output = payload.get("output", {}) if isinstance(payload.get("output"), dict) else {}
            failure = (
                payload.get("failure")
                if isinstance(payload.get("failure"), dict)
                else output.get("failure") if isinstance(output.get("failure"), dict) else {}
            )
            page_failures.setdefault(current_page_url, []).append({
                "tool": payload.get("tool_name", "unknown"),
                "error_type": failure.get("error_type") or output.get("error_type") or "unknown",
                "summary": failure.get("summary") or output.get("summary") or output.get("error") or payload.get("error_summary") or "",
                "locator": payload.get("locator", ""),
            })

    return page_failures


def _failed_actions_from_timeline(timeline_events: list[dict]) -> list[dict]:
    failed: list[dict] = []
    for event in timeline_events:
        if event.get("type") != "agent_tool_failed":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        output = payload.get("output") if isinstance(payload.get("output"), dict) else {}
        failure = payload.get("failure") if isinstance(payload.get("failure"), dict) else {}
        if not failure:
            failure = output.get("failure") if isinstance(output.get("failure"), dict) else {}
        input_data = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        failed.append(
            {
                "tool_name": payload.get("tool_name"),
                "error_type": failure.get("error_type") or output.get("error_type"),
                "summary": failure.get("summary") or output.get("error") or payload.get("error_summary"),
                "locator": payload.get("locator") or input_data.get("locator") or output.get("effective_locator"),
            }
        )
    return failed


def _exploration_completion_status(timeline_events: list[dict]) -> str:
    """探索完成状态：只有 completed 或 failed"""
    for event in timeline_events:
        if event.get("type") == "agent_step_error":
            return "failed"
    return "completed"


def _artifact_quality_warnings(page_artifacts: list[tuple[Path, dict]]) -> list[str]:
    warnings: list[str] = []
    for path, artifact in page_artifacts:
        states = artifact.get("states") if isinstance(artifact.get("states"), list) else []
        if not states:
            warnings.append(f"{path.name} 未记录页面状态。")
            continue
        if _artifact_element_count(states) == 0:
            warnings.append(f"{path.name} 没有采集到可操作元素。")
        quality = artifact.get("quality") if isinstance(artifact.get("quality"), dict) else {}
        for key in ("warnings", "issues"):
            values = quality.get(key)
            if isinstance(values, list):
                for value in values:
                    if value:
                        warnings.append(f"{path.name}: {_string(value)}")
    return warnings


def _artifact_element_count(states: list[dict]) -> int:
    total = 0
    for state in states:
        if not isinstance(state, dict):
            continue
        elements = state.get("elements")
        if isinstance(elements, list):
            total += len(elements)
        children = state.get("children")
        if isinstance(children, list):
            total += _artifact_element_count(children)
    return total


def _render_page_element_badge(element: dict) -> str:
    """将元素渲染为 [role] name 格式的 badge，截断过长的 name。"""
    source = element.get("source", {}) if isinstance(element.get("source"), dict) else {}
    role = source.get("role", "?") or "?"
    name = source.get("name", "") or ""
    key = element.get("key", "")

    # 优先用 key（语义 ID），其次用 name
    display = key or name
    if len(display) > 40:
        display = display[:37] + "..."

    # 角色映射为中文
    role_map = {
        "button": "按钮", "textbox": "输入框", "link": "链接",
        "checkbox": "复选框", "radio": "单选", "combobox": "下拉框",
        "menuitem": "菜单项", "menu": "菜单", "tab": "标签页",
        "dialog": "对话框", "alert": "提示", "tooltip": "提示",
        "row": "行", "cell": "单元格", "columnheader": "列头",
        "img": "图片", "heading": "标题", "paragraph": "段落",
        "listitem": "列表项", "list": "列表",
    }
    role_label = role_map.get(role.lower(), role)
    return f"[{role_label}] {display}"


def _render_page_elements(elements: list[dict], max_count: int = 10) -> list[str]:
    """渲染元素列表为 Markdown 行，每行一个 badge。"""
    lines = []
    # 优先显示可交互元素（按 role 分类）
    interactive_roles = {"button", "textbox", "link", "checkbox", "combobox", "menuitem", "tab", "menu"}
    interactive = [e for e in elements if isinstance(e, dict) and (e.get("source", {}).get("role", "").lower() in interactive_roles)]
    static = [e for e in elements if isinstance(e, dict) and e not in interactive]

    shown = 0
    for e in interactive:
        if shown >= max_count:
            break
        badge = _render_page_element_badge(e)
        lines.append(f"- {badge}")
        shown += 1

    remaining = len(elements) - shown
    if remaining > 0:
        lines.append(f"- _...还有 {remaining} 个元素_")

    return lines


def _render_exploration_summary_from_db(run_id: str, db_path: Path) -> dict:
    """从 DB 读取 exploration_pages 表，构建页面信息字典。"""
    if not db_path.exists():
        return {}
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    pages: dict[str, dict] = {}
    try:
        cur.execute(
            "SELECT id, title, url, entry_path, structure_summary, created_at "
            "FROM exploration_pages WHERE exploration_run_id = ?",
            (run_id,),
        )
        for row in cur.fetchall():
            pages[row["id"]] = {
                "title": row["title"] or "",
                "url": row["url"] or "",
                "entry_path": row["entry_path"] or "",
                "structure_summary": row["structure_summary"] or "",
                "created_at": row["created_at"] or "",
            }
    except Exception:
        pass
    conn.close()
    return pages

    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path_part = parsed.path.strip("/") or "/"
        params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        short_url = path_part
        if "id" in params:
            short_url = f"{path_part}?id={params['id']}"
        elif "agentId" in params:
            short_url = f"{path_part}?agentId={params['agentId']}"
        if len(short_url) > 50:
            short_url = short_url[:47] + "..."
    except Exception:
        short_url = url[:50]

    return {
        "title": title,
        "url": url,
        "short_url": short_url,
        "element_count": element_count,
        "state_count": len(states),
        "filename": path.name,
    }


def _compute_exploration_stats(timeline_events: list[dict], failed_actions: list[dict], start_url: str) -> dict:
    """从 timeline 事件中计算执行统计信息。"""
    stats = {
        "total_events": len(timeline_events),
        "tool_calls": 0,
        "tool_failures": len(failed_actions),
        "navigate_count": 0,
        "click_count": 0,
        "fill_count": 0,
        "snap_count": 0,
        "thought_count": 0,
        "duration_seconds": 0,
        "run_start": "",
    }

    run_start = ""
    run_end = ""

    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("type", "")
        occurred_at = event.get("occurred_at", "")
        if not run_start and occurred_at:
            run_start = occurred_at
        run_end = occurred_at

        if event_type == "agent_tool_started":
            stats["tool_calls"] += 1
            payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
            tool_name = payload.get("tool_name", "")
            if "navigate" in tool_name:
                stats["navigate_count"] += 1
            elif "click" in tool_name:
                stats["click_count"] += 1
            elif "fill" in tool_name:
                stats["fill_count"] += 1
            elif "snap" in tool_name:
                stats["snap_count"] += 1
        elif event_type == "agent_thought":
            stats["thought_count"] += 1

    stats["run_start"] = run_start

    if run_start and run_end:
        try:
            from datetime import datetime as dt
            s = dt.fromisoformat(run_start.replace("Z", "+00:00"))
            e = dt.fromisoformat(run_end.replace("Z", "+00:00"))
            stats["duration_seconds"] = max(int((e - s).total_seconds()), 1)
        except Exception:
            stats["duration_seconds"] = 0

    return stats


def _format_duration(seconds: int) -> str:
    """将秒数格式化为人类可读时长字符串。"""
    if seconds < 60:
        return f"{seconds}秒"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}分{secs}秒"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}小时{mins}分{secs}秒"


def _status_emoji(status: str) -> str:
    """将状态值映射为 emoji 图标。"""
    return {
        "completed": "✅",
        "done": "✅",
        "in_progress": "🔄",
        "running": "🔄",
        "pending": "⏳",
        "failed": "❌",
        "error": "❌",
        "unknown": "❓",
    }.get(status, "❓")


def _default_db_path() -> Path:
    """获取默认数据库路径。"""
    try:
        from app.core.settings import settings as app_settings

        url = getattr(app_settings, "DATABASE_URL", "") or ""
        if url.startswith("sqlite:///"):
            return Path(url.replace("sqlite:///", ""))
    except Exception:
        pass
    return Path("apps/backend/data/ai_testing.db")


def _render_summary_banner(stats: dict, plan_steps: list[dict]) -> str:
    """生成执行概览横幅（badge 格式）。"""
    failures = stats.get("tool_failures", 0)
    pages = stats.get("total_pages", "?")
    if failures > 0:
        status_icon = "⚠️"
    elif plan_steps:
        completed = sum(1 for s in plan_steps if s.get("status") in ("completed", "done"))
        total = len(plan_steps)
        pct = int(completed / total * 100) if total else 0
        status_icon = "✅" if pct == 100 else "🔄"
    else:
        status_icon = "✅"
    return f"{status_icon} 完成 · {pages} 页面 · {failures} 次失败"


def _render_page_section(
    artifact: tuple[Path, dict],
    db_pages: dict[str, dict],
    page_order: dict[str, int],
) -> list[str]:
    """渲染单个页面的报告 section。"""
    path, artifact_data = artifact
    page = artifact_data.get("page", {}) if isinstance(artifact_data.get("page"), dict) else {}
    states = artifact_data.get("states", []) if isinstance(artifact_data.get("states"), list) else []
    page_id = path.stem

    db_info = db_pages.get(page_id, {})
    title = db_info.get("title") or page.get("title") or page_id
    structure_summary = db_info.get("structure_summary") or artifact_data.get("_db_summary", "")
    url = db_info.get("url") or page.get("url", "")

    element_count = _artifact_element_count(states)
    if element_count == 0 and structure_summary:
        # 从 DB 的 structure_summary 中提取元素数量（如"发现 23 个元素"）
        import re
        m = re.search(r"发现\s*(\d+)\s*个.*元素", structure_summary)
        if m:
            element_count = int(m.group(1))

    lines: list[str] = []

    short = _short_url(url)
    lines.append(f"### {title}")
    lines.append("")
    lines.append(f"| | |")
    lines.append(f"|---|---|---|")
    lines.append(f"| 路径 | `{short}` |")
    lines.append(f"| 元素 | {element_count} 个 |")
    if structure_summary:
        lines.append(f"| 摘要 | {structure_summary} |")
    lines.append("")

    # 展开所有元素
    all_elements: list[dict] = []
    for state in states:
        if not isinstance(state, dict):
            continue
        for e in state.get("elements", []):
            if isinstance(e, dict):
                all_elements.append(e)
        all_elements.extend(_collect_elements_from_children(state))

    if all_elements:
        lines.append("**可交互元素**")
        lines.append("")
        lines.extend(_render_page_elements(all_elements, max_count=12))
        lines.append("")

    return lines


def _collect_elements_from_children(state: dict) -> list[dict]:
    """递归收集 state children 里的所有元素。"""
    result: list[dict] = []
    for child in state.get("children", []):
        if isinstance(child, dict):
            for e in child.get("elements", []):
                if isinstance(e, dict):
                    result.append(e)
            result.extend(_collect_elements_from_children(child))
    return result


def _page_visit_order(timeline_events: list[dict]) -> dict[str, int]:
    """从 timeline 中提取页面首次访问顺序。"""
    order: dict[str, int] = {}
    counter = 0
    for event in timeline_events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "agent_tool_completed":
            payload = event.get("payload", {})
            if isinstance(payload, dict) and payload.get("tool_name") == "playwright_snap_tool":
                url = _extract_url_from_event(event)
                if url and url not in order:
                    order[url] = counter
                    counter += 1
    return order


def _short_url(url: str) -> str:
    """将完整 URL 简化为路径部分。"""
    if not url:
        return "/"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url if "://" in url else f"https://{url}")
        path_part = parsed.path.strip("/") or "/"
        params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
        if "agentId" in params:
            return f"{path_part}?agentId={params['agentId']}"
        if "id" in params:
            return f"{path_part}?id={params['id']}"
        return path_part if path_part != "/" else "/"
    except Exception:
        return url[:50]


def _error_type_label(err_type: str) -> str:
    """将错误类型映射为中文标签。"""
    return {
        "locator_not_unique": "🔍 定位器不唯一",
        "not_visible": "👁 元素不可见",
        "action_failed": "⚠️ 操作失败",
        "locator_timeout": "⏱ 定位器超时",
        "pointer_intercepted": "🖱 指针被遮挡",
        "unknown": "❓ 未知错误",
    }.get(err_type, f"❓ {err_type}")


def _build_tool_timing_map(timeline_events: list[dict], run_start: str) -> dict[str, float]:
    """构建 tool step_id -> 相对时间（秒）的映射。"""
    timing: dict[str, float] = {}
    if not run_start:
        return timing
    try:
        from datetime import datetime as dt

        start = dt.fromisoformat(run_start.replace("Z", "+00:00"))
        for event in timeline_events:
            if not isinstance(event, dict):
                continue
            occurred_at = event.get("occurred_at", "")
            if not occurred_at:
                continue
            try:
                t = dt.fromisoformat(occurred_at.replace("Z", "+00:00"))
                elapsed = (t - start).total_seconds()
                event_type = event.get("type", "")
                if event_type in ("agent_tool_started", "agent_tool_completed", "agent_tool_failed"):
                    payload = event.get("payload", {})
                    if isinstance(payload, dict):
                        step_id = payload.get("step_id", "")
                        if step_id and step_id not in timing:
                            timing[step_id] = elapsed
            except Exception:
                pass
    except Exception:
        pass
    return timing


def _write_exploration_report(
    *,
    run_dir: Path,
    run_id: str,
    start_url: str,
    exploration_mode: str,
    page_artifacts: list[tuple[Path, dict]],
    goal: str = "",
    timeline_events: list[dict] | None = None,
    artifact_quality_warnings: list[str] | None = None,
    db_path: Path | None = None,
) -> Path:
    """生成专业的探索报告 Markdown 文档。

    报告结构：
    1. 执行概览（Executive Summary）——一眼看清全局
    2. 目标达成（Goal Progress）——目标探索模式下的子目标进度
    3. 页面图谱（Page Atlas）——URL 拓扑 + 可交互元素索引
    4. 失败诊断（Failure Diagnostics）——按页面分组的失败动作分析
    5. 执行时间线（Execution Timeline）——Mermaid Gantt
    """
    report_path = run_dir / "report.md"
    timeline_events = timeline_events or []
    artifact_quality_warnings = artifact_quality_warnings or []

    # ── 数据准备 ────────────────────────────────────────────────────────────
    db_path = db_path or _default_db_path()
    db_pages = _render_exploration_summary_from_db(run_id, db_path)
    latest_plan_steps = _latest_plan_steps_from_timeline(timeline_events)
    failed_actions = _failed_actions_from_timeline(timeline_events)
    page_topology = _build_page_topology(timeline_events)
    goal_mapping = _build_goal_action_mapping(timeline_events)
    key_insights = _extract_key_insights(timeline_events, failed_actions)
    page_failures = _summarize_failed_actions(failed_actions, timeline_events)
    stats = _compute_exploration_stats(timeline_events, failed_actions, start_url)
    stats["total_pages"] = len(page_artifacts)
    run_start = stats["run_start"]

    # ── 工具调用时间（用于 gantt） ────────────────────────────────────────
    tool_timings = _build_tool_timing_map(timeline_events, run_start)

    # ── 报告主体 ──────────────────────────────────────────────────────────
    lines: list[str] = []

    # ══════════════════════════════════════════════════════════════════════
    # 1. 执行概览
    # ══════════════════════════════════════════════════════════════════════
    lines.extend([
        "# 探索报告",
        "",
        _render_summary_banner(stats, latest_plan_steps),
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 运行 ID | `{run_id}` |",
        f"| 入口 URL | `{start_url}` |",
        f"| 探索方式 | {_exploration_mode_label(exploration_mode)} |",
        f"| 执行时长 | {_format_duration(stats['duration_seconds'])} |",
        f"| 页面产物 | {len(page_artifacts)} 个 |",
        f"| 工具调用 | {stats['tool_calls']} 次 |",
        f"| 调用失败 | {stats['tool_failures']} 次 |",
        f"| 快照采集 | {stats['snap_count']} 次 |",
        "",
    ])

    # 关键发现（如果有）放在概览之后
    if key_insights:
        lines.extend(["**本次探索关键发现**", ""])
        for insight in key_insights:
            lines.append(f"- {insight}")
        lines.append("")

    # 目标（如果有）
    if goal:
        lines.extend(["**探索目标**", ""])
        for line in goal.strip().splitlines():
            line = line.strip()
            if line:
                lines.append(f"- {line}")
        lines.append("")

    # ══════════════════════════════════════════════════════════════════════
    # 2. 目标达成（目标探索模式）
    # ══════════════════════════════════════════════════════════════════════
    if latest_plan_steps and exploration_mode == "goal":
        lines.extend(["---", "", "## 目标达成", ""])
        completed = sum(1 for s in latest_plan_steps if s.get("status") in ("completed", "done"))
        total = len(latest_plan_steps)
        pct = int(completed / total * 100) if total else 0

        # 进度条（文字版）
        filled = "█" * (pct // 10)
        empty = "░" * (10 - len(filled))
        lines.append(f"**进度：** {filled}{empty} **{pct}%**（{completed}/{total} 步完成）")
        lines.append("")

        lines.extend(["| # | 子目标 | 状态 | 尝试 |", "|---|--------|------|------|"])
        for idx, step in enumerate(latest_plan_steps, 1):
            desc = _string(step.get("description") or step.get("content") or "")
            status = step.get("status", "unknown")
            emoji = _status_emoji(status)
            attempts = 1
            for gm in goal_mapping:
                if gm.get("step_id") == step.get("step_id"):
                    attempts = gm.get("attempts", 1)
                    break
            lines.append(f"| {idx} | {desc[:70]}{'...' if len(desc) > 70 else ''} | {emoji} | {attempts} |")
        lines.append("")

    # ══════════════════════════════════════════════════════════════════════
    # 3. 探索路径图
    # ══════════════════════════════════════════════════════════════════════
    path_diagram = _render_exploration_path_flowchart(_build_exploration_path_steps(timeline_events, start_url))
    if path_diagram:
        lines.extend(["---", "", "## 探索路径图", ""])
        lines.append("_按本次运行的页面快照、关键操作和失败节点整理。_")
        lines.append("")
        lines.append(path_diagram)
        lines.append("")

    # ══════════════════════════════════════════════════════════════════════
    # 4. 页面图谱
    # ══════════════════════════════════════════════════════════════════════
    lines.extend(["---", "", "## 页面图谱", ""])

    if page_artifacts:
        lines.append(f"共采集 **{len(page_artifacts)}** 个页面：")
        lines.append("")

        # 按访问顺序排序（timeline 中的首次出现顺序）
        page_order = _page_visit_order(timeline_events)

        for artifact in page_artifacts:
            lines.extend(_render_page_section(artifact, db_pages, page_order))
    else:
        lines.append("_本次探索未产生页面产物。_")
    lines.append("")

    # 拓扑图（附加在页面图谱之后）
    mermaid_topology = _render_mermaid_topology(page_topology)
    if mermaid_topology:
        lines.append("**页面跳转拓扑**：")
        lines.append("")
        lines.append(mermaid_topology)
        lines.append("")

    # ══════════════════════════════════════════════════════════════════════
    # 4. 失败诊断
    # ══════════════════════════════════════════════════════════════════════
    lines.extend(["---", "", "## 失败诊断", ""])

    if page_failures:
        total_failures = sum(len(v) for v in page_failures.values())
        lines.append(f"共 **{total_failures}** 次工具调用失败，按发生页面分组：")
        lines.append("")

        for page_url, failures in page_failures.items():
            short = _short_url(page_url)
            lines.append(f"### `{short}`")
            lines.append("")

            # 按错误类型聚类
            by_type: dict[str, list[dict]] = {}
            for f in failures:
                by_type.setdefault(f.get("error_type", "unknown"), []).append(f)

            for err_type, items in by_type.items():
                err_label = _error_type_label(err_type)
                lines.append(f"**{err_label}**（{len(items)} 次）")
                lines.append("")
                for f in items:
                    loc = f.get("locator", "")
                    summary = f.get("summary", "")
                    if summary and loc:
                        lines.append(f"- `{loc}`：{summary[:120]}{'...' if len(summary) > 120 else ''}")
                    elif loc:
                        lines.append(f"- `{loc}`")
                    elif summary:
                        lines.append(f"- {summary[:120]}{'...' if len(summary) > 120 else ''}")
                lines.append("")
    elif failed_actions:
        lines.append("以下失败未按页面分组（原始记录）：")
        lines.append("")
        for action in failed_actions:
            tool = _string(action.get("tool_name") or "tool")
            err_type = _string(action.get("error_type") or "action_failed")
            err_label = _error_type_label(err_type)
            summary = _string(action.get("summary") or "工具执行失败。")
            locator = _string(action.get("locator") or "")
            suffix = f"（`{locator}`）" if locator else ""
            lines.append(f"- [{tool}] {err_label}：{summary}{suffix}")
        lines.append("")
    else:
        lines.append("✅ 本次探索未遇到工具失败。")
        lines.append("")

    # 产物质量提示
    if artifact_quality_warnings:
        lines.extend(["---", "", "## 产物质量提示", ""])
        for warning in artifact_quality_warnings:
            lines.append(f"- ⚠️ {warning}")
        lines.append("")

    # ══════════════════════════════════════════════════════════════════════
    # 5. 执行时间线（Mermaid Gantt）
    # ══════════════════════════════════════════════════════════════════════
    mermaid_gantt = _render_mermaid_gantt(timeline_events, run_start)
    if mermaid_gantt:
        lines.extend(["---", "", "## 执行时间线", ""])
        lines.append("_工具调用顺序与结果（红色 = 失败）：_")
        lines.append("")
        lines.append(mermaid_gantt)
        lines.append("")

    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
