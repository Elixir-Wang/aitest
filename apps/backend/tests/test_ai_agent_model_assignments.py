from __future__ import annotations

from app.ai_agents.manifest import get_ai_agent, list_ai_agents


def test_ai_agent_manifest_contains_document_editor() -> None:
    agent = get_ai_agent("document_editor")
    assert agent.name == "文档修改智能体"


def test_ai_agent_manifest_ids_are_unique() -> None:
    ids = [agent.id for agent in list_ai_agents()]
    assert len(ids) == len(set(ids))
