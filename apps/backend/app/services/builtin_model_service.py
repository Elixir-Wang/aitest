"""内置模型加载服务。

加载内置模型与「新增模型」是两条独立的路径：加载只依赖内置的密文配置 + 解锁密码，
新增则由使用者自己填写 provider / base_url / API Key。

内置模型的 API Key 在仓库中以**密文**形式内置，密文由解锁密码派生的密钥加密，
只有输入正确密码才能解密并写入模型列表；服务端不需要配置任何环境变量。

- 解锁密码：默认 ``aitest``，可用 ``AI_TESTING_BUILTIN_MODEL_PASSWORD`` 覆盖。
- 密文格式：``v1.<salt_base64url>.<fernet_token>``，salt 随密文一起存储。
- 更换密钥：调用 :func:`encrypt_api_key` 用同一密码重新生成密文并替换内置配置。
"""

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core import settings
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import model_repo
from app.services import operation_log_service

# 从解锁密码派生 Fernet 密钥的迭代次数，与 app.core.security 保持一致。
_KEY_DERIVE_ITERATIONS = 120_000

BUILTIN_MODELS: list[dict[str, str]] = [
    {
        "provider": "sensenova",
        "model": "deepseek-v4-flash",
        "base_url": "https://token.sensenova.cn/v1",
        "description": "内置模型：sensenova deepseek-v4-flash",
        "api_key_encrypted": (
            "v1.Wz9v8r1a7GN1dlP203XqIw.gAAAAABqs9i0xdjHbpjW4Xc-xgh4mDOwXauzbasfEflEPIz_"
            "9bOYoudDZG2XX2mHQy7Mdu1LfadQ-QW6Ivz-vujNt1rdDh93eoTjZbyMjjvUEodF_KQIwFQBGWBrR_"
            "AyV3_dR_LEc7Qp"
        ),
    },
    {
        "provider": "DeepSeek",
        "model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com",
        "description": "内置模型：DeepSeek deepseek-v4-flash",
        "api_key_encrypted": (
            "v1.y2jDwS0QaTJ1TggllDDWSw.gAAAAABqs9i0IjUngnrjhuZHQoUXPHI803Q_SgPCfDpQ6kNdW"
            "kJ9B3i8na_mLDIz2RgaHyFtcw2GrhwAOSXhIy0HcrokVYjW_mLPCar1cnO4OhIV1NclH_Km9lT-oJ"
            "Qwd8EvO67bTqYn"
        ),
    },
]


def load_builtin_models(password: str, actor) -> dict:
    if not hmac.compare_digest(password or "", settings.BUILTIN_MODEL_PASSWORD):
        raise api_error(403, "INVALID_BUILTIN_MODEL_PASSWORD", "密码错误。")

    created = 0
    updated = 0
    unchanged = 0
    with connect() as db:
        for entry in BUILTIN_MODELS:
            api_key = decrypt_api_key(settings.BUILTIN_MODEL_PASSWORD, entry["api_key_encrypted"])
            if not api_key:
                raise api_error(
                    500,
                    "BUILTIN_MODEL_KEY_UNREADABLE",
                    f"内置模型 {entry['provider']} 的密钥密文无法解密，请检查内置配置。",
                )

            existing = model_repo.find_provider_by_identity(
                db,
                provider=entry["provider"],
                model=entry["model"],
                base_url=entry["base_url"],
            )
            description = (existing["description"] if existing else "") or entry["description"]

            if existing and api_key == existing["api_key"] and existing["status"] == "enabled":
                unchanged += 1
                continue

            if existing:
                model_repo.update_provider(
                    db,
                    provider_id=existing["id"],
                    provider=entry["provider"],
                    model=entry["model"],
                    base_url=entry["base_url"],
                    api_key=api_key,
                    description=description,
                    status="enabled",
                )
                updated += 1
                continue

            model_repo.create_provider(
                db,
                provider_id=f"mp-{secrets.token_hex(8)}",
                provider=entry["provider"],
                model=entry["model"],
                base_url=entry["base_url"],
                api_key=api_key,
                description=entry["description"],
                status="enabled",
                created_by=actor["id"],
            )
            created += 1

    operation_log_service.record_change(
        log_type="config",
        module="model",
        action="load_builtin",
        object_type="model_provider",
        object_name="内置模型",
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"加载内置模型：新增 {created} 个，更新 {updated} 个，已存在 {unchanged} 个",
    )
    return {"created": created, "updated": updated, "unchanged": unchanged}


def encrypt_api_key(password: str, api_key: str) -> str:
    """用解锁密码加密 API Key，返回可内置到 :data:`BUILTIN_MODELS` 的密文。"""
    salt = secrets.token_bytes(16)
    token = Fernet(_derive_key(password, salt)).encrypt(api_key.encode("utf-8")).decode("ascii")
    return "v1." + base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=") + "." + token


def decrypt_api_key(password: str, encrypted: str) -> str | None:
    """用解锁密码解密密文，密码错误或密文损坏时返回 ``None``。"""
    try:
        version, salt_part, token = encrypted.split(".", 2)
    except ValueError:
        return None
    if version != "v1" or not salt_part or not token:
        return None
    try:
        salt = base64.urlsafe_b64decode(salt_part + "=" * (-len(salt_part) % 4))
    except (ValueError, TypeError):
        return None
    try:
        return Fernet(_derive_key(password, salt)).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError):
        return None


def _derive_key(password: str, salt: bytes) -> bytes:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _KEY_DERIVE_ITERATIONS)
    return base64.urlsafe_b64encode(raw)
