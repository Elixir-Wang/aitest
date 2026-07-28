from pathlib import Path

from app.agents.page_exploration_loop.services.orchestrator import LoopOrchestrator
from app.agents.page_exploration_loop.services.verifier import verify_action
from app.agents.page_exploration_loop.state.models import FrontierItem, LoopExplorationState, make_state_key


def test_state_key_ignores_element_order() -> None:
    left = make_state_key(url="https://example.test/home", title="Home", element_keys=["button-save", "link-settings"])
    right = make_state_key(url="https://example.test/home", title="Home", element_keys=["link-settings", "button-save"])
    assert left == right


def test_orchestrator_rejects_decision_outside_candidates(tmp_path: Path) -> None:
    state = LoopExplorationState(
        run_id="run-1",
        project_id="project-1",
        start_url="https://example.test",
        budget={"max_pages": 10, "max_actions": 10},
        frontier=[FrontierItem(state_key="state-a", page_key="page-home", element_key="button-save")],
    )

    result = LoopOrchestrator(state, run_dir=tmp_path).run(
        observe=lambda *_: {"state_signature": "state-a", "page_key": "page-home", "candidates": [{"element_key": "button-create"}]},
        decide=lambda *_: {"action_type": "click", "element_key": "button-save"},
        execute=lambda _: (_ for _ in ()).throw(AssertionError("invalid decision must not execute")),
    )

    assert len(result.failures) == 3
    assert result.frontier[0].status == "failed"
    assert result.stop_reason == "frontier_exhausted"


def test_verifier_requires_observed_effect() -> None:
    verified = verify_action(
        before_state="state-a",
        after_observation={"state_signature": "state-b", "title": "Settings"},
        action_success=True,
    )
    no_effect = verify_action(
        before_state="state-a",
        after_observation={"state_signature": "state-a", "title": "Home"},
        action_success=True,
    )
    assert verified.status == "verified"
    assert no_effect.status == "no_effect"
