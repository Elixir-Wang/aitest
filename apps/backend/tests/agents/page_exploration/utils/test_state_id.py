from app.agents.page_exploration.utils.state_id import (
    make_state_id, STATE_ID_PATTERN
)
import re


def test_root_id():
    assert make_state_id("page-x", "root", 1) == "page-x__root__001"


def test_seq3_padding():
    assert make_state_id("page-x", "dialog", 7) == "page-x__dialog__007"
    assert make_state_id("page-x", "form", 100) == "page-x__form__100"


def test_pattern_matches():
    pat = re.compile(STATE_ID_PATTERN)
    assert pat.fullmatch("page-x__root__001")
    assert pat.fullmatch("page-abc-def__dialog__042")
    assert not pat.fullmatch("page-x__unknown__001")  # unknown 不是 type
    assert not pat.fullmatch("page-x__root__1")       # 缺零填充


def test_seq_below_one_raises():
    import pytest
    with pytest.raises(ValueError):
        make_state_id("page-x", "root", 0)
    with pytest.raises(ValueError):
        make_state_id("page-x", "root", -1)
