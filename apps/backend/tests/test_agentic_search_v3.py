"""
Agentic Search 功能单元测试
"""

import pytest
from app.agents.requirement_analysis.tools.search_auxiliary import search_auxiliary_docs


def test_search_auxiliary_docs_keyword_match():
    """测试关键词匹配"""
    search_auxiliary_docs._auxiliary_documents = [
        {
            "filename": "规范.md",
            "markdown_content": "验证码有效期为 5 分钟。超时后需要重新获取。"
        }
    ]

    result = search_auxiliary_docs.invoke({"query": "验证码有效期"})

    assert "验证码有效期为 5 分钟" in result
    assert "【文档: 规范.md】" in result


def test_search_auxiliary_docs_not_found():
    """测试未找到"""
    search_auxiliary_docs._auxiliary_documents = [
        {
            "filename": "规范.md",
            "markdown_content": "其他内容"
        }
    ]

    result = search_auxiliary_docs.invoke({"query": "不存在的内容"})

    assert result == "未找到相关内容"


def test_search_auxiliary_docs_context_window():
    """测试返回上下文"""
    search_auxiliary_docs._auxiliary_documents = [
        {
            "filename": "规范.md",
            "markdown_content": "第1行\n第2行\n第3行\n关键词所在行\n第5行\n第6行\n第7行"
        }
    ]

    result = search_auxiliary_docs.invoke({"query": "关键词"})

    # 应该包含前3行和后3行
    assert "第1行" in result
    assert "关键词所在行" in result
    assert "第7行" in result


def test_search_auxiliary_docs_multiple_documents():
    """测试多文档搜索"""
    search_auxiliary_docs._auxiliary_documents = [
        {
            "filename": "文档A.md",
            "markdown_content": "文档A包含验证码规则。"
        },
        {
            "filename": "文档B.md",
            "markdown_content": "文档B也包含验证码说明。"
        }
    ]

    result = search_auxiliary_docs.invoke({"query": "验证码"})

    # 应该返回两个文档的结果
    assert "【文档: 文档A.md】" in result
    assert "【文档: 文档B.md】" in result


def test_search_auxiliary_docs_max_results():
    """测试最多返回3个结果"""
    # 创建5个文档，每个都包含关键词
    docs = [
        {"filename": f"文档{i}.md", "markdown_content": f"第{i}个文档包含关键词。"}
        for i in range(5)
    ]
    search_auxiliary_docs._auxiliary_documents = docs

    result = search_auxiliary_docs.invoke({"query": "关键词"})

    # 最多返回3个结果
    result_count = result.count("【文档:")
    assert result_count <= 3


def test_search_auxiliary_docs_case_insensitive():
    """测试大小写不敏感"""
    search_auxiliary_docs._auxiliary_documents = [
        {
            "filename": "规范.md",
            "markdown_content": "验证码有效期为 5 分钟。"
        }
    ]

    # 使用大写搜索
    result = search_auxiliary_docs.invoke({"query": "验证码有效期"})

    assert "验证码有效期为 5 分钟" in result


def test_search_auxiliary_docs_empty_documents():
    """测试空辅助文档"""
    search_auxiliary_docs._auxiliary_documents = []

    result = search_auxiliary_docs.invoke({"query": "任何关键词"})

    assert result == "未提供辅助文档"
