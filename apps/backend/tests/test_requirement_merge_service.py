from __future__ import annotations

import unittest
from pydantic import ValidationError
from unittest.mock import patch

from app.schemas.requirement_merge import (
    RequirementCoverageItem,
    RequirementMergeConflictOut,
    RequirementMergeInput,
    RequirementMergeOutput,
    RequirementMergeSourceFile,
)
from app.services.requirement_merge_service import (
    _complete_source_file_coverage,
    _parse_agent_output,
    normalize_merge_output,
    run_requirement_merge,
    run_requirement_merge_v2,
)
from app.services.requirement_fragment_service import build_source_fragments
from app.services import requirement_merge_service
from app.services.requirement_merge_artifact_service import (
    evaluate_merge_quality,
    markdown_structure_retention_issue,
    merge_retention_issue,
)


class RequirementMergeServiceTest(unittest.IsolatedAsyncioTestCase):
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
        self.assertIn("coverage_items 必须覆盖每个有效需求片段", prompt)
        self.assertIn("覆盖每个有效需求片段", prompt)
        self.assertIn("不得摘要化导致需求", prompt)
        self.assertIn("source_excerpt 必须简短", prompt)
        self.assertIn("重复去重 N 处", prompt)
        self.assertIn("没有明显冲突时，才可以生成合并需求稿和质量报告", prompt)
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
            output = await run_requirement_merge(
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
                await run_requirement_merge(
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

    async def test_run_requirement_merge_v2_uses_small_json_stages(self):
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
            if '"task": "classify_fragments"' in prompt:
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
            output = await run_requirement_merge_v2(input_data, fragments)

        self.assertEqual(output.status, "merged")
        self.assertIn("系统应支持用户使用账号登录。", output.markdown_content)
        self.assertEqual(
            [item.coverage_status for item in output.coverage_items],
            ["merged", "duplicate"],
        )


if __name__ == "__main__":
    unittest.main()
