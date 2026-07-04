# apps/backend/tests/agents/page_exploration/utils/test_element_key.py
from app.agents.page_exploration.utils.element_key import (
    build_element_key, slugify, ensure_unique_within_state
)


def test_slugify_lowercase_and_dash():
    assert slugify("Create Agent") == "create-agent"
    assert slugify("创建智能体") == ""  # 全中文 = 空 slug


def test_slugify_collapses_dashes_and_trims():
    assert slugify("a  --  b") == "a-b"
    assert slugify("---foo---") == "foo"
    assert slugify("a" * 50) == "a" * 40  # 截断到 40


def test_build_element_key_role_name():
    src = {"role": "button", "name": "创建智能体"}
    assert build_element_key(src) == "button-创建智能体"

    src = {"role": "button", "name": "Create"}
    assert build_element_key(src) == "button-create"


def test_build_element_key_priority_order():
    # role+name 胜出，label 不参与
    src = {
        "role": "button", "name": "Submit",
        "label": "OK", "placeholder": "请输入"
    }
    assert build_element_key(src) == "button-submit"


def test_build_element_key_only_label():
    src = {"role": "textbox", "label": "搜索"}
    assert build_element_key(src) == "textbox-搜索"


def test_build_element_key_fallback_text():
    src = {"role": "button", "text": "我是按钮"}
    assert build_element_key(src) == "button-我是按钮"


def test_ensure_unique_within_state_passthrough():
    keys = ["button-a", "button-b"]
    out = list(ensure_unique_within_state(keys))
    assert out == ["button-a", "button-b"]


def test_ensure_unique_within_state_collision():
    keys = ["button-a", "button-a", "button-b", "button-a"]
    out = list(ensure_unique_within_state(keys))
    assert out == ["button-a", "button-a-2", "button-b", "button-a-3"]
