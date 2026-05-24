from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.db import connect
from app.seed.init_db import init_db
from app.services import site_exploration_orchestrator


class SiteExplorationOrchestratorTest(unittest.TestCase):
    def test_run_exploration_records_blocker_when_playwright_cli_is_unavailable(self):
        with isolated_exploration_store() as temp_dir:
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO projects (id, name, status, created_by)
                    VALUES ('project-1', '测试项目', 'active', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO project_environments (id, project_id, name, site_url, created_by)
                    VALUES ('env-1', 'project-1', '测试环境', 'https://example.test', 'u-admin')
                    """
                )
                db.execute(
                    """
                    INSERT INTO exploration_runs
                      (id, project_id, environment_id, title, scope, forbidden_paths, login_strategy, created_by)
                    VALUES
                      ('explore-1', 'project-1', 'env-1', '后台探索', '用户管理', '删除', 'reuse_state', 'u-admin')
                    """
                )

            with patch("app.services.site_exploration_orchestrator._playwright_cli_available", return_value=False):
                site_exploration_orchestrator.run_exploration("explore-1")

            with connect() as db:
                run = db.execute("SELECT * FROM exploration_runs WHERE id = 'explore-1'").fetchone()
                coverage = db.execute("SELECT * FROM exploration_module_coverages WHERE exploration_run_id = 'explore-1'").fetchone()
                blocker = db.execute("SELECT * FROM exploration_blockers WHERE exploration_run_id = 'explore-1'").fetchone()
                document = db.execute("SELECT * FROM exploration_document_versions WHERE exploration_run_id = 'explore-1'").fetchone()

            self.assertEqual(run["status"], "blocked")
            self.assertIn("Playwright CLI", run["result_summary"])
            self.assertEqual(coverage["completion_status"], "blocked")
            self.assertEqual(blocker["reason_type"], "runner_unavailable")
            self.assertTrue(document["markdown_path"].endswith("documents/exploration-v1.md"))
            self.assertTrue((Path(temp_dir) / "projects" / document["markdown_path"]).exists())


class isolated_exploration_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_patch = patch("app.core.db.DB_PATH", root / "ai_testing.db")
        self.storage_patch = patch("app.services.site_exploration_orchestrator.PROJECT_FILE_STORAGE_ROOT", root / "projects")
        self.store_path_patch = patch("app.core.storage.PROJECT_FILE_STORAGE_ROOT", root / "projects")
        self.db_patch.start()
        self.storage_patch.start()
        self.store_path_patch.start()
        init_db()
        return root

    def __exit__(self, exc_type, exc, tb):
        self.store_path_patch.stop()
        self.storage_patch.stop()
        self.db_patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
