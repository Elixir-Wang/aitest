from __future__ import annotations

import unittest
from unittest.mock import patch

from app.schemas.requirement_conversion import RequirementConversionInput
from app.services.raw_requirement_format_converter_service import (
    _build_agent_prompt,
    _parse_agent_output,
    convert_raw_requirement_format,
)


class RawRequirementFormatConverterServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_parse_agent_output_accepts_json_string(self):
        output = _parse_agent_output(
            """
            {
              "markdown_content": "# 登录需求\\n",
              "conversion_summary": "智能体已标准化。",
              "quality_score": 95,
              "warnings": ["页脚已移除"]
            }
            """
        )

        self.assertEqual(output.markdown_content, "# 登录需求\n")
        self.assertEqual(output.quality_score, 95)
        self.assertEqual(output.warnings, ["页脚已移除"])

    def test_parse_agent_output_extracts_fenced_json(self):
        output = _parse_agent_output(
            """
            已完成转换：

            ```json
            {
              "markdown_content": "# 登录需求\\n",
              "conversion_summary": "智能体已标准化。",
              "quality_score": 95,
              "warnings": []
            }
            ```
            """
        )

        self.assertEqual(output.markdown_content, "# 登录需求\n")

    def test_parse_agent_output_extracts_json_from_wrapped_text(self):
        output = _parse_agent_output(
            """
            以下是结果：
            {
              "markdown_content": "# 登录需求\\n",
              "conversion_summary": "智能体已标准化。",
              "quality_score": 95,
              "warnings": []
            }
            请查收。
            """
        )

        self.assertEqual(output.markdown_content, "# 登录需求\n")

    def test_parse_agent_output_recovers_markdown_when_summary_has_unescaped_quotes(self):
        output = _parse_agent_output(
            '''
            ```json
            {
              "markdown_content": "# 登录需求\\n\\n```mermaid\\nflowchart TD\\n  A[\\"开始\\"]\\n```",
              "conversion_summary": "修复了如"说明/书"这样的断行。",
              "quality_score": 95,
              "warnings": ["已恢复正文"]
            }
            ```
            '''
        )

        self.assertIn("# 登录需求", output.markdown_content)
        self.assertIn("```mermaid", output.markdown_content)
        self.assertEqual(output.quality_score, 95)
        self.assertEqual(output.warnings, ["已恢复正文"])

    def test_agent_prompt_forbids_creating_business_requirements(self):
        prompt = _build_agent_prompt(
            RequirementConversionInput(
                filename="登录需求.docx",
                file_format="docx",
                candidate_markdown="# 登录\n\n- 支持账号登录",
                candidate_summary="本地转换成功",
            )
        )

        self.assertIn("不得创造、补充或推断业务需求", prompt)
        self.assertIn("只返回一个 JSON 对象", prompt)
        self.assertIn("markdown_content", prompt)

    def test_pdf_agent_prompt_requires_markdown_heading_structure(self):
        prompt = _build_agent_prompt(
            RequirementConversionInput(
                filename="百融统一登录认证授权中心产品需求说明书.pdf",
                file_format="pdf",
                candidate_markdown="百融统一登录认证授权中心产品需求说明书\n\n1. 项目概述\n\n1.1 项目背景",
                candidate_summary="已通过 PyMuPDF PDF 转换器提取文本，页数 5。",
            )
        )

        self.assertIn("file_format=pdf", prompt)
        self.assertIn("必须作为一级标题", prompt)
        self.assertIn("不能把 PDF 标准文件继续输出成纯文本墙", prompt)

    async def test_convert_raw_requirement_format_uses_converter_agent(self):
        async def fake_run_agent(agent_id, prompt):
            class Result:
                output = {
                    "markdown_content": "# 智能体标准化结果\n",
                    "conversion_summary": "智能体完成格式标准化。",
                    "quality_score": 100,
                    "warnings": [],
                }

            self.assertEqual(agent_id, "raw_requirement_format_converter")
            self.assertIn("候选 Markdown", prompt)
            return Result()

        with patch("app.services.raw_requirement_format_converter_service.run_agent", fake_run_agent):
            output = await convert_raw_requirement_format(
                RequirementConversionInput(
                    filename="登录需求.md",
                    file_format="md",
                    candidate_markdown="# 登录",
                    candidate_summary="文本文件直接保存为 Markdown 转换稿。",
                )
            )

        self.assertEqual(output.markdown_content, "# 智能体标准化结果\n")


if __name__ == "__main__":
    unittest.main()
