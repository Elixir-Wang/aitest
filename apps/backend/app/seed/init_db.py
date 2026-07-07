from app.core.db import connect
from app.seed.schema import CREATE_SCHEMA_SQL
from app.seed.seeds import seed_admin_user, seed_system_defaults


def init_db() -> None:
    with connect() as db:
        db.executescript(CREATE_SCHEMA_SQL)
        seed_system_defaults(db)
        seed_admin_user(db)
