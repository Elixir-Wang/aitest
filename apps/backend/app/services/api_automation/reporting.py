import json
from pathlib import Path
from typing import Any


def parse_pytest_json_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    return {
        "total": int(summary.get("total") or 0),
        "passed": int(summary.get("passed") or 0),
        "failed": int(summary.get("failed") or 0),
        "skipped": int(summary.get("skipped") or 0),
        "duration": data.get("duration", 0),
        "exitcode": data.get("exitcode"),
        "tests": data.get("tests", []),
    }
