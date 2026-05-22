from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.services.requirement_file_converter import convert_requirement_file_to_markdown


class RequirementFileConverterTest(unittest.TestCase):
    def test_markdown_file_is_saved_directly(self):
        markdown, summary = convert_requirement_file_to_markdown("需求.md", "# 登录需求".encode("utf-8"))

        self.assertEqual(markdown, "# 登录需求\n")
        self.assertEqual(summary, "文本文件直接保存为 Markdown 转换稿。")

    def test_pdf_uses_local_pdf_skill_script(self):
        def fake_run(cmd, **_kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.write_text("# PDF 转换结果", encoding="utf-8")
            return Mock(returncode=0, stdout='{"stats":{"pages":2,"mode":"native"}}', stderr="")

        with patch("app.services.requirement_file_converter.shutil.which", return_value="node"):
            with patch("app.services.requirement_file_converter.subprocess.run", side_effect=fake_run) as run:
                markdown, summary = convert_requirement_file_to_markdown("需求.pdf", b"%PDF-1.4")

        command = run.call_args.args[0]
        self.assertIn("raw_requirement_format_converter", command[1])
        self.assertIn("pdf_to_markdown", command[1])
        self.assertEqual(markdown, "# PDF 转换结果\n")
        self.assertEqual(summary, "已通过 pdf_to_markdown skill 转换，页数 2。")

    def test_docx_uses_local_docx_skill_script(self):
        def fake_run(cmd, **_kwargs):
            output_path = Path(cmd[cmd.index("--output") + 1])
            output_path.write_text("# DOCX 转换结果", encoding="utf-8")
            return Mock(returncode=0, stdout='{"pages": 1}', stderr="")

        with patch("app.services.requirement_file_converter.shutil.which", return_value="node"):
            with patch("app.services.requirement_file_converter.subprocess.run", side_effect=fake_run) as run:
                markdown, summary = convert_requirement_file_to_markdown("需求.docx", b"docx")

        command = run.call_args.args[0]
        self.assertIn("raw_requirement_format_converter", command[1])
        self.assertIn("docx_to_markdown", command[1])
        self.assertEqual(markdown, "# DOCX 转换结果\n")
        self.assertEqual(summary, "已通过 docx_to_markdown skill 转换，页数 1。")

    def test_pdf_missing_node_fails_clearly(self):
        with patch("app.services.requirement_file_converter.shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as caught:
                convert_requirement_file_to_markdown("需求.pdf", b"%PDF-1.4")

        self.assertIn("缺少 Node.js", str(caught.exception))
