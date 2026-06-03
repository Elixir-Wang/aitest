__all__ = [
    "RequirementConversionInput",
    "RequirementConversionOutput",
    "convert_requirement_file",
    "requirement_standardization_agent",
    "agent",
    "schemas",
    "service",
]


def __getattr__(name: str):
    if name in {"RequirementConversionInput", "RequirementConversionOutput"}:
        from app.agents.requirement_standardization import schemas

        return getattr(schemas, name)
    if name == "convert_requirement_file":
        from app.agents.requirement_standardization.service import convert_requirement_file

        return convert_requirement_file
    if name == "requirement_standardization_agent":
        from app.agents.requirement_standardization.agent import requirement_standardization_agent

        return requirement_standardization_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
