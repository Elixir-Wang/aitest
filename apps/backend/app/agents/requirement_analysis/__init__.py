"""Requirement analysis package."""

from typing import Any


def run_requirement_analysis(*args: Any, **kwargs: Any) -> Any:
    """Lazily load the requirement analysis orchestrator entrypoint."""
    from app.agents.requirement_analysis.orchestrator import run_requirement_analysis as _run

    return _run(*args, **kwargs)

__all__ = ["run_requirement_analysis"]
