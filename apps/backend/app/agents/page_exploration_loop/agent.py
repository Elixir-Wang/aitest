"""Structured local decisions for deterministic loop exploration."""

from langchain_core.language_models import BaseChatModel

from app.agents.page_exploration_loop.schemas import ActionDecision
from app.agents.shared.structured_output import structured_output_runnable


def loop_action_decider(model: BaseChatModel):
    """Return a cross-provider structured-output runnable for local decisions."""
    return structured_output_runnable(model, ActionDecision)
