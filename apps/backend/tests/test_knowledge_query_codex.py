from types import SimpleNamespace

import pytest


def test_knowledge_query_codex_command_enables_agentic_search(monkeypatch):
    from app.services.knowledge import codex_query

    monkeypatch.setattr(codex_query, "_codex_command_path", lambda: "codex")

    command = codex_query._codex_command(
        workdir=codex_query.Path("work"),
        selection=SimpleNamespace(model="assigned-model", base_url="https://assigned.example/v1"),
        prompt="query knowledge",
    )

    assert command[:3] == ["codex", "--search", "exec"]
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "model_provider=\"backend_knowledge_query\"" in command
    assert "model_providers.backend_knowledge_query.base_url=\"https://assigned.example/v1\"" in command
    assert "model_providers.backend_knowledge_query.wire_api=\"responses\"" in command
    assert "model_providers.backend_knowledge_query.requires_openai_auth=true" in command
    assert command[command.index("--model") + 1] == "assigned-model"


def test_knowledge_query_reads_structured_output(tmp_path):
    from app.services.knowledge import codex_query

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "query.json").write_text(
        codex_query.json.dumps(
            {
                "answer": "登录模块需要覆盖成功登录和失败登录。",
                "source_refs": [
                    {
                        "source_type": "requirement",
                        "source_id": "version-1",
                        "source_title": "登录需求 v1",
                        "location": "登录",
                        "excerpt": "用户输入账号密码登录。",
                    }
                ],
                "used_requirement_versions": ["version-1"],
                "used_exploration_runs": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = codex_query._read_query_output(tmp_path)

    assert output.answer == "登录模块需要覆盖成功登录和失败登录。"
    assert output.source_refs[0].source_id == "version-1"


def test_knowledge_query_reports_missing_output(tmp_path):
    from app.services.knowledge import codex_query

    (tmp_path / "output").mkdir()

    with pytest.raises(ValueError, match="未生成 output/query.json"):
        codex_query._read_query_output(tmp_path)
