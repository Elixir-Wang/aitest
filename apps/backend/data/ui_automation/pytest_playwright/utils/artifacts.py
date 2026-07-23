from __future__ import annotations

import json
import os
from pathlib import Path


def write_result(payload: dict) -> None:
    target = os.getenv("UI_RESULT_PATH", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
