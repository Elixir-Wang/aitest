"""Requirement analysis package."""

from typing import Any


def run_requirement_analysis(*args: Any, **kwargs: Any) -> Any:
    """Lazily load the LangGraph workflow entrypoint."""
    from app.agents.requirement_analysis.workflow import run_requirement_analysis as _run

    return _run(*args, **kwargs)

__all__ = ["run_requirement_analysis"]
