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


def list_agent_assignments(db: Connection) -> list[Row]:
    return db.execute(
        """
        SELECT ama.agent_id,
               ama.model_provider_id,
               ama.created_at,
               ama.updated_at,
               mp.provider,
               mp.model,
               mp.base_url,
               mp.api_key_mask,
               mp.status AS model_status
        FROM agent_model_assignments ama
        JOIN model_providers mp ON mp.id = ama.model_provider_id
        ORDER BY ama.agent_id ASC
        """
    ).fetchall()


def find_agent_assignment(db: Connection, agent_id: str) -> Row | None:
    return db.execute(
        """
        SELECT ama.agent_id,
               ama.model_provider_id,
               ama.created_at,
               ama.updated_at,
               mp.provider,
               mp.model,
               mp.base_url,
               mp.api_key_mask,
               mp.status AS model_status
        FROM agent_model_assignments ama
        JOIN model_providers mp ON mp.id = ama.model_provider_id
        WHERE ama.agent_id = ?
        """,
        (agent_id,),
    ).fetchone()


def upsert_agent_assignment(db: Connection, *, agent_id: str, model_provider_id: str) -> None:
    db.execute(
        """
        INSERT INTO agent_model_assignments (agent_id, model_provider_id)
        VALUES (?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
          model_provider_id = excluded.model_provider_id,
          updated_at = CURRENT_TIMESTAMP
        """,
        (agent_id, model_provider_id),
    )
