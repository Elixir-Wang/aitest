"""Independent loop-based website exploration agent."""

__all__ = ["page_exploration_loop_agent"]


def page_exploration_loop_agent(*args, **kwargs):
    """Lazy import to keep state/merge utilities usable without model dependencies."""
    from app.agents.page_exploration_loop.agent import page_exploration_loop_agent as factory

    return factory(*args, **kwargs)
