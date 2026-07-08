# apps/backend/app/services/page_exploration/timeline_projection.py

import hashlib
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from app.services.page_exploration.event_payload import _clean_compact_payload, _compact_event_payload

logger = logging.getLogger(__name__)


def _string(value) -> str:
    return "" if value is None else str(value)


def _coerce_tool_output_dict(output) -> dict:
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except json.JSONDecodeError:
            return {"raw": output}
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    return {}


def _projection_chunk_to_timeline_events(
    mode: str | None,
    data,
    *,
    raw_event_id: str | None,
    tool_inputs: dict[str, dict],
    seen_projection_keys: set[str] | None = None,
    project_id: str = "",
    run_id: str = "",
) -> list[dict]:
    if mode != "updates":
        return []
    events: list[dict] = []
    for message in _messages_from_projection_update(data):
        thought = _projection_message_to_thought_event(message, raw_event_id=raw_event_id)
        if thought:
            projection_key = _projection_message_key(message, thought["display"]["summary"])
            if not _projection_seen(projection_key, seen_projection_keys):
                events.append(thought)
        for tool_call in _message_tool_calls(message):
            tool_id = _tool_call_id(tool_call)
            tool_name = _tool_call_name(tool_call)
            tool_args = _tool_call_args(tool_call)
            if tool_id:
                tool_inputs[tool_id] = {"name": tool_name, "args": tool_args}
            projection_key = f"tool:{tool_id or tool_name}:start"
            if _projection_seen(projection_key, seen_projection_keys):
                continue
            readable = _projection_tool_event_to_timeline_event(
                tool_name=tool_name,
                tool_id=tool_id,
                status="running",
                input_data=tool_args,
                output_data={},
                raw_event_id=raw_event_id,
                project_id=project_id,
                run_id=run_id,
            )
            if readable:
                events.append(readable)
        if _is_projection_tool_message(message):
            tool_id = _message_field(message, "tool_call_id")
            remembered = tool_inputs.get(tool_id, {})
            tool_name = _message_field(message, "name") or _string(remembered.get("name"))
            output_data = _coerce_tool_output_dict(_message_field(message, "content"))
            projection_key = f"tool:{tool_id or tool_name}:end"
            if _projection_seen(projection_key, seen_projection_keys):
                continue
            readable = _projection_tool_event_to_timeline_event(
                tool_name=tool_name,
                tool_id=tool_id,
                status=_tool_output_status(output_data),
                input_data=remembered.get("args") if isinstance(remembered.get("args"), dict) else {},
                output_data=output_data,
                raw_event_id=raw_event_id,
                project_id=project_id,
                run_id=run_id,
            )
            if readable:
                if tool_name == "playwright_snap_tool":
                    readable["snapshot_event"] = {
                        "event": "on_tool_end",
                        "name": tool_name,
                        "data": {"output": output_data},
                    }
                events.append(readable)
    return events


def _tool_output_status(output_data: dict) -> str:
    if output_data.get("success") is False:
        return "failed"
    if output_data.get("error"):
        return "failed"
    failure = output_data.get("failure")
    if isinstance(failure, dict) and output_data.get("success") is not True:
        return "failed"
    return "completed"


def _projection_seen(projection_key: str, seen_projection_keys: set[str] | None) -> bool:
    if seen_projection_keys is None:
        return False
    if projection_key in seen_projection_keys:
        return True
    seen_projection_keys.add(projection_key)
    return False


def _projection_message_key(message, content: str) -> str:
    message_id = _string(_message_field(message, "id"))
    if message_id:
        return f"message:{message_id}"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"message-content:{digest}"


def _projection_message_to_thought_event(message, *, raw_event_id: str | None) -> dict | None:
    if _is_projection_tool_message(message):
        return None
    thought = _public_agent_thought(_message_field(message, "content"))
    if not thought:
        return None
    return {
        "type": "agent_thought",
        "payload": _clean_compact_payload(
            {
                "status": "completed",
                "raw_event_id": raw_event_id,
            }
        ),
        "display": {
            "kind": "thought",
            "title": "Agent",
            "summary": thought,
        },
    }


def _public_agent_thought(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") if item.get("type") in {"text", "output_text"} else ""
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        content = "\n".join(parts)
    text = _compact_event_payload(content).strip()
    if not text:
        return ""
    import re

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    text = re.sub(r"```(?:json|text)?\s*.*?```", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if not text or text.startswith("{") or text.startswith("["):
        return ""
    return text[:500]


def _projection_tool_event_to_timeline_event(
    *,
    tool_name: str,
    tool_id: str,
    status: str,
    input_data: dict,
    output_data: dict,
    raw_event_id: str | None,
    project_id: str = "",
    run_id: str = "",
) -> dict | None:
    event_name = "on_tool_start" if status == "running" else "on_tool_error" if status == "failed" else "on_tool_end"
    display = _readable_tool_display(
        tool_name,
        event_name,
        {"input": input_data, "output": output_data},
        status,
    )
    stream_type = "agent_tool_started" if status == "running" else "agent_tool_failed" if status == "failed" else "agent_tool_completed"
    if tool_name == "write_todos":
        if status != "completed":
            return None
        plan_steps = _todo_plan_steps(input_data.get("todos"))
        # 把 todo 列表落盘到 subgoals.yaml，下一次 check_explored_url 就能读出来
        try:
            from app.agents.page_exploration.tools.url_tools import write_subgoals_snapshot
            from app.core import settings as _settings

            if project_id and run_id:
                write_subgoals_snapshot(
                    project_id=project_id,
                run_id=run_id,
                    base_dir=_settings.PROJECT_FILE_STORAGE_ROOT,
                    todos=input_data.get("todos") if isinstance(input_data.get("todos"), list) else [],
                )
        except Exception as exc:
            logger.warning(
                "failed to persist page exploration subgoals: project_id=%s run_id=%s error=%s",
                project_id,
                run_id,
                exc,
            )
        return {
            "type": "agent_plan_updated",
            "payload": _clean_compact_payload(
                {
                    "step_id": f"agent-tool-{tool_id or tool_name}",
                    "tool_name": tool_name,
                    "status": status,
                    "raw_event_id": raw_event_id,
                    "error_summary": _compact_event_payload(output_data.get("error")),
                    "plan_steps": plan_steps,
                }
            ),
        }
    if display is None:
        return None
    payload = {
        "step_id": f"agent-tool-{tool_id or tool_name}",
        "tool_name": tool_name,
        "status": status,
        "raw_event_id": raw_event_id,
        "error_summary": _compact_event_payload(output_data.get("error")),
    }
    if input_data.get("locator"):
        payload["locator"] = _compact_event_payload(input_data.get("locator"))
    failure = output_data.get("failure")
    if isinstance(failure, dict):
        payload["failure"] = {
            "error_type": _compact_event_payload(failure.get("error_type")),
            "summary": _compact_event_payload(failure.get("summary")),
            "recovered": bool(failure.get("recovered", False)),
            "recovery_warning": _compact_event_payload(failure.get("recovery_warning")),
        }
    return {
        "type": stream_type,
        "payload": _clean_compact_payload(payload),
        "display": display,
    }


def _todo_plan_steps(todos) -> list[dict]:
    if not isinstance(todos, list):
        return []
    steps = []
    for index, todo in enumerate(todos, start=1):
        if not isinstance(todo, dict):
            continue
        content = _readable_todo_description(_compact_event_payload(todo.get("content")))
        if not content:
            continue
        steps.append(
            {
                "step_id": _compact_event_payload(todo.get("id")) or f"agent-todo-{index}",
                "step_number": index,
                "description": content,
                "status": _compact_event_payload(todo.get("status")) or "pending",
                "action_type": "todo",
                "execution_strategy": "agent_plan",
            }
        )
    return steps


def _readable_todo_description(content: str) -> str:
    """Polish agent todos for UI display without changing the requested action."""
    if not content:
        return ""
    description = content.strip()
    description = _replace_once(description, "进入工作台页面", "打开工作台界面")
    description = _replace_once(description, "进入工作台", "打开工作台界面")
    description = _replace_once(description, "进入该 Agent 的草稿编辑页面", "打开该 Agent 的草稿编辑界面")
    description = _replace_once(description, "进入该Agent的草稿编辑页面", "打开该 Agent 的草稿编辑界面")
    description = _replace_once(description, "在草稿编辑页面调试预览找到对话框", "在草稿编辑界面打开调试预览，找到对话框")
    description = _replace_once(description, "在预览对话框的输入框中输入", "在预览对话框中点击输入框，输入")
    description = _replace_once(description, "发送对话", "点击发送按钮发送对话")
    if "新建" in description and "Agent" in description and "点击" not in description:
        description = description.replace("新建", "点击创建按钮，新建", 1)
    return description


def _replace_once(value: str, old: str, new: str) -> str:
    return value.replace(old, new, 1) if old in value else value


def _messages_from_projection_update(data) -> list:
    if not isinstance(data, dict):
        return []
    messages = []
    for value in data.values():
        if isinstance(value, dict):
            node_messages = value.get("messages")
            if isinstance(node_messages, list):
                messages.extend(node_messages)
        elif isinstance(value, list):
            messages.extend(value)
    return messages


def _message_tool_calls(message) -> list:
    calls = _message_field(message, "tool_calls") or _message_field(message, "tool_call_chunks")
    return calls if isinstance(calls, list) else []


def _is_projection_tool_message(message) -> bool:
    message_type = _message_field(message, "type") or _message_field(message, "role")
    return message_type == "tool" or message.__class__.__name__ == "ToolMessage"


def _message_field(message, key: str):
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)


def _tool_call_id(tool_call) -> str:
    return _string(_message_field(tool_call, "id") or _message_field(tool_call, "tool_call_id"))


def _tool_call_name(tool_call) -> str:
    return _string(_message_field(tool_call, "name"))


def _tool_call_args(tool_call) -> dict:
    args = _message_field(tool_call, "args")
    return args if isinstance(args, dict) else {}


def _readable_tool_display(tool_name: str, event_name: str, data: dict, status: str) -> dict | None:
    """生成工具调用的前端显示信息。

    只为关键工具生成显示信息，过滤辅助性工具：
    - 保留：页面操作（导航、点击、快照）、页面事实写入、计划更新
    - 过滤：内部文件读取、URL记录等辅助操作
    """
    input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
    output_data = data.get("output") if isinstance(data.get("output"), dict) else {}
    error = _compact_event_payload(data.get("error")) or _compact_event_payload(output_data.get("error"))

    # 过滤掉辅助性工具：read_file（内部配置读取）、update_explored_url_tool（URL记录）
    if tool_name in {"read_file", "update_explored_url_tool"}:
        return None

    if tool_name == "write_todos":
        todos = input_data.get("todos") if isinstance(input_data, dict) else []
        current = next((todo for todo in todos if isinstance(todo, dict) and todo.get("status") == "in_progress"), None) if isinstance(todos, list) else None
        pending = [todo for todo in todos if isinstance(todo, dict) and todo.get("status") == "pending"][:3] if isinstance(todos, list) else []
        current_content = _readable_todo_description(_tool_field(current or {}, "content"))
        return _tool_display(
            "todo_update",
            "探索计划更新",
            current_content or "更新探索待办计划。",
            status,
            [
                {"label": "当前进行", "value": current_content},
                {
                    "label": "待处理",
                    "value": "\n".join(
                        f"{index + 1}. {_readable_todo_description(_tool_field(todo, 'content'))}"
                        for index, todo in enumerate(pending)
                    ),
                },
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )
    if tool_name == "playwright_navigate_tool":
        url = _tool_field(input_data, "url") or _tool_field(output_data, "url")
        return _tool_display(
            "navigate",
            "打开页面",
            f"打开 {_compact_url_for_display(url) or '目标页面'}",
            status,
            [{"label": "目标 URL", "value": _compact_url_for_display(url), "mono": True}, {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)}],
            error,
        )
    if tool_name == "playwright_click_tool":
        locator = _tool_field(input_data, "locator") or _compact_event_payload(data.get("input"))
        target = _locator_label(locator) or "页面元素"
        return _tool_display(
            "click",
            "点击元素",
            f"点击 {target}",
            status,
            [
                {"label": "目标", "value": target},
                {"label": "定位器", "value": locator, "mono": True},
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )
    if tool_name == "playwright_snap_tool":
        page_title = _tool_field(output_data, "title")
        page_url = _compact_url_for_display(_tool_field(output_data, "url"))
        page_identity = page_title or page_url or "当前页面"
        return _tool_display(
            "snapshot",
            "采集页面快照",
            f"采集 {page_identity} 的页面结构",
            status,
            [
                {"label": "页面", "value": page_title or page_identity},
                {"label": "URL", "value": page_url, "mono": True},
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )
    if tool_name == "write_page_artifact_tool":
        path = _tool_field(output_data, "path") or _tool_field(input_data, "path") or _tool_field(input_data, "artifact_path")
        page_label = _tool_field(input_data, "title") or _tool_field(input_data, "page_title")
        return _tool_display(
            "artifact_write",
            "写入页面事实",
            f"写入 {page_label} 的页面事实（{Path(path).name}）" if page_label and path else f"写入 {Path(path).name}" if path else "写入页面事实",
            status,
            [
                {"label": "页面", "value": page_label},
                {"label": "产物", "value": path, "mono": True},
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )

    # 如果有错误，显示错误信息（即使是未识别的工具）
    if error:
        return _tool_display("error", "执行失败", _error_reason(error), status, [{"label": "原因", "value": error, "tone": "danger"}], error)

    # 未识别的工具不生成显示信息，会被上层过滤掉
    return None


def _tool_display(kind: str, title: str, summary: str, status: str, fields: list[dict], error: str = "") -> dict:
    if error:
        title = f"{title}失败" if not title.endswith("失败") else title
        if not summary or summary == title or "失败" not in summary:
            summary = _error_reason(error) or summary
        if not any(field.get("label") == "原因" for field in fields):
            fields = [*fields, {"label": "原因", "value": error, "tone": "danger"}]
    return {
        "kind": kind,
        "title": title,
        "summary": summary,
        "fields": [field for field in fields if field.get("value")],
    }


def _tool_field(record: dict, key: str) -> str:
    return _compact_event_payload(record.get(key)) if isinstance(record, dict) else ""


def _status_label(status: str) -> str:
    return {"running": "执行中", "completed": "完成", "failed": "失败"}.get(status, status)


def _status_tone(status: str) -> str:
    return "danger" if status == "failed" else "success"


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




def _error_reason(error: str) -> str:
    if not error:
        return ""
    lowered = error.lower()
    if "429" in error or "rate_limit_exceeded" in error:
        return "模型配额限制"
    if "stale_ref" in lowered or "unknown element id" in lowered or "element is not attached" in lowered:
        return "元素引用已失效（页面已刷新）"
    if "timeout" in lowered or "timed out" in lowered:
        return "操作超时"
    if "not visible" in lowered or "not attached" in lowered or "intercept" in lowered:
        return "元素当前不可点击"
    if "no element" in lowered or "no node" in lowered or "not found" in lowered or "selector" in lowered and "resolved" in lowered:
        return "未找到匹配元素"
    if "navigation" in lowered and "fail" in lowered:
        return "页面导航失败"
    if "permission" in lowered or "denied" in lowered:
        return "权限不足或被拒绝"
    return "执行失败"

