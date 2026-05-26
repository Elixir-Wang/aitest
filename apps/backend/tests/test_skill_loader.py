from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents import FunctionTool

from app.agents.definitions import AgentDefinition
from app.agents.registry import agent_registry
from app.agents.runtime import build_agent
from app.agents.skill_loader import load_skill, load_skills
from app.agents.skills import skill_registry


class SkillLoaderTest(unittest.TestCase):
    def test_registry_exposes_requirement_file_agents(self):
        agents = agent_registry.list()

        agent_ids = [agent.id for agent in agents]
        self.assertIn("raw_requirement_format_converter", agent_ids)
        self.assertIn("document_editor", agent_ids)
        self.assertIn("requirement_merge", agent_ids)
        self.assertIn("site_exploration", agent_ids)
        self.assertEqual(agents[0].name, "格式转换智能体")
        self.assertEqual(agents[0].skill_ids, ("pdf_to_markdown", "docx_to_markdown", "markdown_normalize"))
        self.assertEqual(agents[1].name, "需求归并智能体")
        self.assertEqual(agents[1].skill_ids, ("requirement_markdown_merge",))
        document_editor = agent_registry.get("document_editor")
        self.assertEqual(document_editor.name, "文档修改智能体")
        self.assertEqual(document_editor.skill_ids, ("document_editing",))
        site_agent = agent_registry.get("site_exploration")
        self.assertEqual(site_agent.name, "站点探索智能体")
        self.assertEqual(site_agent.skill_ids, ("playwright_cli", "site_exploration"))

    def test_raw_requirement_format_converter_uses_only_real_conversion_skills(self):
        pdf_skill = skill_registry.get("pdf_to_markdown", agent_id="raw_requirement_format_converter")
        docx_skill = skill_registry.get("docx_to_markdown", agent_id="raw_requirement_format_converter")
        normalize_skill = skill_registry.get("markdown_normalize", agent_id="raw_requirement_format_converter")

        self.assertEqual(pdf_skill.agent_id, "raw_requirement_format_converter")
        self.assertEqual(docx_skill.agent_id, "raw_requirement_format_converter")
        self.assertEqual(normalize_skill.agent_id, "raw_requirement_format_converter")
        self.assertTrue(Path(pdf_skill.path).as_posix().endswith("agents/raw_requirement_format_converter/skills/pdf_to_markdown"))
        self.assertTrue(Path(docx_skill.path).as_posix().endswith("agents/raw_requirement_format_converter/skills/docx_to_markdown"))
        self.assertTrue(Path(normalize_skill.path).as_posix().endswith("agents/raw_requirement_format_converter/skills/markdown_normalize"))
        self.assertEqual([getattr(tool, "name", "") for tool in normalize_skill.tools], ["normalize_requirement_markdown_tool"])

        with self.assertRaises(KeyError):
            skill_registry.get("raw_requirement_format_converter", agent_id="raw_requirement_format_converter")

    def test_requirement_merge_agent_uses_markdown_merge_skill(self):
        agent = agent_registry.get("requirement_merge")
        skill = skill_registry.get("requirement_markdown_merge", agent_id="requirement_merge")
        built_agent = build_agent(agent, [skill])

        self.assertEqual(skill.agent_id, "requirement_merge")
        self.assertTrue(Path(skill.path).as_posix().endswith("agents/requirement_merge/skills/requirement_markdown_merge"))
        self.assertIn("Requirement Markdown Merge", built_agent.instructions)
        self.assertIn("Do not simply concatenate files", built_agent.instructions)
        self.assertIn("Source Coverage Rules", built_agent.instructions)
        self.assertEqual(built_agent.tools, [])

    def test_requirement_analysis_agent_uses_analysis_skill_and_structured_output(self):
        agent = agent_registry.get("requirement_analysis")
        skill = skill_registry.get("requirement_analysis", agent_id="requirement_analysis")
        built_agent = build_agent(agent, [skill])

        self.assertEqual(skill.agent_id, "requirement_analysis")
        self.assertTrue(Path(skill.path).as_posix().endswith("agents/requirement_analysis/skills/requirement_analysis"))
        self.assertIn("Requirement Analysis", built_agent.instructions)
        self.assertIn("diagnose the requirement maturity", built_agent.instructions)
        self.assertIn("Do not silently infer missing business facts", built_agent.instructions)
        self.assertEqual(agent.output_type.__name__, "RequirementAnalysisOutput")
        self.assertEqual(built_agent.tools, [])

    def test_document_editor_agent_uses_document_editing_skill(self):
        agent = agent_registry.get("document_editor")
        skill = skill_registry.get("document_editing", agent_id="document_editor")
        built_agent = build_agent(agent, [skill])

        self.assertEqual(skill.agent_id, "document_editor")
        self.assertTrue(Path(skill.path).as_posix().endswith("agents/document_editor/skills/document_editing"))
        self.assertIn("Document Editing", built_agent.instructions)
        self.assertIn("Return edited markdown only in `edited_content`", built_agent.instructions)
        self.assertEqual(built_agent.tools, [])

    def test_site_exploration_agent_uses_playwright_cli_and_exploration_skills(self):
        agent = agent_registry.get("site_exploration")
        playwright_skill = skill_registry.get("playwright_cli", agent_id="site_exploration")
        exploration_skill = skill_registry.get("site_exploration", agent_id="site_exploration")
        built_agent = build_agent(agent, [playwright_skill, exploration_skill])

        self.assertEqual(playwright_skill.agent_id, "site_exploration")
        self.assertEqual(exploration_skill.agent_id, "site_exploration")
        self.assertIn("所有真实浏览器动作必须来自 Playwright CLI", built_agent.instructions)
        self.assertIn("模块覆盖状态", built_agent.instructions)
        self.assertEqual(built_agent.tools, [])

    def test_load_skill_reads_frontmatter_body_and_python_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "sample_skill"
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                """---
name: sample_skill
display_name: 示例技能
description: 示例描述
enabled: true
---
按这个流程工作。
""",
                encoding="utf-8",
            )
            (scripts_dir / "echo_tool.py").write_text(
                """from agents import function_tool

@function_tool
def echo_requirement_title(title: str) -> str:
    \"\"\"返回需求标题。\"\"\"
    return title
""",
                encoding="utf-8",
            )

            bundle = load_skill(skill_dir)

        self.assertEqual(bundle.id, "sample_skill")
        self.assertEqual(bundle.name, "示例技能")
        self.assertEqual(bundle.description, "示例描述")
        self.assertEqual(bundle.instructions, "按这个流程工作。")
        self.assertTrue(bundle.enabled)
        self.assertEqual(len(bundle.tools), 1)
        self.assertIsInstance(bundle.tools[0], FunctionTool)

    def test_load_skills_ignores_directories_without_skill_md(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "ignored").mkdir()
            valid = root / "valid"
            valid.mkdir()
            (valid / "SKILL.md").write_text("---\nname: valid\n---\n正文", encoding="utf-8")

            bundles = load_skills(root)

        self.assertEqual([bundle.id for bundle in bundles], ["valid"])

    def test_build_agent_injects_skill_instructions_and_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "sample_skill"
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: sample_skill\n---\n技能正文", encoding="utf-8")
            (scripts_dir / "tool.py").write_text(
                """from agents import function_tool

@function_tool
def read_sample(value: str) -> str:
    \"\"\"读取示例值。\"\"\"
    return value
""",
                encoding="utf-8",
            )
            skill = load_skill(skill_dir)

        agent = build_agent(
            AgentDefinition(
                id="agent-1",
                name="测试智能体",
                description="测试",
                instructions="基础指令",
                model="gpt-5.4-mini",
                skill_ids=("sample_skill",),
            ),
            [skill],
        )

        self.assertIn("基础指令", agent.instructions)
        self.assertIn("技能正文", agent.instructions)
        self.assertEqual(len(agent.tools), 1)


if __name__ == "__main__":
    unittest.main()
