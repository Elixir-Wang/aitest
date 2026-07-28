from __future__ import annotations

from typing import Any

from app.agents.page_exploration_loop.state.models import LoopExplorationState


def record_transition(
    state: LoopExplorationState,
    *,
    frontier_identity: str,
    payload: dict[str, Any],
) -> None:
    state.transitions.append({"frontier_identity": frontier_identity, **payload})
    state.counters["actions"] = state.counters.get("actions", 0) + 1


def discover_page(state: LoopExplorationState, page_key: str, payload: dict[str, Any]) -> bool:
    if page_key in state.discovered_pages:
        state.discovered_pages[page_key].update(payload)
        return False
    state.discovered_pages[page_key] = {"page_key": page_key, **payload}
    state.counters["pages"] = len(state.discovered_pages)
    return True


def discover_state(state: LoopExplorationState, state_key: str, payload: dict[str, Any]) -> bool:
    if state_key in state.visited_states:
        state.visited_states[state_key].update(payload)
        return False
    state.visited_states[state_key] = {"state_key": state_key, **payload}
    state.counters["states"] = len(state.visited_states)
    return True

