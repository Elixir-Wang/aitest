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
from app.agents.page_exploration_loop.services.checkpoint import save_checkpoint
from app.agents.page_exploration_loop.services.frontier import enqueue_candidates
from app.agents.page_exploration_loop.services.verifier import verify_action
from app.agents.page_exploration_loop.state.models import FrontierItem, LoopExplorationState, make_state_key
from app.agents.page_exploration_loop.state.reducer import discover_page, discover_state, record_transition
from app.services.page_exploration.event_bus import publish
from app.services.page_exploration.event_log import _ExplorationEventLog
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
) -> LoopExplorationState:
    """Run a bounded observe/decide/execute/verify loop in the active browser context."""
    run_dir = storage_root / project_id / "page_exploration" / "runs" / run_id
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

    snapshot = snapshot_with_runtime_context(start_url)
    _persist_snapshot_artifact(snapshot, project_id=project_id, run_id=run_id)
    _ingest_snapshot(state, snapshot)
    _enqueue_snapshot_candidates(state, snapshot)
    _persist(state, run_dir, timeline, "loop_initialized", {"url": snapshot.url})

    while state.can_continue() and asyncio.get_running_loop().time() < deadline:
        item = state.select_next()
        if item is None:
            break
        target = state.visited_states.get(item.state_key, {})
        target_url = str(target.get("url") or "")
        if target_url and target_url != snapshot.url:
            if _is_forbidden(target_url, state.forbidden_paths):
                state.finish_frontier(item, "blocked")
                state.failures.append({"type": "forbidden_path", "url": target_url, "element_key": item.element_key})
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
            continue

        decision = await _decide(decider, state, snapshot, candidate)
        _persist(state, run_dir, timeline, "action_decided", decision)
        if item.element_key and str(decision.get("element_key") or item.element_key) != item.element_key:
            item.retry_count += 1
            item.status = "failed" if item.retry_count > 2 else "pending"
            state.failures.append({"type": "invalid_decision", "expected": item.element_key, "actual": decision.get("element_key")})
            continue
        if decision.get("action_type") in {"skip", "finish_state"}:
            state.finish_frontier(item, "verified")
            record_transition(state, frontier_identity=item.identity, payload={"decision": decision, "verification": {"status": "verified"}})
            continue
        if decision.get("action_type") == "request_human" or decision.get("risk_level") in {"high", "destructive"}:
            state.finish_frontier(item, "blocked")
            state.failures.append({"type": "human_confirmation_required", "element_key": item.element_key})
            _persist(state, run_dir, timeline, "loop_blocked", {"reason": "human_confirmation_required", "element_key": item.element_key})
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
        state.finish_frontier(item, verification.status if verification.status in {"verified", "blocked", "failed"} else "failed")
        if verification.status == "no_effect" and item.retry_count < 2:
            item.retry_count += 1
            item.status = "pending"
        snapshot = after_snapshot
        _ingest_snapshot(state, snapshot)
        _enqueue_snapshot_candidates(state, snapshot)
        _persist(state, run_dir, timeline, "action_verified", verification.model_dump())

    if not state.stop_reason:
        state.stop_reason = "timeout" if asyncio.get_running_loop().time() >= deadline else "frontier_exhausted"
    _persist(state, run_dir, timeline, "loop_finished", {"stop_reason": state.stop_reason, "summary": _summary(state)})
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
    for element in snapshot.elements:
        key = build_element_key({"role": element.role, "name": element.name, "text": element.text})
        if key:
            state.discovered_elements.setdefault(key, {"element_key": key, "role": element.role, "name": element.name, "action_type": element.action_type or "click"})
    state_key = str(snapshot.state_signature or make_state_key(url=snapshot.url, title=snapshot.title, element_keys=element_keys, overlay_signature=json.dumps(snapshot.overlay or {}, sort_keys=True)))
    page_key = make_page_id(urlparse(snapshot.url).path or "/")
    is_new_page = discover_page(state, page_key, {"url": snapshot.url, "title": snapshot.title, "state_key": state_key})
    if is_new_page and len(state.discovered_pages) > state.budget.get("max_pages", 50):
        state.stop_reason = "page_budget_exhausted"
    discover_state(state, state_key, {"url": snapshot.url, "title": snapshot.title, "page_key": page_key})
    state.current_state_key = state_key
    return state_key


def _enqueue_snapshot_candidates(state: LoopExplorationState, snapshot) -> None:
    state_key = _ingest_snapshot(state, snapshot)
    page_key = make_page_id(urlparse(snapshot.url).path or "/")
    enqueue_candidates(state, state_key=state_key, page_key=page_key, candidates=[_candidate_from_element(element) for element in snapshot.elements])


def _candidate_from_element(element) -> dict[str, Any]:
    return {"element_key": build_element_key({"role": element.role, "name": element.name, "text": element.text}), "element_id": element.element_id, "role": element.role, "name": element.name, "text": element.text, "action_type": element.action_type or "click", "risk_level": "low"}


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


def _persist(state: LoopExplorationState, run_dir: Path, timeline: _ExplorationEventLog, event_type: str, payload: dict[str, Any]) -> None:
    save_checkpoint(run_dir, state)
    event = timeline.append(event_type, payload)
    publish(state.run_id, event_type, payload, timeline_event_id=event.get("event_id"))


def _summary(state: LoopExplorationState) -> dict[str, Any]:
    return {"pages": len(state.discovered_pages), "states": len(state.visited_states), "actions": state.counters.get("actions", 0), "pending": sum(item.status == "pending" for item in state.frontier), "failures": len(state.failures)}


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
