"""Compatibility shim for the former LangGraph workflow entrypoint."""

from app.agents.requirement_analysis.orchestrator import run_requirement_analysis


def build_requirement_analysis_workflow():
    """The LangGraph workflow is no longer the primary runtime path."""
    raise RuntimeError(
        "build_requirement_analysis_workflow is deprecated; "
        "use app.agents.requirement_analysis.orchestrator.run_requirement_analysis."
    )


__all__ = ["run_requirement_analysis", "build_requirement_analysis_workflow"]
