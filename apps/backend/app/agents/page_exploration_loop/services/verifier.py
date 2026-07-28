from __future__ import annotations

from typing import Any

from app.agents.page_exploration_loop.schemas import VerificationResult


def verify_action(
    *,
    before_state: str,
    after_observation: dict[str, Any] | None,
    expected_effect: str = "",
    action_success: bool = False,
) -> VerificationResult:
    """Verify an action using structured observation facts, not transport success alone."""
    observation = after_observation if isinstance(after_observation, dict) else {}
    after_state = str(observation.get("state_signature") or "")
    if not action_success:
        return VerificationResult(
            status="failed",
            before_state=before_state,
            after_state=after_state,
            summary=str(observation.get("error") or "浏览器动作失败"),
            evidence=observation,
            retryable=True,
        )
    changed = bool(after_state and after_state != before_state)
    expected = str(expected_effect or "").strip().lower()
    observed_text = " ".join(
        str(observation.get(key) or "") for key in ("page_text_summary", "title", "toast", "overlay")
    ).lower()
    expected_seen = bool(expected and any(token in observed_text for token in expected.split() if len(token) > 1))
    if changed or expected_seen:
        return VerificationResult(
            status="verified",
            before_state=before_state,
            after_state=after_state,
            summary="动作后的页面状态符合预期。",
            evidence=observation,
        )
    return VerificationResult(
        status="no_effect",
        before_state=before_state,
        after_state=after_state,
        summary="动作执行成功，但未观察到可验证的状态变化。",
        evidence=observation,
        retryable=True,
    )

