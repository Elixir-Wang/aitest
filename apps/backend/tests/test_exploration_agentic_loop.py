from pathlib import Path

import pytest

from app.agents.site_exploration.agentic_schemas import AgenticAction, AgenticDecisionOutput, AgenticExplorationInput, AgenticRisk
from app.services.exploration import action_risk, agentic_orchestrator


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
    assert "完整 CRUD" in destructive_decision.reason


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


def test_fallback_decision_uses_guarded_actions_without_mode_gate() -> None:
    decision = agentic_orchestrator.agentic_service.fallback_decision(
        AgenticExplorationInput(
            current_observation={
                "elements": [
                    {
                        "id": "button-create-001",
                        "name": "创建智能体",
                        "role": "button",
                        "action_type": "click",
                        "risk_hint": "guarded",
                        "enabled": True,
                        "visible": True,
                    }
                ]
            },
        )
    )

    assert decision.decision_type == "act"
    assert decision.action is not None
    assert decision.action.target_element_id == "button-create-001"
    assert decision.risk.level == "guarded"


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
    assert result["status"] == "completed"
    assert result["blockers"] == []
    assert '"risk": "guarded"' in result["log"]


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


def _observation(url: str, title: str, signature: str, elements: list[dict]) -> dict:
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
        "page_text_summary": f"{title}，{len(elements)} 个元素。",
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
