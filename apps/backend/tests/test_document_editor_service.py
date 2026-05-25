from __future__ import annotations

import unittest
from unittest.mock import patch

from app.schemas.document_editor import DocumentEditInput, DocumentEditOutput
from app.services.document_editor_service import build_document_edit_prompt, edit_document, parse_document_edit_output


class DocumentEditorServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_build_prompt_includes_generic_document_context_and_instruction(self):
        prompt = build_document_edit_prompt(
            DocumentEditInput(
                document_type="knowledge_article",
                document_title="登录说明",
                content="# 登录\n\n旧内容",
                instruction="改成面向客服的说明",
            )
        )

        self.assertIn("document_type: knowledge_article", prompt)
        self.assertIn("document_title: 登录说明", prompt)
        self.assertIn("改成面向客服的说明", prompt)
        self.assertIn("# 登录", prompt)
        self.assertIn("只返回 JSON", prompt)

    def test_parse_document_edit_output_accepts_json_object(self):
        output = parse_document_edit_output(
            """
            {
              "status": "edited",
              "edited_content": "# 登录\\n\\n新内容",
              "change_summary": "调整为客服说明。",
              "warnings": ["未补充新业务规则"]
            }
            """
        )

        self.assertEqual(output.status, "edited")
        self.assertEqual(output.edited_content, "# 登录\n\n新内容")
        self.assertEqual(output.change_summary, "调整为客服说明。")
        self.assertEqual(output.warnings, ["未补充新业务规则"])

    def test_parse_document_edit_output_rejects_empty_edited_content(self):
        with self.assertRaises(ValueError):
            parse_document_edit_output(
                '{"status":"edited","edited_content":"","change_summary":"空结果","warnings":[]}'
            )

    async def test_edit_document_uses_document_editor_agent(self):
        async def fake_run_agent(agent_id: str, prompt: str):
            self.assertEqual(agent_id, "document_editor")
            self.assertIn("document_type: requirement_standard_file", prompt)
            return type(
                "AgentResult",
                (),
                {
                    "output": {
                        "status": "edited",
                        "edited_content": "# 新标准文件",
                        "change_summary": "按指令修改。",
                        "warnings": [],
                    }
                },
            )()

        with patch("app.services.document_editor_service.run_agent", fake_run_agent):
            result = await edit_document(
                DocumentEditInput(
                    document_type="requirement_standard_file",
                    document_title="标准文件.md",
                    content="# 旧标准文件",
                    instruction="补充验收标准",
                )
            )

        self.assertIsInstance(result, DocumentEditOutput)
        self.assertEqual(result.edited_content, "# 新标准文件")
        self.assertEqual(result.change_summary, "按指令修改。")


if __name__ == "__main__":
    unittest.main()
