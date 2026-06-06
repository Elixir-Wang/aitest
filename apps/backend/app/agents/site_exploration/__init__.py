__all__ = [
    "SiteExplorationInput",
    "SiteExplorationOutput",
    "plan_site_exploration",
    "site_exploration_agent",
    "agent",
    "schemas",
    "service",
]


def __getattr__(name: str):
    if name in {"SiteExplorationInput", "SiteExplorationOutput"}:
        from app.agents.site_exploration import schemas

        return getattr(schemas, name)
    if name == "plan_site_exploration":
        from app.agents.site_exploration.service import plan_site_exploration

        return plan_site_exploration
    if name == "site_exploration_agent":
        from app.agents.site_exploration.agent import site_exploration_agent

        return site_exploration_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
