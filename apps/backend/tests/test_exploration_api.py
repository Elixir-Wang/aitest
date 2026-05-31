from __future__ import annotations

import unittest
from unittest.mock import patch

from app.api.v1 import exploration


class ExplorationApiTest(unittest.TestCase):
    def test_start_project_run_dispatches_runner_outside_request_lifecycle(self):
        service_result = {"id": "explore-1", "title": "探索任务"}
        created_threads = []

        class FakeThread:
            def __init__(self, *, target, args, daemon):
                self.target = target
                self.args = args
                self.daemon = daemon
                self.started = False
                created_threads.append(self)

            def start(self):
                self.started = True

        with (
            patch("app.api.v1.exploration.exploration_service.start_project_run", return_value=service_result) as start_run,
            patch("app.api.v1.exploration.threading.Thread", side_effect=FakeThread),
        ):
            result = exploration.start_project_run("project-1", "explore-1", actor={"id": "u-admin"})

        self.assertEqual(result, service_result)
        start_run.assert_called_once_with("project-1", "explore-1", {"id": "u-admin"})
        self.assertEqual(len(created_threads), 1)
        self.assertIs(created_threads[0].target, exploration.site_exploration_orchestrator.run_exploration)
        self.assertEqual(created_threads[0].args, ("explore-1",))
        self.assertTrue(created_threads[0].daemon)
        self.assertTrue(created_threads[0].started)


if __name__ == "__main__":
    unittest.main()
