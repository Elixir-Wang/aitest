import pytest

from app.agents.requirement_merge.agent import requirement_merge_outline_agent, requirement_merge_section_agent
from app.agents.requirement_merge.schemas import (
    RequirementMergeOutlineModule,
    RequirementMergeOutlineOutput,
    RequirementMergePlacement,
    RequirementMergeSectionContent,
    RequirementMergeSectionCoverage,
    RequirementMergeSectionOutput,
)
from app.schemas.requirement_merge import RequirementMergeSourceFile, TargetOutlineSection
from app.services.requirement_merge import outline_service, section_merge_service
from app.services.requirement_merge.source_outline_service import build_source_outline


def test_requirement_merge_agents_use_langchain_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_create_agent(**kwargs):
        calls.append(kwargs)
        return "agent"

    monkeypatch.setattr("app.agents.requirement_merge.agent.create_agent", fake_create_agent)

    assert requirement_merge_outline_agent("model") == "agent"
    assert requirement_merge_section_agent("model") == "agent"

    assert calls[0]["model"] == "model"
    assert calls[0]["tools"] == []
    assert "二级大纲归并智能体" in calls[0]["system_prompt"]
    assert calls[0]["response_format"].schema is RequirementMergeOutlineOutput
    assert "只生成二级模块" in calls[0]["system_prompt"]
    assert calls[1]["response_format"].schema is RequirementMergeSectionOutput
    assert "模块正文归并智能体" in calls[1]["system_prompt"]


@pytest.mark.anyio
async def test_generate_target_outline_uses_secondary_block_index(monkeypatch: pytest.MonkeyPatch) -> None:
    source_documents = build_source_outline(
        [
            RequirementMergeSourceFile(
                mapping_id="map-1",
                original_filename="需求.md",
                markdown_content=(
                    "# 总需求\n\n"
                    "## 登录\n\n"
                    "登录概述。\n\n"
                    "### 手机验证码\n\n"
                    "验证码规则。\n\n"
                    "## 账号映射\n\n"
                    "映射规则。\n"
                ),
            )
        ]
    )
    captured = {}

    async def fake_generate_outline(input_data):
        captured["input"] = input_data
        return RequirementMergeOutlineOutput(
            outline=[RequirementMergeOutlineModule(id="module-login", title="统一登录")],
            placements=[
                RequirementMergePlacement(source_id="A-01", target_id="module-login"),
                RequirementMergePlacement(source_id="A-02", target_id="module-login"),
            ],
        )

    monkeypatch.setattr(outline_service, "generate_outline_and_placements", fake_generate_outline)

    target_outline, errors, debug = await outline_service.generate_target_outline("统一登录需求", source_documents)

    assert errors == []
    assert captured["input"].model_dump() == {
        "document_name": "统一登录需求",
        "source_blocks": [
            {"id": "A-01", "title": "登录", "children": ["手机验证码"]},
            {"id": "A-02", "title": "账号映射", "children": []},
        ],
    }
    assert debug["input"] == captured["input"].model_dump()
    assert target_outline[0].section_id == "root"
    assert target_outline[0].children[0].section_id == "module-login"
    assert target_outline[0].children[0].level == 2
    assert target_outline[0].children[0].source_node_ids == ["A-01", "A-02"]


@pytest.mark.anyio
async def test_section_merge_uses_langchain_structured_section_output(monkeypatch: pytest.MonkeyPatch) -> None:
    source_documents = build_source_outline(
        [
            RequirementMergeSourceFile(
                mapping_id="map-1",
                original_filename="需求.md",
                markdown_content=(
                    "# 总需求\n\n"
                    "## 登录\n\n"
                    "登录概述。\n\n"
                    "### 手机验证码\n\n"
                    "验证码规则。\n\n"
                    "## 登录票据\n\n"
                    "票据规则。\n"
                ),
            )
        ]
    )
    section = TargetOutlineSection(
        section_id="module-login",
        parent_id="root",
        level=2,
        title="统一登录",
        source_node_ids=["A-01", "A-02"],
    )
    captured = {}

    async def fake_merge_section(input_data):
        captured["input"] = input_data
        return RequirementMergeSectionOutput(
            module_id="module-login",
            title="统一登录",
            sections=[
                RequirementMergeSectionContent(
                    title="登录方式",
                    content=["系统应支持手机验证码登录。"],
                )
            ],
            coverage=[
                RequirementMergeSectionCoverage(source_id="A-01", status="merged"),
                RequirementMergeSectionCoverage(source_id="A-02", status="merged"),
            ],
            conflicts=[],
        )

    monkeypatch.setattr(section_merge_service, "merge_requirement_section", fake_merge_section)

    results, errors = await section_merge_service.merge_sections_by_target_outline(
        source_documents,
        [TargetOutlineSection(section_id="root", level=1, title="统一登录需求", children=[section])],
        [
            section_merge_service.OutlineAssignment(
                source_node_id="A-01",
                target_section_id="module-login",
                assignment_type="primary",
                reason="outline_source_ref",
            ),
            section_merge_service.OutlineAssignment(
                source_node_id="A-02",
                target_section_id="module-login",
                assignment_type="primary",
                reason="outline_source_ref",
            ),
        ],
    )

    assert errors == []
    assert captured["input"].model_dump()["source_blocks"][0]["children"] == ["手机验证码"]
    assert results[0].section_id == "module-login"
    assert [block.content for block in results[0].blocks] == ["### 登录方式", "系统应支持手机验证码登录。"]
    assert {decision.source_node_id for decision in results[0].decisions} == {"A-01", "A-02"}
