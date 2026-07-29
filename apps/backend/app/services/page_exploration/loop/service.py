"""Runtime for the explicit frontier-driven Loop exploration mode."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.agents.page_exploration.tools.runtime_context import (
    click_with_runtime_context,
    fill_with_runtime_context,
    navigate_with_runtime_context,
    snapshot_with_runtime_context,
)
from app.agents.page_exploration.utils.element_key import build_element_key
from app.agents.page_exploration.utils.page_id import make_page_id
from app.agents.page_exploration_loop.agent import loop_action_decider
from app.agents.page_exploration_loop.services.checkpoint import load_checkpoint, save_checkpoint
from app.agents.page_exploration_loop.services.frontier import enqueue_candidates
from app.agents.page_exploration_loop.services.verifier import verify_action
from app.agents.page_exploration_loop.state.models import FrontierItem, LoopExplorationState, make_state_key
from app.agents.page_exploration_loop.state.reducer import discover_page, discover_state, record_transition
from app.services.page_exploration.event_bus import publish
from app.services.page_exploration.event_log import _ExplorationEventLog
from app.services.page_exploration.event_payload import _status_display
from app.services.page_exploration.coverage_registry import (
    is_action_completed,
    is_collection_group_completed,
    is_page_complete,
    load_coverage,
    update_coverage,
)
from app.services.page_exploration.collection_groups import group_collection_items
from app.services.page_exploration.output_registry import _checkpoint_snapshot_artifact_from_event


async def execute_loop_exploration(
    *,
    model,
    project_id: str,
    run_id: str,
    start_url: str,
    scope: str = "",
    forbidden_paths: str = "",
    max_pages: int = 50,
    max_actions: int = 1000,
    timeout_minutes: int = 120,
    storage_root: Path,
    force_reexplore: bool = False,
    resume: bool = False,
) -> LoopExplorationState:
    """Run a bounded observe/decide/execute/verify loop in the active browser context."""
    run_dir = storage_root / project_id / "page_exploration" / "runs" / run_id
    if resume:
        state = _load_resume_state(
            run_dir,
            project_id=project_id,
            run_id=run_id,
            start_url=start_url,
            scope=scope,
            forbidden_paths=forbidden_paths,
            max_pages=max_pages,
            max_actions=max_actions,
        )
    else:
        state = LoopExplorationState(
            run_id=run_id,
            project_id=project_id,
            start_url=start_url,
            scope=scope,
            forbidden_paths=[line.strip() for line in forbidden_paths.splitlines() if line.strip()],
            budget={"max_pages": max_pages, "max_actions": max_actions},
        )
    timeline = _ExplorationEventLog(project_id=project_id, run_id=run_id, filename="timeline_events.jsonl")
    timeline.ensure_exists()
    decider = loop_action_decider(model)
    deadline = asyncio.get_running_loop().time() + max(1, timeout_minutes) * 60
    coverage = load_coverage(storage_root, project_id)

    snapshot = snapshot_with_runtime_context(start_url)
    _persist_snapshot_artifact(snapshot, project_id=project_id, run_id=run_id)
    _ingest_snapshot(state, snapshot)
    _enqueue_snapshot_candidates(
        state,
        snapshot,
        coverage=coverage,
        force_reexplore=force_reexplore,
    )
    _persist(
        state,
        run_dir,
        timeline,
        "loop_resumed" if resume else "loop_initialized",
        {"url": snapshot.url, "pending": sum(item.status == "pending" for item in state.frontier)},
    )
    _publish_loop_plan(state, run_dir, timeline)

    while state.can_continue() and asyncio.get_running_loop().time() < deadline:
        item = state.select_next()
        if item is None:
            break
        _persist(
            state,
            run_dir,
            timeline,
            "step_started",
            _loop_step_payload(state, item, status="running"),
        )
        target = state.visited_states.get(item.state_key, {})
        target_url = str(target.get("url") or "")
        if target_url and target_url != snapshot.url:
            if _is_forbidden(target_url, state.forbidden_paths):
                state.finish_frontier(item, "blocked")
                state.failures.append({"type": "forbidden_path", "url": target_url, "element_key": item.element_key})
                _persist(state, run_dir, timeline, "loop_blocked", {"reason": "forbidden_path", "element_key": item.element_key})
                _persist(
                    state,
                    run_dir,
                    timeline,
                    "step_blocked",
                    _loop_step_payload(state, item, status="blocked", message="目标路径在禁止范围内"),
                )
                _publish_loop_plan(state, run_dir, timeline)
                continue
            navigate_with_runtime_context(target_url)
            snapshot = snapshot_with_runtime_context()
            _persist_snapshot_artifact(snapshot, project_id=project_id, run_id=run_id)
        _ingest_snapshot(state, snapshot)
        candidate = _candidate_from_snapshot(snapshot, item.element_key)
        if item.element_key and candidate is None:
            state.finish_frontier(item, "blocked")
            state.failures.append({"type": "stale_candidate", "element_key": item.element_key, "state_key": item.state_key})
            _persist(state, run_dir, timeline, "loop_blocked", {"reason": "stale_candidate", "element_key": item.element_key})
            _persist(
                state,
                run_dir,
                timeline,
                "step_blocked",
                _loop_step_payload(state, item, status="blocked", message="页面已变化，候选元素失效"),
            )
            _publish_loop_plan(state, run_dir, timeline)
            continue

        decision = await _decide(decider, state, snapshot, candidate)
        _persist(state, run_dir, timeline, "action_decided", decision)
        if item.element_key and str(decision.get("element_key") or item.element_key) != item.element_key:
            item.retry_count += 1
            item.status = "failed" if item.retry_count > 2 else "pending"
            state.failures.append({"type": "invalid_decision", "expected": item.element_key, "actual": decision.get("element_key")})
            _persist(
                state,
                run_dir,
                timeline,
                "step_failed" if item.status == "failed" else "step_retrying",
                _loop_step_payload(
                    state,
                    item,
                    status="failed" if item.status == "failed" else "pending",
                    message="模型返回的元素与当前候选不一致",
                ),
            )
            _publish_loop_plan(state, run_dir, timeline)
            continue
        if decision.get("action_type") in {"skip", "finish_state"}:
            state.finish_frontier(item, "verified")
            record_transition(state, frontier_identity=item.identity, payload={"decision": decision, "verification": {"status": "verified"}})
            _persist(
                state,
                run_dir,
                timeline,
                "step_skipped",
                _loop_step_payload(
                    state,
                    item,
                    status="failed",
                    message=str(decision.get("reason") or decision.get("action_type") or "已跳过"),
                ),
            )
            _publish_loop_plan(state, run_dir, timeline)
            continue
        if decision.get("action_type") == "request_human" or decision.get("risk_level") in {"high", "destructive"}:
            state.finish_frontier(item, "blocked")
            state.failures.append({"type": "human_confirmation_required", "element_key": item.element_key})
            _persist(state, run_dir, timeline, "loop_blocked", {"reason": "human_confirmation_required", "element_key": item.element_key})
            _persist(
                state,
                run_dir,
                timeline,
                "step_blocked",
                _loop_step_payload(state, item, status="blocked", message="高风险动作需要人工确认"),
            )
            _publish_loop_plan(state, run_dir, timeline)
            continue

        before_state = str(snapshot.state_signature or item.state_key)
        action_result = _execute_decision(decision, candidate)
        after_snapshot = snapshot_with_runtime_context()
        _persist_snapshot_artifact(after_snapshot, project_id=project_id, run_id=run_id)
        verification = verify_action(
            before_state=before_state,
            after_observation=_snapshot_payload(after_snapshot),
            expected_effect=str(decision.get("expected_effect") or ""),
            action_success=bool(action_result.get("success")),
        )
        record_transition(
            state,
            frontier_identity=item.identity,
            payload={
                "decision": decision,
                "action_result": action_result,
                "verification": verification.model_dump(),
                "before_state": before_state,
                "after_state": after_snapshot.state_signature,
            },
        )
        if verification.status == "verified":
            _persist_verified_action_coverage(
                state,
                item=item,
                action=str(decision.get("action_type") or item.action_type),
                after_state=str(after_snapshot.state_signature or ""),
                storage_root=storage_root,
            )
            coverage = load_coverage(storage_root, project_id)
        state.finish_frontier(item, verification.status if verification.status in {"verified", "blocked", "failed"} else "failed")
        if verification.status == "no_effect" and item.retry_count < 2:
            item.retry_count += 1
            item.status = "pending"
        snapshot = after_snapshot
        _ingest_snapshot(state, snapshot)
        _enqueue_snapshot_candidates(
            state,
            snapshot,
            coverage=coverage,
            force_reexplore=force_reexplore,
        )
        _persist(state, run_dir, timeline, "action_verified", verification.model_dump())
        _persist(
            state,
            run_dir,
            timeline,
            "step_completed" if verification.status == "verified" else "step_failed",
            _loop_step_payload(
                state,
                item,
                status="completed" if verification.status == "verified" else "failed",
                message=str(verification.model_dump().get("message") or verification.status),
            ),
        )
        _publish_loop_plan(state, run_dir, timeline)

    if not state.stop_reason:
        state.stop_reason = "timeout" if asyncio.get_running_loop().time() >= deadline else "frontier_exhausted"
    _update_loop_coverage(state, storage_root=storage_root)
    _persist(state, run_dir, timeline, "loop_finished", {"stop_reason": state.stop_reason, "summary": _summary(state)})
    return state


def _load_resume_state(
    run_dir: Path,
    *,
    project_id: str,
    run_id: str,
    start_url: str,
    scope: str,
    forbidden_paths: str,
    max_pages: int,
    max_actions: int,
) -> LoopExplorationState:
    state = load_checkpoint(run_dir)
    if state is None:
        raise ValueError(f"未找到可续跑的 Loop 检查点: {run_id}")
    if state.project_id != project_id or state.run_id != run_id or state.start_url.strip() != start_url.strip():
        raise ValueError("Loop 检查点与当前项目、任务或起始 URL 不匹配")
    for item in state.frontier:
        if item.status == "executing":
            item.status = "pending"
    state.scope = scope
    state.forbidden_paths = [line.strip() for line in forbidden_paths.splitlines() if line.strip()]
    state.budget = {"max_pages": max_pages, "max_actions": max_actions}
    state.stop_reason = ""
    return state


async def _decide(decider, state: LoopExplorationState, snapshot, candidate: dict[str, Any] | None) -> dict[str, Any]:
    candidates = [_candidate_from_element(element) for element in snapshot.elements]
    content = {
        "current_page": {"url": snapshot.url, "title": snapshot.title, "state_signature": snapshot.state_signature, "summary": snapshot.page_text_summary},
        "scope": state.scope,
        "candidate_to_execute": candidate,
        "candidates": candidates,
        "visited_state_count": len(state.visited_states),
        "pending_count": sum(item.status == "pending" for item in state.frontier),
        "instruction": "从候选中选择一个动作；若当前元素不应执行，返回 skip。不要生成 locator。",
    }
    result = await decider.ainvoke([{"role": "system", "content": "你是页面探索局部动作决策器，只返回结构化 ActionDecision。"}, {"role": "user", "content": json.dumps(content, ensure_ascii=False)}])
    return result.model_dump() if hasattr(result, "model_dump") else dict(result)


def _execute_decision(decision: dict[str, Any], candidate: dict[str, Any] | None) -> dict[str, Any]:
    if not candidate:
        return {"success": False, "error": "缺少候选元素"}
    element_id = str(candidate.get("element_id") or "")
    action_type = str(decision.get("action_type") or "click")
    if action_type == "fill":
        value = str(decision.get("value") or "loop-test-value")
        result = fill_with_runtime_context(element_id, value)
    elif action_type == "navigate":
        result = navigate_with_runtime_context(str(candidate.get("href") or ""))
    else:
        result = click_with_runtime_context(element_id)
    if hasattr(result, "model_dump"):
        return result.model_dump()
    return result if isinstance(result, dict) else {"success": False, "error": "动作返回值无效"}


def _ingest_snapshot(state: LoopExplorationState, snapshot) -> str:
    element_keys = [build_element_key({"role": element.role, "name": element.name, "text": element.text}) for element in snapshot.elements]
    page_key = make_page_id(urlparse(snapshot.url).path or "/")
    collection_groups = _snapshot_collection_group_map(snapshot)
    for element in snapshot.elements:
        key = build_element_key({"role": element.role, "name": element.name, "text": element.text})
        if key:
            context = element.context if isinstance(element.context, dict) else {}
            item_name = str(context.get("collection_item_name") or "").strip()
            collection_key = str(context.get("collection_key") or "").strip()
            group = collection_groups.get((collection_key, item_name), {})
            state.discovered_elements.setdefault(
                key,
                {
                    "element_key": key,
                    "role": element.role,
                    "name": element.name,
                    "action_type": element.action_type or "click",
                    "page_key": page_key,
                    "collection_key": collection_key,
                    "collection_group_key": str(group.get("key") or ""),
                    "collection_representative": str(group.get("representative") or ""),
                    "collection_actions": group.get("actions") if isinstance(group.get("actions"), list) else [],
                },
            )
    state_key = str(snapshot.state_signature or make_state_key(url=snapshot.url, title=snapshot.title, element_keys=element_keys, overlay_signature=json.dumps(snapshot.overlay or {}, sort_keys=True)))
    is_new_page = discover_page(state, page_key, {"url": snapshot.url, "title": snapshot.title, "state_key": state_key})
    if is_new_page and len(state.discovered_pages) > state.budget.get("max_pages", 50):
        state.stop_reason = "page_budget_exhausted"
    discover_state(state, state_key, {"url": snapshot.url, "title": snapshot.title, "page_key": page_key})
    state.current_state_key = state_key
    return state_key


def _enqueue_snapshot_candidates(
    state: LoopExplorationState,
    snapshot,
    *,
    coverage: dict | None = None,
    force_reexplore: bool = False,
) -> None:
    state_key = _ingest_snapshot(state, snapshot)
    page_key = make_page_id(urlparse(snapshot.url).path or "/")
    if not force_reexplore and is_page_complete(coverage or {}, page_key):
        return
    candidates = [_candidate_from_element(element) for element in snapshot.elements]
    candidates = _collection_representative_candidates(
        candidates,
        coverage=coverage or {},
        page_key=page_key,
        force_reexplore=force_reexplore,
    )
    if not force_reexplore:
        candidates = [
            candidate
            for candidate in candidates
            if not is_action_completed(
                coverage or {},
                page_key,
                str(candidate.get("element_key") or ""),
                str(candidate.get("action_type") or "click"),
            )
        ]
    enqueue_candidates(state, state_key=state_key, page_key=page_key, candidates=candidates)


def _candidate_from_element(element) -> dict[str, Any]:
    context = element.context if isinstance(element.context, dict) else {}
    return {
        "element_key": build_element_key({"role": element.role, "name": element.name, "text": element.text}),
        "element_id": element.element_id,
        "role": element.role,
        "name": element.name,
        "text": element.text,
        "action_type": element.action_type or "click",
        "risk_level": "low",
        "collection_key": str(context.get("collection_key") or "").strip(),
        "collection_item_name": str(context.get("collection_item_name") or "").strip(),
        "collection_item_type": str(context.get("collection_item_type") or "").strip(),
        "collection_item_status": str(context.get("collection_item_status") or "").strip(),
        "collection_actions": context.get("collection_actions") if isinstance(context.get("collection_actions"), list) else [],
    }


def _collection_representative_candidates(
    candidates: list[dict[str, Any]],
    *,
    coverage: dict,
    page_key: str,
    force_reexplore: bool,
) -> list[dict[str, Any]]:
    by_collection: dict[str, list[dict[str, Any]]] = {}
    result = [candidate for candidate in candidates if not candidate.get("collection_key")]
    for candidate in candidates:
        collection_key = str(candidate.get("collection_key") or "").strip()
        if collection_key:
            by_collection.setdefault(collection_key, []).append(candidate)

    for collection_key, collection_candidates in by_collection.items():
        items_by_name: dict[str, dict] = {}
        for candidate in collection_candidates:
            item_name = str(candidate.get("collection_item_name") or "").strip()
            if not item_name:
                result.append(candidate)
                continue
            items_by_name.setdefault(
                item_name,
                {
                    "name": item_name,
                    "type": candidate.get("collection_item_type"),
                    "status": candidate.get("collection_item_status"),
                    "actions": candidate.get("collection_actions"),
                },
            )
        selected_names = {
            str(group.get("representative") or "").strip()
            for group in group_collection_items(list(items_by_name.values()))
            if force_reexplore
            or not is_collection_group_completed(
                coverage,
                page_key,
                collection_key,
                str(group.get("key") or ""),
            )
        }
        result.extend(
            candidate
            for candidate in collection_candidates
            if str(candidate.get("collection_item_name") or "").strip() in selected_names
        )
    return result


def _snapshot_collection_group_map(snapshot) -> dict[tuple[str, str], dict]:
    items_by_collection: dict[str, dict[str, dict]] = {}
    for element in snapshot.elements:
        context = element.context if isinstance(element.context, dict) else {}
        collection_key = str(context.get("collection_key") or "").strip()
        item_name = str(context.get("collection_item_name") or "").strip()
        if not collection_key or not item_name:
            continue
        items_by_collection.setdefault(collection_key, {}).setdefault(
            item_name,
            {
                "name": item_name,
                "type": context.get("collection_item_type"),
                "status": context.get("collection_item_status"),
                "actions": context.get("collection_actions"),
            },
        )
    result: dict[tuple[str, str], dict] = {}
    for collection_key, items in items_by_collection.items():
        for group in group_collection_items(list(items.values())):
            representative = str(group.get("representative") or "").strip()
            if representative:
                result[(collection_key, representative)] = group
    return result


def _candidate_from_snapshot(snapshot, element_key: str) -> dict[str, Any] | None:
    if not element_key:
        return None
    for element in snapshot.elements:
        candidate = _candidate_from_element(element)
        if candidate["element_key"] == element_key:
            return candidate
    return None


def _snapshot_payload(snapshot) -> dict[str, Any]:
    return {"url": snapshot.url, "title": snapshot.title, "state_signature": snapshot.state_signature, "page_text_summary": snapshot.page_text_summary, "overlay": snapshot.overlay}


def _is_forbidden(url: str, forbidden_paths: list[str]) -> bool:
    return any(path and path in url for path in forbidden_paths)


def _persist(
    state: LoopExplorationState,
    run_dir: Path,
    timeline: _ExplorationEventLog,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    save_checkpoint(run_dir, state)
    display = _loop_event_display(event_type, payload)
    event = timeline.append(event_type, payload, display=display)
    publish(
        state.run_id,
        event_type,
        payload,
        display=display,
        timeline_event_id=event.get("event_id"),
    )


def _publish_loop_plan(state: LoopExplorationState, run_dir: Path, timeline: _ExplorationEventLog) -> None:
    _persist(
        state,
        run_dir,
        timeline,
        "agent_plan_updated",
        {
            "strategy": "Loop 探索",
            "total_steps": len(state.frontier),
            "plan_steps": [
                _loop_step_payload(state, item, status=_plan_status(item.status))
                for item in state.frontier
            ],
        },
    )


def _loop_step_payload(
    state: LoopExplorationState,
    item,
    *,
    status: str,
    message: str = "",
) -> dict[str, Any]:
    element = state.discovered_elements.get(item.element_key, {})
    name = str(element.get("name") or item.element_key)
    action_type = str(item.action_type or element.get("action_type") or "click")
    description = f"{action_type}：{name}"
    return {
        "step_id": item.identity,
        "step_number": state.frontier.index(item) + 1,
        "module_name": str(element.get("page_key") or item.page_key),
        "action_type": action_type,
        "description": description,
        "target_description": name,
        "expected_result": message,
        "status": status,
        "message": message,
    }


def _plan_status(status: str) -> str:
    return {
        "executing": "running",
        "verified": "completed",
        "blocked": "blocked",
        "failed": "failed",
    }.get(status, "pending")


def _loop_event_display(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event_type == "agent_plan_updated":
        return _status_display("thought", "Loop 探索计划", f"当前队列 {len(payload.get('plan_steps') or [])} 个动作")
    if event_type == "step_started":
        return _status_display("tool", "开始执行动作", str(payload.get("description") or "开始执行 Loop 动作"))
    if event_type in {"step_completed", "step_failed", "step_skipped", "step_blocked", "step_retrying"}:
        return _status_display("tool", "动作执行结果", str(payload.get("message") or payload.get("description") or "动作已处理"))
    if event_type == "loop_initialized":
        return _status_display("thought", "Loop 探索", f"已打开页面：{payload.get('url') or '起始页面'}")
    if event_type == "loop_resumed":
        return _status_display("thought", "Loop 继续探索", f"从检查点继续，待执行 {payload.get('pending') or 0} 个动作")
    if event_type == "action_decided":
        return _status_display("thought", "Loop 决策", f"选择执行：{payload.get('action_type') or '动作'}")
    if event_type == "action_verified":
        return _status_display("tool", "Loop 校验", str(payload.get("status") or "已完成校验"))
    if event_type == "loop_blocked":
        return _status_display("tool", "Loop 已阻塞", str(payload.get("reason") or "动作未执行"))
    if event_type == "loop_finished":
        return _status_display("thought", "Loop 探索结束", str(payload.get("stop_reason") or "已结束"))
    return _status_display("thought", "Loop 探索进度", event_type)


def _summary(state: LoopExplorationState) -> dict[str, Any]:
    return {"pages": len(state.discovered_pages), "states": len(state.visited_states), "actions": state.counters.get("actions", 0), "pending": sum(item.status == "pending" for item in state.frontier), "failures": len(state.failures)}


def _update_loop_coverage(state: LoopExplorationState, *, storage_root: Path) -> None:
    states_by_page: dict[str, list[str]] = {}
    for state_key, entry in state.visited_states.items():
        page_key = str(entry.get("page_key") or "").strip()
        if page_key:
            states_by_page.setdefault(page_key, []).append(state_key)

    complete = state.stop_reason == "frontier_exhausted" and not any(
        item.status == "pending" for item in state.frontier
    )
    pages = [
        {
            "page_id": page_key,
            "path": urlparse(str(entry.get("url") or "/")).path or "/",
            "artifact": f"pages/{page_key}.yaml",
            "status": "complete" if complete else "partial",
            "states": sorted(states_by_page.get(page_key, [])),
        }
        for page_key, entry in state.discovered_pages.items()
    ]

    completed_actions: list[dict] = []
    for transition in state.transitions:
        verification = transition.get("verification") if isinstance(transition.get("verification"), dict) else {}
        decision = transition.get("decision") if isinstance(transition.get("decision"), dict) else {}
        action = str(decision.get("action_type") or "").strip()
        if verification.get("status") != "verified" or action in {"", "skip", "finish_state"}:
            continue
        identity = str(transition.get("frontier_identity") or "")
        parts = identity.split("|", 2)
        if len(parts) != 3:
            continue
        state_key, element_key, fallback_action = parts
        page_key = str(state.visited_states.get(state_key, {}).get("page_key") or "").strip()
        if not page_key:
            continue
        completed_actions.append(
            {
                "page_id": page_key,
                "element_key": element_key,
                "action": action or fallback_action,
                "from_state": state_key,
                "to_state": str(transition.get("after_state") or "").strip(),
            }
        )

    update_coverage(
        storage_root,
        state.project_id,
        run_id=state.run_id,
        mode="loop",
        pages=pages,
        completed_actions=completed_actions,
        collection_groups=_collection_group_coverage_updates(state, completed_actions),
    )


def _persist_verified_action_coverage(
    state: LoopExplorationState,
    *,
    item,
    action: str,
    after_state: str,
    storage_root: Path,
) -> None:
    page_key = str(state.visited_states.get(item.state_key, {}).get("page_key") or item.page_key).strip()
    if not page_key or not item.element_key or not action:
        return
    update_coverage(
        storage_root,
        state.project_id,
        run_id=state.run_id,
        mode="loop",
        pages=[],
        completed_actions=[
            {
                "page_id": page_key,
                "element_key": item.element_key,
                "action": action,
                "from_state": item.state_key,
                "to_state": after_state,
            }
        ],
        collection_groups=[],
    )


def _collection_group_coverage_updates(
    state: LoopExplorationState,
    completed_actions: list[dict],
) -> list[dict]:
    completed = {
        (
            str(item.get("page_id") or ""),
            str(item.get("element_key") or ""),
            str(item.get("action") or ""),
        )
        for item in completed_actions
    }
    groups: dict[tuple[str, str, str], dict] = {}
    for element in state.discovered_elements.values():
        if not isinstance(element, dict):
            continue
        page_key = str(element.get("page_key") or "").strip()
        collection_key = str(element.get("collection_key") or "").strip()
        group_key = str(element.get("collection_group_key") or "").strip()
        if not page_key or not collection_key or not group_key:
            continue
        group = groups.setdefault(
            (page_key, collection_key, group_key),
            {
                "page_id": page_key,
                "collection_key": collection_key,
                "group_key": group_key,
                "representative": str(element.get("collection_representative") or "").strip(),
                "required": set(),
            },
        )
        actions = element.get("collection_actions") if isinstance(element.get("collection_actions"), list) else []
        if str(element.get("name") or "") in actions:
            group["required"].add(
                (
                    page_key,
                    str(element.get("element_key") or ""),
                    str(element.get("action_type") or "click"),
                )
            )

    updates: list[dict] = []
    for group in groups.values():
        required = group.pop("required")
        group["status"] = "completed" if required and required.issubset(completed) else "pending"
        updates.append(group)
    return updates


def _persist_snapshot_artifact(snapshot, *, project_id: str, run_id: str) -> None:
    _checkpoint_snapshot_artifact_from_event(
        {
            "event": "on_tool_end",
            "name": "playwright_snap_tool",
            "data": {"output": _snapshot_full_payload(snapshot)},
        },
        project_id=project_id,
        run_id=run_id,
    )


def _snapshot_full_payload(snapshot) -> dict[str, Any]:
    payload = snapshot.model_dump()
    payload["elements"] = [element.model_dump() for element in snapshot.elements]
    payload["accessibility_tree"] = [node.model_dump() for node in snapshot.accessibility_tree]
    return payload
