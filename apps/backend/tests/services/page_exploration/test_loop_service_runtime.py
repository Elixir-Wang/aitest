import asyncio
from pathlib import Path

from app.agents.page_exploration.playwright.schemas import ClickResult, ElementInfo, SnapshotResult
from app.agents.page_exploration_loop.schemas import ActionDecision
from app.services.page_exploration.loop import service as loop_service


class _FakeDecider:
    async def ainvoke(self, _messages):
        return ActionDecision(
            action_type="click",
            element_key="button-下一页",
            expected_effect="下一页",
            risk_level="low",
            confidence=1.0,
        )


class _FakeModel:
    def with_structured_output(self, _schema):
        return _FakeDecider()


class _FakeTimeline:
    def __init__(self, **_kwargs):
        self.events = []

    def ensure_exists(self):
        return None

    def append(self, event_type, payload, **_kwargs):
        self.events.append((event_type, payload))
        return {"event_id": f"evt-{len(self.events)}"}


def test_execute_loop_exploration_drives_action_and_verification(monkeypatch, tmp_path: Path) -> None:
    snapshots = [
        SnapshotResult(
            url="https://example.test/home",
            title="Home",
            state_signature="state-home",
            elements=[ElementInfo(element_id="obs-next", role="button", name="下一页", action_type="click", visible=True)],
        ),
        SnapshotResult(url="https://example.test/home", title="Next", state_signature="state-next", elements=[]),
    ]
    executed = []

    monkeypatch.setattr(loop_service, "loop_action_decider", lambda _model: _FakeDecider())
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshots.pop(0))
    monkeypatch.setattr(loop_service, "click_with_runtime_context", lambda element_id: executed.append(element_id) or ClickResult(success=True, element_key="button-下一页"))
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *_args, **_kwargs: None)

    state = asyncio.run(loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-1",
            start_url="https://example.test/home",
            max_pages=1,
            max_actions=3,
            storage_root=tmp_path,
        ))

    assert executed == ["obs-next"]
    assert state.stop_reason == "frontier_exhausted"
    assert state.counters["actions"] == 1
    assert state.visited_states["state-next"]["title"] == "Next"
    assert (tmp_path / "project-1" / "page_exploration" / "runs" / "run-1" / "loop_state.json").exists()
