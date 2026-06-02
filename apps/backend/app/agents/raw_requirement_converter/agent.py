from app.agents.requirement_standardization.agent import (
    SYSTEM_PROMPT,
    requirement_standardization_agent,
)


def raw_requirement_converter_agent(model):
    return requirement_standardization_agent(model)


__all__ = ["SYSTEM_PROMPT", "raw_requirement_converter_agent"]
