from __future__ import annotations

import unittest
from pydantic import ValidationError
from unittest.mock import patch

from app.schemas.requirement_merge import (
    RequirementCoverageItem,
    RequirementMergeInput,
    RequirementMergeOutput,
    RequirementMergeSourceFile,
)
from app.services.requirement_merge_service import _parse_agent_output, run_requirement_merge
from app.services import requirement_merge_service


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

    async def test_run_requirement_merge_uses_agent_output_first(self):
        async def fake_run_agent(agent_id, prompt):
            class Result:
                output = {
                    "status": "merged",
                    "markdown_content": "# 智能体归并结果\n",
                    "merge_summary": "智能体完成归并。",
                    "source_file_ids": ["docmap-1"],
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


if __name__ == "__main__":
    unittest.main()

