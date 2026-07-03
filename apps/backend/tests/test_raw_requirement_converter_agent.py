from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agents.model_selection import ModelSelection
from app.agents.requirement_standardization import schemas
from app.agents.requirement_standardization.agent import requirement_standardization_agent
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


def _model_selection(provider: str = "openai", model: str = "gpt-4o-mini") -> ModelSelection:
    return ModelSelection(provider=provider, model=model, base_url=None, api_key="test-key")


def test_requirement_conversion_output_contract_is_minimal() -> None:
    assert set(RequirementConversionOutput.model_fields) == {
        "markdown_content",
        "conversion_summary",
    }


def test_requirement_conversion_input_uses_candidate_markdown_contract() -> None:
    assert set(RequirementConversionInput.model_fields) == {
        "filename",
        "markdown_content",
    }


def test_requirement_conversion_output_requires_conversion_summary() -> None:
    with pytest.raises(ValidationError):
        RequirementConversionOutput(
            markdown_content="# 登录\n\n- 支持账号密码登录。\n",
            conversion_summary="",
        )


def test_requirement_standardization_schemas_reuse_api_contract() -> None:
    assert schemas.RequirementConversionInput is RequirementConversionInput
    assert schemas.RequirementConversionOutput is RequirementConversionOutput


def test_requirement_standardization_agent_does_not_expose_file_conversion_tools() -> None:
    agent_source = Path("app/agents/requirement_standardization/agent.py").read_text(encoding="utf-8")
    assert "convert_pdf_to_markdown" not in agent_source
    assert "convert_word_to_markdown" not in agent_source
    assert "convert_text_to_markdown" not in agent_source
    assert "langchain_core.tools" not in agent_source


def test_requirement_standardization_uses_service_file_converters() -> None:
    converter_root = Path("app/services/requirement_file_conversion")
    for filename in ("__init__.py", "common.py", "dispatcher.py", "pdf.py", "word.py", "text.py"):
        assert (converter_root / filename).exists()
    assert not Path("app/services/requirement_file_converter.py").exists()
    assert not Path("app/agents/requirement_standardization/tools.py").exists()


def test_requirement_standardization_has_no_deepagents_or_subagents() -> None:
    agent_source = Path("app/agents/requirement_standardization/agent.py").read_text(encoding="utf-8")
    assert "deepagents" not in agent_source
    assert "create_deep_agent" not in agent_source
    assert "FilesystemBackend" not in agent_source
    assert "SUBAGENTS" not in agent_source
    assert "pdf_parser_agent" not in agent_source
    assert "word_parser_agent" not in agent_source
    assert "markdown_formatter_agent" not in agent_source
    assert not Path("app/agents/requirement_standardization/skills").exists()


def test_requirement_standardization_agent_uses_langchain_create_agent(monkeypatch) -> None:
    from langchain.agents.structured_output import ToolStrategy

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
        "app.agents.requirement_standardization.agent.create_agent",
        fake_create_agent,
    )

    agent = requirement_standardization_agent("model")

    assert agent == "agent"
    assert calls["model"] == "model"
    assert calls["tools"] == []
    assert isinstance(calls["response_format"], ToolStrategy)
    assert calls["response_format"].schema is RequirementConversionOutput
    assert calls["response_format"].handle_errors is True
    assert "markdown 文档标准化智能体" in calls["system_prompt"]
    assert "不得编造" in calls["system_prompt"]
    assert "你的唯一处理对象是 candidate_markdown" in calls["system_prompt"]
    assert "先识别结构，再输出 Markdown" in calls["system_prompt"]
    assert "优先级为：标题 > 表格 > Mermaid 流程图 > 列表 > 普通段落 > 代码块" in calls["system_prompt"]
    assert "原文能够支撑的标题层级" in calls["system_prompt"]
    assert "不要为了形式完整强凑标题层级" in calls["system_prompt"]
    assert "有序列表或无序列表" in calls["system_prompt"]
    assert "特点：" in calls["system_prompt"]
    assert "取值为：" in calls["system_prompt"]
    assert "必须整理为列表" in calls["system_prompt"]
    assert "连续枚举项，应整理为无序列表" in calls["system_prompt"]
    assert "去掉条目正文开头重复的" in calls["system_prompt"]
    assert "普通正文、标题、字段值中的同类文字必须保留" in calls["system_prompt"]
    assert "Markdown 表格" in calls["system_prompt"]
    assert "代码块" in calls["system_prompt"]
    assert "Mermaid 流程图" in calls["system_prompt"]
    assert "业务流程箭头链不是代码" in calls["system_prompt"]
    assert "对由箭头串联且语义明确的流程、步骤、状态流转、页面跳转或调用链路，必须整理为 Mermaid 流程图" in calls["system_prompt"]
    assert "ticket verify" not in calls["system_prompt"]
    assert "有账号有权限建 Session" not in calls["system_prompt"]
    assert "已有 `sequenceDiagram`、`flowchart` 或 `graph` 时，保留 Mermaid" in calls["system_prompt"]
    assert "Mermaid 只表达流程关系" in calls["system_prompt"]
    assert "参数、JSON、接口示例、代码、正则、HTML 和长错误提示放到图外" in calls["system_prompt"]
    assert "节点文案必须简短安全" in calls["system_prompt"]
    assert "概括成不含特殊语法符号的短语" in calls["system_prompt"]
    assert "如果无法确认可渲染，不要输出 Mermaid" in calls["system_prompt"]
    assert "依据不足时保持原文文本" in calls["system_prompt"]
    assert "不得把不确定内容强行转换为 Mermaid" in calls["system_prompt"]
    assert "链接和图片引用" in calls["system_prompt"]
    assert "不得根据 filename 后缀臆测原始文件结构" in calls["system_prompt"]
    assert "对 PDF/TXT 转换出的纯文本" not in calls["system_prompt"]
    assert "对 Word/Markdown 转换结果" not in calls["system_prompt"]


@pytest.mark.anyio
async def test_requirement_standardization_service_returns_structured_response(monkeypatch) -> None:
    from app.agents.requirement_standardization.service import convert_requirement_file

    expected = RequirementConversionOutput(
        markdown_content="# 登录\n\n- 支持账号密码登录。\n",
        conversion_summary="已标准化 Markdown。",
    )

    class FakeAgent:
        async def ainvoke(self, payload):
            content = payload["messages"][0]["content"]
            assert "candidate_markdown:" in content
            assert "source_file_path:" not in content
            assert "# 登录\n支持账号密码登录。" in content
            return {"structured_response": expected}

    captured = {}

    def fake_resolve_model_selection(capability_id):
        captured["capability_id"] = capability_id
        return _model_selection()

    monkeypatch.setattr("app.agents.requirement_standardization.service.resolve_model_selection", fake_resolve_model_selection)
    monkeypatch.setattr("app.agents.requirement_standardization.service.build_agent_model", lambda selection, *, extra_body=None: "model")
    monkeypatch.setattr("app.agents.requirement_standardization.service.requirement_standardization_agent", lambda model: FakeAgent())

    result = await convert_requirement_file(
        RequirementConversionInput(
            filename="demo.md",
            markdown_content="# 登录\n支持账号密码登录。",
        )
    )

    assert result is expected
    assert captured["capability_id"] == "requirement_standardization"


@pytest.mark.anyio
async def test_requirement_standardization_service_rejects_missing_structured_response(monkeypatch) -> None:
    from app.agents.requirement_standardization.service import convert_requirement_file

    class FakeAgent:
        async def ainvoke(self, payload):
            return {}

    monkeypatch.setattr("app.agents.requirement_standardization.service.resolve_model_selection", lambda capability_id: _model_selection())
    monkeypatch.setattr("app.agents.requirement_standardization.service.build_agent_model", lambda selection, *, extra_body=None: "model")
    monkeypatch.setattr("app.agents.requirement_standardization.service.requirement_standardization_agent", lambda model: FakeAgent())

    with pytest.raises(ValueError, match="未返回结构化结果"):
        await convert_requirement_file(
            RequirementConversionInput(
                filename="demo.md",
                markdown_content="# 登录\n支持账号密码登录。",
            )
        )


@pytest.mark.anyio
async def test_requirement_standardization_disables_thinking_for_tool_strategy_models(monkeypatch) -> None:
    from app.agents.requirement_standardization.service import convert_requirement_file

    expected = RequirementConversionOutput(
        markdown_content="# 登录\n\n- 支持账号密码登录。\n",
        conversion_summary="已标准化 Markdown。",
    )
    seen = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            return {"structured_response": expected}

    def fake_build_agent_model(selection, *, extra_body=None):
        seen["extra_body"] = extra_body
        return "model"

    monkeypatch.setattr(
        "app.agents.requirement_standardization.service.resolve_model_selection",
        lambda capability_id: _model_selection(provider="deepseek", model="deepseek-reasoner"),
    )
    monkeypatch.setattr("app.agents.requirement_standardization.service.build_agent_model", fake_build_agent_model)
    monkeypatch.setattr("app.agents.requirement_standardization.service.requirement_standardization_agent", lambda model: FakeAgent())

    result = await convert_requirement_file(
        RequirementConversionInput(
            filename="demo.md",
            markdown_content="# 登录\n支持账号密码登录。",
        )
    )

    assert result is expected
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}


def test_document_file_service_uses_requirement_standardization_service() -> None:
    service_path = Path("app/services/document/file_service.py")
    content = service_path.read_text(encoding="utf-8")
    assert "from app.agents.requirement_standardization.service import convert_requirement_file" in content
    assert "from app.agents.raw_requirement_converter.service import convert_requirement_file" not in content
    assert "from app.agents.raw_requirement_converter.converters import convert_requirement_file_to_markdown" not in content


@pytest.mark.anyio
async def test_document_file_service_converts_locally_before_standardization(monkeypatch, tmp_path) -> None:
    from app.services.document import file_service as document_file_service

    source_path = tmp_path / "demo.docx"
    source_path.write_bytes(b"fake-docx")
    seen = {}

    def fake_local_convert(filename, raw_bytes, *, assets_dir=None):
        seen["local"] = {
            "filename": filename,
            "raw_bytes": raw_bytes,
            "assets_dir": assets_dir,
        }
        return "# 登录\n支持账号密码登录。", "已通过本地 Word 转换器提取正文。"

    async def fake_standardize(input_data):
        seen["agent_input"] = input_data
        return RequirementConversionOutput(
            markdown_content="# 登录\n\n- 支持账号密码登录。",
            conversion_summary="已标准化候选 Markdown。",
        )

    monkeypatch.setattr(document_file_service, "convert_requirement_file_to_markdown", fake_local_convert)
    monkeypatch.setattr(document_file_service, "convert_requirement_file", fake_standardize)

    markdown, summary = await document_file_service.convert_to_markdown(
        "demo.docx",
        source_path=source_path,
        assets_dir=tmp_path / "assets",
    )

    assert seen["local"]["raw_bytes"] == b"fake-docx"
    assert seen["agent_input"].markdown_content == "# 登录\n支持账号密码登录。\n"
    assert not hasattr(seen["agent_input"], "conversion_summary")
    assert not hasattr(seen["agent_input"], "file_format")
    assert not hasattr(seen["agent_input"], "source_file_path")
    assert markdown == "# 登录\n\n- 支持账号密码登录。\n"
    assert summary == "已标准化候选 Markdown。"


@pytest.mark.anyio
async def test_document_file_service_returns_agent_markdown_without_mermaid_cleanup(monkeypatch, tmp_path) -> None:
    from app.services.document import file_service as document_file_service

    source_path = tmp_path / "demo.docx"
    source_path.write_bytes(b"fake-docx")

    def fake_local_convert(filename, raw_bytes, *, assets_dir=None):
        return "# 登录\n支持账号密码登录。", "已通过本地 Word 转换器提取正文。"

    async def fake_standardize(input_data):
        return RequirementConversionOutput(
            markdown_content='''# 推荐策略

```mermaid
flowchart TD
    D -->|否| F[提示"产品未开通"<br>或"联系管理员"]
```
''',
            conversion_summary="已标准化候选 Markdown。",
        )

    monkeypatch.setattr(document_file_service, "convert_requirement_file_to_markdown", fake_local_convert)
    monkeypatch.setattr(document_file_service, "convert_requirement_file", fake_standardize)

    markdown, summary = await document_file_service.convert_to_markdown(
        "demo.docx",
        source_path=source_path,
        assets_dir=tmp_path / "assets",
    )

    assert 'F[提示"产品未开通"<br>或"联系管理员"]' in markdown
    assert summary == "已标准化候选 Markdown。"


@pytest.mark.anyio
async def test_document_file_service_raises_when_standardization_fails(monkeypatch, tmp_path) -> None:
    from app.services.document import file_service as document_file_service

    source_path = tmp_path / "demo.md"
    source_path.write_text("# 登录\n支持账号密码登录。", encoding="utf-8")

    def fake_local_convert(filename, raw_bytes, *, assets_dir=None):
        return "# 登录\n支持账号密码登录。", "文本文件直接保存为 Markdown 转换稿。"

    async def fake_standardize(input_data):
        raise ValueError("模型不支持工具调用。")

    monkeypatch.setattr(document_file_service, "convert_requirement_file_to_markdown", fake_local_convert)
    monkeypatch.setattr(document_file_service, "convert_requirement_file", fake_standardize)

    with pytest.raises(ValueError, match="模型不支持工具调用。"):
        await document_file_service.convert_to_markdown(
            "demo.md",
            source_path=source_path,
            assets_dir=tmp_path / "assets",
        )


@pytest.mark.anyio
async def test_document_file_service_raises_when_standardization_returns_empty_markdown(monkeypatch, tmp_path) -> None:
    from app.services.document import file_service as document_file_service

    source_path = tmp_path / "demo.md"
    source_path.write_text("# 登录\n支持账号密码登录。", encoding="utf-8")

    def fake_local_convert(filename, raw_bytes, *, assets_dir=None):
        return "# 登录\n支持账号密码登录。", "文本文件直接保存为 Markdown 转换稿。"

    async def fake_standardize(input_data):
        return RequirementConversionOutput(
            markdown_content="  ",
            conversion_summary="标准化返回空内容。",
        )

    monkeypatch.setattr(document_file_service, "convert_requirement_file_to_markdown", fake_local_convert)
    monkeypatch.setattr(document_file_service, "convert_requirement_file", fake_standardize)

    with pytest.raises(ValueError, match="需求标准化智能体未生成有效 Markdown。"):
        await document_file_service.convert_to_markdown(
            "demo.md",
            source_path=source_path,
            assets_dir=tmp_path / "assets",
        )


def test_raw_requirement_converter_legacy_package_removed() -> None:
    assert not Path("app/agents/raw_requirement_converter").exists()
