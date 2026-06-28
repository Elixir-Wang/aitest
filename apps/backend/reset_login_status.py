#!/usr/bin/env python3
"""
重置登录状态
"""
import json
from pathlib import Path
from datetime import datetime, timezone

ENVIRONMENT_ID = "env-c3bc1023763dbb16"
AUTH_DIR = Path(f"data/projects/environments/{ENVIRONMENT_ID}/auth")
STATUS_FILE = AUTH_DIR / "auto-login-status.json"

print("重置登录状态...")

new_status = {
    "status": "idle",
    "message": "",
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "last_error_code": ""
}

STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(STATUS_FILE, 'w') as f:
    json.dump(new_status, f, ensure_ascii=False, indent=2)

print(f"✅ 已重置状态为 'idle'")
print(f"✅ 请刷新前端页面并重新尝试登录")
