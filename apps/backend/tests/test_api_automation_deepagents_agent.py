import asyncio
from pathlib import Path

from app.agents.api_automation.pytest_requests import agent as agent_module


def test_agent_uses_project_suite_as_filesystem_root(monkeypatch, tmp_path: Path) -> None:
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

    suite_path = tmp_path / "project" / "api_automation" / "pytest_requests"
    result = agent_module.create_pytest_requests_agent(model="model", suite_path=suite_path)

    assert result == "agent"
    assert captured["root_dir"] == str(suite_path.resolve())
    assert captured["virtual_mode"] is True
    assert captured["kwargs"]["model"] == "model"
    assert captured["kwargs"]["backend"].__class__ is FakeBackend
    assert captured["kwargs"]["skills"] == [".deepagents/skills"]
    assert (suite_path / ".deepagents" / "skills" / "pytest-requests-code-generation" / "SKILL.md").is_file()
    assert "utils/data_loader.py" in captured["kwargs"]["system_prompt"]
    assert "虚拟根目录 `/` 已经是" in captured["kwargs"]["system_prompt"]
    assert "禁止创建 `/pytest_requests`" in captured["kwargs"]["system_prompt"]
    assert "/testcases/example/post/test_api.py" in captured["kwargs"]["system_prompt"]
    assert "`cp`、`rsync`、`shutil`" in captured["kwargs"]["system_prompt"]
    assert any(tool.name == "run_pytest_collection" for tool in captured["kwargs"]["tools"])


def test_endpoint_generation_requires_backend_artifact_targets(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["payload"] = payload
            return {"messages": []}

    monkeypatch.setattr(agent_module, "create_pytest_requests_agent", lambda **_: FakeAgent())

    endpoint = {
        "id": "apiend-1",
        "method": "POST",
        "path": "/openapi/v1/agent/analysis/",
        "artifacts": {
            "directory": "testcases/openapi/v1/agent/analysis/post",
            "test_file": "testcases/openapi/v1/agent/analysis/post/test_api.py",
            "data_file": "testcases/openapi/v1/agent/analysis/post/cases.yaml",
        },
    }
    result = asyncio.run(
        agent_module.generate_pytest_requests_endpoints(
            model="model",
            suite_path=tmp_path,
            endpoints=[endpoint],
            cases_by_endpoint={"apiend-1": []},
        )
    )

    content = captured["payload"]["messages"][0]["content"]
    assert result == {"messages": []}
    assert "artifacts.test_file" in content
    assert "唯一合法" in content
    assert "`/` 已经是 pytest_requests" in content
    assert "禁止创建 `/pytest_requests`" in content
    assert "只在前面加一次 `/`" in content
    assert "testcases/openapi/v1/agent/analysis/post/test_api.py" in content
    assert "testcases/openapi/v1/agent/analysis/post/cases.yaml" in content
