"""Tests for artifact tools"""

import pytest
from pathlib import Path
import yaml

from app.agents.page_exploration.tools.artifact_tools import (
    write_page_artifact_tool,
)


@pytest.fixture
def temp_base_dir(tmp_path, monkeypatch):
    """Setup temp directory and patch base path"""
    monkeypatch.setattr(
        'app.agents.page_exploration.tools.artifact_tools.PROJECT_FILE_STORAGE_ROOT',
        tmp_path
    )
    return tmp_path


def test_write_page_artifact_tool_basic(temp_base_dir):
    """Test writing a basic page artifact"""
    elements = [
        {
            "id": "create_agent_btn",
            "name": "创建智能体",
            "role": "button",
            "locators": [
                {
                    "kind": "role",
                    "code": "getByRole('button', { name: '创建智能体' })",
                    "priority": 1,
                    "validation": {
                        "is_unique": True,
                        "is_visible": True
                    }
                }
            ]
        },
        {
            "id": "search_input",
            "name": "搜索",
            "role": "textbox",
            "locators": [
                {
                    "kind": "label",
                    "code": "getByLabel('搜索')",
                    "priority": 1
                }
            ]
        }
    ]

    result = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/workspace/agents",
        "title": "智能体工作台",
        "elements": elements,
        "project_id": "proj-test",
        "page_id": "page-workspace-agents"
    })

    assert result["success"] is True
    assert result["page_id"] == "page-workspace-agents"
    assert result["normalized_path"] == "/workspace/agents"
    assert result["element_count"] == 2
    assert "page-workspace-agents.yaml" in result["file_path"]

    # Verify file was created
    file_path = Path(result["file_path"])
    assert file_path.exists()

    # Verify content
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["page"]["id"] == "page-workspace-agents"
    assert data["page"]["title"] == "智能体工作台"
    assert data["page"]["display_name"] == "agents"
    assert data["page"]["breadcrumb"] == ["workspace", "agents"]
    assert data["page"]["normalized_path"] == "/workspace/agents"
    assert len(data["page"]["elements"]) == 2
    assert data["page"]["elements"][0]["id"] == "create_agent_btn"
    assert data["page"]["elements"][0]["name"] == "创建智能体"

    doc_path = file_path.with_suffix(".md")
    assert doc_path.exists()
    doc = doc_path.read_text(encoding="utf-8")
    assert "# 智能体工作台" in doc
    assert "## 页面用途" in doc
    assert "## 页面功能" in doc
    assert "创建智能体" in doc
    assert "getByRole('button', { name: '创建智能体' })" in doc


def test_write_page_artifact_tool_auto_generate_page_id(temp_base_dir):
    """Test auto-generating page_id from URL"""
    result = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/workspace/agents/create",
        "title": "创建智能体",
        "elements": [],
        "project_id": "proj-test"
    })

    assert result["success"] is True
    assert result["page_id"] == "page-workspace-agents-create"
    assert result["normalized_path"] == "/workspace/agents/create"


def test_write_page_artifact_tool_cross_environment(temp_base_dir):
    """Test that different environment URLs create the same artifact"""
    elements = [
        {
            "id": "btn1",
            "name": "Button",
            "role": "button",
            "locators": []
        }
    ]

    # Write with test environment URL
    result1 = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/workspace/agents",
        "title": "Test",
        "elements": elements,
        "project_id": "proj-test",
        "page_id": "page-workspace-agents"
    })

    # Write with prod environment URL (same normalized path)
    result2 = write_page_artifact_tool.invoke({
        "url": "https://prod.example.com/workspace/agents",
        "title": "Prod",
        "elements": elements,
        "project_id": "proj-test",
        "page_id": "page-workspace-agents"
    })

    # Both should write to the same file
    assert result1["page_id"] == result2["page_id"]
    assert result1["normalized_path"] == result2["normalized_path"]
    assert result1["file_path"] == result2["file_path"]

    # Second write should overwrite first
    file_path = Path(result2["file_path"])
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["page"]["title"] == "Prod"  # Latest write
    assert data["page"]["display_name"] == "agents"
    assert data["page"]["breadcrumb"] == ["workspace", "agents"]


def test_write_page_artifact_tool_uses_path_name_when_titles_repeat(temp_base_dir):
    """Repeated product titles must not drive the page directory name."""
    result1 = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/workspace/agentStore",
        "title": "百融百工",
        "elements": [],
        "project_id": "proj-test",
    })
    result2 = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/workspace/agent/detail",
        "title": "百融百工",
        "elements": [],
        "project_id": "proj-test",
    })

    assert result1["page_id"] == "page-workspace-agentstore"
    assert result2["page_id"] == "page-workspace-agent-detail"

    data1 = yaml.safe_load(Path(result1["file_path"]).read_text(encoding="utf-8"))
    data2 = yaml.safe_load(Path(result2["file_path"]).read_text(encoding="utf-8"))

    assert data1["page"]["title"] == "百融百工"
    assert data2["page"]["title"] == "百融百工"
    assert data1["page"]["display_name"] == "agentstore"
    assert data2["page"]["display_name"] == "detail"
    assert data1["page"]["breadcrumb"] == ["workspace", "agentstore"]
    assert data2["page"]["breadcrumb"] == ["workspace", "agent", "detail"]


def test_write_page_artifact_tool_complex_elements(temp_base_dir):
    """Test writing complex elements with multiple locators"""
    elements = [
        {
            "id": "submit_btn",
            "name": "提交表单",
            "role": "button",
            "locators": [
                {
                    "kind": "role",
                    "code": "getByRole('button', { name: '提交' })",
                    "priority": 1,
                    "validation": {
                        "is_unique": True,
                        "is_visible": True,
                        "match_count": 1
                    }
                },
                {
                    "kind": "testid",
                    "code": "getByTestId('submit-form-btn')",
                    "priority": 2,
                    "validation": {
                        "is_unique": True,
                        "is_visible": True
                    }
                },
                {
                    "kind": "text",
                    "code": "getByText('提交')",
                    "priority": 3
                }
            ]
        }
    ]

    result = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/form",
        "title": "表单页",
        "elements": elements,
        "project_id": "proj-test",
        "page_id": "page-form"
    })

    assert result["success"] is True

    # Verify complex structure
    file_path = Path(result["file_path"])
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    element = data["page"]["elements"][0]
    assert len(element["locators"]) == 3
    assert element["locators"][0]["kind"] == "role"
    assert element["locators"][0]["priority"] == 1
    assert element["locators"][0]["validation"]["is_unique"] is True
    assert element["locators"][1]["kind"] == "testid"
    assert element["locators"][2]["kind"] == "text"


def test_write_page_artifact_tool_empty_elements(temp_base_dir):
    """Test writing a page with no elements"""
    result = write_page_artifact_tool.invoke({
        "url": "https://test.example.com/empty",
        "title": "空页面",
        "elements": [],
        "project_id": "proj-test",
        "page_id": "page-empty"
    })

    assert result["success"] is True
    assert result["element_count"] == 0

    file_path = Path(result["file_path"])
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["page"]["elements"] == []
