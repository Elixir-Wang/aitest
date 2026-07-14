import re
from pathlib import Path

from app.agents.api_automation.pytest_requests.renderer import render_pytest_requests_files
from app.agents.api_automation.pytest_requests.schemas import (
    PytestRequestsGenerationInput,
    PytestRequestsGenerationResult,
)
from app.agents.shared.skill_runtime import ExecutableSkill


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug or "generated"


def _generate(input_data: PytestRequestsGenerationInput) -> PytestRequestsGenerationResult:
    endpoint = input_data.endpoint
    module = endpoint.module or _infer_module(endpoint.path)
    feature = endpoint.feature or _infer_feature(endpoint.path)
    endpoint_key = _slugify(f"{module}_{feature}")
    files = render_pytest_requests_files(input_data)
    return PytestRequestsGenerationResult(
        endpoint_id=endpoint.id,
        endpoint_key=endpoint_key,
        files=files,
        case_count=len(input_data.cases),
    )


def _infer_module(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[0].lower() if parts and parts[0] else "common"


def _infer_feature(path: str) -> str:
    parts = path.strip("/").split("/")
    return parts[1].lower() if len(parts) > 1 else "default"


PYTEST_REQUESTS_CODE_GENERATION_SKILL = ExecutableSkill.from_path(
    Path(__file__).parent / "skills" / "pytest-requests-code-generation",
    runner=_generate,
)


def pytest_requests_skill_fingerprint() -> str:
    return PYTEST_REQUESTS_CODE_GENERATION_SKILL.fingerprint


__all__ = ["PYTEST_REQUESTS_CODE_GENERATION_SKILL", "pytest_requests_skill_fingerprint"]


def __getattr__(name: str):
    if name == "PYTEST_REQUESTS_CODE_GENERATION_SKILL":
        return PYTEST_REQUESTS_CODE_GENERATION_SKILL
    raise AttributeError(name)
