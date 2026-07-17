from __future__ import annotations


def runtime_locustfile_source() -> str:
    return '''import json
from pathlib import Path

from generated_locustfile import *


RUNTIME = json.loads(Path(__file__).with_name("runtime.json").read_text(encoding="utf-8"))
PLAN["request"]["headers"] = {
    **dict(RUNTIME["environment"].get("headers") or {}),
    **dict(PLAN["request"].get("headers") or {}),
}
PerformanceUser.host = RUNTIME["environment"]["api_base_url"]
'''
