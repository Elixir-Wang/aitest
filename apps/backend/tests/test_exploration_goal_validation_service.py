from __future__ import annotations

import unittest

from app.services.exploration_goal_validation_service import (
    terminal_status_for_goal_validation,
    validate_goal,
)


GOAL = "每篇文章内容的超链接和按钮，不能跳转到登陆页面"


class ExplorationGoalValidationServiceTest(unittest.TestCase):
    def test_validate_goal_marks_login_link_failed(self):
        validation = validate_goal(
            GOAL,
            [
                {
                    "page": {"id": "page-001", "title": "文章", "url": "https://example.test/article"},
                    "relations": {
                        "outgoing_edges": [
                            {"to_url": "https://example.test/login?next=/article", "label": "继续阅读"}
                        ]
                    },
                    "actions": [],
                    "accessibility_tree": [],
                }
            ],
            {"edges": []},
        )

        self.assertEqual(validation["status"], "failed")
        self.assertEqual(validation["stats"]["link_failed_count"], 1)
        self.assertEqual(validation["items"][0]["result"], "failed")
        self.assertEqual(terminal_status_for_goal_validation("completed", validation), "blocked")

    def test_validate_goal_marks_unnamed_button_unverified(self):
        validation = validate_goal(
            GOAL,
            [
                {
                    "page": {"id": "page-001", "title": "文章", "url": "https://example.test/article"},
                    "relations": {"outgoing_edges": [{"to_url": "https://example.test/help", "label": "帮助"}]},
                    "actions": [{"role": "button", "action_type": "click", "name": "BUTTON", "locator_hint": "button"}],
                    "accessibility_tree": [],
                }
            ],
            {"edges": []},
        )

        self.assertEqual(validation["status"], "partial")
        self.assertEqual(validation["stats"]["link_checked_count"], 1)
        self.assertEqual(validation["stats"]["button_unverified_count"], 1)
        self.assertEqual(validation["items"][1]["result"], "unverified")
        self.assertIn("按钮名称不可识别", validation["items"][1]["reason"])
        self.assertEqual(terminal_status_for_goal_validation("completed", validation), "waiting_human")

    def test_empty_and_unsupported_goals_are_not_falsely_completed(self):
        self.assertEqual(validate_goal("", [], {})["status"], "skipped")

        validation = validate_goal("梳理所有业务模块", [], {})

        self.assertEqual(validation["status"], "pending")
        self.assertIn("尚未解析", validation["summary"])
        self.assertEqual(terminal_status_for_goal_validation("completed", validation), "waiting_human")

    def test_button_click_validation_evidence_can_pass(self):
        validation = validate_goal(
            GOAL,
            [
                {
                    "page": {"id": "page-001", "title": "文章", "url": "https://example.test/article"},
                    "relations": {"outgoing_edges": []},
                    "actions": [
                        {
                            "role": "button",
                            "action_type": "click",
                            "name": "查看更多",
                            "locator_hint": "button",
                            "validation": {
                                "status": "passed",
                                "after_url": "https://example.test/article#more",
                                "reason": "点击后页面未命中登录页特征。",
                            },
                        }
                    ],
                    "accessibility_tree": [],
                }
            ],
            {"edges": []},
        )

        self.assertEqual(validation["status"], "passed")
        self.assertEqual(validation["stats"]["button_checked_count"], 1)
        self.assertEqual(validation["items"][0]["result"], "passed")


if __name__ == "__main__":
    unittest.main()
