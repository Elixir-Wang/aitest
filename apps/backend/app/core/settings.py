from __future__ import annotations

import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("AI_TESTING_DATA_DIR", BACKEND_ROOT / "data")).resolve()
LOGS_DIR = Path(os.getenv("AI_TESTING_LOGS_DIR", BACKEND_ROOT / "logs")).resolve()
DB_PATH = Path(os.getenv("AI_TESTING_DB_PATH", DATA_DIR / "ai_testing.db")).resolve()

PROJECT_FILE_STORAGE_ROOT = Path(
    os.getenv("AI_TESTING_PROJECT_FILE_STORAGE_DIR", DATA_DIR / "projects")
).resolve()

PLAYWRIGHT_RUNNER_DIR = Path(
    os.getenv("AI_TESTING_PLAYWRIGHT_RUNNER_DIR", BACKEND_ROOT / "runners" / "playwright")
).resolve()
PLAYWRIGHT_CLI_COMMAND = os.getenv("AI_TESTING_PLAYWRIGHT_CLI_COMMAND", "playwright")
PLAYWRIGHT_CLI_TIMEOUT_SECONDS = int(os.getenv("AI_TESTING_PLAYWRIGHT_CLI_TIMEOUT_SECONDS", "7200"))
PLAYWRIGHT_BROWSER_CHANNEL = os.getenv("AI_TESTING_PLAYWRIGHT_BROWSER_CHANNEL", "chrome")
