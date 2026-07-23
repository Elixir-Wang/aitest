from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping


SENSITIVE_KEY_PARTS = ("authorization", "cookie", "token", "secret", "password", "api-key", "apikey")
MAX_TEXT_CHARS = 50_000


def _redact_text(value: str) -> str:
    value = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
    value = re.sub(
        r"(?i)\b(token|secret|password|api[_-]?key)\s*[=:]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        value,
    )
    if len(value) > MAX_TEXT_CHARS:
        return value[:MAX_TEXT_CHARS] + "\n...[TRUNCATED]"
    return value


def redact_sensitive(value: Any, *, key: str = "") -> Any:
    lowered = key.lower()
    if key and any(part in lowered for part in SENSITIVE_KEY_PARTS):
        if isinstance(value, str) and lowered == "authorization" and value.lower().startswith("bearer "):
            return "Bearer [REDACTED]"
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): redact_sensitive(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def build_failure_context(
    run: Mapping[str, Any],
    logs: Mapping[str, str],
    report: Mapping[str, Any],
    suite_path: Path,
    history: list[dict[str, Any]],
    user_context: str,
) -> dict[str, Any]:
    tests = report.get("tests", []) if isinstance(report, Mapping) else []
    failures = [item for item in tests if isinstance(item, Mapping) and item.get("outcome") == "failed"]
    return redact_sensitive(
        {
            "run": dict(run),
            "logs": dict(logs),
            "report_summary": report.get("summary", {}) if isinstance(report, Mapping) else {},
            "failures": failures,
            "suite_path": suite_path.name,
            "history": history,
            "user_context": user_context,
        }
    )
