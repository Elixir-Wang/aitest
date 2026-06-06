def test_requirement_analysis_agent_uses_deepagents_skills_middleware(monkeypatch):
    from app.agents.requirement_analysis import agent as requirement_agent

    captured = {}

    class FilesystemMiddleware:
        def __init__(self, *, backend, system_prompt):
            self.backend = backend
            self.system_prompt = system_prompt

    class SkillsMiddleware:
        def __init__(self, *, backend, sources):
            self.backend = backend
            self.sources = sources

    class SummarizationMiddleware:
        def __init__(self, *, model, backend):
            self.model = model
            self.backend = backend

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return "requirement-analysis-agent"

    monkeypatch.setattr(requirement_agent, "create_agent", fake_create_agent)
    monkeypatch.setattr(requirement_agent, "FilesystemMiddleware", FilesystemMiddleware)
    monkeypatch.setattr(requirement_agent, "SkillsMiddleware", SkillsMiddleware)
    monkeypatch.setattr(requirement_agent, "SummarizationMiddleware", SummarizationMiddleware)

    result = requirement_agent.requirement_analysis_agent("fake:model")

    assert result == "requirement-analysis-agent"
    assert captured["model"] == "fake:model"
    assert captured["tools"] == []
    assert "主需求锚定" in captured["system_prompt"]
    assert type(captured["response_format"]).__name__ == "ToolStrategy"
    middleware_names = [type(item).__name__ for item in captured["middleware"]]
    assert "FilesystemMiddleware" in middleware_names
    assert "SkillsMiddleware" in middleware_names
    assert "SummarizationMiddleware" in middleware_names
    assert (requirement_agent.SKILLS_DIR / "requirement-review" / "SKILL.md").exists()
    assert (requirement_agent.SKILLS_DIR / "test-scenarios" / "SKILL.md").exists()
