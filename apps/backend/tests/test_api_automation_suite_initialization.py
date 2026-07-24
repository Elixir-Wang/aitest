import asyncio
from pathlib import Path

from app.agents.api_automation.pytest_requests import agent as agent_module


def test_initialize_suite_uses_same_project_root(monkeypatch, tmp_path: Path) -> None:
    captured = {}

    class FakeAgent:
        async def ainvoke(self, payload):
            captured["payload"] = payload
            return {"messages": []}

    def fake_create_agent(*, model, suite_path, max_actions):
        captured["model"] = model
        captured["suite_path"] = suite_path
        captured["max_actions"] = max_actions
        return FakeAgent()

    monkeypatch.setattr(agent_module, "create_pytest_requests_agent", fake_create_agent)

    result = asyncio.run(
        agent_module.initialize_pytest_requests_suite(
            model="model",
            suite_path=tmp_path,
            max_actions=12,
        )
    )

    assert result == {"messages": []}
    assert captured["model"] == "model"
    assert captured["suite_path"] == tmp_path
    assert captured["max_actions"] == 12
    assert "补齐缺失的公共框架文件" in captured["payload"]["messages"][0]["content"]
    assert "`/` 已经是 pytest_requests" in captured["payload"]["messages"][0]["content"]
    assert "禁止再创建 `/pytest_requests`" in captured["payload"]["messages"][0]["content"]
    assert "禁止使用宿主机绝对路径" in captured["payload"]["messages"][0]["content"]
