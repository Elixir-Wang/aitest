import pytest

from app.services.test_point_markdown import parse_test_points, serialize_test_points


def sample_point(**overrides):
    point = {
        "point_key": "login.success",
        "title": "正确账号密码登录成功",
        "module": "登录",
        "category": "功能",
        "priority": "P0",
        "description": "验证用户可以使用正确凭据登录。",
        "preconditions": ["用户账号已创建", "登录服务正常"],
        "verification_points": ["登录成功并进入首页", "建立有效会话"],
        "source_refs": ["需求 3.1"],
        "notes": "覆盖主流程",
    }
    point.update(overrides)
    return point


def test_test_point_markdown_round_trip():
    points = [
        sample_point(),
        sample_point(
            point_key="login.failure",
            title="错误密码登录失败",
            priority="P1",
            description="验证错误密码不会建立会话。",
            preconditions=[],
            verification_points=["显示密码错误提示"],
            source_refs=[],
            notes="",
        ),
    ]

    markdown_content = serialize_test_points(points)

    assert markdown_content.startswith("# 测试点\n")
    assert "### [login.success] 正确账号密码登录成功" in markdown_content
    assert parse_test_points(markdown_content) == points


def test_parse_test_points_rejects_duplicate_point_key():
    markdown_content = serialize_test_points([sample_point(), sample_point(title="重复测试点")])

    with pytest.raises(ValueError, match="point_key 重复: login.success"):
        parse_test_points(markdown_content)


def test_parse_test_points_rejects_missing_verification_points():
    markdown_content = serialize_test_points([sample_point()]).replace(
        "- 登录成功并进入首页\n- 建立有效会话",
        "无",
    )

    with pytest.raises(ValueError, match="login.success 缺少验证点"):
        parse_test_points(markdown_content)


def test_parse_test_points_rejects_invalid_priority():
    markdown_content = serialize_test_points([sample_point()]).replace("| 优先级 | P0 |", "| 优先级 | P9 |")

    with pytest.raises(ValueError, match="login.success 的优先级无效: P9"):
        parse_test_points(markdown_content)


def test_parse_test_points_rejects_invalid_category():
    markdown_content = serialize_test_points([sample_point()]).replace("| 类型 | 功能 |", "| 类型 | 未知 |")

    with pytest.raises(ValueError, match="login.success 的类型无效: 未知"):
        parse_test_points(markdown_content)


def test_parse_test_points_with_source_in_table_field():
    """测试从表格字段 "来源" 解析来源引用"""
    markdown_content = """# 测试点

### [test.1] 测试点标题

| 字段 | 内容 |
| --- | --- |
| 模块 | 模块A |
| 类型 | 功能 |
| 优先级 | P0 |
| 来源 | 需求规格 3.1.1, 需求规格 3.2 |

**描述**

测试描述

**前置条件**

- 前置条件1

**验证点**

- 验证点1

**来源引用**

- 无

**备注**

备注

---
"""
    points = parse_test_points(markdown_content)
    assert len(points) == 1
    assert points[0]["source_refs"] == ["需求规格 3.1.1", "需求规格 3.2"]
    assert points[0]["module"] == "模块A"


def test_parse_test_points_merges_sources_from_both_table_and_section():
    """测试同时从表格字段和章节合并来源引用"""
    markdown_content = """# 测试点

### [test.1] 测试点标题

| 字段 | 内容 |
| --- | --- |
| 模块 | 模块A |
| 类型 | 功能 |
| 优先级 | P0 |
| 来源 | 来源A |

**描述**

测试描述

**前置条件**

- 前置条件1

**验证点**

- 验证点1

**来源引用**

- 来源B
- 来源C

**备注**

备注

---
"""
    points = parse_test_points(markdown_content)
    assert len(points) == 1
    # 应该合并去重
    assert set(points[0]["source_refs"]) == {"来源A", "来源B", "来源C"}
