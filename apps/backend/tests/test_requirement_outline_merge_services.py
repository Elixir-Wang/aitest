from __future__ import annotations

from unittest.mock import patch
import unittest

from app.schemas.requirement_merge import (
    OutlineAssignment,
    OutlineSectionBlock,
    OutlineSectionDecision,
    OutlineSectionMergeResult,
    RequirementMergeSourceFile,
    TargetOutlineSection,
)
from app.services import (
    requirement_merge_outline_service,
    requirement_merge_quality_service,
    requirement_merge_render_service,
    requirement_outline_assignment_service,
    requirement_section_merge_service,
    requirement_source_outline_service,
)


class RequirementOutlineMergeServicesTest(unittest.TestCase):
    def test_build_source_outline_keeps_heading_tree_and_preserve_flags(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="""# 总标题

## 接口契约

### login_ticket 生成接口

POST /api/sso/ticket/create

| 字段 | 说明 |
| --- | --- |
| product_code | 产品编码 |

### ticket 校验接口

POST /api/sso/ticket/verify
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )

        documents = requirement_source_outline_service.build_source_outline([source])
        nodes = requirement_source_outline_service.flatten_source_outline(documents)

        self.assertEqual(documents[0].document_code, "A")
        self.assertEqual([node.title for node in nodes], ["总标题", "接口契约", "login_ticket 生成接口", "ticket 校验接口"])
        login_node = next(node for node in nodes if node.title == "login_ticket 生成接口")
        self.assertEqual(login_node.heading_path, ["总标题", "接口契约", "login_ticket 生成接口"])
        self.assertIn("interface", login_node.content_types)
        self.assertIn("table", login_node.content_types)
        self.assertTrue(login_node.preserve_original)

    def test_outline_assignment_render_and_quality_pass(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="""# 统一登录

## login_ticket 生成接口

POST /api/sso/ticket/create

| 字段 | 说明 |
| --- | --- |
| product_code | 产品编码 |
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sect-001",
                    level=2,
                    title="login_ticket 生成接口",
                    source_node_ids=[node.node_id for node in requirement_outline_assignment_service.assignable_source_nodes(documents)],
                )
            ],
        )
        source_nodes = requirement_outline_assignment_service.assignable_source_nodes(documents)
        section_id = requirement_merge_outline_service.assignable_target_sections(outline)[0].section_id
        assignments = [
            OutlineAssignment(
                source_node_id=node.node_id,
                target_section_id=section_id,
                assignment_type="primary",
                reason="测试归属。",
            )
            for node in source_nodes
        ]
        target_ids = {section.section_id for section in requirement_merge_outline_service.assignable_target_sections(outline)}

        self.assertFalse(requirement_outline_assignment_service.validate_assignments(documents, outline, assignments))
        self.assertTrue(all(item.target_section_id in target_ids for item in assignments))

        results = []
        nodes_by_id = {node.node_id: node for node in source_nodes}
        for section in requirement_merge_outline_service.assignable_target_sections(outline):
            nodes = [
                nodes_by_id[assignment.source_node_id]
                for assignment in assignments
                if section.section_id == assignment.target_section_id
            ]
            if nodes:
                results.append(
                    OutlineSectionMergeResult(
                        section_id=section.section_id,
                        blocks=[OutlineSectionBlock(type="source_node_ref", source_node_id=node.node_id) for node in nodes],
                        decisions=[
                            OutlineSectionDecision(
                                section_id=section.section_id,
                                source_node_id=node.node_id,
                                status="preserved_original" if node.preserve_original else "merged",
                                target_heading=section.title,
                                reason="测试章节结果。",
                            )
                            for node in nodes
                        ],
                        conflicts=[],
                    )
                )
        markdown = requirement_merge_render_service.render_merged_markdown("统一登录", documents, outline, results)
        conflicts = requirement_merge_render_service.collect_outline_conflicts(results)
        quality, issues = requirement_merge_quality_service.evaluate_outline_merge_quality(
            source_documents=documents,
            target_outline=outline,
            assignments=assignments,
            section_results=results,
            conflicts=conflicts,
            merged_markdown=markdown,
            stage_errors=[],
        )

        self.assertIn("## login_ticket 生成接口", markdown)
        self.assertIn("POST /api/sso/ticket/create", markdown)
        self.assertEqual(quality, "passed", issues)

    def test_quality_fails_when_preserve_node_is_not_referenced(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="""## login_ticket 生成接口

POST /api/sso/ticket/create
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.fallback_target_outline(documents)
        section = requirement_merge_outline_service.assignable_target_sections(outline)[0]
        nodes = requirement_source_outline_service.flatten_source_outline(documents)
        assignments = [
            OutlineAssignment(
                source_node_id=nodes[0].node_id,
                target_section_id=section.section_id,
                assignment_type="primary",
                reason="测试归属。",
            )
        ]

        quality, issues = requirement_merge_quality_service.evaluate_outline_merge_quality(
            source_documents=documents,
            target_outline=outline,
            assignments=assignments,
            section_results=[],
            conflicts=[],
            merged_markdown="# 合并稿\n\n## 接口契约\n\n接口说明。",
            stage_errors=[],
        )

        self.assertEqual(quality, "failed")
        self.assertTrue(any("高保真旧节点未原文保留" in issue for issue in issues))

    def test_target_outline_has_fixed_root_and_ai_generated_second_third_levels(self):
        sections = [
            TargetOutlineSection(
                section_id="sect-001",
                level=2,
                title="背景与目标",
                children=[
                    TargetOutlineSection(
                        section_id="sect-001-000",
                        parent_id="sect-001",
                        level=3,
                        title="背景与目标概述",
                        source_node_ids=["A-01"],
                    ),
                    TargetOutlineSection(
                        section_id="sect-001-001",
                        parent_id="sect-001",
                        level=3,
                        title="首期目标",
                        source_node_ids=["A-01-01"],
                    )
                ],
            )
        ]

        outline = requirement_merge_outline_service.build_target_outline("统一登录", sections)
        issues = requirement_merge_outline_service.validate_target_outline(outline, "统一登录")

        self.assertFalse(issues)
        self.assertEqual(outline[0].level, 1)
        self.assertEqual(outline[0].title, "统一登录")
        self.assertEqual(outline[0].children[0].level, 2)
        self.assertEqual(outline[0].children[0].source_node_ids, [])
        self.assertEqual(outline[0].children[0].children[0].level, 3)
        self.assertEqual(outline[0].children[0].children[0].source_node_ids, ["A-01"])

    def test_parse_target_outline_source_node_ids(self):
        sections = requirement_merge_outline_service._parse_outline_sections(
            [
                {
                    "section_id": "sect-001",
                    "level": 2,
                    "title": "验收标准",
                    "source_node_ids": ["", None],
                    "children": [
                        {
                            "section_id": "sect-001-000",
                            "level": 3,
                            "title": "验收标准概述",
                            "source_node_ids": ["A-01"],
                        },
                        {
                            "section_id": "sect-001-001",
                            "level": 3,
                            "title": "安全验收",
                            "source_node_ids": ["C-01-14-02"],
                        }
                    ],
                }
            ]
        )

        outline = requirement_merge_outline_service.build_target_outline("统一登录", sections)

        self.assertEqual(outline[0].children[0].source_node_ids, [])
        self.assertEqual(outline[0].children[0].children[0].source_node_ids, ["A-01"])
        self.assertEqual(outline[0].children[0].children[1].source_node_ids, ["C-01-14-02"])

    def test_target_outline_rejects_root_title_mismatch_and_level_four(self):
        outline = [
            TargetOutlineSection(
                section_id="root",
                level=1,
                title="错误标题",
                children=[
                    TargetOutlineSection(
                        section_id="sect-001",
                        parent_id="root",
                        level=2,
                        title="业务章节",
                        children=[
                            TargetOutlineSection(
                                section_id="sect-001-001-001",
                                parent_id="sect-001",
                                level=4,
                                title="过深章节",
                            )
                        ],
                    )
                ],
            )
        ]

        issues = requirement_merge_outline_service.validate_target_outline(outline, "统一登录")

        self.assertTrue(any("一级标题必须等于需求名称" in issue for issue in issues))
        self.assertTrue(any("层级不合法" in issue for issue in issues))

    def test_assignment_rejects_target_root_section(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="## 接口契约\n\nPOST /api/sso/ticket/create\n",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [TargetOutlineSection(section_id="sect-001", level=2, title="接口契约")],
        )
        node = requirement_source_outline_service.flatten_source_outline(documents)[0]
        assignments = [
            OutlineAssignment(
                source_node_id=node.node_id,
                target_section_id="root",
                assignment_type="primary",
                reason="测试归属。",
            )
        ]

        issues = requirement_outline_assignment_service.validate_assignments(documents, outline, assignments)

        self.assertTrue(any("不能归属到一级根节点" in issue for issue in issues))

    def test_assignment_allows_parent_section_without_direct_source_when_children_are_filled(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="""# 统一登录

## 项目背景

背景说明。

## 接入范围

范围说明。
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        nodes = requirement_outline_assignment_service.assignable_source_nodes(documents)
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sect-001",
                    level=2,
                    title="项目概述与范围",
                    children=[
                        TargetOutlineSection(
                            section_id="sect-001-001",
                            parent_id="sect-001",
                            level=3,
                            title="项目背景",
                            source_node_ids=[nodes[0].node_id],
                        ),
                        TargetOutlineSection(
                            section_id="sect-001-002",
                            parent_id="sect-001",
                            level=3,
                            title="接入范围",
                            source_node_ids=[nodes[1].node_id],
                        ),
                    ],
                )
            ],
        )
        assignments = [
            OutlineAssignment(
                source_node_id=nodes[0].node_id,
                target_section_id="sect-001-001",
                assignment_type="primary",
                reason="标题匹配。",
            ),
            OutlineAssignment(
                source_node_id=nodes[1].node_id,
                target_section_id="sect-001-002",
                assignment_type="primary",
                reason="标题匹配。",
            ),
        ]

        issues = requirement_outline_assignment_service.validate_assignments(documents, outline, assignments)

        self.assertFalse(issues)

    def test_assignment_generates_from_target_outline_source_refs_without_ai(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="验收.md",
            markdown_content="""# 统一登录

## 验收标准

### 安全验收

HTTPS 与日志脱敏。
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        nodes = requirement_outline_assignment_service.assignable_source_nodes(documents)
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sec-09",
                    level=2,
                    title="验收标准",
                    children=[
                        TargetOutlineSection(
                            section_id="sec-09-01",
                            parent_id="sec-09",
                            level=3,
                            title="验收标准概述",
                            source_node_ids=[nodes[0].node_id],
                        ),
                        TargetOutlineSection(
                            section_id="sec-09-04",
                            parent_id="sec-09",
                            level=3,
                            title="安全验收",
                            source_node_ids=[nodes[1].node_id],
                        )
                    ],
                )
            ],
        )

        with patch.object(requirement_outline_assignment_service, "run_agent", create=True) as run_agent:
            assignments, errors, debug = self.async_run(
                requirement_outline_assignment_service.assign_source_outline_to_target(documents, outline)
            )

        self.assertFalse(run_agent.called)
        self.assertEqual(errors, [])
        self.assertEqual(
            [(item.source_node_id, item.target_section_id, item.reason) for item in assignments],
            [(nodes[0].node_id, "sec-09-01", "outline_source_ref"), (nodes[1].node_id, "sec-09-04", "outline_source_ref")],
        )
        self.assertEqual(debug["validation_issues"], [])

    def test_outline_source_refs_reject_missing_duplicate_unknown_and_empty_leaf(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="验收.md",
            markdown_content="""## 功能验收

功能通过。

## 安全验收

安全通过。
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        nodes = requirement_outline_assignment_service.assignable_source_nodes(documents)
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sec-01",
                    level=2,
                    title="功能验收",
                    source_node_ids=[nodes[0].node_id, nodes[0].node_id, "missing-node"],
                ),
                TargetOutlineSection(section_id="sec-02", level=2, title="安全验收"),
            ],
        )

        issues = requirement_outline_assignment_service.validate_outline_source_refs(documents, outline)

        self.assertTrue(any("重复标记" in issue for issue in issues))
        self.assertTrue(any("缺少目标大纲来源标记" in issue and nodes[1].node_id in issue for issue in issues))
        self.assertTrue(any("未知旧节点" in issue for issue in issues))
        self.assertTrue(any("目标大纲章节没有旧块归属：sec-02" in issue for issue in issues))

    def test_outline_source_refs_reject_non_leaf_direct_source_refs(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="验收.md",
            markdown_content="""## 验收标准

### 安全验收

安全通过。
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        nodes = requirement_outline_assignment_service.assignable_source_nodes(documents)
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sec-01",
                    level=2,
                    title="验收标准",
                    source_node_ids=[nodes[0].node_id],
                    children=[
                        TargetOutlineSection(
                            section_id="sec-01-01",
                            parent_id="sec-01",
                            level=3,
                            title="安全验收",
                            source_node_ids=[nodes[1].node_id],
                        )
                    ],
                )
            ],
        )

        assignments = requirement_outline_assignment_service.assignments_from_target_outline(outline)
        issues = requirement_outline_assignment_service.validate_outline_source_refs(documents, outline)

        self.assertEqual([(item.source_node_id, item.target_section_id) for item in assignments], [(nodes[1].node_id, "sec-01-01")])
        self.assertTrue(any("非叶子目标大纲章节不能直接承接旧块：sec-01" in issue for issue in issues))
        self.assertTrue(any("缺少目标大纲来源标记" in issue and nodes[0].node_id in issue for issue in issues))

    def test_assignment_reports_title_strong_match_mismatch(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="验收.md",
            markdown_content="""## 验收标准

### 15.2 安全验收

安全通过。
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        nodes = requirement_outline_assignment_service.assignable_source_nodes(documents)
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sec-09",
                    level=2,
                    title="验收标准",
                    children=[
                        TargetOutlineSection(
                            section_id="sec-09-02",
                            parent_id="sec-09",
                            level=3,
                            title="验收标准",
                            source_node_ids=[nodes[0].node_id],
                        ),
                        TargetOutlineSection(
                            section_id="sec-09-03",
                            parent_id="sec-09",
                            level=3,
                            title="B端产品验收",
                            source_node_ids=[nodes[1].node_id],
                        ),
                        TargetOutlineSection(
                            section_id="sec-09-04",
                            parent_id="sec-09",
                            level=3,
                            title="安全验收",
                            source_node_ids=[],
                        ),
                    ],
                )
            ],
        )
        assignments = requirement_outline_assignment_service.assignments_from_target_outline(outline)

        issues = requirement_outline_assignment_service.validate_assignments(documents, outline, assignments)

        self.assertTrue(any("更匹配目标章节 sec-09-04" in issue for issue in issues))

    def test_section_merge_skips_empty_parent_container_and_render_keeps_parent_heading(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="## 项目背景\n\n背景说明。\n",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [
                TargetOutlineSection(
                    section_id="sect-001",
                    level=2,
                    title="项目概述",
                    children=[
                        TargetOutlineSection(section_id="sect-001-001", parent_id="sect-001", level=3, title="项目背景")
                    ],
                )
            ],
        )
        node = requirement_outline_assignment_service.assignable_source_nodes(documents)[0]
        assignments = [
            OutlineAssignment(
                source_node_id=node.node_id,
                target_section_id="sect-001-001",
                assignment_type="primary",
                reason="标题匹配。",
            )
        ]

        results, errors = self.async_run(requirement_section_merge_service.merge_sections_by_target_outline(documents, outline, assignments))
        markdown = requirement_merge_render_service.render_merged_markdown("统一登录", documents, outline, results)

        self.assertFalse(errors)
        self.assertEqual([result.section_id for result in results], ["sect-001-001"])
        self.assertIn("## 项目概述", markdown)
        self.assertIn("### 项目背景", markdown)
        self.assertIn("背景说明", markdown)

    def test_assignment_rejects_discarded_source_node(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="## 接口契约\n\nPOST /api/sso/ticket/create\n",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [TargetOutlineSection(section_id="sect-001", level=2, title="接口契约")],
        )
        node = requirement_outline_assignment_service.assignable_source_nodes(documents)[0]
        assignments = [
            OutlineAssignment(
                source_node_id=node.node_id,
                target_section_id="sect-001",
                assignment_type="discarded_non_requirement",
                reason="非需求内容。",
            )
        ]

        issues = requirement_outline_assignment_service.validate_assignments(documents, outline, assignments)

        self.assertTrue(any("归属类型不合法" in issue for issue in issues))

    def test_assignment_parser_rejects_legacy_multi_target_array(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="## 接口契约\n\nPOST /api/sso/ticket/create\n",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [TargetOutlineSection(section_id="sect-001", level=2, title="接口契约")],
        )
        node = requirement_outline_assignment_service.assignable_source_nodes(documents)[0]
        assignments = requirement_outline_assignment_service._parse_assignments(
            [
                {
                    "source_node_id": node.node_id,
                    "target_section_ids": ["sect-001", "sect-002"],
                    "assignment_type": "primary",
                    "reason": "旧格式一对多归属。",
                }
            ]
        )

        issues = requirement_outline_assignment_service.validate_assignments(documents, outline, assignments)

        self.assertTrue(any("缺少目标章节" in issue for issue in issues))

    def test_assignment_debug_keeps_validation_issues(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="## 项目概述\n\n说明内容。\n",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        documents = requirement_source_outline_service.build_source_outline([source])
        outline = requirement_merge_outline_service.build_target_outline(
            "统一登录",
            [TargetOutlineSection(section_id="sect-001", level=2, title="项目概述")],
        )

        assignments, errors, debug = self.async_run(
            requirement_outline_assignment_service.assign_source_outline_to_target(documents, outline)
        )

        self.assertEqual(assignments, [])
        self.assertTrue(any("旧大纲归属生成失败" in error for error in errors))
        self.assertTrue(any("目标大纲章节没有旧块归属：sect-001" in issue for issue in debug["validation_issues"]))
        self.assertEqual(debug["raw_output"], "assignments generated from target_outline.source_node_ids")

    def async_run(self, coroutine):
        import asyncio

        return asyncio.run(coroutine)


if __name__ == "__main__":
    unittest.main()
