"""Coverage state for first-time full page exploration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def element_key(element: dict[str, Any]) -> str:
    """Build a stable key without depending on ephemeral observation ids."""
    stable = str(element.get("stable_key") or "").strip()
    if stable:
        return stable
    role = str(element.get("role") or "generic").strip()
    name = str(element.get("name") or element.get("label") or "").strip()
    context = str(element.get("semantic_context") or element.get("context") or "").strip()
    return "|".join((role, name, context))


@dataclass
class CoverageState:
    """Tracks every discovered element and its execution result."""

    elements: dict[str, dict[str, Any]] = field(default_factory=dict)
    states: dict[str, dict[str, Any]] = field(default_factory=dict)
    created_test_data: list[dict[str, Any]] = field(default_factory=list)
    cleanup_results: list[dict[str, Any]] = field(default_factory=list)

    def discover_elements(self, discovered: list[dict[str, Any]]) -> list[str]:
        new_keys: list[str] = []
        for item in discovered:
            key = element_key(item)
            if not key:
                continue
            existing = self.elements.get(key)
            if existing is None:
                self.elements[key] = {**item, "stable_key": key, "status": "pending"}
                new_keys.append(key)
            else:
                existing.update({k: v for k, v in item.items() if v not in (None, "")})
        return new_keys

    def discover_state(self, state_signature: str, facts: dict[str, Any] | None = None) -> None:
        if not state_signature:
            return
        self.states.setdefault(state_signature, {"state_signature": state_signature, **(facts or {})})

    def next_pending(self) -> dict[str, Any] | None:
        return next((item for item in self.elements.values() if item.get("status") == "pending"), None)

    def mark_executing(self, key: str) -> None:
        self._require(key)["status"] = "executing"

    def mark_verified(self, key: str, result: dict[str, Any] | None = None) -> None:
        item = self._require(key)
        item["status"] = "verified"
        if result:
            item["result"] = result

    def mark_failed(self, key: str, error: str) -> None:
        item = self._require(key)
        item["status"] = "failed"
        item["error"] = error

    def record_test_data(self, record: dict[str, Any]) -> None:
        self.created_test_data.append(record)

    def record_cleanup(self, record: dict[str, Any]) -> None:
        self.cleanup_results.append(record)

    @property
    def pending_count(self) -> int:
        return sum(item.get("status") in {"pending", "executing"} for item in self.elements.values())

    @property
    def verified_count(self) -> int:
        return sum(item.get("status") == "verified" for item in self.elements.values())

    @property
    def complete(self) -> bool:
        return bool(self.elements) and self.pending_count == 0 and all(
            item.get("status") in {"verified", "failed"} for item in self.elements.values()
        ) and len(self.cleanup_results) >= len(self.created_test_data)

    def summary(self) -> dict[str, int | bool]:
        counts: dict[str, int] = {}
        for item in self.elements.values():
            status = str(item.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {
            "discovered": len(self.elements),
            "verified": self.verified_count,
            "pending": self.pending_count,
            "states": len(self.states),
            "created_test_data": len(self.created_test_data),
            "cleanup_results": len(self.cleanup_results),
            "complete": self.complete,
            **{f"status_{key}": value for key, value in counts.items()},
        }

    def _require(self, key: str) -> dict[str, Any]:
        if key not in self.elements:
            raise KeyError(f"未知探索元素: {key}")
        return self.elements[key]
