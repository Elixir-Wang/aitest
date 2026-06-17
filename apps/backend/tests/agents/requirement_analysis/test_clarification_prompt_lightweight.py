from app.agents.requirement_analysis.clarification import CLARIFICATION_SYSTEM_PROMPT


def test_clarification_prompt_does_not_force_heavy_test_artifacts() -> None:
    assert "每个 item 至少 3 个 test_cases" not in CLARIFICATION_SYSTEM_PROMPT
    assert "每个 test_case 至少 3 个 assertion_points" not in CLARIFICATION_SYSTEM_PROMPT
    assert "每个 option 有 pros/cons" not in CLARIFICATION_SYSTEM_PROMPT
    assert "至少3个 test_cases" not in CLARIFICATION_SYSTEM_PROMPT
    assert "至少 3 个 test_cases" not in CLARIFICATION_SYSTEM_PROMPT


def test_clarification_prompt_prefers_lightweight_output() -> None:
    assert "默认不生成 test_cases" in CLARIFICATION_SYSTEM_PROMPT
    assert "options 默认 0-2 个" in CLARIFICATION_SYSTEM_PROMPT
    assert "不要求 pros/cons" in CLARIFICATION_SYSTEM_PROMPT
