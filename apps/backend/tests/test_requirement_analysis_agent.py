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


def test_requirement_analysis_codex_prompt_orders_review_scenarios_auxiliary_answers_and_report():
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

    review_index = prompt.index("第一阶段：使用 requirement-review")
    scenarios_index = prompt.index("第二阶段：使用 test-scenarios")
    auxiliary_index = prompt.index("第三阶段：使用辅助文件")
    assert review_index < scenarios_index < auxiliary_index
    assert "需求分析智能体" in prompt
    assert "Codex CLI 需求分析智能体" not in prompt
    assert "非交互式批处理任务" in prompt
    assert "不要只回复确认" in prompt
    assert "如果辅助文件能回答待确认问题" in prompt
    assert "删除对应待确认条目" in prompt
    assert "写入 preliminary_requirement_markdown" in prompt
    assert "output/analysis.json" in prompt
    assert "output/analysis.md" in prompt
    assert "analysis_report_markdown" in prompt
    assert "待确认需求 tab 后面的分析报告 tab" in prompt


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
    assert settings.REQUIREMENT_ANALYSIS_CODEX_COMMAND.endswith(r"runners\codex\node_modules\.bin\codex.cmd")


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
            [runner.os.environ.get("COMSPEC", "cmd"), "/c", "echo unauthorized 1>&2 && exit /b 1"],
            tmp_path,
            runner.os.environ.copy(),
        )


def test_requirement_analysis_codex_reports_missing_analysis_output(tmp_path):
    from app.agents.requirement_analysis_codex import runner

    (tmp_path / "output").mkdir()

    with pytest.raises(ValueError, match="需求分析智能体未生成 output/analysis.json"):
        runner._read_analysis_output(tmp_path)


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
