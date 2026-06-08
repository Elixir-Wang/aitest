from pathlib import Path

import pytest

from app.agents.site_exploration.agentic_schemas import AgenticAction, AgenticDecisionOutput, AgenticRisk
from app.services.exploration import action_risk, agentic_orchestrator, artifact_service
from app.services.exploration.service import parse_exploration_log_entries


def test_action_risk_allows_crud_actions_without_environment_split() -> None:
    decision = action_risk.evaluate_action(
        {"type": "click"},
        {"name": "创建智能体", "role": "button", "action_type": "click"},
    )
    destructive_decision = action_risk.evaluate_action(
        {"type": "click"},
        {"name": "删除智能体", "role": "button", "action_type": "click"},
    )

    assert decision.allowed is True
    assert decision.risk.level == "guarded"
    assert destructive_decision.allowed is True
    assert destructive_decision.risk.level == "destructive"
    assert "CRUD 闭环验证" in destructive_decision.reason


def test_action_risk_allows_safe_click() -> None:
    decision = action_risk.evaluate_action(
        {"type": "click"},
        {"name": "使用", "role": "button", "action_type": "click"},
    )

    assert decision.allowed is True
    assert decision.risk.level == "safe"


def test_action_risk_treats_sorting_as_safe_even_when_label_contains_publish() -> None:
    decision = action_risk.evaluate_action(
        {"type": "click"},
        {"name": "按发布时间排序", "role": "button", "action_type": "click"},
    )

    assert decision.allowed is True
    assert decision.risk.level == "safe"


def test_agentic_decision_failure_blocks_without_fallback_action(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = _runner(tmp_path)
    run = {
        "id": "explore-1",
        "title": "百融百工",
        "goal": "完整探索",
        "scope": "工作台",
        "forbidden_paths": "",
    }
    observation = _observation(
        "https://example.test/workspace",
        "工作台",
        "state-entry",
        [
            {
                "id": "button-publish-001",
                "name": "发布",
                "role": "button",
                "action_type": "click",
                "risk_hint": "destructive",
            }
        ],
    )

    async def fail_decide(input_data):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fail_decide)

    decision = runner._decide(run, observation, max_pages=50, max_actions=1000, max_turns=200)

    assert decision.decision_type == "block"
    assert decision.action is None
    assert decision.risk.level == "destructive"
    assert "模型决策不可用" in decision.reason


def test_agentic_loop_observes_decides_clicks_and_observes_again(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-use-001", "name": "使用", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            ),
            _observation("https://example.test/workspace/use", "使用", "state-use", []),
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        elements = input_data.current_observation.get("elements", [])
        if not elements:
            return AgenticDecisionOutput(decision_type="finish", reason="已覆盖可执行入口。")
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-use-001"),
            reason="覆盖工作台使用入口。",
            expected_result="进入使用页面。",
            risk=AgenticRisk(level="safe", reason="使用按钮为可执行入口。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert result["status"] == "completed"
    assert [page["page"]["id"] for page in result["structured_pages"]] == ["page-001", "page-002"]
    assert fake_session.clicked == ["button-use-001"]
    assert result["graph"]["edges"][0]["type"] == "agent_action"
    assert result["graph"]["edges"][0]["source"] == "page-001"
    assert result["graph"]["edges"][0]["target"] == "page-002"
    assert '"event": "observe"' in result["log"]
    assert '"event": "agent_decision"' in result["log"]
    assert '"event": "action_result"' in result["log"]
    assert '"event": "step_recorded"' in result["log"]
    assert '"title": "观察页面"' in result["log"]
    step_entries = [entry for entry in parse_exploration_log_entries(result["log"]) if entry["event"] == "step_recorded"]
    assert step_entries
    assert step_entries[0]["event_label"] == "探索步骤"
    assert step_entries[0]["category"] == "page"
    assert step_entries[0]["summary"] == "观察页面：工作台，1 个元素。"


def test_agentic_loop_publishes_live_module_page_and_step_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-use-001", "name": "使用", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            ),
            _observation("https://example.test/workspace/use", "使用", "state-use", []),
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        elements = input_data.current_observation.get("elements", [])
        if not elements:
            return AgenticDecisionOutput(decision_type="finish", reason="已覆盖可执行入口。")
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-use-001"),
            reason="覆盖工作台使用入口。",
            expected_result="进入使用页面。",
            risk=AgenticRisk(level="safe", reason="使用按钮为可执行入口。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)
    published: list[tuple[str, dict]] = []
    runner._publish = lambda event_type, payload: published.append((event_type, payload))

    runner.run()

    module_events = [payload for event_type, payload in published if event_type == "module_updated"]
    page_events = [payload for event_type, payload in published if event_type == "page_discovered"]
    step_events = [payload for event_type, payload in published if event_type == "step_recorded"]
    assert module_events
    assert page_events
    assert step_events
    assert {payload["module_key"] for payload in module_events} == {"planned-01"}
    assert {payload["module_key"] for payload in page_events} == {"planned-01"}
    assert {payload["module_key"] for payload in step_events} == {"planned-01"}
    assert module_events[-1]["explored_page_count"] == 2
    assert module_events[-1]["recent_page_title"] == "使用"
    assert module_events[-1]["completion_status"] == "running"


def test_agentic_loop_writes_live_snapshot_for_detail_reload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-use-001", "name": "使用", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            ),
            _observation("https://example.test/workspace/use", "使用", "state-use", []),
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        elements = input_data.current_observation.get("elements", [])
        if not elements:
            return AgenticDecisionOutput(decision_type="finish", reason="已覆盖可执行入口。")
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-use-001"),
            reason="覆盖工作台使用入口。",
            expected_result="进入使用页面。",
            risk=AgenticRisk(level="safe", reason="使用按钮为可执行入口。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    runner.run()

    bundle = artifact_service.load_exploration_run_artifacts(tmp_path)
    assert bundle["pages"]
    assert bundle["pages"][0]["content"]["steps"]
    assert bundle["pages"][0]["content"]["steps"][0]["title"] == "观察页面"


def test_agentic_loop_derives_semantic_page_titles_when_browser_title_is_generic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://www.cybotstar.cn/agentStore",
                "百融百工",
                "state-agent-store",
                [{"id": "button-create-001", "name": "创建智能体", "role": "button", "action_type": "click", "risk_hint": "guarded"}],
                page_text_summary="标题：百融百工。正文：探索广场 结果即刻交付 全部 已订阅。",
            ),
            _observation(
                "https://www.cybotstar.cn/workspace/agentAnalysis?id=17990&agentId=17618",
                "百融百工",
                "state-agent-analysis",
                [],
                page_text_summary="标题：百融百工。正文：数据统计 用户洞察 Token 消耗量 用户。",
            ),
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        if fake_session.index == 0:
            return AgenticDecisionOutput(
                decision_type="act",
                action=AgenticAction(type="click", target_element_id="button-create-001"),
                reason="进入分析页。",
                expected_result="进入分析页。",
                risk=AgenticRisk(level="guarded", reason="入口按钮。"),
            )
        return AgenticDecisionOutput(decision_type="finish", reason="已覆盖。")

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    pages = [page["page"] for page in result["structured_pages"]]
    assert pages[0]["title"] == "百融百工"
    assert pages[0]["semantic_title"] == "探索广场"
    assert pages[0]["module"] == "探索广场"
    assert pages[1]["semantic_title"] == "用户洞察"
    assert pages[1]["module"] == "效果评测"
    assert result["graph"]["nodes"][0]["semantic_title"] == "探索广场"


def test_agentic_loop_includes_action_failure_diagnostics_in_steps_and_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-use-001", "name": "使用", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            )
        ],
        click_result={
            "status": "failed",
            "element_id": "button-use-001",
            "before_url": "https://example.test/workspace",
            "after_url": "https://example.test/workspace",
            "error_type": "locator_timeout",
            "error_summary": "等待目标元素可执行超时。",
            "error": "locator.click: Timeout 3000ms exceeded.",
        },
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        if fake_session.clicked:
            return AgenticDecisionOutput(decision_type="finish", reason="失败动作已记录。")
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-use-001"),
            reason="覆盖使用入口。",
            expected_result="进入使用页面。",
            risk=AgenticRisk(level="safe", reason="使用按钮为可执行入口。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)
    published: list[tuple[str, dict]] = []
    runner._publish = lambda event_type, payload: published.append((event_type, payload))

    result = runner.run()

    action = result["structured_pages"][0]["actions"][0]
    assert action["status"] == "failed"
    assert action["result"]["error_type"] == "locator_timeout"
    action_steps = [step for step in result["structured_pages"][0]["steps"] if step["type"] == "action_result"]
    assert "原因：等待目标元素可执行超时" in action_steps[-1]["detail"]
    assert '"error_type": "locator_timeout"' in result["log"]
    completed_events = [payload for event_type, payload in published if event_type == "action_completed"]
    assert completed_events[-1]["error_type"] == "locator_timeout"
    assert completed_events[-1]["error_summary"] == "等待目标元素可执行超时。"


def test_agentic_loop_back_decision_executes_browser_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation("https://example.test/workspace", "工作台", "state-entry", []),
            _observation("https://example.test/settings", "设置", "state-settings", []),
        ],
        index=1,
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        if fake_session.back_count:
            return AgenticDecisionOutput(decision_type="finish", reason="已返回上一页面。")
        return AgenticDecisionOutput(decision_type="back", reason="当前页面无可执行入口，返回上一页面继续。")

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert result["status"] == "completed"
    assert fake_session.back_count == 1
    assert result["graph"]["edges"][0]["action"] == "go_back"
    assert result["graph"]["edges"][0]["source"] == "page-001"
    assert result["graph"]["edges"][0]["target"] == "page-002"


def test_agentic_loop_executes_guarded_crud_action_without_mode_blocker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-create-001", "name": "创建智能体", "role": "button", "action_type": "click", "risk_hint": "guarded"}],
            )
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        if fake_session.clicked:
            return AgenticDecisionOutput(decision_type="finish", reason="已覆盖创建入口。")
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-create-001"),
            reason="尝试覆盖创建入口。",
            expected_result="打开创建弹窗。",
            risk=AgenticRisk(level="safe", reason="模型判断为入口按钮。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert fake_session.clicked == ["button-create-001"]
    assert result["status"] == "partial"
    assert result["crud_flow"]["create_started"] is True
    assert result["crud_flow"]["create_verified"] is False
    assert result["blockers"][0]["type"] == "crud_incomplete"
    assert '"risk": "guarded"' in result["log"]


def test_agentic_loop_passes_ai_explore_test_data_to_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-use-001", "name": "使用", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            )
        ]
    )
    captured_inputs = []

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        captured_inputs.append(input_data)
        return AgenticDecisionOutput(decision_type="finish", reason="已覆盖。")

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert result["crud_flow"]["test_data_name"] == "AI_EXPLORE_1"
    assert captured_inputs[0].run["crud_test_data_name"] == "AI_EXPLORE_1"
    assert captured_inputs[0].current_observation["crud_flow"]["test_data_name"] == "AI_EXPLORE_1"


def test_agentic_loop_rewrites_fill_values_to_ai_explore_test_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace/new",
                "新建",
                "state-new",
                [{"id": "input-name-001", "name": "名称", "role": "textbox", "action_type": "fill", "risk_hint": "guarded"}],
            ),
            _observation(
                "https://example.test/workspace/new",
                "新建",
                "state-filled",
                [],
                page_text_summary="名称 AI_EXPLORE_1",
            ),
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        if fake_session.filled:
            return AgenticDecisionOutput(decision_type="finish", reason="已填写测试数据。")
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="fill", target_element_id="input-name-001", value="随便写一个名字"),
            reason="填写创建名称。",
            expected_result="表单出现测试名称。",
            risk=AgenticRisk(level="guarded", reason="写入名称。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert fake_session.filled == [("input-name-001", "AI_EXPLORE_1")]
    assert result["crud_flow"]["create_started"] is True
    assert result["crud_flow"]["create_verified"] is True


def test_agentic_loop_blocks_destructive_action_without_ai_explore_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-entry",
                [{"id": "button-delete-001", "name": "删除 textin测试", "role": "button", "action_type": "click", "risk_hint": "destructive"}],
                page_text_summary="列表 textin测试 删除",
            )
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-delete-001"),
            reason="删除一条已有数据。",
            expected_result="数据被删除。",
            risk=AgenticRisk(level="destructive", reason="删除。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert fake_session.clicked == []
    assert result["status"] == "partial"
    assert result["blockers"][0]["type"] == "crud_scope_violation"
    assert "AI_EXPLORE_1" in result["blockers"][0]["reason"]


def test_agentic_loop_enters_scoped_route_before_recording_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/agentStore",
                "百融百工",
                "state-agent-store",
                [{"id": "button-workspace-001", "name": "工作台", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            ),
            _observation(
                "https://example.test/workspace",
                "百融百工",
                "state-workspace",
                [],
                page_text_summary="标题：百融百工。正文：工作台 类型 全部 状态 全部。",
            ),
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        return AgenticDecisionOutput(decision_type="finish", reason="已进入工作台。")

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)
    runner.start_url = "https://example.test/agentStore"

    result = runner.run()

    assert fake_session.navigated == ["https://example.test/workspace"]
    assert [page["page"]["url"] for page in result["structured_pages"]] == ["https://example.test/workspace"]
    assert result["structured_pages"][0]["page"]["module"] == "工作台"


def test_agentic_loop_blocks_navigation_outside_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_session = _FakeSession(
        [
            _observation(
                "https://example.test/workspace",
                "工作台",
                "state-workspace",
                [{"id": "button-agent-store-001", "name": "探索广场", "role": "button", "action_type": "click", "risk_hint": "safe"}],
            )
        ]
    )

    monkeypatch.setattr(agentic_orchestrator, "PlaywrightBrowserSession", lambda **kwargs: fake_session)

    async def fake_decide(input_data):
        return AgenticDecisionOutput(
            decision_type="act",
            action=AgenticAction(type="click", target_element_id="button-agent-store-001"),
            reason="尝试进入探索广场。",
            expected_result="进入探索广场。",
            risk=AgenticRisk(level="safe", reason="导航入口。"),
        )

    monkeypatch.setattr(agentic_orchestrator.agentic_service, "decide_next_action", fake_decide)
    runner = _runner(tmp_path)

    result = runner.run()

    assert fake_session.clicked == []
    assert result["status"] == "partial"
    assert result["blockers"][0]["type"] == "scope_boundary"
    assert "工作台" in result["blockers"][0]["reason"]


def _runner(tmp_path: Path) -> agentic_orchestrator._AgenticLoopRunner:
    runner = agentic_orchestrator._AgenticLoopRunner(
        run_id="explore-1",
        artifact_root=tmp_path,
        start_url="https://example.test/workspace",
        forbidden_paths="",
        storage_state_path="",
        log_path=tmp_path / "logs" / "run.log",
    )
    runner._load_run = lambda: {
        "id": "explore-1",
        "title": "工作台探索",
        "goal": "工作台模块全部内容",
        "scope": "工作台",
        "forbidden_paths": "",
        "max_pages": 10,
        "max_actions": 10,
    }
    runner._cancel_requested = lambda: False
    runner._publish = lambda event_type, payload: None
    return runner


def _observation(
    url: str,
    title: str,
    signature: str,
    elements: list[dict],
    *,
    page_text_summary: str | None = None,
) -> dict:
    normalized_elements = []
    for element in elements:
        normalized_elements.append(
            {
                "enabled": True,
                "visible": True,
                "text": element["name"],
                "primary_selector": {
                    "kind": "role",
                    "code": f"page.getByRole('button', {{ name: '{element['name']}' }})",
                    "verification": {"checked": True, "unique": True, "visible": True, "match_count": 1},
                },
                **element,
            }
        )
    return {
        "url": url,
        "normalized_url": url,
        "title": title,
        "state_signature": signature,
        "page_text_summary": page_text_summary or f"{title}，{len(elements)} 个元素。",
        "elements": normalized_elements,
        "forms": [],
        "dialogs": [],
        "tables": [],
        "links": [],
        "breadcrumbs": [],
    }


class _FakeSession:
    def __init__(self, observations: list[dict], index: int = 0, click_result: dict | None = None) -> None:
        self.observations = observations
        self.index = index
        self.click_result = click_result
        self.clicked: list[str] = []
        self.filled: list[tuple[str, str]] = []
        self.navigated: list[str] = []
        self.back_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def observe(self) -> dict:
        return self.observations[min(self.index, len(self.observations) - 1)]

    def click(self, element_id: str) -> dict:
        before = self.observe()
        self.clicked.append(element_id)
        if self.click_result is not None:
            return dict(self.click_result)
        self.index = min(self.index + 1, len(self.observations) - 1)
        after = self.observe()
        return {
            "status": "passed",
            "element_id": element_id,
            "before_url": before["url"],
            "after_url": after["url"],
            "url_changed": before["normalized_url"] != after["normalized_url"],
            "state_signature_changed": before["state_signature"] != after["state_signature"],
        }

    def fill(self, element_id: str, value: str) -> dict:
        before = self.observe()
        self.filled.append((element_id, value))
        self.index = min(self.index + 1, len(self.observations) - 1)
        after = self.observe()
        return {
            "status": "passed",
            "element_id": element_id,
            "value": value,
            "before_url": before["url"],
            "after_url": after["url"],
            "url_changed": before["normalized_url"] != after["normalized_url"],
            "state_signature_changed": before["state_signature"] != after["state_signature"],
        }

    def navigate(self, url: str) -> dict:
        before = self.observe()
        self.navigated.append(url)
        for index, observation in enumerate(self.observations):
            if observation["normalized_url"] == url:
                self.index = index
                break
        after = self.observe()
        return {
            "status": "passed",
            "before_url": before["url"],
            "after_url": after["url"],
            "url_changed": before["normalized_url"] != after["normalized_url"],
            "state_signature_changed": before["state_signature"] != after["state_signature"],
        }

    def go_back(self) -> dict:
        before = self.observe()
        self.back_count += 1
        self.index = max(self.index - 1, 0)
        after = self.observe()
        return {
            "status": "passed",
            "before_url": before["url"],
            "after_url": after["url"],
            "url_changed": before["normalized_url"] != after["normalized_url"],
            "state_signature_changed": before["state_signature"] != after["state_signature"],
        }
