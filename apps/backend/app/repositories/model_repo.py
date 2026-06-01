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
    api_key: str,
    description: str,
    status: str,
    created_by: str,
) -> None:
    db.execute(
        """
        INSERT INTO model_providers (id, provider, model, base_url, api_key, description, status, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (provider_id, provider, model, base_url, api_key, description, status, created_by),
    )


def update_provider(
    db: Connection,
    *,
    provider_id: str,
    provider: str,
    model: str,
    base_url: str,
    api_key: str,
    description: str,
    status: str,
) -> None:
    db.execute(
        """
        UPDATE model_providers
        SET provider = ?, model = ?, base_url = ?, api_key = ?, description = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (provider, model, base_url, api_key, description, status, provider_id),
    )


def delete_provider(db: Connection, provider_id: str) -> None:
    db.execute("DELETE FROM model_providers WHERE id = ?", (provider_id,))


def list_model_assignments(db: Connection) -> list[Row]:
    return db.execute(
        """
        SELECT ma.capability_id,
               ma.model_provider_id,
               ma.created_at,
               ma.updated_at,
               mp.provider,
               mp.model,
               mp.base_url,
               mp.api_key,
               mp.status AS model_status
        FROM model_assignments ma
        JOIN model_providers mp ON mp.id = ma.model_provider_id
        ORDER BY ma.capability_id ASC
        """
    ).fetchall()


def find_model_assignment(db: Connection, capability_id: str) -> Row | None:
    return db.execute(
        """
        SELECT ma.capability_id,
               ma.model_provider_id,
               ma.created_at,
               ma.updated_at,
               mp.provider,
               mp.model,
               mp.base_url,
               mp.api_key,
               mp.status AS model_status
        FROM model_assignments ma
        JOIN model_providers mp ON mp.id = ma.model_provider_id
        WHERE ma.capability_id = ?
        """,
        (capability_id,),
    ).fetchone()


def upsert_model_assignment(db: Connection, *, capability_id: str, model_provider_id: str) -> None:
    db.execute(
        """
        INSERT INTO model_assignments (capability_id, model_provider_id)
        VALUES (?, ?)
        ON CONFLICT(capability_id) DO UPDATE SET
          model_provider_id = excluded.model_provider_id,
          updated_at = CURRENT_TIMESTAMP
        """,
        (capability_id, model_provider_id),
    )
