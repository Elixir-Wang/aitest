from app.agents.capabilities import (
    get_ai_capability,
    list_agent_capabilities,
    list_ai_capabilities,
    list_llm_task_capabilities,
)


def test_ai_capabilities_include_document_editor_as_agent() -> None:
    capability = get_ai_capability("document_editor")
    assert capability.name == "文档修改"
    assert capability.kind == "agent"


def test_ai_capability_ids_are_unique() -> None:
    ids = [capability.id for capability in list_ai_capabilities()]
    assert len(ids) == len(set(ids))


def test_agent_capabilities_include_document_editor() -> None:
    ids = [capability.id for capability in list_agent_capabilities()]
    assert "document_editor" in ids
    assert "requirement_merge" in ids


def test_llm_task_capabilities_exclude_document_editor() -> None:
    ids = [capability.id for capability in list_llm_task_capabilities()]
    assert "document_editor" not in ids
