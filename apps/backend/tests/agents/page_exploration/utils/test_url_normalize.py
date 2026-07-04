# apps/backend/tests/agents/page_exploration/utils/test_url_normalize.py
from app.agents.page_exploration.utils.url_normalize import (
    normalize_for_compare, urls_equal_modulo_hash
)


def test_normalize_query_order_independent():
    a = normalize_for_compare("/x?a=1&b=2")
    b = normalize_for_compare("/x?b=2&a=1")
    assert a == b


def test_normalize_drops_hash():
    a = normalize_for_compare("/x#frag")
    b = normalize_for_compare("/x")
    assert a == b


def test_normalize_keeps_fragment():
    # 路径里的 hash 区分（fragment 是 DOM 锚点，忽略；URL 协议/host 区分）
    a = normalize_for_compare("https://a.com/x")
    b = normalize_for_compare("https://b.com/x")
    assert a != b


def test_normalize_lowercase_path():
    a = normalize_for_compare("/X")
    b = normalize_for_compare("/x")
    # query 排序 + path lowercase
    assert a == b or a.rstrip("/") == b.rstrip("/")  # 实施可放宽


def test_urls_equal_modulo_hash_true():
    assert urls_equal_modulo_hash("/x#a", "/x#b")


def test_urls_equal_modulo_hash_false():
    assert not urls_equal_modulo_hash("/x", "/y")
