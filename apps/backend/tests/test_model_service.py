from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.schemas.model import ModelProviderIn
from app.services import model_service


class ModelServiceTest(unittest.TestCase):
    def test_create_model_provider_stores_plain_api_key_for_runtime_use(self):
        with isolated_model_store():
            model = model_service.create_model_provider(
                ModelProviderIn(
                    provider="DeepSeek",
                    model="deepseek-chat",
                    base_url="https://api.deepseek.com",
                    api_key="sk-plain-value",
                    status="enabled",
                ),
                {"id": "u-admin", "role": "admin"},
            )
            with connect() as db:
                row = db.execute("SELECT api_key FROM model_providers WHERE id = ?", (model["id"],)).fetchone()

        self.assertEqual(row["api_key"], "sk-plain-value")


class isolated_model_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "ai_testing.db"
        self.patch = patch("app.core.db.DB_PATH", db_path)
        self.patch.start()
        with connect() as db:
            db.executescript(
                """
                CREATE TABLE model_providers (
                  id TEXT PRIMARY KEY,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  base_url TEXT NOT NULL,
                  api_key TEXT NOT NULL DEFAULT '',
                  description TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'enabled',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(provider, model, base_url)
                );
                """
            )
        return self

    def __exit__(self, exc_type, exc, tb):
        self.patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
