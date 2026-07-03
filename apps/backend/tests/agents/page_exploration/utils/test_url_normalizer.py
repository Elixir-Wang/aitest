"""测试 URL 归一化工具"""

from app.agents.page_exploration.utils.url_normalizer import normalize_url


def test_normalize_url_extracts_path():
    """测试提取域名后的路径"""
    assert normalize_url("https://test.example.com/workspace/agents") == "/workspace/agents"
    assert normalize_url("https://prod.example.com/workspace/agents") == "/workspace/agents"


def test_normalize_url_removes_trailing_slash():
    """测试去除尾部斜杠"""
    assert normalize_url("https://test.com/workspace/agents/") == "/workspace/agents"
    assert normalize_url("https://test.com/workspace/") == "/workspace"
    assert normalize_url("https://test.com/") == "/"  # Preserve root


def test_normalize_url_removes_query_and_fragment():
    """测试去除 query 和 fragment"""
    assert normalize_url("https://test.com/workspace?tab=all") == "/workspace"
    assert normalize_url("https://test.com/workspace#section1") == "/workspace"
    assert normalize_url("https://test.com/workspace?tab=all#section1") == "/workspace"


def test_normalize_url_decodes_percent_encoding():
    """测试 URL 解码"""
    assert normalize_url("https://test.com/workspace%20agents") == "/workspace agents"
    assert normalize_url("https://test.com/%E6%99%BA%E8%83%BD%E4%BD%93") == "/智能体"


def test_normalize_url_converts_to_lowercase():
    """测试转小写"""
    assert normalize_url("https://test.com/Workspace/Agents") == "/workspace/agents"
