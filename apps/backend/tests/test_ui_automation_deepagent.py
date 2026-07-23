import asyncio
from pathlib import Path

from app.agents.ui_automation.pytest_playwright import agent as agent_module


def test_agent_uses_project_suite_as_filesystem_root(monkeypatch, tmp_path: Path):
    captured = {}

    class FakeBackend:
        def __init__(self, *, root_dir, virtual_mode):
            captured["root_dir"] = root_dir
            captured["virtual_mode"] = virtual_mode

    def fake_create_deep_agent(**kwargs):
        captured["kwargs"] = kwargs
        return "agent"

    monkeypatch.setattr(agent_module, "FilesystemBackend", FakeBackend)
    monkeypatch.setattr(agent_module, "create_deep_agent", fake_create_deep_agent)

    result = agent_module.create_pytest_playwright_agent(model="model", suite_path=tmp_path)

    assert result == "agent"
    assert captured["root_dir"] == str(tmp_path.resolve())
    assert captured["virtual_mode"] is True
    assert captured["kwargs"]["skills"] == [".deepagents/skills"]
    assert (tmp_path / ".deepagents/skills/pytest-playwright-ui-generation/SKILL.md").exists()
    tool_names = {tool.name for tool in captured["kwargs"]["tools"]}
    assert tool_names == {"validate_automation_plan", "render_automation_plan", "run_pytest_collection"}
    assert "允许修改指定的派生测试数据文件" in captured["kwargs"]["system_prompt"]
    assert "不得回写原始测试用例" in captured["kwargs"]["system_prompt"]
    assert "不得编造 locator" in captured["kwargs"]["system_prompt"]


def test_case_generation_prompt_contains_backend_owned_paths(monkeypatch, tmp_path: Path):
    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["payload"] = payload
            return {"messages": []}

    monkeypatch.setattr(agent_module, "create_pytest_playwright_agent", lambda **_: FakeAgent())

    result = asyncio.run(
        agent_module.generate_pytest_playwright_case(
            model="model",
            suite_path=tmp_path,
            case_payload={"id": "case-1", "title": "登录"},
            evidence_payload={"pages": []},
            artifacts={
                "test_file": "testcases/generated/project_1/test_login.py",
                "data_file": "data/projects/project_1/cases/login.yaml",
                "plan_file": "data/projects/project_1/cases/login.plan.json",
            },
        )
    )

    content = captured["payload"]["messages"][0]["content"]
    assert result == {"messages": []}
    assert "testcases/generated/project_1/test_login.py" in content
    assert "data/projects/project_1/cases/login.yaml" in content
    assert "data/projects/project_1/cases/login.plan.json" in content
    assert "唯一合法" in content
