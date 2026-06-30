import json
from pathlib import Path
import inspect

import pytest

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

    assert captured["agent_args"] == ("fake-model", "project-1", "run-1")
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
    assert "input" not in captured["payload"]
    assert updates


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


def test_invoke_agent_checkpoints_snapshot_as_page_artifact(monkeypatch, tmp_path: Path) -> None:
    class FakeAgent:
        async def astream_events(self, payload, **kwargs):
            yield {
                "event": "on_tool_end",
                "name": "playwright_snap_tool",
                "run_id": "tool-run-1",
                "data": {
                    "output": {
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
                        "raw_output": "button 创建智能体",
                        "error": None,
                    }
                },
            }
            yield {
                "event": "on_chain_end",
                "name": "agent",
                "run_id": "agent-run-1",
                "data": {"output": {"messages": [{"content": "探索完成"}]}},
            }

    monkeypatch.setattr(page_exploration_service.settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)

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


def test_execute_exploration_async_publishes_realtime_events(monkeypatch) -> None:
    class FakeAgent:
        async def ainvoke(self, payload):
            return {"messages": [{"content": "探索完成，发现工作台入口。"}]}

    def fake_page_exploration_agent(model, project_id, run_id):
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
    assert any(event["payload"].get("message") == "探索完成，发现工作台入口。" for event in events)


def test_execute_exploration_async_does_not_complete_after_stop(monkeypatch) -> None:
    class FakeAgent:
        async def ainvoke(self, payload):
            return {"messages": [{"content": "探索完成。"}]}

    def fake_page_exploration_agent(model, project_id, run_id):
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


def test_agent_stream_tool_error_updates_started_step() -> None:
    event_bus.clear("run-tool-lifecycle")

    page_exploration_service._publish_agent_stream_event(
        "run-tool-lifecycle",
        {
            "event": "on_tool_start",
            "name": "playwright_click_tool",
            "run_id": "tool-run-1",
            "data": {"input": {"locator": "button-对话历史-028"}},
        },
    )
    page_exploration_service._publish_agent_stream_event(
        "run-tool-lifecycle",
        {
            "event": "on_tool_error",
            "name": "playwright_click_tool",
            "run_id": "tool-run-1",
            "data": {"error": "Unknown element id: button-对话历史-028"},
        },
    )

    events = event_bus.get_history("run-tool-lifecycle")

    assert [event["type"] for event in events] == ["step_started", "step_failed"]
    assert events[0]["payload"]["step_id"] == events[1]["payload"]["step_id"]
    assert events[0]["payload"]["step_id"] == "agent-on_tool-tool-run-1"


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
