from app.agents.api_automation.pytest_requests.renderer import render_pytest_requests_files, slugify
from app.agents.api_automation.pytest_requests.schemas import (
    PytestRequestsGenerationInput,
    PytestRequestsGenerationResult,
)


def pytest_requests_generation_agent(
    input_data: PytestRequestsGenerationInput,
) -> PytestRequestsGenerationResult:
    endpoint = input_data.endpoint
    endpoint_key = slugify(f"{endpoint.method}_{endpoint.path}_{endpoint.id}")
    return PytestRequestsGenerationResult(
        endpoint_id=endpoint.id,
        endpoint_key=endpoint_key,
        files=render_pytest_requests_files(input_data),
        case_count=len(input_data.cases),
    )


__all__ = ["pytest_requests_generation_agent"]
