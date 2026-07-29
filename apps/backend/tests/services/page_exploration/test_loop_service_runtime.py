import asyncio
from pathlib import Path

import pytest

from app.agents.page_exploration.playwright.schemas import ClickResult, ElementInfo, SnapshotResult
from app.agents.page_exploration_loop.schemas import ActionDecision
from app.agents.page_exploration_loop.services.checkpoint import save_checkpoint
from app.agents.page_exploration_loop.state.models import FrontierItem, LoopExplorationState
from app.services.page_exploration.loop import service as loop_service
from app.services.page_exploration.coverage_registry import update_coverage
from app.services.page_exploration.coverage_registry import is_action_completed, load_coverage


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


class _SkipDecider:
    async def ainvoke(self, _messages):
        return ActionDecision(
            action_type="skip",
            element_key="button-下一页",
            risk_level="low",
            confidence=1.0,
        )


class _FailAfterFirstDecision:
    def __init__(self):
        self.calls = 0

    async def ainvoke(self, _messages):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("rate limited")
        return ActionDecision(
            action_type="click",
            element_key="button-下一页",
            expected_effect="下一页",
            risk_level="low",
            confidence=1.0,
        )


class _ResumeDecider:
    async def ainvoke(self, _messages):
        return ActionDecision(
            action_type="click",
            element_key="button-继续",
            expected_effect="进入下一状态",
            risk_level="low",
            confidence=1.0,
        )


class _HumanDecider:
    async def ainvoke(self, _messages):
        return ActionDecision(
            action_type="request_human",
            element_key="button-下一页",
            risk_level="high",
            confidence=1.0,
        )


class _InvalidDecider:
    async def ainvoke(self, _messages):
        return ActionDecision(
            action_type="click",
            element_key="button-其他",
            risk_level="low",
            confidence=1.0,
        )


class _FakeTimeline:
    def __init__(self, **_kwargs):
        self.events = []

    def ensure_exists(self):
        return None

    def append(self, event_type, payload, **_kwargs):
        self.events.append((event_type, payload))
        return {"event_id": f"evt-{len(self.events)}"}


def test_execute_loop_exploration_drives_action_and_verification(monkeypatch, tmp_path: Path) -> None:
    published = []
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
    monkeypatch.setattr(loop_service, "publish", lambda *args, **kwargs: published.append((args, kwargs)))

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
    assert any(args[1] == "agent_plan_updated" and args[2]["plan_steps"] for args, _kwargs in published)
    assert all(
        kwargs.get("display", {}).get("summary")
        for args, kwargs in published
        if args[1] in {"loop_initialized", "action_decided", "action_verified", "loop_finished"}
    )
    assert (tmp_path / "project-1" / "page_exploration" / "runs" / "run-1" / "loop_state.json").exists()
    assert is_action_completed(
        load_coverage(tmp_path, "project-1"),
        "page-home",
        "button-下一页",
        "click",
    ) is True


def test_execute_loop_exploration_persists_verified_action_before_later_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    decider = _FailAfterFirstDecision()
    snapshots = [
        SnapshotResult(
            url="https://example.test/home",
            title="Home",
            state_signature="state-home",
            elements=[ElementInfo(element_id="obs-next", role="button", name="下一页", action_type="click", visible=True)],
        ),
        SnapshotResult(
            url="https://example.test/home",
            title="Next",
            state_signature="state-next",
            elements=[ElementInfo(element_id="obs-more", role="button", name="继续", action_type="click", visible=True)],
        ),
    ]

    monkeypatch.setattr(loop_service, "loop_action_decider", lambda _model: decider)
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshots.pop(0))
    monkeypatch.setattr(
        loop_service,
        "click_with_runtime_context",
        lambda _element_id: ClickResult(success=True, element_key="button-下一页"),
    )
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *_args, **_kwargs: None)

    with pytest.raises(RuntimeError, match="rate limited"):
        asyncio.run(
            loop_service.execute_loop_exploration(
                model=_FakeModel(),
                project_id="project-1",
                run_id="run-1",
                start_url="https://example.test/home",
                max_pages=1,
                max_actions=3,
                storage_root=tmp_path,
            )
        )

    assert is_action_completed(
        load_coverage(tmp_path, "project-1"),
        "page-home",
        "button-下一页",
        "click",
    ) is True


def test_skip_decision_closes_step_and_refreshes_plan(monkeypatch, tmp_path: Path) -> None:
    published = []
    snapshot = SnapshotResult(
        url="https://example.test/home",
        title="Home",
        state_signature="state-home",
        elements=[ElementInfo(element_id="obs-next", role="button", name="下一页", action_type="click", visible=True)],
    )

    monkeypatch.setattr(loop_service, "loop_action_decider", lambda _model: _SkipDecider())
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshot)
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *args, **kwargs: published.append((args, kwargs)))

    asyncio.run(
        loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-1",
            start_url="https://example.test/home",
            max_pages=1,
            max_actions=3,
            storage_root=tmp_path,
        )
    )

    event_types = [args[1] for args, _kwargs in published]
    assert event_types.count("step_started") == 1
    assert event_types.count("step_skipped") == 1
    assert event_types[-2:] == ["agent_plan_updated", "loop_finished"]


def test_resume_loop_exploration_executes_only_unfinished_checkpoint_item(
    monkeypatch,
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    marker = run_dir / "keep-me.txt"
    marker.write_text("preserved", encoding="utf-8")
    checkpoint = LoopExplorationState(
        run_id="run-1",
        project_id="project-1",
        start_url="https://example.test/home",
        current_state_key="state-home",
        frontier=[
            FrontierItem(
                state_key="state-home",
                page_key="page-home",
                element_key="button-已完成",
                action_type="click",
                status="verified",
            ),
            FrontierItem(
                state_key="state-home",
                page_key="page-home",
                element_key="button-继续",
                action_type="click",
                status="executing",
            ),
        ],
        visited_states={
            "state-home": {
                "state_key": "state-home",
                "page_key": "page-home",
                "url": "https://example.test/home",
                "title": "Home",
            }
        },
        counters={"actions": 1, "pages": 1, "states": 1},
        budget={"max_pages": 1, "max_actions": 3},
        stop_reason="frontier_exhausted",
    )
    save_checkpoint(run_dir, checkpoint)
    snapshots = [
        SnapshotResult(
            url="https://example.test/home",
            title="Home",
            state_signature="state-home",
            elements=[
                ElementInfo(element_id="obs-done", role="button", name="已完成", action_type="click", visible=True),
                ElementInfo(element_id="obs-next", role="button", name="继续", action_type="click", visible=True),
            ],
        ),
        SnapshotResult(
            url="https://example.test/home",
            title="Next",
            state_signature="state-next",
            elements=[],
        ),
    ]
    executed = []
    published = []

    monkeypatch.setattr(loop_service, "loop_action_decider", lambda _model: _ResumeDecider())
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshots.pop(0))
    monkeypatch.setattr(
        loop_service,
        "click_with_runtime_context",
        lambda element_id: executed.append(element_id) or ClickResult(success=True, element_key="button-继续"),
    )
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *args, **kwargs: published.append((args, kwargs)))

    state = asyncio.run(
        loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-1",
            start_url="https://example.test/home",
            max_pages=1,
            max_actions=3,
            storage_root=tmp_path,
            resume=True,
        )
    )

    assert executed == ["obs-next"]
    assert marker.read_text(encoding="utf-8") == "preserved"
    assert state.counters["actions"] == 2
    assert state.frontier[0].status == "verified"
    assert state.frontier[1].status == "verified"
    assert any(args[1] == "loop_resumed" for args, _kwargs in published)


def test_resume_loop_exploration_rejects_mismatched_checkpoint(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-1"
    save_checkpoint(
        run_dir,
        LoopExplorationState(
            run_id="other-run",
            project_id="project-1",
            start_url="https://example.test/home",
        ),
    )
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)

    with pytest.raises(ValueError, match="检查点"):
        asyncio.run(
            loop_service.execute_loop_exploration(
                model=_FakeModel(),
                project_id="project-1",
                run_id="run-1",
                start_url="https://example.test/home",
                storage_root=tmp_path,
                resume=True,
            )
        )


def test_stale_candidate_closes_step_as_blocked(monkeypatch, tmp_path: Path) -> None:
    published = []
    snapshot = SnapshotResult(
        url="https://example.test/home",
        title="Home",
        state_signature="state-home",
        elements=[ElementInfo(element_id="obs-next", role="button", name="下一页", action_type="click", visible=True)],
    )
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshot)
    monkeypatch.setattr(loop_service, "_candidate_from_snapshot", lambda *_args: None)
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *args, **kwargs: published.append((args, kwargs)))

    asyncio.run(
        loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-1",
            start_url=snapshot.url,
            storage_root=tmp_path,
        )
    )

    event_types = [args[1] for args, _kwargs in published]
    assert event_types.count("step_started") == 1
    assert event_types.count("step_blocked") == 1


def test_invalid_decision_closes_each_attempt(monkeypatch, tmp_path: Path) -> None:
    published = []
    snapshot = SnapshotResult(
        url="https://example.test/home",
        title="Home",
        state_signature="state-home",
        elements=[ElementInfo(element_id="obs-next", role="button", name="下一页", action_type="click", visible=True)],
    )
    monkeypatch.setattr(loop_service, "loop_action_decider", lambda _model: _InvalidDecider())
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshot)
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *args, **kwargs: published.append((args, kwargs)))

    asyncio.run(
        loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-1",
            start_url=snapshot.url,
            storage_root=tmp_path,
        )
    )

    event_types = [args[1] for args, _kwargs in published]
    assert event_types.count("step_started") == 3
    assert event_types.count("step_retrying") == 2
    assert event_types.count("step_failed") == 1


def test_execute_loop_exploration_skips_completed_action_coverage(monkeypatch, tmp_path: Path) -> None:
    update_coverage(
        tmp_path,
        "project-1",
        run_id="old-run",
        mode="autonomous",
        pages=[],
        completed_actions=[
            {
                "page_id": "page-home",
                "element_key": "button-下一页",
                "action": "click",
            }
        ],
        collection_groups=[],
    )
    snapshot = SnapshotResult(
        url="https://example.test/home",
        title="Home",
        state_signature="state-home",
        elements=[ElementInfo(element_id="obs-next", role="button", name="下一页", action_type="click", visible=True)],
    )
    executed = []

    monkeypatch.setattr(loop_service, "loop_action_decider", lambda _model: _FakeDecider())
    monkeypatch.setattr(loop_service, "snapshot_with_runtime_context", lambda *_args: snapshot)
    monkeypatch.setattr(loop_service, "click_with_runtime_context", lambda element_id: executed.append(element_id))
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *_args, **_kwargs: None)

    state = asyncio.run(
        loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-2",
            start_url="https://example.test/home",
            max_pages=1,
            max_actions=3,
            storage_root=tmp_path,
        )
    )

    assert executed == []
    assert state.frontier == []
    assert state.stop_reason == "frontier_exhausted"


def test_force_reexplore_executes_completed_action(monkeypatch, tmp_path: Path) -> None:
    update_coverage(
        tmp_path,
        "project-1",
        run_id="old-run",
        mode="loop",
        pages=[],
        completed_actions=[
            {
                "page_id": "page-home",
                "element_key": "button-下一页",
                "action": "click",
            }
        ],
        collection_groups=[],
    )
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
    monkeypatch.setattr(
        loop_service,
        "click_with_runtime_context",
        lambda element_id: executed.append(element_id) or ClickResult(success=True, element_key="button-下一页"),
    )
    monkeypatch.setattr(loop_service, "_persist_snapshot_artifact", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(loop_service, "_ExplorationEventLog", _FakeTimeline)
    monkeypatch.setattr(loop_service, "publish", lambda *_args, **_kwargs: None)

    asyncio.run(
        loop_service.execute_loop_exploration(
            model=_FakeModel(),
            project_id="project-1",
            run_id="run-3",
            start_url="https://example.test/home",
            max_pages=1,
            max_actions=3,
            storage_root=tmp_path,
            force_reexplore=True,
        )
    )

    assert executed == ["obs-next"]


def test_enqueue_collection_candidates_keeps_one_representative_per_group() -> None:
    snapshot = SnapshotResult(
        url="https://example.test/workspace",
        title="Workspace",
        state_signature="workspace-root",
        elements=[
            ElementInfo(
                element_id="card-tmp",
                role="article",
                name="tmp",
                action_type="click",
                visible=True,
                context={
                    "collection_key": "workspace.agent_cards",
                    "collection_item_name": "tmp",
                    "collection_item_type": "自主规划 Agent",
                    "collection_item_status": "已发布",
                    "collection_actions": ["分析", "使用"],
                },
            ),
            ElementInfo(
                element_id="card-other",
                role="article",
                name="无插件智能体2",
                action_type="click",
                visible=True,
                context={
                    "collection_key": "workspace.agent_cards",
                    "collection_item_name": "无插件智能体2",
                    "collection_item_type": "自主规划 Agent",
                    "collection_item_status": "已发布",
                    "collection_actions": ["分析", "使用"],
                },
            ),
            ElementInfo(
                element_id="card-draft",
                role="article",
                name="draft-agent",
                action_type="click",
                visible=True,
                context={
                    "collection_key": "workspace.agent_cards",
                    "collection_item_name": "draft-agent",
                    "collection_item_type": "自主规划 Agent",
                    "collection_item_status": "草稿",
                    "collection_actions": ["编辑", "发布"],
                },
            ),
        ],
    )
    state = loop_service.LoopExplorationState(
        run_id="run-1",
        project_id="project-1",
        start_url=snapshot.url,
    )

    loop_service._enqueue_snapshot_candidates(state, snapshot, coverage={})

    assert [item.element_key for item in state.frontier] == ["article-tmp", "article-draft-agent"]


def test_enqueue_collection_candidates_skips_completed_group() -> None:
    snapshot = SnapshotResult(
        url="https://example.test/workspace",
        title="Workspace",
        state_signature="workspace-root",
        elements=[
            ElementInfo(
                element_id="card-tmp",
                role="article",
                name="tmp",
                action_type="click",
                visible=True,
                context={
                    "collection_key": "workspace.agent_cards",
                    "collection_item_name": "tmp",
                    "collection_item_type": "自主规划 Agent",
                    "collection_item_status": "已发布",
                    "collection_actions": ["分析", "使用"],
                },
            )
        ],
    )
    coverage = {
        "schema_version": "1.0",
        "pages": {
            "page-workspace": {
                "status": "partial",
                "collections": {
                    "workspace.agent_cards": {
                        "groups": {"自主规划 Agent:已发布": {"status": "completed"}}
                    }
                },
            }
        },
    }
    state = loop_service.LoopExplorationState(
        run_id="run-1",
        project_id="project-1",
        start_url=snapshot.url,
    )

    loop_service._enqueue_snapshot_candidates(state, snapshot, coverage=coverage)

    assert state.frontier == []


def test_collection_group_coverage_completes_only_after_all_representative_actions() -> None:
    state = loop_service.LoopExplorationState(
        run_id="run-1",
        project_id="project-1",
        start_url="https://example.test/workspace",
        discovered_elements={
            "button-analyze": {
                "element_key": "button-analyze",
                "name": "分析",
                "action_type": "click",
                "page_key": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "collection_group_key": "自主规划 Agent:已发布",
                "collection_representative": "tmp",
                "collection_actions": ["分析", "使用"],
            },
            "button-use": {
                "element_key": "button-use",
                "name": "使用",
                "action_type": "click",
                "page_key": "page-workspace",
                "collection_key": "workspace.agent_cards",
                "collection_group_key": "自主规划 Agent:已发布",
                "collection_representative": "tmp",
                "collection_actions": ["分析", "使用"],
            },
        },
    )

    pending = loop_service._collection_group_coverage_updates(
        state,
        [{"page_id": "page-workspace", "element_key": "button-analyze", "action": "click"}],
    )
    completed = loop_service._collection_group_coverage_updates(
        state,
        [
            {"page_id": "page-workspace", "element_key": "button-analyze", "action": "click"},
            {"page_id": "page-workspace", "element_key": "button-use", "action": "click"},
        ],
    )

    assert pending[0]["status"] == "pending"
    assert completed == [
        {
            "page_id": "page-workspace",
            "collection_key": "workspace.agent_cards",
            "group_key": "自主规划 Agent:已发布",
            "representative": "tmp",
            "status": "completed",
        }
    ]
