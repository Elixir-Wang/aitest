from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.agents.page_exploration_loop.services.checkpoint import save_checkpoint
from app.agents.page_exploration_loop.services.frontier import enqueue_candidates
from app.agents.page_exploration_loop.services.verifier import verify_action
from app.agents.page_exploration_loop.state.models import FrontierItem, LoopExplorationState
from app.agents.page_exploration_loop.state.reducer import discover_page, discover_state, record_transition


class LoopOrchestrator:
    """Deterministic frontier loop with injectable browser/model callbacks."""

    def __init__(self, state: LoopExplorationState, *, run_dir=None):
        self.state = state
        self.run_dir = run_dir

    def run(
        self,
        *,
        observe: Callable[[LoopExplorationState, FrontierItem], dict[str, Any]],
        decide: Callable[[LoopExplorationState, FrontierItem, dict[str, Any]], dict[str, Any]],
        execute: Callable[[dict[str, Any]], dict[str, Any]],
        verify: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
        persist: Callable[[LoopExplorationState, dict[str, Any]], None] | None = None,
    ) -> LoopExplorationState:
        while self.state.can_continue():
            item = self.state.select_next()
            if item is None:
                break
            observation = observe(self.state, item) or {}
            state_key = str(observation.get("state_signature") or item.state_key)
            page_key = str(observation.get("page_key") or item.page_key)
            discover_page(self.state, page_key, observation)
            discover_state(self.state, state_key, observation)
            decision = decide(self.state, item, observation) or {"action_type": "skip"}
            candidates = observation.get("candidates") if isinstance(observation.get("candidates"), list) else []
            if decision.get("element_key") and decision["element_key"] not in {
                str(candidate.get("element_key") or candidate.get("key") or "") for candidate in candidates
            }:
                item.retry_count += 1
                self.state.failures.append({"type": "invalid_decision", "element_key": decision.get("element_key")})
                self.state.finish_frontier(item, "failed" if item.retry_count > 2 else "pending")
                continue
            result = execute(decision) or {"success": False, "error": "未返回动作结果"}
            verification = (verify(result, observation) if verify else verify_action(
                before_state=state_key,
                after_observation=result.get("observation"),
                expected_effect=str(decision.get("expected_effect") or ""),
                action_success=bool(result.get("success")),
            ))
            payload = {"decision": decision, "result": result, "verification": verification}
            record_transition(self.state, frontier_identity=item.identity, payload=payload)
            self.state.finish_frontier(item, verification.status if verification.status in {"verified", "blocked", "failed"} else "failed")
            if verification.status == "no_effect" and item.retry_count < 2:
                item.retry_count += 1
                item.status = "pending"
            if isinstance(result.get("candidates"), list):
                enqueue_candidates(self.state, state_key=state_key, page_key=page_key, candidates=result["candidates"])
            if persist:
                persist(self.state, payload)
            if self.run_dir is not None:
                save_checkpoint(self.run_dir, self.state)
        if not self.state.stop_reason and not any(item.status == "pending" for item in self.state.frontier):
            self.state.stop_reason = "frontier_exhausted"
        return self.state

