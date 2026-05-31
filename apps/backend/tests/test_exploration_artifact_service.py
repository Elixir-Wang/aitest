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
                    "goal": "验证链接不跳登录页",
                },
                summary={"status": "completed", "summary": "已完成", "markdown_content": "# 探索报告"},
                page_artifacts=[
                    {
                        "page": {
                            "id": "page-001",
                            "title": "用户管理",
                            "url": "https://example.test/users",
                            "normalized_url": "https://example.test/users",
                            "module": "用户管理",
                            "page_type": "list",
                            "depth": 0,
                            "status": "explored",
                            "structure_summary": "可交互元素：button 1。",
                        },
                        "accessibility_tree": [
                            {
                                "id": "node-001",
                                "role": "button",
                                "name": "新增用户",
                                "locator_hint": "getByRole('button', { name: '新增用户' })",
                                "children": [],
                            }
                        ],
                        "actions": [],
                        "forms": [],
                        "tables": [],
                        "relations": {"incoming_edges": [], "outgoing_edges": []},
                        "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                    }
                ],
                graph={"nodes": [{"id": "page-001", "url": "https://example.test/users"}], "edges": [], "paths": []},
                blockers=[],
                log_content="run ok",
                goal_validation={
                    "goal": "验证链接不跳登录页",
                    "status": "partial",
                    "summary": "目标验证部分完成：按钮未验证。",
                    "stats": {
                        "page_count": 1,
                        "link_total_count": 0,
                        "link_checked_count": 0,
                        "link_failed_count": 0,
                        "button_total_count": 1,
                        "button_checked_count": 0,
                        "button_unverified_count": 1,
                        "button_failed_count": 0,
                        "unverified_count": 1,
                    },
                    "items": [],
                },
            )

            bundle = load_exploration_run_artifacts(root)

            self.assertTrue((root / "run.yaml").exists())
            self.assertTrue((root / "summary.yaml").exists())
            self.assertTrue((root / "graph.yaml").exists())
            self.assertTrue((root / "blockers.yaml").exists())
            self.assertTrue((root / "checks" / "goal-validation.yaml").exists())
            self.assertTrue((root / "documents" / "exploration-v1.md").exists())
            self.assertTrue((root / "logs" / "run.log").exists())
            self.assertTrue(artifacts["report_path"].replace("\\", "/").endswith("documents/exploration-v1.md"))
            self.assertTrue(artifacts["log_path"].replace("\\", "/").endswith("logs/run.log"))
            self.assertEqual(bundle["summary"]["summary"], "已完成")
            self.assertEqual(bundle["summary"]["goal"], "验证链接不跳登录页")
            self.assertEqual(bundle["summary"]["goal_validation"]["status"], "partial")
            self.assertEqual(bundle["goal_validation"]["goal"], "验证链接不跳登录页")
            self.assertEqual(bundle["pages"][0]["content"]["page"]["title"], "用户管理")

            report = (root / "documents" / "exploration-v1.md").read_text(encoding="utf-8")
            for heading in [
                "## 1. 报告摘要",
                "## 2. 探索结论",
                "## 目标验证结果",
                "## 3. 探索范围与边界",
                "## 4. 覆盖概览",
                "## 5. 模块覆盖矩阵",
                "## 6. 页面事实摘要",
                "## 7. 页面关系与路径",
                "## 8. 阻塞与跳过",
                "## 9. 风险与缺口",
                "## 10. 待人工确认事项",
                "## 11. 证据索引",
            ]:
                self.assertIn(heading, report)
            self.assertIn("链接验证：0/0", report)
            self.assertIn("按钮验证：0/1", report)


if __name__ == "__main__":
    unittest.main()
