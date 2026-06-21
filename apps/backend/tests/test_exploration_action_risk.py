from app.services.exploration import action_risk


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
