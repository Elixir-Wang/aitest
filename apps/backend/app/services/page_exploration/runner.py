# apps/backend/app/services/page_exploration/runner.py

import asyncio
import logging
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core import settings
from app.core.db import connect as default_connect
from app.core.environment_auth_state import auth_state_path, auth_state_summary
from app.repositories import exploration_run_repo as default_exploration_run_repo
from app.services.page_exploration import event_bus as default_event_bus
from app.services.page_exploration.event_log import _ExplorationEventLog, _publish_run_terminal_event
from app.services.page_exploration.event_payload import _compact_event_payload
from app.services.page_exploration.output_registry import (
    _append_project_page_edge,
    _checkpoint_snapshot_artifact_from_event,
    _element_name_from_locator,
    _page_identity_from_url,
    _register_exploration_outputs,
)
from app.services.page_exploration.report_writer import (
    _exploration_completion_status,
    _read_timeline_events_from_run_dir,
)
from app.services.page_exploration.run_detail import _normalize_exploration_run_detail
from app.services.page_exploration.timeline_projection import _projection_chunk_to_timeline_events


_running_explorations: dict[str, dict[str, object]] = {}
_exploration_lock = threading.Lock()
logger = logging.getLogger(__name__)


class ExplorationCancelledError(Exception):
    """Raised when a user-requested exploration stop is observed."""


def _service_attr(name: str, default):
    service_module = sys.modules.get("app.services.page_exploration.service")
    return getattr(service_module, name, default)


def _connect():
    return _service_attr("connect", default_connect)()


def _exploration_run_repo():
    return _service_attr("exploration_run_repo", default_exploration_run_repo)


def _event_bus():
    return _service_attr("event_bus", default_event_bus)


def _project_file_storage_root() -> Path:
    service_settings = _service_attr("settings", settings)
    return getattr(service_settings, "PROJECT_FILE_STORAGE_ROOT", settings.PROJECT_FILE_STORAGE_ROOT)


def _capability_id() -> str:
    return str(_service_attr("CAPABILITY_ID", "page_exploration"))


def _string(value) -> str:
    return "" if value is None else str(value)


def _exploration_run_is_stopping(run_id: str) -> bool:
    with _exploration_lock:
        runtime = _running_explorations.get(run_id)
        if runtime and runtime.get("should_stop"):
            return True

    with _connect() as db:
        run = _exploration_run_repo().find_by_id(db, run_id)
        return bool(run and run["status"] in {"stopping", "cancelled"})


def _ensure_exploration_not_stopping(run_id: str) -> None:
    if _exploration_run_is_stopping(run_id):
        raise ExplorationCancelledError("用户已停止探索任务。")


def _finalize_cancelled_exploration_run(run_id: str) -> None:
    finished_at = datetime.now(timezone.utc).isoformat()
    with _connect() as db:
        run = _exploration_run_repo().find_by_id(db, run_id)
        if not run:
            return
        if run["status"] == "cancelled":
            _event_bus().close(run_id)
            return
    artifact_summary = _service_attr(
        "_register_failed_exploration_outputs",
        _register_failed_exploration_outputs,
    )(run_id)
    result_summary = "探索任务已由用户停止。"
    if artifact_summary:
        result_summary = f"探索任务已由用户停止；{artifact_summary}"
    with _connect() as db:
        _exploration_run_repo().update_status(
            db,
            run_id,
            "cancelled",
            finished_at=finished_at,
            result_summary=result_summary,
        )
    _publish_run_terminal_event(
        _project_id_from_run(run),
        run_id,
        "run_cancelled",
        {
            "status": "cancelled",
            "result_summary": result_summary,
            "finished_at": finished_at,
        },
    )


def _run_exploration_background(run_id: str) -> None:
    """后台执行探索任务"""
    run_dict: dict = {}
    try:
        with _exploration_lock:
            _running_explorations[run_id] = {
                "should_stop": False,
                "current_page": None,
            }

        with _connect() as db:
            run = _exploration_run_repo().find_by_id(db, run_id)
            if run and run["status"] in {"stopping", "cancelled"}:
                raise ExplorationCancelledError("用户已停止探索任务。")
            _exploration_run_repo().update_status(
                db,
                run_id,
                "running",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            run = _exploration_run_repo().find_detail_by_id(db, run_id)
            if not run:
                return
            run_dict = dict(run)
        _event_bus().publish(
            run_id,
            "run_started",
            {
                "status": "running",
                "started_at": run_dict.get("started_at"),
                "result_summary": "探索任务已开始。",
            },
        )

        _service_attr("_execute_exploration", _execute_exploration)(run_id, run_dict)

    except ExplorationCancelledError:
        _finalize_cancelled_exploration_run(run_id)
    except Exception as e:
        artifact_summary = _service_attr(
            "_register_failed_exploration_outputs",
            _register_failed_exploration_outputs,
        )(run_id)
        result_summary = f"探索失败: {str(e)}"
        if artifact_summary:
            result_summary = f"{result_summary}；{artifact_summary}"
        with _connect() as db:
            _exploration_run_repo().update_status(
                db,
                run_id,
                "blocked",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=result_summary,
            )
        _publish_run_terminal_event(
            str(run_dict.get("project_id") or ""),
            run_id,
            "run_failed",
            {
                "status": "blocked",
                "error": str(e),
                "result_summary": result_summary,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    finally:
        _event_bus().close(run_id)
        with _exploration_lock:
            _running_explorations.pop(run_id, None)


def _execute_exploration(run_id: str, run_config: dict) -> None:
    """执行探索逻辑 - 集成deepagents Agent"""
    from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body

    project_id = run_config["project_id"]
    start_url = _exploration_start_url(run_config)
    scope = str(run_config.get("scope") or "").strip()
    goal = str(run_config.get("goal") or "").strip()
    exploration_mode = str(run_config["exploration_mode"]).strip()
    max_pages = run_config["max_pages"]
    storage_state_path = _exploration_auth_state_path(run_config)

    model_selection = resolve_model_selection(_capability_id())
    model = build_agent_model(model_selection, extra_body=thinking_disabled_extra_body(model_selection))

    asyncio.run(_service_attr("_execute_exploration_async", _execute_exploration_async)(
        model=model,
        project_id=project_id,
        run_id=run_id,
        start_url=start_url,
        exploration_mode=exploration_mode,
        max_pages=max_pages,
        scope=scope,
        goal=goal,
        storage_state_path=storage_state_path,
    ))


def _register_failed_exploration_outputs(run_id: str) -> str:
    """失败时登记本轮已写出的部分产物，供探索概览展示完整上下文。"""
    try:
        with _connect() as db:
            run = _exploration_run_repo().find_detail_by_id(db, run_id)
            if not run:
                return ""
            run_dict = _normalize_exploration_run_detail(dict(run))

        return _register_exploration_outputs(
            project_id=run_dict["project_id"],
            run_id=run_id,
            start_url=_exploration_start_url(run_dict),
            scope=str(run_dict.get("scope") or "").strip(),
            exploration_mode=str(run_dict.get("exploration_mode") or "goal").strip(),
            max_pages=int(run_dict.get("max_pages") or 0),
            result_status="failed",
        )
    except Exception as exc:
        logger.warning("failed to register failed exploration outputs: run_id=%s error=%s", run_id, exc)
        return f"失败产物登记失败：{exc}"


def _exploration_start_url(run_config: dict) -> str:
    """Use the configured environment entry URL; scope is a module constraint, not a URL."""
    start_url = str(run_config.get("environment_site_url") or "").strip()
    if not start_url:
        raise ValueError("探索任务缺少环境站点入口 URL，请先配置项目环境的站点地址。")
    return start_url


def _exploration_auth_state_path(run_config: dict) -> Path | None:
    environment_id = str(run_config.get("environment_id") or "").strip()
    if not environment_id:
        return None

    summary = auth_state_summary(
        environment_id=environment_id,
        login_strategy=str(run_config.get("environment_login_strategy") or ""),
        reuse_auth_state=bool(run_config.get("environment_reuse_auth_state")),
    )
    if summary.get("status") != "valid":
        return None

    path = auth_state_path(environment_id)
    return path if path.exists() else None


def _exploration_mode_label(exploration_mode: str) -> str:
    return "自主探索" if exploration_mode == "autonomous" else "目标探索"


def _exploration_agent_prompt(
    start_url: str,
    exploration_mode: str,
    scope: str,
    max_pages: int,
    goal: str = "",
) -> str:
    lines = [f"请探索网站: {start_url}"]
    mode_label = _exploration_mode_label(exploration_mode)
    lines.append(f"探索方式: {mode_label}")
    if scope.strip():
        lines.append(f"探索范围: {scope.strip()}")
    if goal.strip():
        lines.append(f"探索目标: {goal.strip()}")
    lines.append("")
    if exploration_mode == "autonomous":
        lines.extend(
            [
                "执行策略:",
                "- 这是自主探索：以探索范围为覆盖边界，自动识别范围内的主要模块、页面、入口和可测元素。",
                "- 如果提供了探索目标，它只是补充关注点，不作为单一路径完成条件。",
                "- 按模块盘点，不要因为某个具体动作完成就提前停止；达到范围覆盖或预算上限后总结。",
            ]
        )
    else:
        lines.extend(
            [
                "执行策略:",
                "- 这是目标探索：以探索目标为主线和完成条件，优先执行目标描述的页面流程。",
                "- 不要扩展为全量功能盘点；只探索完成目标所必需的页面、弹窗、字段和状态。",
                "- 目标完成、被阻塞或达到预算上限后停止并总结，不要继续无关分支。",
                "- **第一步必须用 `write_todos` 把上面“探索目标”拆成 3-7 个可验证子步骤**。",
                "  每条包含：动词开头的动作描述 + 明确的完成判据。",
                "- 后续每完成一个子步骤，必须 `write_todos` 标记 completed，再开始下一个。",
                "- 子步骤全部 completed 或被阻塞时立即停止，输出阶段总结。",
            ]
        )

    if exploration_mode == "goal" and goal.strip():
        lines.append("")
        lines.append("目标分解模板（请按此思路调整后写入 write_todos）：")
        for index, hint in enumerate(_initial_subgoal_hints(goal), start=1):
            lines.append(f"  {index}. {hint}")

    lines.append(f"最多探索 {max_pages} 个页面。")
    return "\n".join(lines)


def _initial_subgoal_hints(goal: str) -> list[str]:
    """根据探索目标生成粗粒度的子步骤提示，供 LLM 在第一轮 write_todos 中参考调整。"""
    goal_summary = goal.strip() or "探索目标"
    return [
        (
            f"步骤 1 / 进入入口：定位目标“{goal_summary}”的入口页面，"
            "用 snap 完成基线快照（完成判据：snapshot 中能看到入口元素，且 URL/标题符合预期）。"
        ),
        (
            "步骤 2 / 第一步动作：执行目标描述的第一个动作（点击/输入/选择），"
            "完成后立即 snap 校验（完成判据：URL/弹窗/列表/详情页有可观察的预期变化）。"
        ),
        (
            "步骤 3 / 中间流程：按目标描述的顺序推进，每个动作都 snap 验证，"
            "失败时用 filter({ hasText }) / 父级容器链式定位缩小范围后再重试。"
        ),
        (
            "步骤 4 / 关键表单 / 提交：填写目标涉及的关键字段并提交，"
            "记录成功提示、跳转或列表更新（完成判据：出现成功 Toast 或跳到详情/列表）。"
        ),
        (
            "步骤 5 / 终点确认：到达目标终点后，记录核心元素的稳健定位器"
            "（优先 getByRole / getByLabel / getByTestId，回退到 filter({hasText}) 链式），"
            "并在 merge_page_artifact_tool 中沉淀为 state tree。"
        ),
    ]


async def _execute_exploration_async(
    model,
    project_id: str,
    run_id: str,
    start_url: str,
    exploration_mode: str,
    max_pages: int,
    scope: str = "",
    goal: str = "",
    storage_state_path: Path | None = None,
) -> None:
    """异步执行探索"""
    from app.agents.page_exploration.agent import page_exploration_agent
    from app.agents.page_exploration.tools.runtime_context import browser_session_context

    _ensure_exploration_not_stopping(run_id)

    agent = page_exploration_agent(model, max_actions=max(40, min(int(max_pages or 80) * 6, 200)))
    _event_bus().publish(
        run_id,
        "planning_completed",
        {
            "plan_id": f"{run_id}-plan",
            "goal_summary": goal or f"{_exploration_mode_label(exploration_mode)}：探索 {start_url}",
            "scope_summary": scope or start_url,
            "strategy": (
                "围绕明确探索目标执行页面流程，并在目标完成或阻塞后停止。"
                if exploration_mode == "goal"
                else "按探索范围自动盘点主要模块、页面入口和可测元素。"
            ),
            "modules": [scope or "主探索模块"],
            "estimated_duration_minutes": None,
            "risk_assessment": "",
            "success_criteria": [
                goal or f"最多探索 {max_pages} 个页面，并记录页面事实与关键操作。"
            ],
            "total_steps": 0,
            "steps": [],
        },
    )

    payload = {
        "messages": [
            {
                "role": "user",
                "content": _exploration_agent_prompt(
                    start_url,
                    exploration_mode,
                    scope,
                    max_pages,
                    goal=goal,
                ),
            }
        ]
    }
    with browser_session_context(start_url=start_url, storage_state_path=storage_state_path):
        await _service_attr("_invoke_agent_with_realtime_events", _invoke_agent_with_realtime_events)(
            agent,
            payload,
            run_id,
            project_id=project_id,
            max_pages=max_pages,
        )
    _ensure_exploration_not_stopping(run_id)

    artifact_summary = _register_exploration_outputs(
        project_id=project_id,
        run_id=run_id,
        start_url=start_url,
        scope=scope,
        exploration_mode=exploration_mode,
        max_pages=max_pages,
        goal=goal,
    )
    _ensure_exploration_not_stopping(run_id)
    run_dir = _project_file_storage_root() / project_id / "page_exploration" / "runs" / run_id
    completion_status = _exploration_completion_status(_read_timeline_events_from_run_dir(run_dir))

    with _connect() as db:
        run = _exploration_run_repo().find_by_id(db, run_id)
        if run and run["status"] in {"stopping", "cancelled"}:
            raise ExplorationCancelledError("用户已停止探索任务。")
        _exploration_run_repo().update_status(
            db,
            run_id,
            completion_status,
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_summary=artifact_summary,
        )
    terminal_event_type = "run_completed" if completion_status == "completed" else "run_failed"
    _publish_run_terminal_event(
        project_id,
        run_id,
        terminal_event_type,
        {
            "status": completion_status,
            "result_summary": artifact_summary,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


async def _invoke_agent_with_realtime_events(
    agent,
    payload: dict,
    run_id: str,
    *,
    project_id: str = "",
    max_pages: int = 50,
):
    timeline_log = _ExplorationEventLog(project_id=project_id, run_id=run_id, filename="timeline_events.jsonl")
    raw_log = _ExplorationEventLog(project_id=project_id, run_id=run_id, filename="raw_events.jsonl")
    timeline_log.ensure_exists()
    config = _agent_recursion_config(max_pages)
    result = await _service_attr("_astream_agent_with_timeline_events", _astream_agent_with_timeline_events)(
        agent,
        payload,
        run_id,
        config,
        timeline_log=timeline_log,
        raw_log=raw_log,
        project_id=project_id,
    )
    _ensure_exploration_not_stopping(run_id)
    return result


async def _astream_agent_with_timeline_events(
    agent,
    payload: dict,
    run_id: str,
    config: dict,
    *,
    timeline_log: _ExplorationEventLog,
    raw_log: _ExplorationEventLog,
    project_id: str,
) -> dict:
    if not hasattr(agent, "astream"):
        raise TypeError("页面探索 Agent 必须支持 projection stream: astream(..., stream_mode=[...])")
    final_result: dict | None = None
    tool_inputs: dict[str, dict] = {}
    seen_projection_keys: set[str] = set()
    page_transition_state: dict[str, str | dict] = {}
    async for chunk in agent.astream(payload, config=config, stream_mode=["updates", "messages", "values"]):
        _ensure_exploration_not_stopping(run_id)
        mode, data = _stream_chunk_parts(chunk)
        raw_event = raw_log.append(
            "agent_projection_event",
            {
                "mode": mode or "unknown",
                "data": _compact_event_payload(data),
            },
        )
        for readable_event in _projection_chunk_to_timeline_events(
            mode,
            data,
            raw_event_id=raw_event.get("event_id"),
            tool_inputs=tool_inputs,
            seen_projection_keys=seen_projection_keys,
            project_id=project_id,
            run_id=run_id,
        ):
            display = readable_event.get("display")
            persisted_event = timeline_log.append(
                readable_event["type"],
                readable_event["payload"],
                display=display,
            )
            _event_bus().publish(
                run_id,
                readable_event["type"],
                readable_event["payload"],
                display=display,
                timeline_event_id=persisted_event.get("event_id"),
            )
            snapshot_event = readable_event.get("snapshot_event")
            if isinstance(snapshot_event, dict):
                _checkpoint_snapshot_artifact_from_event(snapshot_event, project_id=project_id, run_id=run_id)
                _record_page_transition_from_snapshot(
                    snapshot_event,
                    project_id=project_id,
                    run_id=run_id,
                    state=page_transition_state,
                )
            _remember_page_transition_action(readable_event, page_transition_state)
        if mode == "values" and isinstance(data, dict):
            final_result = data
    return final_result or {}


def _remember_page_transition_action(readable_event: dict, state: dict) -> None:
    payload = readable_event.get("payload") if isinstance(readable_event.get("payload"), dict) else {}
    if readable_event.get("type") != "agent_tool_completed":
        return
    if payload.get("tool_name") != "playwright_click_tool":
        return
    locator = _string(payload.get("locator"))
    state["last_action"] = {
        "action": "click",
        "locator": locator,
        "element_name": _element_name_from_locator(locator),
    }


def _record_page_transition_from_snapshot(
    snapshot_event: dict,
    *,
    project_id: str,
    run_id: str,
    state: dict,
) -> None:
    data = snapshot_event.get("data") if isinstance(snapshot_event.get("data"), dict) else {}
    output = data.get("output") if isinstance(data.get("output"), dict) else {}
    url = _string(output.get("url"))
    if not url:
        return
    current_page_id, current_path = _page_identity_from_url(url)
    previous_page_id = _string(state.get("last_page_id"))
    previous_url = _string(state.get("last_url"))
    last_action = state.get("last_action") if isinstance(state.get("last_action"), dict) else {}

    if previous_page_id and previous_page_id != current_page_id and last_action:
        _append_project_page_edge(
            project_id=project_id,
            run_id=run_id,
            from_page_id=previous_page_id,
            to_page_id=current_page_id,
            action=_string(last_action.get("action")) or "click",
            element_name=_string(last_action.get("element_name")),
            locator=_string(last_action.get("locator")),
            from_url=previous_url,
            to_url=url,
        )
        state["last_action"] = {}
    elif previous_page_id == current_page_id and last_action:
        state["last_action"] = {}

    state["last_page_id"] = current_page_id
    state["last_url"] = current_path


def _stream_chunk_parts(chunk) -> tuple[str | None, object]:
    if isinstance(chunk, tuple):
        if len(chunk) == 2 and isinstance(chunk[0], str):
            return chunk[0], chunk[1]
        if len(chunk) == 3 and isinstance(chunk[1], str):
            return chunk[1], chunk[2]
    return None, chunk


def _project_id_from_run(run) -> str:
    if not run:
        return ""
    if isinstance(run, dict):
        return _string(run.get("project_id"))
    try:
        return _string(run["project_id"])
    except (KeyError, TypeError):
        return ""


def _agent_recursion_config(max_pages: int) -> dict:
    try:
        page_budget = int(max_pages or 0)
    except (TypeError, ValueError):
        page_budget = 0
    return {"recursion_limit": max(100, page_budget * 8)}
