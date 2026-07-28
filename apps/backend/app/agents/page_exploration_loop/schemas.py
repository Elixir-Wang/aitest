from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ActionDecision(BaseModel):
    """A local action selected from server-provided candidates."""

    action_type: Literal[
        "click",
        "fill",
        "navigate",
        "observe_overlay",
        "skip",
        "request_human",
        "finish_state",
    ]
    element_key: str | None = None
    value: str | None = None
    expected_effect: str = ""
    risk_level: Literal["low", "medium", "high", "destructive"] = "low"
    reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    status: Literal["verified", "no_effect", "blocked", "failed"]
    before_state: str = ""
    after_state: str = ""
    summary: str = ""
    evidence: dict = Field(default_factory=dict)
    retryable: bool = False

