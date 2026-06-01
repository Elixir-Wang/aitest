import hashlib
import hmac
import secrets


def hash_secret(value: str, salt: str | None = None) -> str:
    secret_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), secret_salt.encode("utf-8"), 120_000)
    return f"{secret_salt}${digest.hex()}"


def verify_secret(value: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hash_secret(value, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, expected)

