import pytest

from app.agents.requirement_exploration.schemas import (
    RequirementExplorationInput,
    RequirementExplorationPlan,
)


@pytest.fixture
def simple_requirement_markdown():
    """简单的需求文档示例"""
    return """
# 用户管理系统

## 用户列表

### 功能描述
展示系统中所有用户的列表，支持查询和操作。

### 功能要点
- 展示用户列表表格，包含以下字段：
  - 用户名
  - 邮箱
  - 角色
  - 状态
- 支持按用户名搜索
- 支持按角色筛选
- 点击"新增用户"按钮打开创建表单

### UI元素
- 搜索输入框：id为"user-search"
- 角色筛选下拉框：class为"role-filter"
- 新增用户按钮：button[data-testid="add-user-btn"]
- 用户列表表格：id为"user-table"

## 用户编辑

### 功能描述
编辑用户的基本信息。

### 前置条件
需要先在用户列表中选择要编辑的用户。

### 功能要点
- 打开编辑弹窗，展示用户当前信息
- 可编辑字段：用户名、邮箱、角色
- 点击"保存"按钮提交修改
- 点击"取消"按钮关闭弹窗
"""


@pytest.fixture
def project_context():
    """项目上下文示例"""
    return {
        "project_id": "test-project-id",
        "project_name": "测试项目",
        "project_description": "用于测试的项目",
    }


def test_requirement_exploration_input_validation(simple_requirement_markdown, project_context):
    """测试输入数据验证"""
    input_data = RequirementExplorationInput(
        requirement_markdown=simple_requirement_markdown,
        project_context=project_context,
    )

    assert input_data.requirement_markdown == simple_requirement_markdown
    assert input_data.project_context == project_context


def test_requirement_exploration_plan_structure():
    """测试探索计划数据结构"""
    plan = RequirementExplorationPlan(
        requirement_doc_id="doc-123",
        requirement_run_id="run-456",
        business_boundary="用户管理系统",
        summary="已生成 2 个探索计划项",
        items=[
            {
                "id": "plan-query_filter-01",
                "business_module": "用户列表模块",
                "capability_type": "query_filter",
                "title": "用户查询筛选功能",
                "requirement_section": "用户列表",
                "steps": ["完整探索用户列表的查询筛选功能"],
                "exploration_points": ["验证搜索框功能", "验证角色筛选"],
                "ui_elements": [
                    {
                        "element_name": "搜索输入框",
                        "selector_type": "CSS",
                        "selector": "#user-search",
                        "page_path": "/users",
                        "confidence": "high",
                    }
                ],
                "related_items": [],
            },
            {
                "id": "plan-create_import-02",
                "business_module": "用户列表模块",
                "capability_type": "create_import",
                "title": "新增用户功能",
                "requirement_section": "用户列表",
                "steps": ["测试新增用户按钮和表单提交"],
                "exploration_points": ["验证表单字段", "验证提交结果"],
                "ui_elements": [
                    {
                        "element_name": "新增用户按钮",
                        "selector_type": "CSS",
                        "selector": 'button[data-testid="add-user-btn"]',
                        "page_path": "/users",
                        "confidence": "high",
                    }
                ],
                "related_items": [],
            },
        ],
        dependencies=[
            {
                "from_item_id": "plan-query_filter-01",
                "to_item_id": "plan-create_import-02",
                "dependency_type": "related",
                "description": "新增用户后可在列表中查询",
            }
        ],
    )

    assert plan.requirement_doc_id == "doc-123"
    assert plan.requirement_run_id == "run-456"
    assert plan.business_boundary == "用户管理系统"
    assert len(plan.items) == 2
    assert len(plan.dependencies) == 1

    # 验证第一个item
    item1 = plan.items[0]
    assert item1.id == "plan-query_filter-01"
    assert item1.capability_type == "query_filter"
    assert len(item1.ui_elements) == 1
    assert item1.ui_elements[0].selector == "#user-search"
    assert item1.ui_elements[0].confidence == "high"

    # 验证依赖关系
    dep = plan.dependencies[0]
    assert dep.from_item_id == "plan-query_filter-01"
    assert dep.to_item_id == "plan-create_import-02"
    assert dep.dependency_type == "related"


def test_ui_element_locator_validation():
    """测试UI元素定位信息验证"""
    from app.agents.requirement_exploration.schemas import UIElementLocator

    element = UIElementLocator(
        element_name="登录按钮",
        selector_type="CSS",
        selector="#login-btn",
        page_path="/login",
        confidence="high",
    )

    assert element.element_name == "登录按钮"
    assert element.selector_type == "CSS"
    assert element.selector == "#login-btn"
    assert element.confidence == "high"


def test_empty_requirement_markdown():
    """测试空需求文档"""
    input_data = RequirementExplorationInput(
        requirement_markdown="",
        project_context={},
    )

    assert input_data.requirement_markdown == ""


def test_plan_with_no_dependencies():
    """测试没有依赖关系的计划"""
    plan = RequirementExplorationPlan(
        requirement_doc_id="doc-123",
        requirement_run_id="run-456",
        business_boundary="测试系统",
        summary="测试计划",
        items=[
            {
                "id": "plan-content_display-01",
                "business_module": "测试模块",
                "capability_type": "content_display",
                "title": "内容展示",
                "requirement_section": "测试章节",
                "steps": ["测试内容展示"],
                "exploration_points": ["验证展示效果"],
                "ui_elements": [],
                "related_items": [],
            }
        ],
        dependencies=[],  # 空依赖列表
    )

    assert len(plan.dependencies) == 0
    assert len(plan.items) == 1
