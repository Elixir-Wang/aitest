import json
from pathlib import Path
from typing import Any


def load_observations(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("观察执行结果不存在或格式无效。") from exc
    observations = payload.get("observations", []) if isinstance(payload, dict) else []
    return [observation for observation in observations if isinstance(observation, dict)]


def find_case_observation(path: Path, case_id: str) -> dict[str, Any]:
    for observation in load_observations(path):
        if observation.get("case_id") == case_id:
            return observation
    raise ValueError("执行结果中未找到该用例的观察证据。")


def infer_assertions(observation: dict[str, Any]) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    status_code = observation.get("status_code")
    if isinstance(status_code, int):
        assertions.append({"type": "status_code", "path": "", "expected": status_code})
    response_body = observation.get("response_body")
    if isinstance(response_body, dict):
        business_code = response_body.get("code")
        if isinstance(business_code, (str, int, float, bool)):
            assertions.append({"type": "jsonpath_equals", "path": "$.code", "expected": business_code})
    if not assertions:
        raise ValueError("观察证据无法形成有效断言建议。")
    return assertions
