from app.agents.capabilities import (
    get_ai_capability,
    list_ai_capabilities,
)


def test_ai_capabilities_include_document_editor() -> None:
    capability = get_ai_capability("document_editor")
    assert capability.name == "文档修改"
    assert not hasattr(capability, "kind")


def test_ai_capability_ids_are_unique() -> None:
    ids = [capability.id for capability in list_ai_capabilities()]
    assert len(ids) == len(set(ids))


def test_ai_capabilities_include_business_agents() -> None:
    ids = [capability.id for capability in list_ai_capabilities()]
    assert "document_editor" in ids
    assert "requirement_analysis" in ids
    assert "page_exploration" in ids
    assert "site_exploration" not in ids


def test_ai_capability_names_do_not_repeat_agent_suffix() -> None:
    names = [capability.name for capability in list_ai_capabilities()]

    assert all("智能体" not in name for name in names)


def test_ai_capabilities_exclude_letter_captcha_recognition() -> None:
    ids = [capability.id for capability in list_ai_capabilities()]
    assert "letter_captcha_recognition" not in ids


def test_ai_capabilities_do_not_carry_redundant_kind() -> None:
    assert all(not hasattr(capability, "kind") for capability in list_ai_capabilities())
