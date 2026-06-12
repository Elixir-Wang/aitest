# Lazy imports to avoid circular dependencies and missing langchain
__all__ = ["generate_exploration_plan_from_requirement"]


def __getattr__(name):
    if name == "generate_exploration_plan_from_requirement":
        from app.agents.requirement_exploration.service import generate_exploration_plan_from_requirement

        return generate_exploration_plan_from_requirement
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

