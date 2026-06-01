from pathlib import Path

import pytest

from app.agents.raw_requirement_converter import schemas
from app.agents.raw_requirement_converter.agent import raw_requirement_converter_agent
from app.agents.raw_requirement_converter.tools import (
    convert_markdown_to_markdown,
    convert_pdf_to_markdown,
    convert_text_to_markdown,
    convert_word_to_markdown,
    normalize_markdown_content,
    tools,
)
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


def test_requirement_conversion_output_contract_is_minimal() -> None:
    assert set(RequirementConversionOutput.model_fields) == {
        "markdown_content",
        "conversion_summary",
    }


def test_requirement_conversion_input_uses_source_path_contract() -> None:
    assert set(RequirementConversionInput.model_fields) == {
        "filename",
        "file_format",
        "source_file_path",
        "assets_dir_path",
    }


def test_raw_requirement_converter_schemas_reuse_api_contract() -> None:
    assert schemas.RequirementConversionInput is RequirementConversionInput
    assert schemas.RequirementConversionOutput is RequirementConversionOutput


def test_raw_requirement_converter_exposes_file_conversion_tools() -> None:
    assert tools == [
        convert_pdf_to_markdown,
        convert_word_to_markdown,
        convert_text_to_markdown,
        convert_markdown_to_markdown,
        normalize_markdown_content,
    ]
    assert normalize_markdown_content.invoke({"markdown": "# 标题\n正文"}) == "# 标题\n正文\n"


def test_raw_requirement_converter_has_split_converters() -> None:
    converter_root = Path("app/agents/raw_requirement_converter/converters")
    for filename in ("__init__.py", "pdf.py", "word.py", "text.py", "markdown.py"):
        assert (converter_root / filename).exists()


def test_raw_requirement_converter_has_no_deepagents_or_subagents() -> None:
    agent_source = Path("app/agents/raw_requirement_converter/agent.py").read_text(encoding="utf-8")
    assert "deepagents" not in agent_source
    assert "create_deep_agent" not in agent_source
    assert "FilesystemBackend" not in agent_source
    assert "SUBAGENTS" not in agent_source
    assert "pdf_parser_agent" not in agent_source
    assert "word_parser_agent" not in agent_source
    assert "markdown_formatter_agent" not in agent_source
    assert not Path("app/agents/raw_requirement_converter/skills").exists()


def test_raw_requirement_converter_agent_uses_langchain_create_agent(monkeypatch) -> None:
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
        "app.agents.raw_requirement_converter.agent.create_agent",
        fake_create_agent,
    )

    agent = raw_requirement_converter_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == tools
    assert calls["response_format"] is RequirementConversionOutput
    assert "原始需求文件 Markdown 转换智能体" in calls["system_prompt"]
    assert "不得编造" in calls["system_prompt"]


@pytest.mark.anyio
async def test_raw_requirement_converter_service_returns_structured_response(monkeypatch, tmp_path) -> None:
    from app.agents.raw_requirement_converter.service import convert_requirement_file

    source_path = tmp_path / "demo.md"
    source_path.write_text("# 登录\n支持账号密码登录。", encoding="utf-8")
    expected = RequirementConversionOutput(
        markdown_content="# 登录\n\n- 支持账号密码登录。\n",
        conversion_summary="已标准化 Markdown。",
    )

    class FakeAgent:
        async def ainvoke(self, payload):
            content = payload["messages"][0]["content"]
            assert "source_file_path:" in content
            assert str(source_path) in content
            return {"structured_response": expected}

    monkeypatch.setattr("app.agents.raw_requirement_converter.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.raw_requirement_converter.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.raw_requirement_converter.service.raw_requirement_converter_agent", lambda model: FakeAgent())

    result = await convert_requirement_file(
        RequirementConversionInput(
            filename="demo.md",
            file_format="md",
            source_file_path=str(source_path),
        )
    )

    assert result is expected


@pytest.mark.anyio
async def test_raw_requirement_converter_service_rejects_missing_structured_response(monkeypatch, tmp_path) -> None:
    from app.agents.raw_requirement_converter.service import convert_requirement_file

    source_path = tmp_path / "demo.md"
    source_path.write_text("# 登录\n支持账号密码登录。", encoding="utf-8")

    class FakeAgent:
        async def ainvoke(self, payload):
            return {}

    monkeypatch.setattr("app.agents.raw_requirement_converter.service.resolve_model_selection", lambda capability_id: "selection")
    monkeypatch.setattr("app.agents.raw_requirement_converter.service.build_agent_model", lambda selection: "model")
    monkeypatch.setattr("app.agents.raw_requirement_converter.service.raw_requirement_converter_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await convert_requirement_file(
            RequirementConversionInput(
                filename="demo.md",
                file_format="md",
                source_file_path=str(source_path),
            )
        )


def test_document_file_service_uses_raw_requirement_converter_service() -> None:
    service_path = Path("app/services/document_file_service.py")
    content = service_path.read_text(encoding="utf-8")
    assert "from app.agents.raw_requirement_converter.service import convert_requirement_file" in content
    assert "from app.agents.raw_requirement_converter.converters import convert_requirement_file_to_markdown" not in content
    assert "from app.services.requirement_file_converter import convert_requirement_file_to_markdown" not in content
