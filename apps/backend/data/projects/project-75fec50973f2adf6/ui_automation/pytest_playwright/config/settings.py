from __future__ import annotations

import os


BASE_URL = os.getenv("UI_BASE_URL", "").rstrip("/")
UI_LOCALE = os.getenv("UI_LOCALE", "zh-CN")
UI_TIMEOUT_MS = int(os.getenv("UI_TIMEOUT_MS", "30000"))
UI_AUTH_STATE_PATH = os.getenv("UI_AUTH_STATE_PATH", "").strip()
