from app.agents.api_automation.pytest_requests.agent import pytest_requests_generation_agent
from app.agents.api_automation.pytest_requests.schemas import (
    PytestRequestsGenerationInput,
    PytestRequestsGenerationResult,
)


def generate_pytest_requests_code(
    input_data: PytestRequestsGenerationInput,
) -> PytestRequestsGenerationResult:
    return pytest_requests_generation_agent(input_data)
