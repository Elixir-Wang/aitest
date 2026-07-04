"""需求澄清答复服务的回归测试。

核心回归项：result.json 中只含 option_a / option_b 的字符串字段，
前端用 `<question_id>_option_a` / `<question_id>_option_b` 合成 ID 提交时，
后端必须能命中并写入 understanding_markdown。
"""

import pytest
from fastapi import HTTPException

from app.schemas.document import RequirementClarificationAnswerIn
from app.services.document.service import (
    _match_synthesized_option,
    _option_answer_text,
    _resolve_clarification_answer,
)


_QUESTION = {
    "id": "clar-001",
    "question": "Plan A 中提到的'兜底多图解析模型'具体是哪个模型？",
    "option_a": "系统预设一个默认模型（如 Qwen3.6-plus），用户不可修改",
    "option_b": "在赛博坦后台增加一个'兜底多图解析模型'配置项，由管理员指定",
    "source_excerpt": "如果没有定义图片特定模型进行多图解析，默认使用兜底多图解析模型。",
    "impact": "影响多图解析的核心逻辑实现。",
}


def _payload(
    *,
    answer_type: str,
    selected_option_id: str = "",
    custom_answer: str = "",
) -> RequirementClarificationAnswerIn:
    return RequirementClarificationAnswerIn(
        question_id="clar-001",
        answer_type=answer_type,
        selected_option_id=selected_option_id,
        custom_answer=custom_answer,
    )


def _raised_code(exc_info) -> tuple[int, str]:
    """把 api_error(...) 抛出的 HTTPException 解构成 (status_code, code)。"""
    http_exc: HTTPException = exc_info.value
    detail = http_exc.detail
    assert isinstance(detail, dict)
    return http_exc.status_code, detail["code"]


def test_resolve_clarification_answer_defer_returns_empty_string() -> None:
    answer, selected, note = _resolve_clarification_answer(
        _QUESTION, _payload(answer_type="defer", custom_answer="稍后再说")
    )
    assert answer == ""
    assert selected == ""
    assert note == "稍后再说"


def test_resolve_clarification_answer_custom_requires_text() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _resolve_clarification_answer(
            _QUESTION, _payload(answer_type="custom", custom_answer="   ")
        )
    status, code = _raised_code(exc_info)
    assert status == 422
    assert code == "REQUIREMENT_CLARIFICATION_CUSTOM_ANSWER_REQUIRED"


def test_resolve_clarification_answer_recommended_synthesized_option_a() -> None:
    """回归缺陷：<question_id>_option_a 必须命中并返回 option_a 文本。"""
    answer, selected, note = _resolve_clarification_answer(
        _QUESTION,
        _payload(answer_type="recommended_option", selected_option_id="clar-001_option_a"),
    )
    assert answer == _QUESTION["option_a"]
    assert selected == "clar-001_option_a"
    assert note == ""


def test_resolve_clarification_answer_recommended_synthesized_option_b() -> None:
    answer, selected, _ = _resolve_clarification_answer(
        _QUESTION,
        _payload(answer_type="recommended_option", selected_option_id="clar-001_option_b"),
    )
    assert answer == _QUESTION["option_b"]
    assert selected == "clar-001_option_b"


def test_resolve_clarification_answer_unknown_option_id_raises_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _resolve_clarification_answer(
            _QUESTION,
            _payload(answer_type="recommended_option", selected_option_id="clar-999_option_a"),
        )
    status, code = _raised_code(exc_info)
    assert status == 404
    assert code == "REQUIREMENT_CLARIFICATION_OPTION_NOT_FOUND"


def test_resolve_clarification_answer_missing_selected_id_raises_422() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _resolve_clarification_answer(
            _QUESTION, _payload(answer_type="recommended_option")
        )
    status, code = _raised_code(exc_info)
    assert status == 422
    assert code == "REQUIREMENT_CLARIFICATION_OPTION_REQUIRED"


def test_resolve_clarification_answer_legacy_options_array() -> None:
    """老 schema（options 数组）仍然兼容。"""
    question_with_options = {
        **_QUESTION,
        "options": [
            {"id": "opt-1", "answer_markdown": "老格式答案 A"},
            {"id": "opt-2", "description": "老格式答案 B"},
        ],
    }
    answer, selected, _ = _resolve_clarification_answer(
        question_with_options,
        _payload(answer_type="recommended_option", selected_option_id="opt-1"),
    )
    assert answer == "老格式答案 A"
    assert selected == "opt-1"

    answer, selected, _ = _resolve_clarification_answer(
        question_with_options,
        _payload(answer_type="recommended_option", selected_option_id="opt-2"),
    )
    assert answer == "老格式答案 B"


def test_resolve_clarification_answer_empty_option_text_raises_422() -> None:
    question_empty = {**_QUESTION, "option_a": "", "option_b": ""}
    with pytest.raises(HTTPException) as exc_info:
        _resolve_clarification_answer(
            question_empty,
            _payload(answer_type="recommended_option", selected_option_id="clar-001_option_a"),
        )
    status, code = _raised_code(exc_info)
    assert status == 422
    assert code == "REQUIREMENT_CLARIFICATION_OPTION_EMPTY"


def test_match_synthesized_option_rejects_other_prefixes() -> None:
    """合成 ID 必须严格匹配 <question_id>_option_{a,b} 形式。"""
    assert _match_synthesized_option("clar-001_option_c", "clar-001", _QUESTION) is None
    assert _match_synthesized_option("other-001_option_a", "clar-001", _QUESTION) is None
    assert _match_synthesized_option("clar-001_optiona", "clar-001", _QUESTION) is None
    assert _match_synthesized_option("clar-001_option_a", "", _QUESTION) is None


def test_match_synthesized_option_returns_empty_when_text_empty() -> None:
    """合成 ID 命中但源字段为空时仍返回匹配结果（文本为空），由上层 422 处理。"""
    question = {**_QUESTION, "option_a": "  "}
    text, option_id = _match_synthesized_option("clar-001_option_a", "clar-001", question)
    assert text == ""
    assert option_id == "clar-001_option_a"


def test_option_answer_text_falls_back_to_description() -> None:
    assert _option_answer_text({"answer_markdown": "A"}) == "A"
    assert _option_answer_text({"description": "D"}) == "D"
    assert _option_answer_text({}) == ""


def test_resolve_clarification_answer_legacy_recommended_decision_options() -> None:
    """老 schema（recommended_options / decision_options）也兼容。"""
    question_legacy = {
        **_QUESTION,
        "recommended_options": [{"id": "rec-1", "answer_markdown": "推荐 1"}],
        "decision_options": [{"id": "dec-1", "description": "决策 1"}],
    }
    answer, selected, _ = _resolve_clarification_answer(
        question_legacy,
        _payload(answer_type="recommended_option", selected_option_id="rec-1"),
    )
    assert (answer, selected) == ("推荐 1", "rec-1")

    answer, selected, _ = _resolve_clarification_answer(
        question_legacy,
        _payload(answer_type="recommended_option", selected_option_id="dec-1"),
    )
    assert (answer, selected) == ("决策 1", "dec-1")
