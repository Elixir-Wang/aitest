"""validation: triggered_by 解析, from_state == parent, depth 护栏。"""
from __future__ import annotations

from dataclasses import dataclass

from app.agents.page_exploration.schemas import PageArtifact, State, Element
from app.services.page_exploration.page_artifact_writer import (
    NewStateObservation,
)


@dataclass
class ValidationIssue:
    code: str
    message: str
    rejected_state_title: str | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue]

    @property
    def ok(self) -> bool:
        return not self.issues


class PageArtifactValidator:
    MAX_DEPTH = 16

    def compute_depth(self, obs: NewStateObservation, parent_depth: int | None) -> int:
        if obs.state_type == "root":
            return 1
        return (parent_depth or 0) + 1

    def validate_observation(
        self,
        obs: NewStateObservation,
        existing_tree: PageArtifact | None,
        parent_depth: int | None,
    ) -> ValidationResult:
        issues: list[ValidationIssue] = []

        # depth 护栏
        depth = self.compute_depth(obs, parent_depth)
        if depth > self.MAX_DEPTH:
            issues.append(ValidationIssue(
                code="depth_exceeds_safety_limit",
                message=f"depth {depth} > max {self.MAX_DEPTH}",
                rejected_state_title=obs.title,
            ))
            return ValidationResult(issues)

        # root: 不需要 triggered_by 也不需要 from_state 校验
        if obs.state_type == "root":
            if obs.triggered_by is not None:
                issues.append(ValidationIssue(
                    code="root_must_have_no_triggered_by",
                    message="root state should not have triggered_by",
                    rejected_state_title=obs.title,
                ))
            return ValidationResult(issues)

        # 非 root: 必须有 triggered_by
        if obs.triggered_by is None:
            issues.append(ValidationIssue(
                code="missing_triggered_by",
                message="non-root state requires triggered_by",
                rejected_state_title=obs.title,
            ))
            return ValidationResult(issues)

        # from_state 必须可解析
        tb = obs.triggered_by
        parent_state = self._find_state_by_id(existing_tree, tb.from_state) if existing_tree else None
        if parent_state is None:
            issues.append(ValidationIssue(
                code="triggered_by_from_state_unresolved",
                message=f"from_state '{tb.from_state}' not found in tree",
                rejected_state_title=obs.title,
            ))
            return ValidationResult(issues)

        # from_state 必须等于直接父
        if obs.parent_state_id != tb.from_state:
            issues.append(ValidationIssue(
                code="triggered_by_from_state_not_parent",
                message=(f"triggered_by.from_state '{tb.from_state}' != parent_state_id "
                         f"'{obs.parent_state_id}' (cross-level not allowed)"),
                rejected_state_title=obs.title,
            ))

        # element_key 必须可在 from_state.elements 中找到
        ekeys = {e.key for e in parent_state.elements}
        if tb.element_key not in ekeys:
            issues.append(ValidationIssue(
                code="triggered_by_element_key_unresolved",
                message=f"element_key '{tb.element_key}' not in parent_state.elements",
                rejected_state_title=obs.title,
            ))

        return ValidationResult(issues)

    def _find_state_by_id(self, tree: PageArtifact | None, sid: str) -> State | None:
        if tree is None:
            return None
        return _walk(tree.states, sid)


def _walk(states: list, sid: str) -> State | None:
    for s in states:
        if s.id == sid:
            return s
        nested = _walk(s.children, sid)
        if nested is not None:
            return nested
    return None
