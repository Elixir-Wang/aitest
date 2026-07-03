import json
from contextlib import nullcontext
from pathlib import Path
import inspect

import pytest

from app.services.exploration import event_bus
from app.services.exploration import page_exploration_service
from app.api.v1 import page_exploration as page_exploration_api


def test_execute_exploration_async_invokes_deep_agent_with_user_message(monkeypatch) -> None:
    captured = {}

    class FakeAgent:
        async def astream(self, payload, **kwargs):
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            yield ("values", {"messages": []})

    def fake_page_exploration_agent(model, tools=None, skill_names=None, max_actions=80):
        captured["agent_args"] = (model, tools, skill_names, max_actions)
        return FakeAgent()

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            return self

        def fetchone(self):
            return {"status": "running"}

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
    monkeypatch.setattr(
        "app.agents.page_exploration.tools.runtime_context.browser_session_context",
        lambda **_kwargs: nullcontext(),
    )

    import asyncio

    asyncio.run(
        page_exploration_service._execute_exploration_async(
            model="fake-model",
            project_id="project-1",
            run_id="run-1",
            start_url="https://www.cybotstar.cn/agentStore",
            exploration_mode="goal",
            max_pages=3,
            scope="工作台",
            goal="进入工作台，新建自主规划agent，随机输入名称，进入草稿页面，调试预览对话框输入hi",
        )
    )

    assert captured["agent_args"][0] == "fake-model"
    assert captured["agent_args"][3] == max(40, min(int(3) * 6, 200))  # max_actions 计算正确
    assert captured["payload"] == {
        "messages": [
            {
                "role": "user",
                "content": (
                    "请探索网站: https://www.cybotstar.cn/agentStore\n"
                    "探索方式: 目标探索\n"
                    "探索范围: 工作台\n"
                    "探索目标: 进入工作台，新建自主规划agent，随机输入名称，进入草稿页面，调试预览对话框输入hi\n"
                    "\n"
                    "执行策略:\n"
                    "- 这是目标探索：以探索目标为主线和完成条件，优先执行目标描述的页面流程。\n"
                    "- 不要扩展为全量功能盘点；只探索完成目标所必需的页面、弹窗、字段和状态。\n"
                    "- 目标完成、被阻塞或达到预算上限后停止并总结，不要继续无关分支。\n"
                    "最多探索 3 个页面。"
                ),
            }
        ]
    }


def test_execute_exploration_disables_thinking_for_supported_models(monkeypatch) -> None:
    captured = {}

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["selection"] = selection
        captured["extra_body"] = extra_body
        return "fake-model"

    async def fake_execute_exploration_async(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "app.agents.model_selection.resolve_model_selection",
        lambda capability_id: captured.setdefault("capability_id", capability_id) or "selection",
    )
    monkeypatch.setattr(
        "app.agents.model_selection.thinking_disabled_extra_body",
        lambda selection: {"thinking": {"type": "disabled"}},
    )
    monkeypatch.setattr("app.agents.model_selection.build_agent_model", fake_build_agent_model)
    monkeypatch.setattr(page_exploration_service, "_execute_exploration_async", fake_execute_exploration_async)

    page_exploration_service._execute_exploration(
        "run-1",
        {
            "project_id": "project-1",
            "environment_site_url": "https://www.cybotstar.cn/agentStore",
            "scope": "工作台",
            "goal": "登录",
            "exploration_mode": "goal",
            "max_pages": 3,
        },
    )

    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}
    assert captured["capability_id"] == page_exploration_service.CAPABILITY_ID
    assert captured["model"] == "fake-model"
    assert captured["kwargs"]["project_id"] == "project-1"
    assert captured["kwargs"]["run_id"] == "run-1"


def test_exploration_agent_prompt_distinguishes_goal_and_autonomous_modes() -> None:
    goal_prompt = page_exploration_service._exploration_agent_prompt(
        "https://example.test/agentStore",
        "goal",
        "工作台",
        5,
        goal="新建自主规划 agent 并在预览对话框输入 hi",
    )
    autonomous_prompt = page_exploration_service._exploration_agent_prompt(
        "https://example.test/agentStore",
        "autonomous",
        "工作台",
        5,
        goal="重点关注创建、配置、对话能力",
    )

    assert "探索目标: 新建自主规划 agent 并在预览对话框输入 hi" in goal_prompt
    assert "以探索目标为主线和完成条件" in goal_prompt
    assert "不要扩展为全量功能盘点" in goal_prompt
    assert "以探索范围为覆盖边界" in autonomous_prompt
    assert "它只是补充关注点，不作为单一路径完成条件" in autonomous_prompt


def test_invoke_agent_writes_timeline_and_raw_logs_from_projection_stream(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class FakeAgent:
        async def astream(self, payload, **kwargs):
            captured["payload"] = payload
            captured["kwargs"] = kwargs
            yield ("updates", {"agent": {"messages": [{"content": "", "tool_calls": [{"id": "tool-run-1", "name": "playwright_snap_tool", "args": {"url": "https://example.test/workspace"}}]}]}})
            yield ("updates", {"tools": {"messages": [{"type": "tool", "tool_call_id": "tool-run-1", "name": "playwright_snap_tool", "content": json.dumps({"title": "工作台", "url": "https://example.test/workspace"}, ensure_ascii=False)}]}})
            yield ("values", {"messages": [{"content": "探索完成"}]})

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
    assert captured["kwargs"]["stream_mode"] == ["updates", "messages", "values"]
    assert captured["kwargs"]["config"]["recursion_limit"] >= 100

    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-log"
    timeline_path = run_dir / "timeline_events.jsonl"
    raw_path = run_dir / "raw_events.jsonl"
    assert timeline_path.exists()
    assert raw_path.exists()
    timeline_events = [json.loads(line) for line in timeline_path.read_text(encoding="utf-8").splitlines()]
    raw_events = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    assert [event["type"] for event in timeline_events] == [
        "agent_step_started",
        "agent_tool_started",
        "agent_tool_completed",
    ]
    assert timeline_events[1]["display"]["title"] == "采集页面快照"
    assert all(event.get("display") for event in timeline_events)
    assert raw_events[0]["type"] == "agent_projection_event"
    assert raw_events[0]["payload"]["mode"] == "updates"


def test_agent_stream_events_carry_timeline_event_id_for_dedup(monkeypatch, tmp_path: Path) -> None:
    """Live SSE events must share an id with the persisted timeline entry.

    Without this, every live ``agent_thought``/``agent_tool_*`` event is
    re-emitted by the next ``run_snapshot`` (which carries the persisted
    timeline) and the frontend chat panel ends up rendering every agent
    message twice.
    """
    class FakeAgent:
        async def astream(self, payload, **kwargs):
            yield (
                "updates",
                {
                    "agent": {
                        "messages": [
                            {
                                "id": "msg-1",
                                "type": "ai",
                                "content": "我来开始探索这个网站。",
                                "tool_calls": [
                                    {
                                        "id": "tool-run-1",
                                        "name": "playwright_snap_tool",
                                        "args": {"url": "https://example.test/workspace"},
                                    }
                                ],
                            }
                        ]
                    }
                },
            )
            yield (
                "updates",
                {
                    "tools": {
                        "messages": [
                            {
                                "type": "tool",
                                "tool_call_id": "tool-run-1",
                                "name": "playwright_snap_tool",
                                "content": json.dumps(
                                    {"title": "工作台", "url": "https://example.test/workspace"},
                                    ensure_ascii=False,
                                ),
                            }
                        ]
                    }
                },
            )
            yield ("values", {"messages": [{"content": "探索完成"}]})

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    run_id = "run-dedup"
    event_bus.clear(run_id)

    import asyncio

    asyncio.run(
        page_exploration_service._invoke_agent_with_realtime_events(
            FakeAgent(),
            {"messages": [{"role": "user", "content": "探索工作台"}]},
            run_id,
            page_exploration_service._initial_exploration_plan_steps("https://example.test/workspace", 3),
            project_id="project-1",
            max_pages=3,
        )
    )

    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / run_id
    timeline_events = [
        json.loads(line)
        for line in (run_dir / "timeline_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    bus_events = event_bus.get_history(run_id)

    # The first entry is the lifecycle ``step_started`` from
    # ``_invoke_agent_with_realtime_events`` which never went through the
    # streaming loop's persisted_log.call, so it is allowed to lack a
    # matching timeline_event_id.
    persisted_ids = {event["event_id"] for event in timeline_events}

    # Every streaming-loop publisher must tag the live SSE message with the
    # same event_id the timeline log wrote, so frontend dedup can collapse
    # the live entry with the snapshot replay of the same entry.
    stream_only = [
        event
        for event in bus_events
        if event["type"]
        not in {"step_started", "run_status_updated", "run_started", "run_completed", "run_failed", "run_cancelled"}
    ]
    assert stream_only, "expected streaming-loop events to be captured in bus history"
    for event in stream_only:
        assert event.get("timeline_event_id"), f"missing timeline_event_id on {event['type']}: {event}"
        assert event["timeline_event_id"] in persisted_ids, (
            f"timeline_event_id {event['timeline_event_id']} from live event does not match any persisted event_id"
        )

    # Also verify the agent_thought entry that the user complained about is
    # actually published at all.
    thought_events = [event for event in stream_only if event["type"] == "agent_thought"]
    assert thought_events, "expected at least one agent_thought to be published live"
    for event in thought_events:
        assert event["timeline_event_id"] in persisted_ids


def test_cancelled_agent_run_does_not_write_terminal_timeline_event(monkeypatch, tmp_path: Path) -> None:
    class FakeAgent:
        async def astream(self, payload, **kwargs):
            yield ("values", {"messages": [{"content": "探索完成"}]})

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            return self

        def fetchone(self):
            return {"status": "cancelled"}

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())

    event_bus.clear("run-cancelled")

    import asyncio

    with pytest.raises(page_exploration_service.ExplorationCancelledError):
        asyncio.run(
            page_exploration_service._invoke_agent_with_realtime_events(
                FakeAgent(),
                {"messages": [{"role": "user", "content": "探索工作台"}]},
                "run-cancelled",
                page_exploration_service._initial_exploration_plan_steps("https://example.test/workspace", 3),
                project_id="project-1",
                max_pages=3,
            )
        )

    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-cancelled"
    timeline_events = [
        json.loads(line)
        for line in (run_dir / "timeline_events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["type"] for event in timeline_events] == [
        "agent_step_started",
    ]
    serialized_events = json.dumps(timeline_events, ensure_ascii=False)
    assert "页面探索已停止" not in serialized_events
    assert "页面探索失败" not in json.dumps(timeline_events, ensure_ascii=False)
    assert "页面探索 Agent 执行失败" not in json.dumps(timeline_events, ensure_ascii=False)
    assert all(event["type"] != "step_failed" for event in event_bus.get_history("run-cancelled"))


def test_exploration_detail_reads_persisted_timeline_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-log"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "timeline_events.jsonl"
    events_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_id": "evt-000001",
                        "run_id": "run-log",
                        "type": "agent_tool_started",
                        "payload": {"tool_name": "playwright_click_tool"},
                        "display": {"kind": "click", "title": "点击元素", "summary": "点击 登录"},
                        "occurred_at": "2026-07-01T02:14:07+00:00",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "event_id": "evt-000002",
                        "run_id": "run-log",
                        "type": "agent_tool_completed",
                        "payload": {"tool_name": "playwright_click_tool"},
                        "display": {"kind": "click", "title": "点击元素", "summary": "点击 登录完成"},
                        "occurred_at": "2026-07-01T02:14:08+00:00",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    events = page_exploration_service._read_recent_timeline_events(
        {"project_id": "project-1", "id": "run-log"}
    )

    assert [event["event_id"] for event in events] == ["evt-000001", "evt-000002"]
    assert events[0]["payload"]["tool_name"] == "playwright_click_tool"
    assert events[0]["display"]["summary"] == "点击 登录"


def test_invoke_agent_checkpoints_snapshot_as_page_artifact(monkeypatch, tmp_path: Path) -> None:
    class FakeAgent:
        async def astream(self, payload, **kwargs):
            snapshot = {
                "url": "https://example.test/workspace?tab=agents",
                "title": "工作台",
                "elements": [
                    {
                        "ref": "button-create-001",
                        "role": "button",
                        "name": "创建智能体",
                        "text": "创建智能体",
                        "visible": True,
                    }
                ],
                "accessibility_tree": [
                    {"id": "ax-1", "role": "button", "name": "创建智能体"},
                    {"id": "ax-2", "role": "text", "name": "自主规划 Agent"},
                    {"id": "ax-3", "role": "text", "name": "Multi-Agent"},
                ],
                "visible_text_blocks": ["创建智能体", "自主规划 Agent", "Multi-Agent"],
                "error": None,
            }
            yield (
                "updates",
                {
                    "tools": {
                        "messages": [
                            {
                                "type": "tool",
                                "tool_call_id": "tool-run-1",
                                "name": "playwright_snap_tool",
                                "content": json.dumps(snapshot, ensure_ascii=False),
                            }
                        ]
                    }
                },
            )
            yield ("values", {"messages": [{"content": "探索完成"}]})

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            return self

        def fetchone(self):
            return {"status": "running"}

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())

    import asyncio

    asyncio.run(
        page_exploration_service._invoke_agent_with_realtime_events(
            FakeAgent(),
            {"messages": [{"role": "user", "content": "探索工作台"}]},
            "run-checkpoint",
            page_exploration_service._initial_exploration_plan_steps("https://example.test/workspace", 3),
            project_id="project-1",
            max_pages=3,
        )
    )

    page_path = (
        tmp_path
        / "project-1"
        / "page_exploration"
        / "runs"
        / "run-checkpoint"
        / "pages"
        / "page-workspace-tab-agents.yaml"
    )
    assert page_path.exists()
    import yaml

    data = yaml.safe_load(page_path.read_text(encoding="utf-8"))
    assert data["page"]["id"] == "page-workspace-tab-agents"
    assert data["page"]["url"] == "https://example.test/workspace?tab=agents"
    assert data["page"]["elements"][0]["locators"][0]["code"] == "getByRole('button', { name: '创建智能体' })"
    assert data["page"]["accessibility_tree"][1]["name"] == "自主规划 Agent"
    assert "Multi-Agent" in data["page"]["visible_text_blocks"]
    assert data["states"][0]["accessibility_tree"][2]["name"] == "Multi-Agent"
    assert "raw_output" not in data["states"][0]


def test_snapshot_checkpoint_registers_visible_artifact(monkeypatch, tmp_path: Path) -> None:
    calls = {
        "roots": [],
        "pages": [],
        "artifacts": [],
    }

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            if "UPDATE exploration_runs SET artifact_root" in sql:
                calls["roots"].append(params)
            elif "INSERT INTO exploration_pages" in sql:
                calls["pages"].append(params)
            elif "INSERT INTO exploration_artifacts" in sql:
                calls["artifacts"].append(params)
            return self

    event = {
        "event": "on_tool_end",
        "name": "playwright_snap_tool",
        "data": {
            "output": {
                "url": "https://example.test/workspace",
                "title": "工作台",
                "elements": [
                    {
                        "ref": "button-create-001",
                        "role": "button",
                        "name": "创建智能体",
                        "visible": True,
                    }
                ],
            }
        },
    }

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())

    path = page_exploration_service._checkpoint_snapshot_artifact_from_event(
        event,
        project_id="project-1",
        run_id="run-checkpoint",
    )

    assert path is not None
    assert calls["roots"][0][0] == str(tmp_path / "project-1" / "page_exploration" / "runs" / "run-checkpoint")
    assert calls["pages"][0][0] == "page-workspace"
    assert calls["artifacts"][0][0] == "run-checkpoint-page-workspace-yaml"
    assert calls["artifacts"][0][2] == "page_yaml"
    assert calls["artifacts"][0][3] == str(tmp_path / "project-1" / "page_exploration" / "pages" / "page-workspace.yaml")
    assert (tmp_path / "project-1" / "page_exploration" / "pages" / "page-workspace.yaml").exists()


def test_repeated_snapshot_checkpoints_create_separate_visible_artifacts(monkeypatch, tmp_path: Path) -> None:
    """同 URL 重复 snap 不再序号化创建多个 artifact 文件，而是覆盖最新。

    设计变更：原实现 `_unique_snapshot_artifact_path` 序号化生成
    `page-workspace-2.yaml` / `-3.yaml`... 是当前 bug 的直接源头。
    新实现：同 URL 写同一文件，最新快照胜出。第二个 artifact_id
    入库但 yaml 路径覆盖原文件。
    """
    artifact_paths = []
    artifact_ids = []

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            if "INSERT INTO exploration_artifacts" in sql:
                artifact_ids.append(params[0])
                if len(params) > 1:
                    artifact_paths.append(params[1])
            return self

    event = {
        "event": "on_tool_end",
        "name": "playwright_snap_tool",
        "data": {
            "output": {
                "url": "https://example.test/workspace",
                "title": "工作台",
                "elements": [],
            }
        },
    }

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())

    first = page_exploration_service._checkpoint_snapshot_artifact_from_event(
        event,
        project_id="project-1",
        run_id="run-checkpoint",
    )
    second = page_exploration_service._checkpoint_snapshot_artifact_from_event(
        event,
        project_id="project-1",
        run_id="run-checkpoint",
    )

    assert first is not None
    assert second is not None
    # 同 URL 覆盖最新：两个返回同一文件
    assert first == second
    # 数据库仍记录两次写入（用于审计）
    assert len(artifact_ids) == 2


def test_execute_exploration_async_publishes_realtime_events(monkeypatch) -> None:
    class FakeAgent:
        async def astream(self, payload, **kwargs):
            yield ("values", {"messages": [{"content": "探索完成，发现工作台入口。"}]})

    def fake_page_exploration_agent(model, tools=None, skill_names=None, max_actions=80):
        return FakeAgent()

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            return self

        def fetchone(self):
            return {"status": "running"}

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
            exploration_mode="goal",
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
    assert not any(event["payload"].get("message") == "探索完成，发现工作台入口。" for event in events)
    assert events[-1]["payload"].get("status") == "completed"


def test_execute_exploration_async_does_not_complete_after_stop(monkeypatch) -> None:
    class FakeAgent:
        async def astream(self, payload, **kwargs):
            yield ("values", {"messages": [{"content": "探索完成。"}]})

    def fake_page_exploration_agent(model, tools=None, skill_names=None, max_actions=80):
        return FakeAgent()

    class FakeRun:
        def __init__(self, status: str):
            self.status = status

        def __getitem__(self, key):
            if key == "status":
                return self.status
            raise KeyError(key)

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            return self

    statuses = iter(["running", "stopping"])
    updates = []

    monkeypatch.setattr(
        "app.agents.page_exploration.agent.page_exploration_agent",
        fake_page_exploration_agent,
    )
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())
    monkeypatch.setattr(
        page_exploration_service.exploration_run_repo,
        "find_by_id",
        lambda db, run_id: FakeRun(next(statuses, "stopping")),
    )
    monkeypatch.setattr(
        page_exploration_service.exploration_run_repo,
        "update_status",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    import asyncio

    with pytest.raises(page_exploration_service.ExplorationCancelledError):
        asyncio.run(
            page_exploration_service._execute_exploration_async(
                model="fake-model",
                project_id="project-1",
                run_id="run-stop",
                start_url="https://www.cybotstar.cn/agentStore",
                exploration_mode="goal",
                max_pages=3,
                scope="工作台",
            )
        )

    assert not any(args[2] == "completed" for args, _kwargs in updates)


def test_stop_exploration_async_finalizes_cancelled_and_closes_stream(monkeypatch) -> None:
    class FakeRun(dict):
        pass

    class FakeConnection:
        closed = False

        def __enter__(self):
            self.closed = False
            return self

        def __exit__(self, exc_type, exc, tb):
            self.closed = True
            return False

    updated_statuses = []
    published_events = []
    closed_runs = []
    run = FakeRun({"id": "run-stop", "status": "running"})

    def fake_find_by_id(db, run_id):
        if db.closed:
            raise RuntimeError("database connection is closed")
        return run

    def fake_update_status(db, run_id, status, **kwargs):
        updated_statuses.append((run_id, status, kwargs))
        run["status"] = status
        run.update(kwargs)

    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())
    monkeypatch.setattr(page_exploration_service.exploration_run_repo, "find_by_id", fake_find_by_id)
    monkeypatch.setattr(page_exploration_service.exploration_run_repo, "update_status", fake_update_status)
    monkeypatch.setattr(page_exploration_service.event_bus, "publish", lambda *args: published_events.append(args))
    monkeypatch.setattr(page_exploration_service.event_bus, "close", lambda run_id: closed_runs.append(run_id))

    result = page_exploration_service.stop_exploration_async(actor={}, run_id="run-stop")

    assert result["status"] == "cancelled"
    assert updated_statuses[0][1] == "cancelled"
    assert updated_statuses[0][2]["result_summary"] == "探索任务已由用户停止。"
    assert published_events[0][1] == "run_cancelled"
    assert closed_runs == ["run-stop"]


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


def test_exploration_auth_state_path_uses_valid_environment_state(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "environments" / "env-1" / "auth" / "storage-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"cookies": [{"name": "sid"}], "origins": []}), encoding="utf-8")

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    assert page_exploration_service._exploration_auth_state_path(
        {
            "environment_id": "env-1",
            "environment_login_strategy": "account_password",
            "environment_reuse_auth_state": 1,
        }
    ) == state_path


def test_exploration_auth_state_path_ignores_run_login_strategy(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "environments" / "env-1" / "auth" / "storage-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"cookies": [{"name": "sid"}], "origins": []}), encoding="utf-8")

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    assert page_exploration_service._exploration_auth_state_path(
        {
            "environment_id": "env-1",
            "login_strategy": "skip_login",
            "environment_login_strategy": "account_password",
            "environment_reuse_auth_state": 1,
        }
    ) == state_path


def test_exploration_auth_state_path_requires_reuse_enabled(monkeypatch, tmp_path: Path) -> None:
    state_path = tmp_path / "environments" / "env-1" / "auth" / "storage-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"cookies": [{"name": "sid"}], "origins": []}), encoding="utf-8")

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    assert page_exploration_service._exploration_auth_state_path(
        {
            "environment_id": "env-1",
            "environment_login_strategy": "account_password",
            "environment_reuse_auth_state": 0,
        }
    ) is None


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


def test_event_bus_can_skip_history_replay_for_snapshot_streams() -> None:
    event_bus.clear("run-bus-no-replay")
    event_bus.publish("run-bus-no-replay", "planning_completed", {"plan_id": "plan-1"})

    import asyncio

    async def collect_events():
        subscription = event_bus.subscribe("run-bus-no-replay", replay=False)
        pending = asyncio.create_task(subscription.__anext__())
        await asyncio.sleep(0)
        event_bus.publish("run-bus-no-replay", "step_started", {"step_id": "step-1"})
        first = await pending
        await subscription.aclose()
        return first

    first = asyncio.run(collect_events())
    assert first["type"] == "step_started"


def test_event_bus_close_all_wakes_active_subscribers() -> None:
    event_bus.clear()

    import asyncio

    async def wait_for_shutdown() -> bool:
        subscription = event_bus.subscribe("run-shutdown")
        task = asyncio.create_task(subscription.__anext__())
        await asyncio.sleep(0)
        event_bus.close_all()
        try:
            await task
        except StopAsyncIteration:
            return True
        finally:
            await subscription.aclose()
        return False

    assert asyncio.run(wait_for_shutdown())


def test_projection_tool_events_publish_readable_whitelisted_sse_payloads() -> None:
    tool_inputs: dict[str, dict] = {}

    started = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "agent": {
                "messages": [
                    {
                        "tool_calls": [
                            {
                                "id": "tool-run-1",
                                "name": "playwright_click_tool",
                                "args": {"locator": "button-login-1"},
                            }
                        ]
                    }
                ]
            }
        },
        raw_event_id="evt-000001",
        tool_inputs=tool_inputs,
    )
    completed = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "tools": {
                "messages": [
                    {
                        "type": "tool",
                        "tool_call_id": "tool-run-1",
                        "name": "playwright_click_tool",
                        "content": json.dumps({"success": True, "raw_output": "very long debug output"}, ensure_ascii=False),
                    }
                ]
            }
        },
        raw_event_id="evt-000002",
        tool_inputs=tool_inputs,
    )

    events = started + completed

    assert [event["type"] for event in events] == ["agent_tool_started", "agent_tool_completed"]
    assert events[0]["payload"]["step_id"] == events[1]["payload"]["step_id"]
    assert events[0]["payload"]["step_id"] == "agent-tool-tool-run-1"
    assert events[0]["payload"]["tool_name"] == "playwright_click_tool"
    assert events[0]["display"]["kind"] == "click"
    assert events[1]["display"]["kind"] == "click"
    forbidden_payload_keys = {
        "debug_ref",
        "duration_ms",
        "input",
        "messages",
        "output",
        "raw_output",
        "response_metadata",
    }
    assert forbidden_payload_keys.isdisjoint(events[0]["payload"])
    assert forbidden_payload_keys.isdisjoint(events[1]["payload"])
    assert "very long debug output" not in json.dumps(events, ensure_ascii=False)


def test_projection_write_todos_only_completed_updates_plan_without_transcript_display() -> None:
    tool_inputs: dict[str, dict] = {}
    started = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "agent": {
                "messages": [
                    {
                        "tool_calls": [
                            {
                                "id": "todo-run-1",
                                "name": "write_todos",
                                "args": {
                                    "todos": [
                                        {"content": "打开工作台", "status": "completed"},
                                        {"content": "点击创建智能体", "status": "in_progress"},
                                        {"content": "发送对话并等待回复", "status": "pending"},
                                    ]
                                },
                            }
                        ]
                    }
                ]
            }
        },
        raw_event_id="evt-000004",
        tool_inputs=tool_inputs,
    )
    completed = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "tools": {
                "messages": [
                    {
                        "type": "tool",
                        "tool_call_id": "todo-run-1",
                        "name": "write_todos",
                        "content": json.dumps({"success": True}, ensure_ascii=False),
                    }
                ]
            }
        },
        raw_event_id="evt-000005",
        tool_inputs=tool_inputs,
    )

    assert started == []
    events = completed
    assert [event["type"] for event in events] == ["agent_plan_updated"]
    assert events[0]["payload"]["tool_name"] == "write_todos"
    assert events[0]["payload"]["plan_steps"] == [
        {
            "step_id": "agent-todo-1",
            "step_number": 1,
            "description": "打开工作台",
            "status": "completed",
            "action_type": "todo",
            "execution_strategy": "agent_plan",
        },
        {
            "step_id": "agent-todo-2",
            "step_number": 2,
            "description": "点击创建智能体",
            "status": "in_progress",
            "action_type": "todo",
            "execution_strategy": "agent_plan",
        },
        {
            "step_id": "agent-todo-3",
            "step_number": 3,
            "description": "点击发送按钮发送对话并等待回复",
            "status": "pending",
            "action_type": "todo",
            "execution_strategy": "agent_plan",
        },
    ]
    assert "display" not in events[0]


def test_projection_skips_messages_already_seen_in_cumulative_updates() -> None:
    seen_projection_keys: set[str] = set()
    first = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "agent": {
                "messages": [
                    {
                        "id": "msg-1",
                        "content": "已进入工作台，下一步查找创建智能体入口。",
                    }
                ]
            }
        },
        raw_event_id="evt-000006",
        tool_inputs={},
        seen_projection_keys=seen_projection_keys,
    )
    second = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "agent": {
                "messages": [
                    {
                        "id": "msg-1",
                        "content": "已进入工作台，下一步查找创建智能体入口。",
                    },
                    {
                        "id": "msg-2",
                        "content": "现在点击创建智能体。",
                    },
                ]
            }
        },
        raw_event_id="evt-000007",
        tool_inputs={},
        seen_projection_keys=seen_projection_keys,
    )

    assert [event["display"]["summary"] for event in first] == ["已进入工作台，下一步查找创建智能体入口。"]
    assert [event["display"]["summary"] for event in second] == ["现在点击创建智能体。"]


def test_projection_assistant_messages_publish_public_thought_events() -> None:
    events = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "agent": {
                "messages": [
                    {
                        "content": "已进入工作台，下一步查找创建智能体入口。",
                    }
                ]
            }
        },
        raw_event_id="evt-000003",
        tool_inputs={},
    )

    assert [event["type"] for event in events] == ["agent_thought"]
    assert events[0]["payload"]["status"] == "completed"
    assert events[0]["display"] == {
        "kind": "thought",
        "title": "Agent",
        "summary": "已进入工作台，下一步查找创建智能体入口。",
    }


def test_projection_assistant_messages_strip_private_thinking() -> None:
    events = page_exploration_service._projection_chunk_to_timeline_events(
        "updates",
        {
            "agent": {
                "messages": [
                    {
                        "content": "<think>secret selector guess</think>\n已完成页面观察，准备点击工作台。",
                    }
                ]
            }
        },
        raw_event_id="evt-000004",
        tool_inputs={},
    )

    assert len(events) == 1
    assert events[0]["display"]["summary"] == "已完成页面观察，准备点击工作台。"
    assert "secret selector guess" not in json.dumps(events, ensure_ascii=False)


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


def test_modules_from_db_pages_preserves_module_grouping() -> None:
    modules = page_exploration_service._modules_from_db_pages(
        {
            "id": "run-1",
            "status": "completed",
            "scope": "全部",
            "max_pages": 5,
            "result_summary": "探索完成。",
        },
        [
            {
                "id": "page-workspace",
                "module_key": "工作台",
                "title": "工作台首页",
                "url": "https://example.test/workspace",
                "entry_path": "/workspace",
                "snapshot_path": "/tmp/page-workspace.yaml",
                "structure_summary": "发现工作台入口。",
            },
            {
                "id": "page-users",
                "module_key": "用户管理",
                "title": "用户列表",
                "url": "https://example.test/users",
                "entry_path": "/users",
                "snapshot_path": "/tmp/page-users.yaml",
                "structure_summary": "发现用户列表。",
            },
        ],
    )

    assert [module["module_key"] for module in modules] == ["工作台", "用户管理"]
    assert modules[0]["explored_page_count"] == 1
    assert modules[0]["pages"][0]["yaml_path"] == "/tmp/page-workspace.yaml"
    assert modules[1]["pages"][0]["title"] == "用户列表"


def test_list_project_pages_reads_project_shared_pages(monkeypatch, tmp_path: Path) -> None:
    page_root = tmp_path / "project-1" / "page_exploration"
    project_pages = page_root / "pages"
    project_pages.mkdir(parents=True)
    (project_pages / "page-workspace.yaml").write_text(
        """
page:
  id: page-workspace
  title: 工作台首页
  display_name: workspace
  breadcrumb:
    - workspace
  normalized_path: /workspace
  structure_summary: 发现工作台入口。
  last_explored:
    run_id: run-1
    timestamp: '2026-07-02T11:34:59Z'
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    rows = page_exploration_service.list_project_pages(actor={"id": "u-1"}, project_id="project-1")

    assert rows == [
        {
            "id": "page-workspace",
            "exploration_run_id": "run-1",
            "module_key": "",
            "title": "工作台首页",
            "display_name": "workspace",
            "breadcrumb": ["workspace"],
            "url": "",
            "entry_path": "/workspace",
            "structure_summary": "发现工作台入口。",
            "screenshot_path": "",
            "snapshot_path": str(page_root / "pages" / "page-workspace.yaml"),
            "trace_path": "",
            "created_at": "2026-07-02T11:34:59Z",
            "updated_at": "2026-07-02T11:34:59Z",
        }
    ]


def test_get_project_page_yaml_content_reads_shared_page_yaml(monkeypatch, tmp_path: Path) -> None:
    page_root = tmp_path / "project-1" / "page_exploration"
    project_pages = page_root / "pages"
    project_pages.mkdir(parents=True)
    yaml_content = "page:\n  id: page-workspace\n  title: 工作台首页\n"
    (project_pages / "page-workspace.yaml").write_text(yaml_content, encoding="utf-8")

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

    result = page_exploration_service.get_project_page_yaml_content(
        actor={"id": "u-1"},
        project_id="project-1",
        page_id="page-workspace",
    )

    assert result == {
        "page_id": "page-workspace",
        "file_name": "page-workspace.yaml",
        "file_path": str(project_pages / "page-workspace.yaml"),
        "content": yaml_content,
    }


def test_register_exploration_outputs_indexes_page_and_report(monkeypatch, tmp_path: Path) -> None:
    page_root = tmp_path / "project-1" / "page_exploration"
    pages_dir = page_root / "runs" / "run-1" / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page-workspace.yaml").write_text(
        """
page:
  id: page-workspace
  title: 工作台
  url: https://example.test/workspace
  normalized_url: /workspace
  module: 工作台
  structure_summary: 发现工作台入口。
states:
  - id: default
    elements:
      - id: create-button
        name: 创建
        role: button
""",
        encoding="utf-8",
    )

    calls = {
        "roots": [],
        "pages": [],
        "artifacts": [],
    }

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            if "UPDATE exploration_runs SET artifact_root" in sql:
                calls["roots"].append(params)
            elif "INSERT INTO exploration_pages" in sql:
                calls["pages"].append(params)
            elif "INSERT INTO exploration_artifacts" in sql:
                calls["artifacts"].append(params)
            return self

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())

    summary = page_exploration_service._register_exploration_outputs(
        project_id="project-1",
        run_id="run-1",
        start_url="https://example.test",
        scope="工作台",
        exploration_mode="autonomous",
        max_pages=3,
    )

    assert summary == "探索完成，已登记 1 个页面产物。"
    assert calls["roots"][0][0] == str(page_root / "runs" / "run-1")
    assert calls["pages"][0][0] == "page-workspace"
    assert calls["pages"][0][8].endswith("page-workspace.yaml")
    artifact_types = {params[2] for params in calls["artifacts"]}
    assert artifact_types == {"page_yaml", "report"}
    page_artifact = next(params for params in calls["artifacts"] if params[2] == "page_yaml")
    assert page_artifact[3] == str(page_root / "pages" / "page-workspace.yaml")
    assert (page_root / "pages" / "page-workspace.yaml").exists()
    assert (page_root / "runs" / "run-1" / "summary.yaml").exists()
    assert (page_root / "runs" / "run-1" / "report.md").exists()


def test_failed_exploration_registers_current_partial_outputs(monkeypatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "project-1" / "page_exploration" / "runs" / "run-failed"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page-current.yaml").write_text(
        """
page:
  id: page-current
  title: 当前轮页面
  url: https://example.test/current
  normalized_url: /current
  module: 当前模块
  structure_summary: 当前轮已经采集到页面事实。
""",
        encoding="utf-8",
    )

    class FakeConnection:
        def __init__(self):
            self.pages = []
            self.artifacts = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            if "SELECT er.*" in sql:
                return self
            if "UPDATE exploration_runs SET artifact_root" in sql:
                self.artifact_root = params[0]
            elif "INSERT INTO exploration_pages" in sql:
                self.pages.append(params)
            elif "INSERT INTO exploration_artifacts" in sql:
                self.artifacts.append(params)
            return self

        def fetchone(self):
            return {
                "id": "run-failed",
                "project_id": "project-1",
                "environment_id": "env-1",
                "environment_site_url": "https://example.test",
                "exploration_mode": "autonomous",
                "scope": "当前模块",
                "max_pages": 3,
            }

    fake = FakeConnection()
    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: fake)

    summary = page_exploration_service._register_failed_exploration_outputs("run-failed")

    assert summary == "已保留本次失败前生成的 1 个页面产物。"
    assert fake.artifact_root == str(run_dir)
    assert fake.pages[0][0] == "page-current"
    assert {params[2] for params in fake.artifacts} == {"page_yaml", "report"}


def test_cancelled_exploration_registers_current_partial_outputs(monkeypatch) -> None:
    registered = []
    statuses = []

    def fake_register(run_id: str) -> str:
        registered.append(run_id)
        return "已保留本次取消前生成的 2 个页面产物。"

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql, params=()):
            return self

        def fetchone(self):
            return {"id": "run-cancelled", "status": "running"}

    def fake_update_status(db, run_id, status, **kwargs):
        statuses.append((run_id, status, kwargs.get("result_summary", "")))

    monkeypatch.setattr(page_exploration_service, "_register_failed_exploration_outputs", fake_register)
    monkeypatch.setattr(page_exploration_service, "connect", lambda: FakeConnection())
    monkeypatch.setattr(page_exploration_service.exploration_run_repo, "update_status", fake_update_status)

    page_exploration_service._finalize_cancelled_exploration_run("run-cancelled")

    assert registered == ["run-cancelled"]
    assert statuses == [
        (
            "run-cancelled",
            "cancelled",
            "探索任务已由用户停止；已保留本次取消前生成的 2 个页面产物。",
        )
    ]
