from __future__ import annotations

from app.agents.page_exploration_loop.state.models import FrontierItem, LoopExplorationState


def priority_for_candidate(candidate: dict) -> float:
    """Deterministic priority; higher values are explored first."""
    action = str(candidate.get("action_type") or "click").lower()
    score = 10.0
    if candidate.get("opens_new_page") or candidate.get("href"):
        score += 40
    if candidate.get("opens_overlay"):
        score += 30
    if action in {"fill", "submit"}:
        score += 20
    if candidate.get("risk_level") in {"high", "destructive"}:
        score -= 50
    if candidate.get("verified"):
        score -= 100
    return score


def enqueue_candidates(
    state: LoopExplorationState,
    *,
    state_key: str,
    page_key: str,
    candidates: list[dict],
) -> int:
    added = 0
    for candidate in candidates:
        element_key = str(candidate.get("element_key") or candidate.get("key") or "").strip()
        if not element_key:
            continue
        item = FrontierItem(
            state_key=state_key,
            page_key=page_key,
            element_key=element_key,
            action_type=str(candidate.get("action_type") or "click"),
            priority=priority_for_candidate(candidate),
        )
        added += int(state.enqueue(item))
    return added

