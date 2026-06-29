import json
from pathlib import Path
import inspect

from app.services.exploration import event_bus
from app.services.exploration import page_exploration_service
from app.api.v1 import page_exploration as page_exploration_api


def test_execute_exploration_async_invokes_deep_agent_with_user_message(monkeypatch) -> None:
    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["payload"] = payload
            return {"messages": []}

    def fake_page_exploration_agent(model, project_id, run_id):
        captured["agent_args"] = (model, project_id, run_id)
        return FakeAgent()

    class FakeConnection:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    updates = []

    monkeypatch.setattr(
        "app.agents.page_exploration.agent.page_exploration_agent",
        fake_page_exploration_agent,
    )
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())
    monkeypatch.setattr(
        page_exploration_service.exploration_run_repo,
        "update_status",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    import asyncio

    asyncio.run(
        page_exploration_service._execute_exploration_async(
            model="fake-model",
            project_id="project-1",
            run_id="run-1",
            start_url="https://www.cybotstar.cn/agentStore",
            max_pages=3,
            scope="工作台",
        )
    )

    assert captured["agent_args"] == ("fake-model", "project-1", "run-1")
    assert captured["payload"] == {
        "messages": [
            {
                "role": "user",
                "content": "请探索网站: https://www.cybotstar.cn/agentStore\n探索范围: 工作台\n最多探索 3 个页面。",
            }
        ]
    }
    assert "input" not in captured["payload"]
    assert updates


def test_invoke_agent_writes_event_log_and_passes_recursion_config(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class FakeAgent:
        async def astream_events(self, payload, **kwargs):
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            yield {
                "event": "on_tool_start",
                "name": "playwright_snap_tool",
                "run_id": "tool-run-1",
                "data": {"input": {"url": "https://example.test/workspace"}},
            }
            yield {
                "event": "on_tool_end",
                "name": "playwright_snap_tool",
                "run_id": "tool-run-1",
                "data": {"output": {"title": "工作台"}},
            }
            yield {
                "event": "on_chain_end",
                "name": "agent",
                "run_id": "agent-run-1",
                "data": {"output": {"messages": [{"content": "探索完成"}]}},
            }

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    event_bus.clear("run-log")

    import asyncio

    result = asyncio.run(
        page_exploration_service._invoke_agent_with_realtime_events(
            FakeAgent(),
            {"messages": [{"role": "user", "content": "探索工作台"}]},
            "run-log",
            page_exploration_service._initial_exploration_plan_steps("https://example.test/workspace", 3),
            project_id="project-1",
            max_pages=3,
        )
    )

    assert result["messages"][0]["content"] == "探索完成"
    assert captured["kwargs"]["version"] == "v2"
    assert captured["kwargs"]["config"]["recursion_limit"] >= 100

    events_path = tmp_path / "project-1" / "page_exploration" / "runs" / "run-log" / "events.jsonl"
    assert events_path.exists()
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    assert [event["type"] for event in events] == [
        "agent_step_started",
        "agent_stream_event",
        "agent_stream_event",
        "agent_stream_event",
        "agent_step_completed",
    ]
    assert events[1]["payload"]["event"] == "on_tool_start"


def test_execute_exploration_async_publishes_realtime_events(monkeypatch) -> None:
    class FakeAgent:
        async def ainvoke(self, payload):
            return {"messages": [{"content": "探索完成，发现工作台入口。"}]}

    def fake_page_exploration_agent(model, project_id, run_id):
        return FakeAgent()

    class FakeConnection:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.agents.page_exploration.agent.page_exploration_agent",
        fake_page_exploration_agent,
    )
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())
    monkeypatch.setattr(
        page_exploration_service.exploration_run_repo,
        "update_status",
        lambda *args, **kwargs: None,
    )

    event_bus.clear("run-events")

    import asyncio

    async def run_and_collect():
        await page_exploration_service._execute_exploration_async(
            model="fake-model",
            project_id="project-1",
            run_id="run-events",
            start_url="https://www.cybotstar.cn/agentStore",
            max_pages=3,
            scope="工作台",
        )
        collected = []
        async for event in event_bus.subscribe("run-events"):
            collected.append(event)
            if event["type"] == "run_completed":
                break
        return collected

    events = asyncio.run(run_and_collect())
    event_types = [event["type"] for event in events]

    assert "planning_completed" in event_types
    assert "step_started" in event_types
    assert "step_completed" in event_types
    assert event_types[-1] == "run_completed"
    assert any(event["payload"].get("message") == "探索完成，发现工作台入口。" for event in events)


def test_exploration_start_url_uses_environment_site_url_not_scope() -> None:
    assert (
        page_exploration_service._exploration_start_url(
            {
                "environment_site_url": "https://www.cybotstar.cn/agentStore",
                "scope": "工作台",
            }
        )
        == "https://www.cybotstar.cn/agentStore"
    )


def test_exploration_start_url_requires_configured_environment_url() -> None:
    import pytest

    with pytest.raises(ValueError, match="环境站点入口 URL"):
        page_exploration_service._exploration_start_url({"scope": "工作台"})


def test_event_bus_replays_history_and_delivers_live_events() -> None:
    event_bus.clear("run-bus")
    event_bus.publish("run-bus", "planning_completed", {"plan_id": "plan-1"})

    import asyncio

    async def collect_events():
        subscription = event_bus.subscribe("run-bus")
        first = await subscription.__anext__()
        event_bus.publish("run-bus", "step_started", {"step_id": "step-1"})
        second = await subscription.__anext__()
        await subscription.aclose()
        return first, second

    first, second = asyncio.run(collect_events())
    assert first["type"] == "planning_completed"
    assert second["type"] == "step_started"


def test_exploration_stream_does_not_cancel_event_bus_subscription() -> None:
    source = inspect.getsource(page_exploration_api.stream_exploration_progress)

    assert "event_task.cancel()" not in source
    assert "pump_events" in source


def test_modules_from_artifacts_builds_frontend_progress_when_db_pages_are_empty(tmp_path: Path) -> None:
    run_dir = tmp_path / "project-1" / "exploration" / "explore-1"
    live_dir = run_dir / "live"
    live_dir.mkdir(parents=True)

    (live_dir / "state.json").write_text(
        json.dumps(
            {
                "artifact_schema_version": 2,
                "summary": {
                    "modules": [
                        {
                            "module_key": "planned-01",
                            "module_name": "工作台模块",
                            "status": "running",
                            "planned_page_count": 2,
                            "explored_page_count": 1,
                            "action_count": 3,
                            "entry_path": "工作台",
                        }
                    ]
                },
                "pages": [
                    {
                        "file_path": "live/pages/page-001.yaml",
                        "page_url": "https://example.test/workspace",
                        "title": "百融百工",
                        "content": {
                            "page": {
                                "id": "page-001",
                                "semantic_title": "工作台",
                                "title": "百融百工",
                                "url": "https://example.test/workspace",
                                "normalized_url": "/workspace",
                                "module": "工作台",
                                "status": "explored",
                                "structure_summary": "发现工作台卡片。",
                            },
                            "steps": [
                                {
                                    "id": "step-001",
                                    "type": "click",
                                    "title": "创建按钮",
                                    "detail": "打开创建弹窗。",
                                    "status": "completed",
                                }
                            ],
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    modules = page_exploration_service._modules_from_artifacts(
        {
            "id": "explore-1",
            "status": "running",
            "scope": "工作台",
            "artifact_root": str(run_dir),
            "result_summary": "正在探索。",
        }
    )

    assert len(modules) == 1
    assert modules[0]["module_key"] == "planned-01"
    assert modules[0]["module_name"] == "工作台模块"
    assert modules[0]["completion_status"] == "running"
    assert modules[0]["explored_page_count"] == 1
    assert modules[0]["pages"][0]["title"] == "工作台"
    assert modules[0]["pages"][0]["steps"][0]["title"] == "创建按钮"
