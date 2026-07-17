from importlib import import_module


_SCHEMA_EXPORTS = {
    "ApiAssertion",
    "ApiAutomationGenerationInput",
    "ApiAutomationGenerationResult",
    "ApiGeneratedCase",
}


def __getattr__(name: str):
    if name in _SCHEMA_EXPORTS:
        return getattr(import_module("app.agents.api_automation.case_generation.schemas"), name)
    if name == "api_automation_generation_agent":
        return import_module("app.agents.api_automation.case_generation.agent").api_automation_generation_agent
    if name == "generate_api_test_cases":
        return import_module("app.agents.api_automation.case_generation.service").generate_api_test_cases
    raise AttributeError(name)


__all__ = [
    "ApiAssertion",
    "ApiAutomationGenerationInput",
    "ApiAutomationGenerationResult",
    "ApiGeneratedCase",
    "api_automation_generation_agent",
    "generate_api_test_cases",
]
