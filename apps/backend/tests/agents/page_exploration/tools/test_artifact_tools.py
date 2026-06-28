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
        'app.agents.page_exploration.tools.artifact_tools.Path',
        lambda x: tmp_path if x == "data/projects" else Path(x)
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
    assert data["page"]["normalized_path"] == "/workspace/agents"
    assert len(data["page"]["elements"]) == 2
    assert data["page"]["elements"][0]["id"] == "create_agent_btn"
    assert data["page"]["elements"][0]["name"] == "创建智能体"


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
