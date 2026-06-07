import os

from cryptography.fernet import Fernet, InvalidToken

from app.core.db import connect
from app.core import settings
from app.core.security import hash_secret, verify_secret


def credential_key_path():
    return settings.PROJECT_FILE_STORAGE_ROOT.parent / ".secrets" / "environment-credentials.key"


def save_credentials(project_id: str, environment_id: str, *, username: str, password: str) -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE project_environments
            SET username = ?, password_encrypted = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE project_id = ? AND id = ?
            """,
            (
                username,
                _fernet().encrypt(password.encode("utf-8")).decode("ascii"),
                hash_secret(password),
                project_id,
                environment_id,
            ),
        )


def load_credentials(project_id: str, environment_id: str) -> dict | None:
    with connect() as db:
        row = db.execute(
            """
            SELECT username, password_encrypted, password_hash
            FROM project_environments
            WHERE project_id = ? AND id = ?
            """,
            (project_id, environment_id),
        ).fetchone()
    if not row:
        return None
    username = row["username"]
    encrypted_password = row["password_encrypted"]
    password_hash = row["password_hash"]
    if not isinstance(username, str):
        return None
    password = _decrypt_secret(encrypted_password) if isinstance(encrypted_password, str) else None
    if password is None:
        return None
    if isinstance(password_hash, str) and password_hash and not verify_secret(password, password_hash):
        return None
    return {"username": username, "password": password}


def delete_credentials(project_id: str, environment_id: str) -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE project_environments
            SET password_encrypted = '', password_hash = '', updated_at = CURRENT_TIMESTAMP
            WHERE project_id = ? AND id = ?
            """,
            (project_id, environment_id),
        )


def credentials_exist(project_id: str, environment_id: str) -> bool:
    return load_credentials(project_id, environment_id) is not None


def _fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def _load_or_create_key() -> bytes:
    path = credential_key_path()
    if path.exists():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _decrypt_secret(value: str) -> str | None:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError, OSError):
        return None
