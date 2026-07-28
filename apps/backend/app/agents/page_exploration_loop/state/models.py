from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


FrontierStatus = Literal["pending", "executing", "verified", "blocked", "failed"]


def make_state_key(
    *,
    url: str,
    title: str = "",
    element_keys: list[str] | None = None,
    overlay_signature: str = "",
    selection_signature: str = "",
) -> str:
    """Create a stable state identity without transient browser ids."""
    payload = {
        "url": (url or "").strip(),
        "title": (title or "").strip(),
        "elements": sorted(set(element_keys or [])),
        "overlay": (overlay_signature or "").strip(),
        "selection": (selection_signature or "").strip(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"state-{hashlib.sha256(encoded.encode('utf-8')).hexdigest()[:20]}"


@dataclass
class FrontierItem:
    state_key: str
    page_key: str
    element_key: str = ""
    action_type: str = "click"
    priority: float = 0.0
    retry_count: int = 0
    status: FrontierStatus = "pending"
    source_transition_id: str = ""

    @property
    def identity(self) -> str:
        return "|".join((self.state_key, self.element_key, self.action_type))


@dataclass
class LoopExplorationState:
    run_id: str
    project_id: str
    start_url: str
    scope: str = ""
    forbidden_paths: list[str] = field(default_factory=list)
    current_state_key: str = ""
    frontier: list[FrontierItem] = field(default_factory=list)
    visited_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    discovered_pages: dict[str, dict[str, Any]] = field(default_factory=dict)
    discovered_elements: dict[str, dict[str, Any]] = field(default_factory=dict)
    transitions: list[dict[str, Any]] = field(default_factory=list)
    pending_verifications: list[str] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    created_test_data: list[dict[str, Any]] = field(default_factory=list)
    cleanup_results: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=lambda: {"actions": 0, "pages": 0, "states": 0})
    budget: dict[str, int] = field(default_factory=lambda: {"max_pages": 50, "max_actions": 1000})
    stop_reason: str = ""

    def enqueue(self, item: FrontierItem) -> bool:
        if any(existing.identity == item.identity for existing in self.frontier):
            return False
        if item.identity in {str(t.get("frontier_identity")) for t in self.transitions}:
            return False
        self.frontier.append(item)
        return True

    def select_next(self) -> FrontierItem | None:
        pending = [item for item in self.frontier if item.status == "pending"]
        if not pending:
            return None
        selected = max(pending, key=lambda item: (item.priority, item.retry_count * -1, item.identity))
        selected.status = "executing"
        return selected

    def finish_frontier(self, item: FrontierItem, status: FrontierStatus) -> None:
        item.status = status

    def can_continue(self) -> bool:
        if self.stop_reason:
            return False
        if self.counters.get("actions", 0) >= self.budget.get("max_actions", 1000):
            self.stop_reason = "budget_exhausted"
            return False
        return any(item.status == "pending" for item in self.frontier)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["frontier"] = [asdict(item) for item in self.frontier]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LoopExplorationState":
        values = dict(payload)
        values["frontier"] = [
            FrontierItem(**item) for item in values.get("frontier", []) if isinstance(item, dict)
        ]
        return cls(**{key: value for key, value in values.items() if key in cls.__dataclass_fields__})
