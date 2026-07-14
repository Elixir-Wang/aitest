from typing import Any

from pydantic import BaseModel


class PytestRequestsEndpoint(BaseModel):
    id: str
    method: str
    path: str
    summary: str = ""
    module: str = ""
    feature: str = ""


class PytestRequestsGenerationInput(BaseModel):
    endpoint: PytestRequestsEndpoint
    cases: list[dict[str, Any]] = []
    is_first_time: bool = False


class GeneratedCodeFile(BaseModel):
    key: str
    language: str
    content: str
    kind: str = ""  # "test", "data", or "" for support files


class PytestRequestsGenerationResult(BaseModel):
    endpoint_id: str
    endpoint_key: str
    files: list[GeneratedCodeFile]
    case_count: int
