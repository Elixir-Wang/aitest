import asyncio
import json
from pathlib import Path

import pytest

from app.presentation.serializers import serialize_exploration_run
from app.services.exploration import service as exploration_service
from app.services.exploration import simple_orchestrator
from app.services.exploration import site_orchestrator
from app.services.exploration import unified_orchestrator
from app.services.exploration import goal_validation_service
from app.agents.site_exploration.execution_decision.schemas import AgenticAction, AgenticDecisionOutput
from app.services.exploration.browser_session import resolve_navigation_url
from app.services.exploration.plan_and_execute.executor import PlanExecutor, StepExecutionResult
from app.services.exploration.plan_and_execute.planner import (
    ExplorationPlan,
    ExplorationPlanner,
    ExplorationStep,
    PlannerInput,
)


def test_serialize_exploration_run_uses_environment_auth_summary() -> None:
    result = serialize_exploration_run(
        {
            "id": "explore-1",
            "project_id": "project-1",
            "project_name": "测试项目",
            "environment_id": "env-1",
            "environment_name": "测试环境",
            "environment_site_url": "https://example.test",
            "title": "首页探索",
            "status": "pending",
            "scope": "",
            "forbidden_paths": "",
            "login_strategy": "account_password",
            "environment_login_strategy": "account_password",
            "environment_captcha_strategy": "ai_letter",
            "environment_reuse_auth_state": 1,
            "environment_username": "tester",
            "environment_has_password": 1,
            "goal": "",
            "notes": "",
            "max_pages": 50,
            "max_actions": 1000,
            "timeout_minutes": 120,
            "artifact_root": "",
            "result_summary": "",
            "created_at": "2026-06-06 10:00:00",
            "updated_at": "2026-06-06 10:00:00",
            "started_at": None,
            "finished_at": None,
        },
        "admin",
    )

    assert result["login_strategy"] == "account_password"
    assert result["captcha_strategy"] == "ai_letter"
    assert result["reuse_auth_state"] is True
    assert result["has_login_credentials"] is True
    assert "environment_username" not in result


def test_run_snapshot_uses_environment_auth_summary_without_secrets() -> None:
    snapshot = exploration_service._run_snapshot(
        {
            "title": "首页探索",
            "status": "pending",
            "environment_id": "env-1",
            "scope": "",
            "forbidden_paths": "",
            "login_strategy": "account_password",
            "environment_login_strategy": "account_password",
            "environment_captcha_strategy": "ai_letter",
            "environment_reuse_auth_state": 1,
            "environment_username": "tester",
            "environment_has_password": 1,
            "goal": "",
            "notes": "",
            "max_pages": 50,
            "max_actions": 1000,
            "timeout_minutes": 120,
            "result_summary": "",
        }
    )

    assert snapshot["login_strategy"] == "account_password"
    assert snapshot["captcha_strategy"] == "ai_letter"
    assert snapshot["reuse_auth_state"] is True
    assert snapshot["has_login_credentials"] is True
    assert "environment_username" not in snapshot


def test_site_orchestrator_reads_elements_from_v2_states() -> None:
    primary_selector = {
        "kind": "role",
        "code": "page.getByRole('button', { name: '新建用户' })",
        "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
    }
    fallback_selector = {
        "kind": "testid",
        "code": "page.getByTestId('create-user')",
        "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
    }
    page_artifact = {
        "page": {
            "id": "page-001",
            "module": "用户管理",
            "title": "用户列表",
            "url": "https://example.test/users",
        },
        "states": [
            {
                "id": "default",
                "elements": [
                    {
                        "id": "create-user-button",
                        "name": "新建用户",
                        "role": "button",
                        "primary_selector": primary_selector,
                        "fallback_selector": fallback_selector,
                    }
                ],
            }
        ],
        "accessibility_tree": [],
    }

    elements = site_orchestrator._elements_from_page_artifacts(
        [page_artifact],
        module_key="用户管理",
        page_url="https://example.test",
    )

    assert elements == [
        {
            "module_key": "用户管理",
            "page_id": "page-001",
            "element_name": "新建用户",
            "element_type": "button",
            "recommended_locator": "page.getByRole('button', { name: '新建用户' })",
            "fallback_locator": "page.getByTestId('create-user')",
            "stability_note": "主 selector 已通过唯一性和可见性校验。",
            "source_ref": "https://example.test/users",
            "primary_selector": primary_selector,
            "fallback_selector": fallback_selector,
        }
    ]


def test_page_index_payload_falls_back_to_actions_as_steps() -> None:
    payload = site_orchestrator._page_index_payload(
        {
            "page": {
                "id": "page-001",
                "title": "首页",
                "url": "https://example.test",
                "normalized_url": "https://example.test",
                "structure_summary": "已采集首页。",
            },
            "actions": [
                {
                    "id": "action-001",
                    "type": "click",
                    "target": "登录按钮",
                    "status": "passed",
                    "result": "跳转到登录页。",
                }
            ],
        },
        module_key="入口页",
    )

    assert payload["steps"] == [
        {
            "id": "action-001",
            "type": "click",
            "title": "登录按钮",
            "detail": "跳转到登录页。",
            "status": "passed",
            "occurred_at": None,
            "artifact_path": "",
            "source": "",
        }
    ]


def test_unified_orchestrator_publishes_frontend_step_event() -> None:
    captured = []
    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-1",
        Path("/tmp/explore-1"),
        "https://example.test",
    )
    orchestrator._publish = lambda event_type, payload: captured.append((event_type, payload))
    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="observe",
        description="观察首页",
        target_description="首页",
        expected_result="采集页面事实",
        module_name="入口页",
    )
    result = StepExecutionResult(
        step=step,
        success=True,
        message="已采集首页。",
        page_state={"url": "https://example.test"},
    )

    orchestrator._publish_step_recorded(step, result, status="completed")

    assert captured[0][0] == "step_recorded"
    assert captured[0][1]["module_key"] == "入口页"
    assert captured[0][1]["page_id"] == "page-001"
    assert captured[0][1]["step"]["id"] == "step-001"
    assert captured[0][1]["step"]["detail"] == "已采集首页。"


def test_unified_orchestrator_uses_lifecycle_page_before_page_state() -> None:
    captured = []
    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-1",
        Path("/tmp/explore-1"),
        "https://example.test",
    )
    orchestrator._publish = lambda event_type, payload: captured.append((event_type, payload))
    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="navigate",
        description="导航到工作台",
        target_description="/workspace",
        expected_result="进入工作台",
        module_name="工作台",
    )

    orchestrator._publish_step_recorded(step, None, status="running")

    assert captured[0][0] == "step_recorded"
    assert captured[0][1]["page_id"] == "lifecycle"


def test_planner_normalizes_first_navigate_target_to_start_url() -> None:
    planner = ExplorationPlanner()
    plan = planner._parse_and_validate_plan(
        {
            "plan_id": "plan-1",
            "goal_summary": "探索工作台",
            "scope_summary": "工作台",
            "strategy": "先进入工作台再探索",
            "modules": ["工作台"],
            "steps": [
                {
                    "step_id": "step-001",
                    "step_number": 1,
                    "action_type": "navigate",
                    "description": "导航至智能体商店/工作台首页",
                    "target_description": "起始URL对应的页面，应包含智能体卡片列表",
                    "target_selector": "",
                    "expected_result": "页面加载完成",
                    "module_name": "工作台",
                }
            ],
        },
        PlannerInput(
            run_id="explore-1",
            title="工作台探索",
            goal="探索工作台",
            scope="工作台",
            forbidden_paths="",
            start_url="https://example.test/workspace",
        ),
    )

    assert plan.steps[0].target_selector == "https://example.test/workspace"


def test_plan_executor_rejects_natural_language_navigation_target(tmp_path: Path) -> None:
    class FakeBrowserSession:
        start_url = ""

        def navigate(self, url):
            raise AssertionError("不应把自然语言目标传给 browser.navigate")

    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="navigate",
        description="导航至工作台首页",
        target_description="起始URL对应的页面，应包含智能体卡片列表",
        expected_result="页面加载完成",
        module_name="工作台",
    )
    executor = PlanExecutor(
        browser_session=FakeBrowserSession(),
        artifact_root=tmp_path,
        plan=ExplorationPlan(
            plan_id="plan-1",
            goal_summary="探索工作台",
            scope_summary="工作台",
            strategy="直接执行",
            modules=["工作台"],
            steps=[step],
        ),
    )

    result = executor._execute_navigate(step)

    assert result.success is False
    assert "缺少有效URL" in result.error


def test_plan_executor_resolves_relative_navigation_target_against_start_url(tmp_path: Path) -> None:
    class FakeBrowserSession:
        start_url = "https://example.test/login"

        def __init__(self):
            self.navigated_urls = []

        def navigate(self, url):
            self.navigated_urls.append(url)
            return {"status": "passed", "url": url}

        def observe(self):
            return {
                "url": self.navigated_urls[-1],
                "title": "工作台",
                "elements": [],
            }

    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="navigate",
        description="导航至工作台首页",
        target_description="/workspace",
        target_selector="/workspace",
        expected_result="页面加载完成",
        module_name="工作台",
    )
    browser = FakeBrowserSession()
    executor = PlanExecutor(
        browser_session=browser,
        artifact_root=tmp_path,
        plan=ExplorationPlan(
            plan_id="plan-1",
            goal_summary="探索工作台",
            scope_summary="工作台",
            strategy="直接执行",
            modules=["工作台"],
            steps=[step],
        ),
    )

    result = executor._execute_navigate(step)

    assert result.success is True
    assert browser.navigated_urls == ["https://example.test/workspace"]


def test_browser_session_resolves_relative_navigation_url_at_boundary() -> None:
    assert (
        resolve_navigation_url("/workspace", "https://example.test/login?next=/workspace")
        == "https://example.test/workspace"
    )
    assert resolve_navigation_url("https://other.test/workspace", "https://example.test/login") == "https://other.test/workspace"
    assert resolve_navigation_url("/workspace", "about:blank") == "/workspace"


def test_unified_orchestrator_reports_planning_timeout_with_readable_message(tmp_path: Path) -> None:
    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-1",
        tmp_path / "explore-1",
        "https://example.test",
    )
    orchestrator.live_progress = {
        "modules": {
            "planned-01": {
                "pages": {
                    "lifecycle": {
                        "id": "lifecycle",
                        "status": "running",
                        "steps": [{"id": "planning-started", "status": "running", "detail": "正在生成计划"}],
                    }
                }
            }
        },
        "plan": {},
        "events": [],
    }

    message = orchestrator._exception_message(asyncio.TimeoutError())
    orchestrator._record_live_failure(message)

    progress = json.loads((tmp_path / "explore-1" / "live" / "progress.json").read_text(encoding="utf-8"))
    step = progress["modules"]["planned-01"]["pages"]["lifecycle"]["steps"][0]
    assert "探索计划生成超时" in message
    assert progress["modules"]["planned-01"]["pages"]["lifecycle"]["status"] == "failed"
    assert step["status"] == "failed"
    assert "180 秒" in step["detail"]


def test_unified_orchestrator_uses_fallback_plan_when_planner_times_out(tmp_path: Path) -> None:
    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-1",
        tmp_path / "explore-1",
        "https://example.test/workspace",
    )
    planner_input = PlannerInput(
        run_id="explore-1",
        title="工作台探索",
        goal="点击测试智能体卡片",
        scope="工作台",
        forbidden_paths="",
        start_url="https://example.test/workspace",
        timeout_minutes=5,
    )

    plan = orchestrator._fallback_plan(planner_input, "模型规划超时")
    annotated = orchestrator._annotate_execution_strategy(plan)

    assert annotated.plan_id == "fallback-explore-1"
    assert [step.action_type for step in annotated.steps] == ["navigate", "observe", "agentic_explore"]
    assert annotated.steps[0].target_selector == "https://example.test/workspace"
    assert annotated.steps[2].execution_strategy == "agentic"


def test_site_orchestrator_execute_unified_uses_unified_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {}

    def fail_simple(*args, **kwargs):
        raise AssertionError("主探索链路不应默认调用 simple_orchestrator")

    def fake_run_unified_exploration_sync(**kwargs):
        captured.update(kwargs)
        return {
            "status": "completed",
            "summary": "统一探索完成",
            "structured_pages": [],
            "graph": {"nodes": [], "edges": [], "paths": []},
            "log": "unified",
            "log_path": "",
        }

    monkeypatch.setattr(simple_orchestrator, "run_simple_exploration", fail_simple)
    monkeypatch.setattr(site_orchestrator, "_safe_run_context_from_db", lambda run_id: ("https://example.test", "/logout", "/tmp/state.json"))
    monkeypatch.setattr(unified_orchestrator, "run_unified_exploration_sync", fake_run_unified_exploration_sync)

    result = site_orchestrator._execute_unified_exploration("explore-1", tmp_path / "explore-1")

    assert result["summary"] == "统一探索完成"
    assert captured == {
        "run_id": "explore-1",
        "artifact_root": tmp_path / "explore-1",
        "start_url": "https://example.test",
        "forbidden_paths": "/logout",
        "storage_state_path": "/tmp/state.json",
    }


def test_unified_orchestrator_passes_run_goal_to_agentic_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {}

    async def fake_decide_next_action(input_data):
        captured["input"] = input_data.model_dump()
        return AgenticDecisionOutput(
            decision_type="finish",
            reason="目标已确认",
        )

    monkeypatch.setattr(
        "app.agents.site_exploration.execution_decision.service.decide_next_action",
        fake_decide_next_action,
    )

    class FakeBrowserSession:
        def observe(self):
            return {"url": "https://example.test/home", "title": "Home", "elements": []}

    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-12345678",
        tmp_path,
        "https://example.test/home",
        forbidden_paths="/admin",
    )
    orchestrator.run_context = {
        "title": "目标探索",
        "goal": "只验证文章详情页链接跳转，不执行 CRUD。",
        "scope": "/articles",
        "forbidden_paths": "/admin",
    }
    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="agentic_explore",
        description="探索页面上的链接",
        target_description="文章详情页",
        expected_result="完成链接验证",
        module_name="文章",
    )

    result = asyncio.run(orchestrator._execute_agentic_step(step, FakeBrowserSession()))

    assert result.success is True
    assert captured["input"]["run"]["goal"] == "只验证文章详情页链接跳转，不执行 CRUD。"
    assert captured["input"]["run"]["current_step"] == "探索页面上的链接"
    assert captured["input"]["run"]["scope"] == "/articles"
    assert captured["input"]["run"]["forbidden_paths"] == "/admin"


def test_unified_orchestrator_executes_agentic_act_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_decide_next_action(input_data):
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(
                type="click",
                target_element_id="link-article-detail",
                intent="打开文章详情",
            ),
            reason="目标要求验证文章详情页链接",
            expected_result="进入详情页",
        )

    monkeypatch.setattr(
        "app.agents.site_exploration.execution_decision.service.decide_next_action",
        fake_decide_next_action,
    )

    class FakeBrowserSession:
        def __init__(self):
            self.clicked = []

        def observe(self):
            return {
                "url": "https://example.test/articles",
                "title": "Articles",
                "elements": [{"id": "link-article-detail", "role": "link", "name": "详情"}],
            }

        def click(self, element_id):
            self.clicked.append(element_id)
            return {"status": "passed"}

    class FakeExecutor:
        def __init__(self):
            self.pages = []

        def _record_page_visit(self, page_state):
            self.pages.append(page_state)

    browser_session = FakeBrowserSession()
    executor = FakeExecutor()
    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-12345678",
        tmp_path,
        "https://example.test/articles",
    )
    orchestrator.run_context = {
        "title": "文章探索",
        "goal": "验证文章详情页链接跳转。",
        "scope": "/articles",
        "forbidden_paths": "",
    }
    orchestrator.executor = executor
    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="agentic_explore",
        description="探索文章链接",
        target_description="文章链接",
        expected_result="进入详情页",
        module_name="文章",
    )

    result = asyncio.run(orchestrator._execute_agentic_step(step, browser_session))

    assert result.success is True
    assert browser_session.clicked == ["link-article-detail"]
    assert executor.pages[0]["url"] == "https://example.test/articles"


def test_unified_orchestrator_reports_agentic_decision_timeout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def slow_decide_next_action(input_data):
        await asyncio.sleep(1)
        return AgenticDecisionOutput(decision_type="finish", reason="done")

    monkeypatch.setattr(
        "app.agents.site_exploration.execution_decision.service.decide_next_action",
        slow_decide_next_action,
    )
    monkeypatch.setattr(unified_orchestrator, "AGENTIC_DECISION_TIMEOUT_SECONDS", 0.01)

    class FakeBrowserSession:
        def observe(self):
            return {"url": "https://example.test/articles", "title": "Articles", "elements": []}

    orchestrator = unified_orchestrator.UnifiedExplorationOrchestrator(
        "explore-12345678",
        tmp_path,
        "https://example.test/articles",
    )
    step = ExplorationStep(
        step_id="step-001",
        step_number=1,
        action_type="agentic_explore",
        description="探索文章链接",
        target_description="文章链接",
        expected_result="进入详情页",
        module_name="文章",
    )

    result = asyncio.run(orchestrator._execute_agentic_step(step, FakeBrowserSession()))

    assert result.success is False
    assert "Agent 决策超时" in result.error
    assert result.page_state["url"] == "https://example.test/articles"


def test_structured_goal_without_action_evidence_is_partial() -> None:
    result = goal_validation_service.validate_goal(
        "模块一：进入工作台\n1. 点击“测试_自主规划智能体”卡片。\n2. 输入 flow1 并发送。",
        [
            {
                "page": {"id": "page-001", "title": "工作台", "url": "https://example.test/workspace"},
                "accessibility_tree": [
                    {"id": "button-agent", "role": "button", "name": "测试_自主规划智能体"},
                    {"id": "textbox-search", "role": "textbox", "name": "搜索"},
                ],
                "actions": [
                    {"id": "button-agent", "name": "测试_自主规划智能体", "action_type": "click", "status": "observed"},
                ],
                "steps": [
                    {"type": "observe", "title": "采集页面事实", "detail": "发现智能体卡片。", "status": "completed"},
                ],
            }
        ],
        {"nodes": [], "edges": [], "paths": []},
    )

    assert result["status"] == "partial"
    assert "未找到点击、填写、选择、发送、发布、返回等目标步骤执行证据" in result["summary"]


def test_structured_goal_with_action_evidence_can_pass() -> None:
    result = goal_validation_service.validate_goal(
        "模块一：进入工作台\n1. 点击“测试_自主规划智能体”卡片。",
        [
            {
                "page": {"id": "page-001", "title": "工作台", "url": "https://example.test/workspace"},
                "accessibility_tree": [
                    {"id": "button-agent", "role": "button", "name": "测试_自主规划智能体"},
                ],
                "actions": [
                    {"id": "action-001", "type": "click", "name": "测试_自主规划智能体", "status": "passed"},
                ],
                "steps": [
                    {"type": "action_result", "title": "点击卡片", "detail": "点击测试_自主规划智能体：passed", "status": "completed"},
                ],
            }
        ],
        {"nodes": [], "edges": [], "paths": []},
    )

    assert result["status"] == "passed"


def test_site_orchestrator_registers_v2_report_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    created = []

    def fake_create_artifact(db, **kwargs):
        created.append(kwargs)

    monkeypatch.setattr(site_orchestrator.exploration_repo, "create_artifact", fake_create_artifact)

    site_orchestrator._persist_common_artifacts(
        object(),
        "explore-1",
        {
            "run_path": "project-1/exploration/explore-1/run.yaml",
            "summary_path": "project-1/exploration/explore-1/summary.yaml",
            "graph_path": "project-1/exploration/explore-1/graph.yaml",
            "blockers_path": "project-1/exploration/explore-1/blockers.yaml",
            "report_path": "project-1/exploration/explore-1/reports/exploration-report.md",
        },
        "project-1/exploration/explore-1/logs/run.log",
    )

    assert {
        "artifact_type": "markdown",
        "file_path": "project-1/exploration/explore-1/reports/exploration-report.md",
        "title": "探索报告",
        "summary": "站点探索 v2 产物。",
    } in [
        {
            "artifact_type": item["artifact_type"],
            "file_path": item["file_path"],
            "title": item["title"],
            "summary": item["summary"],
        }
        for item in created
    ]


def test_site_orchestrator_uses_configured_entry_with_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth_root = tmp_path / "projects"
    monkeypatch.setattr(site_orchestrator, "PROJECT_FILE_STORAGE_ROOT", auth_root)
    monkeypatch.setattr(site_orchestrator.auth_state_path.__globals__["settings"], "PROJECT_FILE_STORAGE_ROOT", auth_root)
    state_path = auth_root / "environments" / "env-1" / "auth" / "storage-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        '{"cookies":[{"name":"sid","value":"secret","domain":"www.cybotstar.cn","path":"/"}],"origins":[]}',
        encoding="utf-8",
    )

    run = {
        "project_id": "project-1",
        "environment_id": "env-1",
        "environment_site_url": "https://www.cybotstar.cn/agentStore",
        "environment_login_strategy": "account_password",
        "environment_captcha_strategy": "manual",
        "environment_reuse_auth_state": 1,
        "forbidden_paths": "",
    }

    assert site_orchestrator._stored_auth_state_path_for_run(run) == state_path
    assert site_orchestrator._exploration_start_url(run) == "https://www.cybotstar.cn/agentStore"


def test_site_orchestrator_does_not_use_empty_auth_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    auth_root = tmp_path / "projects"
    monkeypatch.setattr(site_orchestrator, "PROJECT_FILE_STORAGE_ROOT", auth_root)
    monkeypatch.setattr(site_orchestrator.auth_state_path.__globals__["settings"], "PROJECT_FILE_STORAGE_ROOT", auth_root)
    state_path = auth_root / "environments" / "env-1" / "auth" / "storage-state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text('{"cookies":[],"origins":[]}', encoding="utf-8")

    run = {
        "project_id": "project-1",
        "environment_id": "env-1",
        "environment_site_url": "https://www.cybotstar.cn/agentStore",
        "environment_login_strategy": "account_password",
        "environment_captcha_strategy": "manual",
        "environment_reuse_auth_state": 1,
        "forbidden_paths": "",
    }

    assert site_orchestrator._stored_auth_state_path_for_run(run) is None


def test_site_orchestrator_does_not_rewrite_login_like_configured_entry() -> None:
    run = {
        "project_id": "project-1",
        "environment_id": "env-1",
        "environment_site_url": "https://example.test/login",
        "environment_login_strategy": "account_password",
        "environment_captcha_strategy": "manual",
        "environment_reuse_auth_state": 1,
    }

    assert site_orchestrator._exploration_start_url(run) == "https://example.test/login"


def test_simple_exploration_completed_result_matches_persist_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeBrowserSession:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def navigate(self, url):
            return {"status": "passed", "after_url": url}

        def observe(self):
            return {
                "url": "https://example.test/home",
                "normalized_url": "https://example.test/home",
                "title": "Home",
                "page_text_summary": "首页摘要",
                "elements": [
                    {
                        "id": "button-login",
                        "role": "button",
                        "name": "登录",
                        "action_type": "click",
                        "primary_selector": {"kind": "role", "code": "getByRole('button', { name: '登录' })"},
                    }
                ],
                "forms": [],
                "tables": [],
            }

    monkeypatch.setattr(simple_orchestrator, "PlaywrightBrowserSession", FakeBrowserSession)

    result = simple_orchestrator.run_simple_exploration(
        run_id="explore-1",
        artifact_root=tmp_path / "explore-1",
        start_url="https://example.test/home",
    )

    assert result["status"] == "completed"
    assert isinstance(result["structured_pages"], list)
    assert result["structured_pages"][0]["page"]["url"] == "https://example.test/home"
    assert result["structured_pages"][0]["actions"][0]["name"] == "登录"
    assert isinstance(result["graph"], dict)
    assert result["log"]
    assert "+08:00" in result["log"]


def test_persist_completed_result_tolerates_missing_log_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {}

    def fake_validate_goal(goal, page_artifacts, graph):
        return {"status": "not_applicable", "summary": ""}

    def fake_terminal_status(result_status, goal_validation):
        return result_status

    def fake_write_artifacts(
        artifact_root,
        *,
        run,
        summary,
        page_artifacts,
        graph,
        blockers,
        log_content,
        goal_validation=None,
    ):
        captured["log_content"] = log_content
        return {}

    monkeypatch.setattr(site_orchestrator.exploration_goal_validation_service, "validate_goal", fake_validate_goal)
    monkeypatch.setattr(
        site_orchestrator.exploration_goal_validation_service,
        "terminal_status_for_goal_validation",
        fake_terminal_status,
    )
    monkeypatch.setattr(site_orchestrator, "_goal_validation_status_summary", lambda goal_validation: "")
    monkeypatch.setattr(site_orchestrator.exploration_artifact_service, "write_exploration_artifacts", fake_write_artifacts)
    monkeypatch.setattr(site_orchestrator.exploration_repo, "list_module_coverages", lambda db, run_id: [])
    monkeypatch.setattr(site_orchestrator.exploration_repo, "create_module_coverage", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator.exploration_repo, "update_module_coverage", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator.exploration_repo, "update_run_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator, "_persist_common_artifacts", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator, "_publish_module_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator, "_publish_page_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator, "_publish_step_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator, "_publish_blocker_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator, "_publish_run_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(site_orchestrator.exploration_event_bus, "close", lambda *args, **kwargs: None)

    run = {
        "id": "explore-1",
        "title": "探索",
        "project_name": "项目",
        "environment_name": "测试环境",
        "environment_site_url": "https://example.test/home",
        "scope": "",
        "goal": "",
    }
    result = {
        "status": "completed",
        "summary": "完成探索",
        "structured_pages": [
            {
                "page": {
                    "id": "page-001",
                    "url": "https://example.test/home",
                    "title": "Home",
                    "normalized_url": "https://example.test/home",
                    "module": "站点入口",
                    "depth": 0,
                    "status": "explored",
                    "structure_summary": "首页摘要",
                },
                "accessibility_tree": [],
                "actions": [],
                "forms": [],
                "tables": [],
                "relations": {"incoming_edges": [], "outgoing_edges": []},
                "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
            }
        ],
        "graph": {"nodes": [], "edges": [], "paths": []},
    }

    status, summary = site_orchestrator._persist_completed_result(None, run, tmp_path, result)

    assert status == "completed"
    assert summary == "完成探索"
    assert captured["log_content"] == "完成探索"


def test_empty_page_module_is_not_marked_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    run = {
        "id": "explore-1",
        "title": "探索",
        "environment_name": "测试环境",
        "environment_site_url": "https://example.test",
        "scope": "工作台",
    }
    result = {"status": "completed", "summary": "完成探索", "structured_pages": [], "blockers": []}

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

    monkeypatch.setattr(site_orchestrator, "connect", lambda: FakeConnection())
    monkeypatch.setattr(site_orchestrator.exploration_repo, "list_module_coverages", lambda db, run_id: [])

    modules = site_orchestrator._build_module_coverages(
        run,
        result,
        [],
        "partial",
        None,
        "https://example.test",
    )

    assert modules[0]["module_key"] == "unclassified"
    assert modules[0]["explored_page_count"] == 0
    assert modules[0]["completion_status"] == "partial"
    assert "未探索到页面事实" in modules[0]["completion_summary"]
