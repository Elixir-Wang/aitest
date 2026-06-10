import sys
from types import SimpleNamespace

import pytest


class FakeStructuredModel:
    def __init__(self, response):
        self.response = response
        self.messages = None

    async def ainvoke(self, messages):
        self.messages = messages
        return self.response


class FakeModel:
    def __init__(self, response):
        self.response = response
        self.schema = None
        self.structured_model = FakeStructuredModel(response)

    def with_structured_output(self, schema):
        self.schema = schema
        return self.structured_model


class FakeAgent:
    def __init__(self, response):
        self.response = response
        self.payload = None

    async def ainvoke(self, payload):
        self.payload = payload
        return {"structured_response": self.response}


def test_requirement_analysis_input_includes_primary_and_optional_auxiliary_documents():
    from app.schemas.requirement_analysis import RequirementAnalysisAuxiliaryDocument, RequirementAnalysisInput

    input_data = RequirementAnalysisInput(
        project_id="project-1",
        document_id="doc-1",
        document_name="登录需求",
        primary_mapping_id="main-1",
        primary_filename="main.md",
        primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
        auxiliary_documents=[
            RequirementAnalysisAuxiliaryDocument(
                mapping_id="aux-1",
                filename="辅助.md",
                markdown_content="# 辅助\n\n验证码有效期为 5 分钟。",
            )
        ],
    )

    assert input_data.primary_markdown_content.startswith("# 主需求")
    assert len(input_data.auxiliary_documents) == 1
    assert input_data.auxiliary_documents[0].filename == "辅助.md"
    assert "验证码有效期为 5 分钟" in input_data.auxiliary_documents[0].markdown_content


def test_requirement_analysis_input_contract_only_contains_primary_fields():
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    assert set(RequirementAnalysisInput.model_fields) == {
        "project_id",
        "document_id",
        "document_name",
        "run_id",
        "primary_mapping_id",
        "primary_filename",
        "primary_markdown_content",
        "auxiliary_documents",
    }


def test_requirement_analysis_codex_prompt_uses_requirement_review_with_testability_view():
    from app.agents.requirement_analysis_codex.runner import _build_codex_prompt
    from app.schemas.requirement_analysis import RequirementAnalysisAuxiliaryDocument, RequirementAnalysisInput

    prompt = _build_codex_prompt(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
            auxiliary_documents=[
                RequirementAnalysisAuxiliaryDocument(
                    mapping_id="aux-1",
                    filename="辅助.md",
                    markdown_content="# 辅助\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert "使用 requirement-review skill 对 input/primary.md 做需求分析" in prompt
    assert "test-scenarios" not in prompt
    assert "测试目标、角色、前置条件、操作步骤、预期结果、边界值、异常路径和错误场景缺口" in prompt
    assert "需求分析智能体" in prompt
    assert "Codex CLI 需求分析智能体" not in prompt
    assert "非交互式批处理任务" in prompt
    assert "不要只回复确认" in prompt
    assert "不读取、不引用、不推测任何辅助文档" in prompt
    assert "辅助文档增强由后续 RequirementAuxiliaryEnhancementAgent 处理" in prompt
    assert "applied_supplements 必须为空数组" in prompt
    assert "output/analysis.json" in prompt
    assert "output/analysis.md" in prompt
    assert "analysis_report_markdown" in prompt
    assert "待确认需求 tab 后面的分析报告 tab" in prompt
    assert "分析报告只写分析摘要、成熟度、关键缺口分类、测试覆盖缺口、质量门禁和下一步建议" in prompt
    assert "分析报告不要出现“待确认问题”“待人工确认”“澄清问题”等面向人工答复的章节、标题、统计或问题清单" in prompt
    assert "关键缺口只做归类和影响说明，不要写成可答复的问题清单" in prompt
    assert "测试覆盖缺口只说明测试覆盖影响，不要展开具体待人工答复事项" in prompt
    assert "分析报告不要重复、统计或摘要 clarification_questions/conflicts；这些内容只进入结构化字段" in prompt
    assert "需要人工回答或裁决的内容必须进入 clarification_questions/conflicts" in prompt
    assert "status 只能是 completed、needs_clarification、blocked" in prompt
    assert "quality_gate.result，只能是 passed、warning、blocked" in prompt
    assert "coverage_audit 必须是数组" in prompt


def test_requirement_analysis_codex_command_resolves_windows_cmd_shim(monkeypatch):
    from app.agents.requirement_analysis_codex import runner

    monkeypatch.setattr(runner, "REQUIREMENT_ANALYSIS_CODEX_COMMAND", "codex")
    monkeypatch.setattr(runner.os, "name", "nt")
    monkeypatch.setattr(
        runner.shutil,
        "which",
        lambda command: r"C:\Users\tester\AppData\Roaming\npm\codex.cmd" if command == "codex.cmd" else None,
    )

    assert runner._codex_command_path().endswith(r"codex.cmd")


def test_requirement_analysis_codex_default_command_uses_backend_runner():
    from app.core import settings

    assert settings.REQUIREMENT_ANALYSIS_CODEX_RUNNER_DIR.name == "codex"
    assert "runners" in settings.REQUIREMENT_ANALYSIS_CODEX_COMMAND
    assert "codex" in settings.REQUIREMENT_ANALYSIS_CODEX_COMMAND
    assert "node_modules" in settings.REQUIREMENT_ANALYSIS_CODEX_COMMAND


def test_requirement_analysis_codex_command_uses_assigned_model_config(monkeypatch):
    from app.agents.requirement_analysis_codex import runner

    monkeypatch.setattr(runner, "_codex_command_path", lambda: "codex")

    command = runner._codex_command(
        workdir=runner.Path("work"),
        selection=SimpleNamespace(model="assigned-model", base_url="https://assigned.example/v1"),
        prompt="run analysis",
    )

    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "model_provider=\"backend_requirement_analysis\"" in command
    assert "model_providers.backend_requirement_analysis.base_url=\"https://assigned.example/v1\"" in command
    assert "model_providers.backend_requirement_analysis.wire_api=\"responses\"" in command
    assert "model_providers.backend_requirement_analysis.requires_openai_auth=true" in command
    assert command[command.index("--model") + 1] == "assigned-model"
    assert command.index("--ignore-user-config") < command.index("--sandbox")
    assert command.index("--ignore-rules") < command.index("--sandbox")


def test_requirement_analysis_codex_command_allows_configured_absolute_path(monkeypatch, tmp_path):
    from app.agents.requirement_analysis_codex import runner

    codex_path = tmp_path / "codex"
    codex_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(runner, "REQUIREMENT_ANALYSIS_CODEX_COMMAND", str(codex_path))

    assert runner._codex_command_path() == str(codex_path)


def test_requirement_analysis_codex_command_reports_missing_cli(monkeypatch):
    from app.agents.requirement_analysis_codex import runner

    monkeypatch.setattr(runner, "REQUIREMENT_ANALYSIS_CODEX_COMMAND", "codex")
    monkeypatch.setattr(runner.shutil, "which", lambda command: None)

    with pytest.raises(RuntimeError, match="未检测到可用需求分析智能体执行命令"):
        runner._codex_command_path()


def test_requirement_analysis_codex_reports_process_failure_as_agent_failure(tmp_path):
    from app.agents.requirement_analysis_codex import runner

    with pytest.raises(RuntimeError, match="需求分析智能体执行失败，退出码：1"):
        runner._run_codex_process(
            [sys.executable, "-c", "import sys; print('unauthorized', file=sys.stderr); sys.exit(1)"],
            tmp_path,
            runner.os.environ.copy(),
        )


def test_requirement_analysis_codex_reports_missing_analysis_output(tmp_path):
    from app.agents.requirement_analysis_codex import runner

    (tmp_path / "output").mkdir()

    with pytest.raises(ValueError, match="需求分析智能体未生成 output/analysis.json"):
        runner._read_analysis_output(tmp_path)


def test_requirement_analysis_codex_normalizes_legacy_agent_output(tmp_path):
    from app.agents.requirement_analysis_codex import runner

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "analysis.md").write_text("# 分析报告\n\n有条件通过。", encoding="utf-8")
    (output_dir / "analysis.json").write_text(
        runner.json.dumps(
            {
                "status": "CONDITIONAL_PASS",
                "analysis_summary": "需求基本清晰，但仍有待确认项。",
                "preliminary_requirement_markdown": "# 主需求",
                "analysis_report_markdown": "",
                "applied_supplements": [
                    {
                        "source_file": "input/auxiliary/001-aux-1-supporting.md",
                        "applied_to": "验证码有效期",
                        "evidence": "辅助文档说明验证码有效期为 5 分钟。",
                    }
                ],
                "maturity_assessment": {
                    "overall_level": "中等成熟，有条件可进入方案设计",
                    "dimensions": [{"name": "完整性", "notes": "缺少异常路径。"}],
                },
                "key_gaps": ["缺少异常路径。"],
                "assumptions": ["验证码登录为本期范围。"],
                "modules": [{"name": "登录模块", "scope": "验证码登录。", "rules": ["验证码有效期 5 分钟。"]}],
                "clarification_questions": [
                    {
                        "id": "CQ-001",
                        "question": "验证码错误次数上限是多少？",
                        "priority": "HIGH",
                        "recommended_options": [
                            {
                                "label": "5 次",
                                "answer_markdown": "验证码连续错误 5 次后锁定 10 分钟。",
                            }
                        ],
                    }
                ],
                "conflicts": [
                    {
                        "id": "CF-001",
                        "topic": "验证码有效期",
                        "description": "主需求未说明，辅助文档说明为 5 分钟。",
                        "sources": ["input/primary.md", "input/auxiliary/001-aux-1-supporting.md"],
                        "resolution_needed": "确认验证码有效期是否为 5 分钟。",
                    }
                ],
                "coverage_audit": {
                    "covered": ["登录主流程"],
                    "partial": ["异常路径"],
                    "missing": ["错误次数上限"],
                },
                "quality_gate": {
                    "decision": "有条件通过",
                    "pass": False,
                    "blocking_items": ["确认验证码错误次数上限"],
                    "non_blocking_items": ["补充性能指标"],
                },
                "next_actions": ["由产品确认验证码错误次数上限。"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = runner._read_analysis_output(tmp_path)

    assert output.status == "needs_clarification"
    assert output.quality_gate.result == "warning"
    assert output.quality_gate.blocking_issues == ["确认验证码错误次数上限"]
    assert output.analysis_report_markdown == "# 分析报告\n\n有条件通过。"
    assert output.applied_supplements == []
    assert output.maturity_assessment.level == "RA2"
    assert output.key_gaps[0].category == "other"
    assert output.assumptions[0].validation_needed == "需要业务负责人确认。"
    assert output.modules[0].module_name == "登录模块"
    assert output.clarification_questions[0].dimension == "other"
    assert output.clarification_questions[0].recommended_options[0].id == "OPT-001"
    assert output.conflicts[0].issue_type == "conflict"
    assert len(output.coverage_audit) == 3


@pytest.mark.anyio
async def test_requirement_analysis_codex_runner_runs_blocking_cli_in_thread(monkeypatch):
    from app.agents.requirement_analysis_codex import runner
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput, RequirementQualityGate

    calls = {}

    async def fake_to_thread(function, *args):
        calls["function"] = function
        calls["args"] = args
        return RequirementAnalysisOutput(
            status="completed",
            analysis_summary="Codex 分析完成。",
            preliminary_requirement_markdown="# 主需求",
            quality_gate=RequirementQualityGate(result="passed", testability_score=90),
        )

    monkeypatch.setattr(runner.asyncio, "to_thread", fake_to_thread)

    input_data = RequirementAnalysisInput(
        project_id="project-1",
        document_id="doc-1",
        document_name="登录需求",
        primary_mapping_id="main-1",
        primary_filename="main.md",
        primary_markdown_content="# 主需求",
    )
    output = await runner.run_requirement_analysis_with_codex(input_data)

    assert output.status == "completed"
    assert calls["function"] is runner._run_codex_requirement_analysis
    assert calls["args"] == (input_data,)


@pytest.mark.anyio
async def test_requirement_analysis_service_uses_codex_cli_runner(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import (
        RequirementAnalysisAuxiliaryDocument,
        RequirementAnalysisInput,
        RequirementAnalysisOutput,
        RequirementQualityGate,
    )

    captured = {}

    async def fake_runner(input_data):
        captured["input"] = input_data
        return RequirementAnalysisOutput(
            status="completed",
            analysis_summary="Codex 分析完成。",
            preliminary_requirement_markdown=input_data.primary_markdown_content + "\n\n## 辅助补充\n\n验证码有效期为 5 分钟。",
            quality_gate=RequirementQualityGate(result="passed", testability_score=92),
        )

    monkeypatch.setattr(service, "run_requirement_analysis_with_codex", fake_runner)

    output = await service.analyze_requirement(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
            auxiliary_documents=[
                RequirementAnalysisAuxiliaryDocument(
                    mapping_id="aux-1",
                    filename="辅助.md",
                    markdown_content="# 辅助\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert output.analysis_summary == "Codex 分析完成。"
    assert "辅助补充" in output.preliminary_requirement_markdown
    assert captured["input"].document_name == "登录需求"


@pytest.mark.anyio
async def test_requirement_analysis_service_delegates_to_codex_runner(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput, RequirementQualityGate

    response = RequirementAnalysisOutput(
        status="completed",
        analysis_summary="需求分析完成。",
        preliminary_requirement_markdown="# 主需求\n\n用户可以使用验证码登录。",
        quality_gate=RequirementQualityGate(result="passed", testability_score=90),
    )
    captured = {}

    async def fake_runner(input_data):
        captured["input"] = input_data
        return response

    monkeypatch.setattr(service, "run_requirement_analysis_with_codex", fake_runner)

    output = await service.analyze_requirement(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
        )
    )

    assert output.status == "completed"
    assert captured["input"].primary_filename == "main.md"


@pytest.mark.anyio
async def test_requirement_analysis_service_uses_primary_markdown_as_preliminary_requirement(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput, RequirementAnalysisOutput, RequirementQualityGate

    response = RequirementAnalysisOutput(
        status="needs_clarification",
        analysis_summary="需求存在待澄清项。",
        preliminary_requirement_markdown="",
        quality_gate=RequirementQualityGate(result="warning", testability_score=72),
    )
    async def fake_runner(input_data):
        return response

    monkeypatch.setattr(service, "run_requirement_analysis_with_codex", fake_runner)

    primary_markdown = "# 主需求\n\n## 登录\n\n用户可以使用验证码登录。\n\n| 字段 | 说明 |\n| --- | --- |\n| 手机号 | 必填 |\n"
    output = await service.analyze_requirement(
        RequirementAnalysisInput(
            project_id="project-1",
            document_id="doc-1",
            document_name="登录需求",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            primary_markdown_content=primary_markdown,
        )
    )

    assert output.preliminary_requirement_markdown == primary_markdown.strip()


def test_primary_analysis_agent_uses_tool_strategy(monkeypatch):
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.requirement_analysis.primary_analysis.agent import primary_analysis_agent
    from app.schemas.requirement_analysis import RequirementAnalysisOutput

    calls = {}

    def fake_create_agent(model, tools, *, system_prompt, response_format):
        calls.update(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "response_format": response_format,
            }
        )
        return "agent"

    monkeypatch.setattr(
        "app.agents.requirement_analysis.primary_analysis.agent.create_agent",
        fake_create_agent,
    )

    agent = primary_analysis_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert isinstance(calls["response_format"], ToolStrategy)
    assert calls["response_format"].schema is RequirementAnalysisOutput
    assert calls["response_format"].handle_errors is True
    assert "主需求分析智能体" in calls["system_prompt"]
    assert "不要拆出“当前缺口”“缺失说明”等额外字段或解释段" in calls["system_prompt"]
    assert "写入 impact" in calls["system_prompt"]


@pytest.mark.anyio
async def test_requirement_analysis_service_rejects_missing_structured_response(monkeypatch):
    from app.agents.requirement_analysis.primary_analysis import service
    from app.schemas.requirement_analysis import RequirementAnalysisInput

    async def missing_output(input_data):
        raise ValueError("需求分析智能体未返回结构化结果。")

    monkeypatch.setattr(service, "run_requirement_analysis_with_codex", missing_output)

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await service.analyze_requirement(
            RequirementAnalysisInput(
                project_id="project-1",
                document_id="doc-1",
                document_name="登录需求",
                primary_mapping_id="main-1",
                primary_filename="main.md",
                primary_markdown_content="# 主需求\n\n用户可以使用验证码登录。",
            )
        )


def test_auxiliary_enhancement_input_contains_questions_and_articles():
    from app.agents.requirement_analysis.auxiliary_enhancement.service import _build_auxiliary_enhancement_input
    from app.schemas.requirement_analysis import (
        RequirementAuxiliaryArticleForEnhancement,
        RequirementAuxiliaryEnhancementInput,
        RequirementEnhancementQuestion,
    )

    prompt = _build_auxiliary_enhancement_input(
        RequirementAuxiliaryEnhancementInput(
            project_id="project-1",
            document_id="doc-1",
            analysis_id="analysis-1",
            primary_mapping_id="main-1",
            primary_filename="main.md",
            questions=[
                RequirementEnhancementQuestion(
                    id="q-1",
                    question="验证码有效期是多少？",
                    primary_excerpt="用户可以使用验证码登录。",
                )
            ],
            auxiliary_articles=[
                RequirementAuxiliaryArticleForEnhancement(
                    mapping_id="supporting-1",
                    filename="supporting.md",
                    markdown_content="# 辅助需求\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert "questions" in prompt
    assert "auxiliary_articles" in prompt
    assert "验证码有效期是多少" in prompt
    assert "supporting.md" in prompt
    assert "验证码有效期为 5 分钟" in prompt
    assert "search_auxiliary_documents" not in prompt


@pytest.mark.anyio
async def test_auxiliary_enhancement_service_uses_direct_structured_model(monkeypatch):
    from app.agents.requirement_analysis.auxiliary_enhancement import service
    from app.schemas.requirement_analysis import (
        RequirementAuxiliaryArticleForEnhancement,
        RequirementAuxiliaryEnhancementInput,
        RequirementAuxiliaryEnhancementOutput,
        RequirementEnhancementQuestion,
    )

    response = RequirementAuxiliaryEnhancementOutput(
        enhancement_summary="从辅助文档找到验证码有效期。",
        unchanged_question_ids=[],
    )
    fake_agent = FakeAgent(response)

    monkeypatch.setattr(service, "resolve_model_selection", lambda capability_id: {"model": "fake:model"})
    monkeypatch.setattr(service, "build_agent_model", lambda selection: "model")
    monkeypatch.setattr(service, "auxiliary_enhancement_agent", lambda model: fake_agent)

    output = await service.enhance_requirement_with_auxiliary_articles(
        RequirementAuxiliaryEnhancementInput(
            project_id="project-1",
            document_id="doc-1",
            analysis_id="analysis-1",
            questions=[RequirementEnhancementQuestion(id="q-1", question="验证码有效期是多少？")],
            auxiliary_articles=[
                RequirementAuxiliaryArticleForEnhancement(
                    mapping_id="supporting-1",
                    filename="supporting.md",
                    markdown_content="# 辅助需求\n\n验证码有效期为 5 分钟。",
                )
            ],
        )
    )

    assert output.enhancement_summary == "从辅助文档找到验证码有效期。"
    message_content = fake_agent.payload["messages"][0]["content"]
    assert "auxiliary_articles" in message_content
    assert "验证码有效期为 5 分钟" in message_content


def test_auxiliary_enhancement_agent_uses_tool_strategy(monkeypatch):
    from langchain.agents.structured_output import ToolStrategy

    from app.agents.requirement_analysis.auxiliary_enhancement.agent import auxiliary_enhancement_agent
    from app.schemas.requirement_analysis import RequirementAuxiliaryEnhancementOutput

    calls = {}

    def fake_create_agent(model, tools, *, system_prompt, response_format):
        calls.update(
            {
                "model": model,
                "tools": tools,
                "system_prompt": system_prompt,
                "response_format": response_format,
            }
        )
        return "agent"

    monkeypatch.setattr(
        "app.agents.requirement_analysis.auxiliary_enhancement.agent.create_agent",
        fake_create_agent,
    )

    agent = auxiliary_enhancement_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert isinstance(calls["response_format"], ToolStrategy)
    assert calls["response_format"].schema is RequirementAuxiliaryEnhancementOutput
    assert calls["response_format"].handle_errors is True
    assert "辅助文档增强智能体" in calls["system_prompt"]
