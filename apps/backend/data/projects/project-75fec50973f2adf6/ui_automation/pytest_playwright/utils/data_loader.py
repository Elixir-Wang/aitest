from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_case_data(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _resolve_environment_values(payload)


def _resolve_environment_values(value):
    if isinstance(value, dict):
        if value.get("source") == "environment" and value.get("key"):
            return os.getenv(str(value["key"]), value.get("default", ""))
        return {key: _resolve_environment_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_environment_values(item) for item in value]
    return value
