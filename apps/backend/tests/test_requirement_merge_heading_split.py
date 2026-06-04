from app.schemas.requirement_merge import RequirementMergeSourceFile
from app.services.requirement_merge.source_block_service import build_source_blocks
from app.services.requirement_merge.source_outline_service import build_source_outline, flatten_source_outline


def test_source_outline_splits_by_second_level_heading_only():
    source_files = [
        RequirementMergeSourceFile(
            mapping_id="map-1",
            original_filename="需求.md",
            markdown_content=(
                "# 总需求\n\n"
                "## 登录\n\n"
                "登录概述。\n\n"
                "### 手机验证码\n\n"
                "验证码规则。\n\n"
                "### 密码登录\n\n"
                "密码规则。\n\n"
                "## 注册\n\n"
                "注册规则。\n"
            ),
        )
    ]

    nodes = flatten_source_outline(build_source_outline(source_files))

    assert [(node.level, node.title) for node in nodes] == [(2, "登录"), (2, "注册")]
    assert nodes[0].sub_headings == ["手机验证码", "密码登录"]
    assert "### 手机验证码" in nodes[0].content_markdown
    assert all(node.must_assign for node in nodes)


def test_source_blocks_do_not_split_oversized_second_level_section_by_third_level_heading():
    source_files = [
        RequirementMergeSourceFile(
            mapping_id="map-1",
            original_filename="需求.md",
            markdown_content=(
                "# 总需求\n\n"
                "## 登录\n\n"
                "登录概述。\n\n"
                "### 手机验证码\n\n"
                "验证码规则。\n\n"
                "### 密码登录\n\n"
                "密码规则。\n"
            ),
        )
    ]

    blocks = build_source_blocks(source_files, max_chars=1)

    assert len(blocks) == 1
    assert blocks[0].original_heading == "登录"
    assert blocks[0].heading_path == ["登录"]
    assert blocks[0].sub_headings == ["手机验证码", "密码登录"]
    assert "### 密码登录" in blocks[0].markdown
