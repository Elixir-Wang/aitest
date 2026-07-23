from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def collect_suite(suite_path: Path, test_paths: list[str] | None = None, timeout: int = 120) -> dict:
    environment = dict(os.environ)
    environment.pop("VIRTUAL_ENV", None)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", *(test_paths or ["testcases"])],
        cwd=suite_path,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=environment,
    )
    return {
        "ok": completed.returncode == 0,
        "exitcode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


__all__ = ["collect_suite"]

