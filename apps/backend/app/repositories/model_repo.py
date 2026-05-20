from __future__ import annotations

from sqlite3 import Connection, Row


def list_providers(db: Connection) -> list[Row]:
    return db.execute("SELECT * FROM model_providers ORDER BY created_at DESC, provider ASC").fetchall()


def find_provider_by_id(db: Connection, provider_id: str) -> Row | None:
    return db.execute("SELECT * FROM model_providers WHERE id = ?", (provider_id,)).fetchone()


def create_provider(
    db: Connection,
    *,
    provider_id: str,
    provider: str,
    model: str,
    base_url: str,
    api_key_hash: str,
    api_key_mask: str,
    description: str,
    status: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO model_providers (id, provider, model, base_url, api_key_hash, api_key_mask, description, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (provider_id, provider, model, base_url, api_key_hash, api_key_mask, description, status, created_by),
    )


def update_provider(
    db: Connection,
    *,
    provider_id: str,
    provider: str,
    model: str,
    base_url: str,
    api_key_hash: str,
    api_key_mask: str,
    description: str,
    status: str,
) -> None:
    db.execute(
        """
        UPDATE model_providers
        SET provider = ?, model = ?, base_url = ?, api_key_hash = ?, api_key_mask = ?, description = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (provider, model, base_url, api_key_hash, api_key_mask, description, status, provider_id),
    )


def delete_provider(db: Connection, provider_id: str) -> None:
    db.execute("DELETE FROM model_providers WHERE id = ?", (provider_id,))

