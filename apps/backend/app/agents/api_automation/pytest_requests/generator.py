from app.agents.api_automation.pytest_requests.schemas import (
    PytestRequestsGenerationInput,
    PytestRequestsGenerationResult,
)
from app.agents.api_automation.pytest_requests.skill import (
    PYTEST_REQUESTS_CODE_GENERATION_SKILL,
    pytest_requests_skill_fingerprint,
)

generate_pytest_requests_code = PYTEST_REQUESTS_CODE_GENERATION_SKILL.invoke

__all__ = ["generate_pytest_requests_code", "pytest_requests_skill_fingerprint"]


def __getattr__(name: str):
    if name == "pytest_requests_skill_fingerprint":
        return pytest_requests_skill_fingerprint
    raise AttributeError(name)
