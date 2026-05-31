from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path
from pydantic import ValidationError
from unittest.mock import patch

from app.schemas.requirement_merge import (
    RequirementClusterDecisionRaw,
    RequirementCoverageItem,
    RequirementMergeConflictOut,
    RequirementMergeInput,
    RequirementMergeOutput,
    RequirementMergeSourceFile,
    RequirementSectionMergeOutputRaw,
)
from app.services.requirement_merge_service import (
    _canonicalize_cluster_decision_payload,
    _complete_source_file_coverage,
    _parse_agent_output,
    normalize_merge_output,
    run_requirement_merge,
    run_requirement_merge_agent,
)
from app.services.requirement_fragment_service import build_source_fragments
from app.services.requirement_source_block_service import build_source_blocks
from app.services import requirement_merge_service
from app.services.requirement_merge_artifact_service import (
    public_artifact_tabs,
    read_merge_artifact_tabs,
    write_merge_machine_artifacts,
    write_merge_artifacts,
    evaluate_merge_quality,
    markdown_structure_retention_issue,
    merge_retention_issue,
)


class RequirementMergeServiceTest(unittest.IsolatedAsyncioTestCase):
    def _artifact_store(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        patches = [
            patch(
                "app.services.requirement_merge_artifact_service.project_requirement_dir",
                lambda project_id, document_id: root / project_id / "requirements" / document_id,
            ),
            patch("app.services.requirement_merge_artifact_service.store_path", lambda path: str(path)),
        ]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(temp_dir.cleanup)
        return root

    def test_source_blocks_keep_section_context_and_structures_together(self):
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content="""# 总标题

## login_ticket 生成接口

产品后端调用认证中心创建登录票据。

请求地址：

POST /api/sso/ticket/create

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| product_code | string | 产品编码 |

```json
{"code": "SUCCESS"}
```

## 查询产品进入状态接口

进入产品前需要查询状态。

```mermaid
flowchart TD
  A["查询"] --> B["判断 action"]
```
""",
            conversion_status="success",
            mapping_status="pending_merge",
        )

        blocks = build_source_blocks([source])

        self.assertEqual([block.block_id for block in blocks], ["A-01", "A-02"])
        self.assertEqual(blocks[0].source_code, "A")
        self.assertEqual(blocks[0].original_heading, "login_ticket 生成接口")
        self.assertIn("产品后端调用认证中心", blocks[0].markdown)
        self.assertIn("| product_code | string | 产品编码 |", blocks[0].markdown)
        self.assertIn("```json", blocks[0].markdown)
        self.assertIn("```mermaid", blocks[1].markdown)
        self.assertIn("state_flow", blocks[1].content_types)

    def test_source_blocks_split_oversized_second_level_by_complete_third_level_units(self):
        markdown = """# 总标题

## 接口契约

### login_ticket 生成接口

请求地址：

POST /api/sso/ticket/create

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| product_code | string | 产品编码 |

### ticket 校验接口

请求地址：

POST /api/sso/ticket/verify

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| login_ticket | string | 一次性票据 |
"""
        source = RequirementMergeSourceFile(
            mapping_id="docmap-api",
            original_filename="接口契约.md",
            markdown_content=markdown,
            conversion_status="success",
            mapping_status="pending_merge",
        )

        blocks = build_source_blocks([source], max_chars=120)

        self.assertEqual([block.block_id for block in blocks], ["A-01", "A-02"])
        self.assertEqual(blocks[0].heading_path, ["接口契约", "login_ticket 生成接口"])
        self.assertEqual(blocks[1].heading_path, ["接口契约", "ticket 校验接口"])
        self.assertIn("| product_code |", blocks[0].markdown)
        self.assertIn("| login_ticket |", blocks[1].markdown)

    def test_merge_artifacts_expose_quality_and_confirmation_documents(self):
        self._artifact_store()
        source_files = [
            RequirementMergeSourceFile(
                mapping_id="docmap-1",
                original_filename="接口契约.md",
                markdown_content="## 接口\n\n支持 ticket 校验。",
                conversion_status="success",
                mapping_status="pending_merge",
            )
        ]
        source_blocks = build_source_blocks(source_files)

        tabs = write_merge_artifacts(
            "project-artifact-test",
            "doc-artifact-test",
            "mergerun-three-docs",
            preview_markdown="# 合并后的文档\n\n## 接口契约\n\n支持 ticket 校验。",
            coverage_items=[
                {
                    "source_block_id": "A-01",
                    "mapping_id": "docmap-1",
                    "source_heading": "接口",
                    "source_excerpt": "支持 ticket 校验。",
                    "coverage_status": "merged",
                    "target_module": "接口契约",
                    "target_heading": "ticket 校验",
                    "reason": "已合并。",
                }
            ],
            conflicts=[],
            merge_summary="已生成合并后的文档。",
            diff_summary="无明显冲突。",
            affected_modules=["接口契约"],
            source_files=source_files,
            source_blocks=source_blocks,
            quality_result="passed",
            blocking_issues=[],
        )

        self.assertEqual([tab["key"] for tab in tabs], ["merged", "quality", "confirmations"])
        self.assertEqual([tab["label"] for tab in tabs], ["合并后的文档", "质量检测", "待确认项"])
        self.assertEqual([tab["key"] for tab in public_artifact_tabs(tabs)], ["quality", "confirmations"])

        saved_tabs = read_merge_artifact_tabs("project-artifact-test", "doc-artifact-test", "mergerun-three-docs")
        self.assertEqual([tab["key"] for tab in saved_tabs], ["quality", "confirmations"])
        quality_markdown = saved_tabs[0]["content"]
        self.assertIn("# 质量检测", quality_markdown)
        self.assertIn("## 检测结论", quality_markdown)
        self.assertIn("| 合并质量 | 通过 |", quality_markdown)
        self.assertIn("## 来源覆盖", quality_markdown)
        self.assertIn("| 来源文件数 | 1 |", quality_markdown)
        self.assertIn("| 来源块总数 | 1 |", quality_markdown)
        self.assertIn("## 内容保留", quality_markdown)
        self.assertIn("## 合并完整性", quality_markdown)
        self.assertIn("## 来源追溯摘要", quality_markdown)
        self.assertIn("接口：已合入「接口契约 / ticket 校验」", quality_markdown)
        self.assertNotIn("docmap-1", quality_markdown)
        self.assertNotIn("mapping_id", quality_markdown)
        self.assertNotIn("fragment", quality_markdown)
        confirmation_markdown = saved_tabs[1]["content"]
        self.assertIn("# 待确认项", confirmation_markdown)
        self.assertIn("本次未发现需要人工确认的差异。", confirmation_markdown)

    def test_machine_artifacts_include_source_blocks_as_primary_traceability_unit(self):
        self._artifact_store()
        source = RequirementMergeSourceFile(
            mapping_id="docmap-1",
            original_filename="接口契约.md",
            markdown_content="## 接口\n\n支持 ticket 校验。",
            conversion_status="success",
            mapping_status="pending_merge",
        )
        source_blocks = build_source_blocks([source])

        paths = write_merge_machine_artifacts(
            "project-artifact-test",
            "doc-artifact-test",
            "mergerun-source-blocks",
            source_fragments=[],
            source_blocks=source_blocks,
            decisions=[],
        )

        self.assertIn("source_blocks_path", paths)
        self.assertIn("source-blocks.json", paths["source_blocks_path"])

    def test_merge_output_accepts_coverage_items(self):
        output = RequirementMergeOutput(
            status="merged",
            markdown_content="# 需求",
            merge_summary="已归并 1 个标准文件。",
            coverage_items=[
                RequirementCoverageItem(
                    mapping_id="docmap-1",
                    source_excerpt="支持账号登录",
                    coverage_status="merged",
                    reason="已归并到需求工作稿。",
                )
            ],
        )

        self.assertEqual(output.coverage_items[0].coverage_status, "merged")

    def test_merge_output_rejects_invalid_status(self):
        with self.assertRaises(ValidationError):
            RequirementMergeOutput(status="done", merge_summary="invalid")

    def test_coverage_item_rejects_invalid_status(self):
        with self.assertRaises(ValidationError):
            RequirementCoverageItem(
                mapping_id="docmap-1",
                source_excerpt="支持账号登录",
                coverage_status="unknown",
                reason="invalid",
            )

    def test_parse_agent_output_accepts_json_string(self):
        output = _parse_agent_output(
            """
            {
              "status": "merged",
              "markdown_content": "# 登录需求\\n",
              "merge_summary": "已由智能体归并 2 个文件。",
              "source_file_ids": ["docmap-1"]
            }
            """
        )

        self.assertEqual(output.status, "merged")
        self.assertEqual(output.source_file_ids, ["docmap-1"])

    def test_parse_agent_output_extracts_fenced_json(self):
        output = _parse_agent_output(
            """
            已完成需求归并：

            ```json
            {
              "status": "merged",
              "markdown_content": "# 登录需求\\n",
              "merge_summary": "已由智能体归并 1 个文件。",
              "source_file_ids": ["docmap-1"],
              "coverage_items": [
                {
                  "mapping_id": "docmap-1",
                  "source_excerpt": "支持账号登录",
                  "coverage_status": "merged",
                  "reason": "已合入。"
                }
              ]
            }
            ```
            """
        )

        self.assertEqual(output.status, "merged")
        self.assertEqual(output.coverage_items[0].mapping_id, "docmap-1")

    def test_parse_agent_output_extracts_json_from_wrapped_text(self):
        output = _parse_agent_output(
            """
            以下是归并结果：
            {
              "status": "merged",
              "markdown_content": "# 登录需求\\n",
              "merge_summary": "已由智能体归并 1 个文件。",
              "source_file_ids": ["docmap-1"],
              "coverage_items": [
                {
                  "mapping_id": "docmap-1",
                  "source_excerpt": "支持账号登录",
                  "coverage_status": "merged",
                  "reason": "已合入。"
                }
              ]
            }
            请查收。
            """
        )

        self.assertEqual(output.markdown_content, "# 登录需求\n")

    def test_parse_agent_output_repairs_unescaped_quotes_in_markdown_content(self):
        output = _parse_agent_output(
            """
            {
              "status": "merged",
              "markdown_content": "# 登录需求\\n\\n- 请求体需包含 access_status("CONNECTED")，可选 bind_source。",
              "markdown_preview": "",
              "merge_summary": "已由智能体归并 1 个文件。",
              "source_file_ids": ["docmap-1"],
              "coverage_items": [
                {
                  "mapping_id": "docmap-1",
                  "source_excerpt": "支持账号登录",
                  "coverage_status": "merged",
                  "reason": "已合入。"
                }
              ]
            }
            """
        )

        self.assertIn('access_status("CONNECTED")', output.markdown_content)

    def test_parse_agent_output_completes_truncated_coverage_array(self):
        output = _parse_agent_output(
            """
            {
              "status": "merged",
              "markdown_content": "# 登录需求\\n",
              "merge_summary": "已由智能体归并 1 个文件。",
              "source_file_ids": ["docmap-1"],
              "coverage_items": [
                {
                  "mapping_id": "docmap-1",
                  "source_excerpt": "支持账号登录",
                  "coverage_status": "merged",
                  "reason": "已合入。"
                },
                {
                  "mapping_id": "docmap-1",
                  "source_excerpt": "支持邮箱登录",
                  "coverage_status": "merged",
                  "reason": "已合入。"
                }
            """
        )

        self.assertEqual(len(output.coverage_items), 2)
        self.assertEqual(output.coverage_items[1].source_excerpt, "支持邮箱登录")

    def test_parse_agent_output_completes_partial_preview_payload(self):
        output = _parse_agent_output(
            """
            {
              "status": "preview",
              "markdown_content": "",
              "markdown_preview": "# 登录需求\\n"
            }
            """
        )

        self.assertEqual(output.status, "preview")
        self.assertEqual(output.markdown_preview, "# 登录需求\n")
        self.assertIn("未返回归并摘要", output.merge_summary)

    def test_complete_source_file_coverage_adds_missing_file_items(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="统一登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="接入说明.docx",
                    markdown_content="# 接入说明\n\n- 支持 SSO 登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                ),
                RequirementMergeSourceFile(
                    mapping_id="docmap-2",
                    original_filename="接口契约.md",
                    markdown_content="# 接口契约\n\n- 支持 ticket 校验",
                    conversion_status="success",
                    mapping_status="pending_merge",
                ),
            ],
        )
        output = RequirementMergeOutput(
            status="preview",
            markdown_preview="# 统一登录需求\n",
            merge_summary="已生成候选稿。",
            source_file_ids=["docmap-1"],
            coverage_items=[
                RequirementCoverageItem(
                    mapping_id="docmap-1",
                    source_excerpt="支持 SSO 登录",
                    coverage_status="merged",
                    reason="已合入。",
                )
            ],
        )

        _complete_source_file_coverage(output, input_data)

        self.assertEqual(output.source_file_ids, ["docmap-1"])
        self.assertEqual({item.mapping_id for item in output.coverage_items}, {"docmap-1", "docmap-2"})

    def test_canonicalize_cluster_decision_payload_normalizes_raw_statuses(self):
        raw_decision = RequirementClusterDecisionRaw(
            cluster_id="cluster-1",
            decision="deduplicate",
            canonical_meaning="支持账号登录。",
            fragment_decisions=[
                {
                    "fragment_id": "frag-1",
                    "coverage_status": "included",
                    "target_module": "登录",
                    "target_heading": "账号登录",
                    "reason": "合入。",
                },
                {
                    "fragment_id": "frag-2",
                    "coverage_status": "deduplicated",
                    "target_module": "登录",
                    "target_heading": "账号登录",
                    "reason": "重复。",
                },
            ],
        )

        decision = _canonicalize_cluster_decision_payload(raw_decision)

        self.assertEqual(decision.decision, "duplicate")
        self.assertEqual(
            [item.coverage_status for item in decision.fragment_decisions],
            ["merged", "duplicate"],
        )

    def test_canonicalize_cluster_decision_payload_rejects_unknown_fragment_status(self):
        raw_decision = RequirementClusterDecisionRaw(
            cluster_id="cluster-1",
            decision="merge",
            fragment_decisions=[
                {
                    "fragment_id": "frag-1",
                    "coverage_status": "mystery_status",
                    "reason": "无法识别。",
                }
            ],
        )

        with self.assertRaisesRegex(ValueError, "无法归一化"):
            _canonicalize_cluster_decision_payload(raw_decision)

    def test_requirement_cluster_decision_raw_coerces_none_string_fields(self):
        raw_decision = RequirementClusterDecisionRaw(
            cluster_id="cluster-1",
            decision="merge",
            fragment_decisions=[
                {
                    "fragment_id": "frag-1",
                    "coverage_status": "merged",
                    "target_module": None,
                    "target_heading": None,
                    "covered_by_fragment_id": None,
                    "related_conflict_key": None,
                    "related_clarification_key": None,
                    "reason": None,
                }
            ],
        )

        item = raw_decision.fragment_decisions[0]

        self.assertEqual(item.target_module, "")
        self.assertEqual(item.target_heading, "")
        self.assertEqual(item.covered_by_fragment_id, "")
        self.assertEqual(item.related_conflict_key, "")
        self.assertEqual(item.related_clarification_key, "")
        self.assertEqual(item.reason, "")

    def test_agent_prompt_forbids_source_document_grouping_in_markdown(self):
        prompt = requirement_merge_service._build_agent_prompt(
            RequirementMergeInput(
                project_id="project-1",
                document_id="doc-1",
                document_name="统一登录需求",
                merge_mode="initial",
                source_files=[
                    RequirementMergeSourceFile(
                        mapping_id="docmap-1",
                        original_filename="接入说明.docx",
                        markdown_content="# 接入说明\n\n- 支持 SSO 登录",
                        conversion_status="success",
                        mapping_status="pending_merge",
                    )
                ],
            )
        )

        self.assertIn("禁止展示源文件名", prompt)
        self.assertIn("源文件追溯只能放在 coverage_items", prompt)
        self.assertIn("不得污染正式需求正文", prompt)
        self.assertIn("coverage_items 必须覆盖每个有效来源块", prompt)
        self.assertIn("覆盖每个有效来源块", prompt)
        self.assertIn("不得摘要化导致需求", prompt)
        self.assertIn("source_excerpt 必须简短", prompt)
        self.assertIn("重复去重 N 处", prompt)
        self.assertIn("没有明显冲突时，才可以生成合并后的文档", prompt)
        self.assertIn("不要求生成质量报告文档", prompt)
        self.assertIn("纯说明性内容标 discarded", prompt)
        self.assertIn("Mermaid 流程图", prompt)
        self.assertIn("不得改写成普通段落或项目符号", prompt)

    def test_merge_quality_fails_when_merged_draft_drops_most_source_content(self):
        source_markdown = "\n".join(f"- 支持独有业务规则 {index:02d}，需要在合并稿中保留。" for index in range(1, 31))
        source_files = [
            RequirementMergeSourceFile(
                mapping_id="docmap-1",
                original_filename="长需求.md",
                markdown_content=f"# 长需求\n\n{source_markdown}",
                conversion_status="success",
                mapping_status="pending_merge",
            )
        ]
        short_markdown = "# 长需求\n\n## 需求概述\n\n- 支持主要业务规则。"

        issue = merge_retention_issue(short_markdown, source_files)
        quality_result, blocking_issues = evaluate_merge_quality(
            [
                {
                    "mapping_id": "docmap-1",
                    "source_excerpt": "支持独有业务规则",
                    "coverage_status": "merged",
                    "reason": "智能体声称已合入。",
                }
            ],
            [],
            short_markdown,
            source_files,
            "已归并 1 个标准文件。",
        )

        self.assertIn("异常过短", issue)
        self.assertEqual(quality_result, "failed")
        self.assertTrue(any("疑似只生成摘要" in item for item in blocking_issues))

    def test_merge_quality_fails_when_structured_markdown_is_flattened(self):
        source_markdown = """# 接口需求

## 状态查询

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| product_code | string | 产品编码 |
| action | string | 前端动作 |
| reason | string | 处理原因 |

```mermaid
flowchart TD
  A["查询状态"] --> B["判断 action"]
```

```json
{
  "code": "SUCCESS",
  "data": {
    "action": "SHOW_INVITE_DIALOG"
  }
}
```
"""
        source_files = [
            RequirementMergeSourceFile(
                mapping_id="docmap-1",
                original_filename="接口需求.md",
                markdown_content=source_markdown,
                conversion_status="success",
                mapping_status="pending_merge",
            )
        ]
        flattened_markdown = """# 接口需求

## 状态查询

- product_code 为产品编码。
- action 用于表示前端动作。
- 查询状态后判断 action。
- 成功时返回 SUCCESS 和 SHOW_INVITE_DIALOG。
"""

        issue = markdown_structure_retention_issue(flattened_markdown, source_files)
        quality_result, blocking_issues = evaluate_merge_quality(
            [
                {
                    "mapping_id": "docmap-1",
                    "source_excerpt": "状态查询接口包含字段、流程和响应示例",
                    "coverage_status": "merged",
                    "reason": "智能体声称已合入。",
                }
            ],
            [],
            flattened_markdown,
            source_files,
            "已归并 1 个标准文件。",
        )

        self.assertIn("结构化 Markdown", issue)
        self.assertEqual(quality_result, "failed")
        self.assertTrue(any("结构化 Markdown" in item for item in blocking_issues))

    def test_normalize_merge_output_uses_source_filename_stem_and_duplicate_count(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="统一登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="接入说明.docx",
                    markdown_content="# 接入说明\n\n- 支持 SSO 登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        output = normalize_merge_output(
            RequirementMergeOutput(
                status="merged",
                markdown_content="# 统一登录需求\n\n- 支持 SSO 登录",
                merge_summary="已归并 1 个标准文件。",
                coverage_items=[
                    RequirementCoverageItem(
                        mapping_id="docmap-1",
                        source_heading="docmap-1",
                        source_excerpt="支持 SSO 登录",
                        coverage_status="duplicate",
                        reason="与已合入语句表达相同。",
                    )
                ],
                conflicts=[
                    RequirementMergeConflictOut(
                        title="不会使用",
                        source_refs=[{"mapping_id": "docmap-1", "filename": "接入说明.docx"}],
                        fragment_a="A",
                        fragment_b="B",
                    )
                ],
            ),
            input_data,
        )

        self.assertEqual(output.coverage_items[0].source_heading, "接入说明")
        self.assertIn("重复去重 1 处", output.merge_summary)
        self.assertEqual(output.conflicts[0].source_refs[0]["filename"], "接入说明")

    def test_cluster_conflicts_normalizes_agent_conflict_payload(self):
        decision = requirement_merge_service.RequirementClusterDecision(
            cluster_id="cluster-1",
            decision="conflict",
            canonical_meaning="登录入口保留规则",
            fragment_decisions=[],
            conflicts=[
                {
                    "title": "登录入口保留规则冲突",
                    "fragment_ids": ["A-01", "B-02"],
                    "fragment_a": "原产品登录入口必须保留。",
                    "fragment_b": "统一认证接入后隐藏原登录入口。",
                }
            ],
        )

        conflicts = requirement_merge_service._cluster_conflicts([decision])

        self.assertEqual(len(conflicts), 1)
        self.assertIsInstance(conflicts[0], RequirementMergeConflictOut)
        self.assertEqual(conflicts[0].source_refs, [{"fragment_id": "A-01"}, {"fragment_id": "B-02"}])
        self.assertEqual(conflicts[0].agent_suggestion, "需要人工确认。")

    def test_section_merge_payload_normalizes_list_content(self):
        raw_output = RequirementSectionMergeOutputRaw(
            section_key="cluster-1",
            blocks=[
                {
                    "type": "paragraph",
                    "content": ["官网统一认证中心提供统一登录入口。", "产品侧保留全量登录入口。"],
                }
            ],
            covered_fragment_ids=[1, "B-02", None],
        )

        output = requirement_merge_service._canonicalize_section_merge_payload(raw_output)

        self.assertEqual(output.blocks[0].content, "官网统一认证中心提供统一登录入口。\n产品侧保留全量登录入口。")
        self.assertEqual(output.covered_fragment_ids, ["1", "B-02"])

    def test_section_merge_payload_normalizes_bullet_list_content(self):
        raw_output = RequirementSectionMergeOutputRaw(
            section_key="cluster-1",
            blocks=[
                {
                    "type": "list",
                    "content": ["支持账号登录", "支持短信登录"],
                }
            ],
            covered_fragment_ids=[],
        )

        output = requirement_merge_service._canonicalize_section_merge_payload(raw_output)

        self.assertEqual(output.blocks[0].type, "bullet_list")
        self.assertEqual(output.blocks[0].content, "")
        self.assertEqual(output.blocks[0].items, ["支持账号登录", "支持短信登录"])

    def test_normalize_merge_output_rejects_uncovered_source_file(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="统一登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="接入说明.docx",
                    markdown_content="# 接入说明\n\n- 支持 SSO 登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )

        with self.assertRaisesRegex(ValueError, "未返回段落映射"):
            normalize_merge_output(
                RequirementMergeOutput(
                    status="merged",
                    markdown_content="# 统一登录需求\n",
                    merge_summary="已归并。",
                    coverage_items=[],
                ),
                input_data,
            )

    async def test_run_requirement_merge_uses_agent_output_first(self):
        async def fake_run_agent(agent_id, prompt):
            class Result:
                output = {
                    "status": "merged",
                    "markdown_content": "# 智能体归并结果\n",
                    "merge_summary": "智能体完成归并。",
                    "source_file_ids": ["docmap-1"],
                    "coverage_items": [
                        {
                            "mapping_id": "docmap-1",
                            "source_excerpt": "支持账号登录",
                            "coverage_status": "merged",
                            "reason": "已合入。",
                        }
                    ],
                }

            self.assertEqual(agent_id, "requirement_merge")
            self.assertIn("只返回一个 JSON 对象", prompt)
            return Result()

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge_agent(
                RequirementMergeInput(
                    project_id="project-1",
                    document_id="doc-1",
                    document_name="登录需求",
                    merge_mode="initial",
                    source_files=[
                        RequirementMergeSourceFile(
                            mapping_id="docmap-1",
                            original_filename="登录.md",
                            markdown_content="# 登录\n\n- 支持账号登录",
                            conversion_status="success",
                            mapping_status="pending_merge",
                        )
                    ],
                )
            )

        self.assertEqual(output.markdown_content, "# 智能体归并结果\n")
        self.assertEqual(output.merge_summary, "智能体完成归并。")

    async def test_run_requirement_merge_raises_when_agent_fails(self):
        async def fake_run_agent(_agent_id, _prompt):
            raise RuntimeError("model not configured")

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            with self.assertRaisesRegex(RuntimeError, "model not configured"):
                await run_requirement_merge_agent(
                    RequirementMergeInput(
                        project_id="project-1",
                        document_id="doc-1",
                        document_name="登录需求",
                        merge_mode="initial",
                        source_files=[
                            RequirementMergeSourceFile(
                                mapping_id="docmap-1",
                                original_filename="登录.md",
                                markdown_content="# 登录认证\n\n- 支持账号登录",
                                conversion_status="success",
                                mapping_status="pending_merge",
                            )
                        ],
                    )
                )

    async def test_run_requirement_merge_uses_small_json_stages(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            self.assertNotIn("classify_fragments", prompt)
            if '"task": "classify_source_blocks"' in prompt:
                self.assertIn('"source_blocks"', prompt)
                self.assertNotIn('"fragments"', prompt)
                result.output = {
                    "classifications": [
                        {
                            "block_id": fragments[0].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "block_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        },
                        {
                            "block_id": fragments[1].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "block_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        },
                    ]
                }
            elif '"task": "decide_cluster"' in prompt:
                result.output = {
                    "cluster_id": "cluster-0001-account_login",
                    "decision": "merge",
                    "canonical_meaning": "支持账号登录。",
                    "fragment_decisions": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "coverage_status": "merged",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "reason": "作为主规则合入。",
                        },
                        {
                            "fragment_id": fragments[1].fragment_id,
                            "coverage_status": "duplicate",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "covered_by_fragment_id": fragments[0].fragment_id,
                            "reason": "与主规则重复。",
                        },
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt:
                result.output = {
                    "section_key": "cluster-0001-account_login",
                    "blocks": [
                        {
                            "type": "paragraph",
                            "content": "系统应支持用户使用账号登录。",
                        }
                    ],
                    "covered_fragment_ids": [fragments[0].fragment_id, fragments[1].fragment_id],
                }
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(output.status, "merged")
        self.assertIn("系统应支持用户使用账号登录。", output.markdown_content)
        self.assertEqual(
            [item.coverage_status for item in output.coverage_items],
            ["merged", "duplicate"],
        )
        self.assertEqual([item.source_block_id for item in output.coverage_items], [fragments[0].fragment_id, fragments[1].fragment_id])

    async def test_run_requirement_merge_repairs_non_json_stage_output(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)
        calls = {"classification": 0}

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            if '"task": "classify_source_blocks"' in prompt:
                calls["classification"] += 1
                result.output = "我来分析一下：这个片段属于登录需求。"
            elif "JSON 修复阶段" in prompt:
                result.output = {
                    "classifications": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "fragment_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        }
                    ]
                }
            elif '"task": "decide_cluster"' in prompt:
                result.output = {
                    "cluster_id": "cluster-0001-account_login",
                    "decision": "merge",
                    "canonical_meaning": "支持账号登录。",
                    "fragment_decisions": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "coverage_status": "merged",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "reason": "合入账号登录需求。",
                        }
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt:
                result.output = {
                    "section_key": "cluster-0001-account_login",
                    "blocks": [{"type": "paragraph", "content": "系统应支持账号登录。"}],
                    "covered_fragment_ids": [fragments[0].fragment_id],
                }
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(calls["classification"], 1)
        self.assertEqual(output.status, "merged")
        self.assertIn("系统应支持账号登录。", output.markdown_content)

    async def test_run_requirement_merge_falls_back_when_classification_json_remains_invalid(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)

        async def fake_run_agent(_agent_id, _prompt):
            class Result:
                output = "我无法返回 JSON。"

            return Result()

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(output.status, "preview")
        self.assertIn("本地确定性候选稿", output.markdown_preview)
        self.assertIn("支持账号登录", output.markdown_preview)
        self.assertEqual(output.coverage_items[0].coverage_status, "pending_clarification")
        self.assertIn("片段分类未返回合法 JSON", output.merge_summary)

    async def test_run_requirement_merge_falls_back_when_section_json_remains_invalid(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            if '"task": "classify_source_blocks"' in prompt:
                result.output = {
                    "classifications": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "fragment_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        }
                    ]
                }
            elif '"task": "decide_cluster"' in prompt:
                cluster_id = re.search(r'"cluster_id": "([^"]+)"', prompt).group(1)
                result.output = {
                    "cluster_id": cluster_id,
                    "decision": "merge",
                    "canonical_meaning": "支持账号登录。",
                    "fragment_decisions": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "coverage_status": "merged",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "reason": "合入账号登录需求。",
                        }
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt or "JSON 修复阶段" in prompt:
                result.output = "章节内容如下：支持账号登录。"
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(output.status, "preview")
        self.assertIn("支持账号登录", output.markdown_preview)
        self.assertIn("章节归并未返回合法 JSON", output.merge_summary)

    async def test_run_requirement_merge_retries_missing_classifications(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录\n- 支持短信登录\n- 支持邮箱登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)
        classification_calls = {"count": 0}

        def classification(fragment):
            return {
                "fragment_id": fragment.fragment_id,
                "business_module": "登录",
                "semantic_key": fragment.fragment_id,
                "fragment_role": "requirement",
                "summary": fragment.text,
                "confidence": 0.9,
            }

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            if '"task": "classify_source_blocks"' in prompt:
                classification_calls["count"] += 1
                if classification_calls["count"] == 1:
                    result.output = {"classifications": [classification(fragments[0])]}
                else:
                    result.output = {"classifications": [classification(fragment) for fragment in fragments[1:]]}
            elif '"task": "decide_cluster"' in prompt:
                fragment = next(fragment for fragment in fragments if fragment.fragment_id in prompt)
                cluster_id = re.search(r'"cluster_id": "([^"]+)"', prompt).group(1)
                result.output = {
                    "cluster_id": cluster_id,
                    "decision": "merge",
                    "canonical_meaning": fragment.text,
                    "fragment_decisions": [
                        {
                            "fragment_id": fragment.fragment_id,
                            "coverage_status": "merged",
                            "target_module": "登录",
                            "target_heading": "登录方式",
                            "reason": "合入登录方式需求。",
                        }
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt:
                section_key = re.search(r'"section_key": "([^"]+)"', prompt).group(1)
                fragment = next(fragment for fragment in fragments if fragment.fragment_id in prompt)
                result.output = {
                    "section_key": section_key,
                    "blocks": [{"type": "paragraph", "content": fragment.text}],
                    "covered_fragment_ids": [fragment.fragment_id],
                }
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(classification_calls["count"], 2)
        self.assertEqual(output.status, "merged")
        self.assertEqual(len(output.coverage_items), 3)
        self.assertIn("支持邮箱登录", output.markdown_content)

    async def test_run_requirement_merge_normalizes_model_decision_statuses(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            if '"task": "classify_source_blocks"' in prompt:
                result.output = {
                    "classifications": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "fragment_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        },
                        {
                            "fragment_id": fragments[1].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "fragment_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        }
                    ]
                }
            elif '"task": "decide_cluster"' in prompt:
                cluster_id = re.search(r'"cluster_id": "([^"]+)"', prompt).group(1)
                result.output = {
                    "cluster_id": cluster_id,
                    "decision": "deduplicate",
                    "canonical_meaning": "支持账号登录。",
                    "fragment_decisions": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "coverage_status": "included",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "reason": "合入账号登录需求。",
                        },
                        {
                            "fragment_id": fragments[1].fragment_id,
                            "coverage_status": "deduplicated",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "covered_by_fragment_id": fragments[0].fragment_id,
                            "reason": "与账号登录需求重复。",
                        }
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt:
                section_key = re.search(r'"section_key": "([^"]+)"', prompt).group(1)
                result.output = {
                    "section_key": section_key,
                    "blocks": [{"type": "paragraph", "content": "系统应支持账号登录。"}],
                    "covered_fragment_ids": [fragments[0].fragment_id],
                }
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(output.status, "merged")
        self.assertEqual(
            [item.coverage_status for item in output.coverage_items],
            ["merged", "duplicate"],
        )
        self.assertIn("系统应支持账号登录。", output.markdown_content)

    async def test_run_requirement_merge_derives_unknown_cluster_decision_from_fragment_statuses(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="initial",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            if '"task": "classify_source_blocks"' in prompt:
                result.output = {
                    "classifications": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "fragment_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        }
                    ]
                }
            elif '"task": "decide_cluster"' in prompt:
                cluster_id = re.search(r'"cluster_id": "([^"]+)"', prompt).group(1)
                result.output = {
                    "cluster_id": cluster_id,
                    "decision": "already_handled",
                    "canonical_meaning": "支持账号登录。",
                    "fragment_decisions": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "coverage_status": "covered",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "reason": "合入账号登录需求。",
                        }
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt:
                section_key = re.search(r'"section_key": "([^"]+)"', prompt).group(1)
                result.output = {
                    "section_key": section_key,
                    "blocks": [{"type": "paragraph", "content": "系统应支持账号登录。"}],
                    "covered_fragment_ids": [fragments[0].fragment_id],
                }
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(output.status, "merged")
        self.assertEqual(output.coverage_items[0].coverage_status, "merged")

    async def test_run_requirement_merge_writes_incremental_result_as_merged_content(self):
        input_data = RequirementMergeInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            merge_mode="incremental",
            source_files=[
                RequirementMergeSourceFile(
                    mapping_id="docmap-1",
                    original_filename="登录.md",
                    markdown_content="# 登录\n\n- 支持账号登录",
                    conversion_status="success",
                    mapping_status="pending_merge",
                )
            ],
        )
        fragments = build_source_fragments(input_data.source_files)

        async def fake_run_agent(_agent_id, prompt):
            class Result:
                output = {}

            result = Result()
            if '"task": "classify_source_blocks"' in prompt:
                result.output = {
                    "classifications": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "business_module": "登录",
                            "semantic_key": "account_login",
                            "fragment_role": "requirement",
                            "summary": "支持账号登录",
                            "confidence": 0.9,
                        }
                    ]
                }
            elif '"task": "decide_cluster"' in prompt:
                cluster_id = re.search(r'"cluster_id": "([^"]+)"', prompt).group(1)
                result.output = {
                    "cluster_id": cluster_id,
                    "decision": "merge",
                    "canonical_meaning": "支持账号登录。",
                    "fragment_decisions": [
                        {
                            "fragment_id": fragments[0].fragment_id,
                            "coverage_status": "merged",
                            "target_module": "登录",
                            "target_heading": "账号登录",
                            "reason": "合入账号登录需求。",
                        }
                    ],
                    "conflicts": [],
                    "clarification_items": [],
                }
            elif '"task": "merge_section"' in prompt:
                section_key = re.search(r'"section_key": "([^"]+)"', prompt).group(1)
                result.output = {
                    "section_key": section_key,
                    "blocks": [{"type": "paragraph", "content": "系统应支持账号登录。"}],
                    "covered_fragment_ids": [fragments[0].fragment_id],
                }
            else:
                self.fail("unexpected prompt")
            return result

        with patch("app.services.requirement_merge_service.run_agent", fake_run_agent):
            output = await run_requirement_merge(input_data, fragments)

        self.assertEqual(output.status, "merged")
        self.assertIn("系统应支持账号登录。", output.markdown_content)
        self.assertEqual(output.markdown_preview, "")


if __name__ == "__main__":
    unittest.main()
