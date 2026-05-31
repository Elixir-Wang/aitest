from __future__ import annotations

import unittest

from app.services import exploration_event_bus


class ExplorationEventBusTest(unittest.TestCase):
    def tearDown(self) -> None:
        exploration_event_bus.reset_for_tests()

    def test_subscriber_receives_same_run_events(self):
        stream = exploration_event_bus.subscribe("run-1", heartbeat_seconds=0.01)
        self.assertIsNone(next(stream))

        exploration_event_bus.publish("run-1", "page_discovered", {"page_id": "page-1"})

        event = next(stream)
        self.assertEqual(event["type"], "page_discovered")
        self.assertEqual(event["run_id"], "run-1")
        self.assertEqual(event["payload"]["page_id"], "page-1")

    def test_subscriber_ignores_other_run_events(self):
        stream = exploration_event_bus.subscribe("run-1", heartbeat_seconds=0.01)
        self.assertIsNone(next(stream))

        exploration_event_bus.publish("run-2", "page_discovered", {"page_id": "page-2"})

        self.assertIsNone(next(stream))

    def test_close_ends_subscription(self):
        stream = exploration_event_bus.subscribe("run-1", heartbeat_seconds=0.01)
        self.assertIsNone(next(stream))

        exploration_event_bus.close("run-1")

        with self.assertRaises(StopIteration):
            next(stream)


if __name__ == "__main__":
    unittest.main()
