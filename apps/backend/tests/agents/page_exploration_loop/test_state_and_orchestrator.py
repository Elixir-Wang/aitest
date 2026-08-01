from app.agents.page_exploration_loop.services.verifier import verify_action
from app.agents.page_exploration_loop.state.models import make_state_key


def test_state_key_ignores_element_order() -> None:
    left = make_state_key(url="https://example.test/home", title="Home", element_keys=["button-save", "link-settings"])
    right = make_state_key(url="https://example.test/home", title="Home", element_keys=["link-settings", "button-save"])
    assert left == right


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
