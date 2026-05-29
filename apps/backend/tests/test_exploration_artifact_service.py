from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.exploration_artifact_service import load_exploration_run_artifacts, write_exploration_artifacts


class ExplorationArtifactServiceTest(unittest.TestCase):
    def test_write_and_load_yaml_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifacts = write_exploration_artifacts(
                root,
                run={
                    "id": "explore-1",
                    "project_id": "project-1",
                    "project_name": "测试项目",
                    "environment_id": "env-1",
                    "environment_name": "测试环境",
                    "title": "后台探索",
                },
                summary={"status": "completed", "summary": "已完成", "markdown_content": "# 探索报告"},
                pages=[
                    {
                        "title": "用户管理",
                        "url": "https://example.test/users",
                        "entry_path": "https://example.test",
                        "structure_summary": "可交互元素：button 1。",
                    }
                ],
                elements=[
                    {
                        "name": "新增用户",
                        "type": "button",
                        "locator": "button",
                        "href": "",
                        "page_url": "https://example.test/users",
                    }
                ],
                blockers=[],
                log_content="run ok",
            )

            bundle = load_exploration_run_artifacts(root)

            self.assertTrue((root / "run.yaml").exists())
            self.assertTrue((root / "summary.yaml").exists())
            self.assertTrue((root / "graph.yaml").exists())
            self.assertTrue((root / "blockers.yaml").exists())
            self.assertTrue((root / "logs" / "run.log").exists())
            self.assertTrue(artifacts["log_path"].replace("\\", "/").endswith("logs/run.log"))
            self.assertEqual(bundle["summary"]["summary"], "已完成")
            self.assertEqual(bundle["pages"][0]["content"]["page"]["title"], "用户管理")


if __name__ == "__main__":
    unittest.main()
