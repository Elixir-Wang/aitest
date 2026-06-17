import base64
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core import settings


def environment_root(environment_id: str) -> Path:
    return settings.PROJECT_FILE_STORAGE_ROOT / "environments" / environment_id


def auth_state_path(environment_id: str) -> Path:
    return environment_root(environment_id) / "auth" / "storage-state.json"


def auth_state_status(
    *,
    environment_id: str,
    login_strategy: str,
    reuse_auth_state: bool,
) -> str:
    return auth_state_summary(
        environment_id=environment_id,
        login_strategy=login_strategy,
        reuse_auth_state=reuse_auth_state,
    )["status"]


def auth_state_summary(
    *,
    environment_id: str,
    login_strategy: str,
    reuse_auth_state: bool,
) -> dict:
    if login_strategy != "account_password" or not reuse_auth_state:
        return {"status": "none", "expires_at": None}

    path = auth_state_path(environment_id)
    if not path.exists():
        return {"status": "none", "expires_at": None}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "expired", "expires_at": None}

    cookies = payload.get("cookies")
    origins = payload.get("origins")
    if not isinstance(cookies, list) or not isinstance(origins, list):
        return {"status": "expired", "expires_at": None}

    expires_at = _earliest_expires_at(payload)
    if expires_at and expires_at <= datetime.now(timezone.utc):
        return {"status": "expired", "expires_at": expires_at.isoformat()}
    return {"status": "valid", "expires_at": expires_at.isoformat() if expires_at else None}


def delete_auth_state(environment_id: str) -> None:
    auth_dir = auth_state_path(environment_id).parent
    if auth_dir.exists():
        shutil.rmtree(auth_dir)


def _earliest_expires_at(payload: dict) -> datetime | None:
    expires_at_values: list[datetime] = []
    cookies = payload.get("cookies")
    if isinstance(cookies, list):
        for cookie in cookies:
            expires_at = _cookie_expires_at(cookie)
            if expires_at:
                expires_at_values.append(expires_at)

    origins = payload.get("origins")
    if isinstance(origins, list):
        for origin in origins:
            expires_at_values.extend(_origin_token_expires_at_values(origin))

    return min(expires_at_values) if expires_at_values else None


def _cookie_expires_at(cookie: object) -> datetime | None:
    if not isinstance(cookie, dict):
        return None
    expires = cookie.get("expires")
    if not isinstance(expires, int | float) or expires <= 0:
        return None
    try:
        return datetime.fromtimestamp(expires, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _origin_token_expires_at_values(origin: object) -> list[datetime]:
    if not isinstance(origin, dict):
        return []
    expires_at_values: list[datetime] = []
    for storage_key in ("localStorage", "sessionStorage"):
        storage = origin.get(storage_key)
        if not isinstance(storage, list):
            continue
        for item in storage:
            if not isinstance(item, dict):
                continue
            expires_at = _jwt_expires_at(item.get("value"))
            if expires_at:
                expires_at_values.append(expires_at)
    return expires_at_values


def _jwt_expires_at(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if len(parts) < 2:
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    exp = claims.get("exp")
    if not isinstance(exp, int | float) or exp <= 0:
        return None
    try:
        return datetime.fromtimestamp(exp, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
