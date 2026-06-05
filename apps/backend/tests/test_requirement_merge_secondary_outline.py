import pytest
from pydantic import ValidationError

from app.agents.requirement_merge.agent import requirement_merge_outline_agent, requirement_merge_section_agent
from app.agents.requirement_merge.schemas import (
    RequirementMergeOutlineInput,
    RequirementMergeOutlineModule,
    RequirementMergeOutlineOutput,
    RequirementMergePlacement,
    RequirementMergeSectionContent,
    RequirementMergeSectionCoverage,
    RequirementMergeSectionInput,
    RequirementMergeSectionOutput,
)
from app.schemas.requirement_merge import (
    OutlineAssignment,
    OutlineSectionDecision,
    OutlineSectionMergeResult,
    RequirementMergeSourceFile,
    TargetOutlineSection,
)
from app.services.document import merge_orchestrator
from app.services.requirement_merge import artifact_service, outline_service, quality_service, section_merge_service
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
    assert "输入是一组来源文档" in calls[0]["system_prompt"]
    assert "把所有来源块分配到新二级模块" in calls[0]["system_prompt"]
    assert "不要按来源文档分组生成目录" in calls[0]["system_prompt"]
    assert "先建立上下文，再进入方案设计、业务流程、接口数据、安全约束和验收交付" in calls[0]["system_prompt"]
    assert "不要机械生成上述所有模块" in calls[0]["system_prompt"]
    assert calls[1]["response_format"].schema is RequirementMergeSectionOutput
    assert "模块正文归并智能体" in calls[1]["system_prompt"]
    assert "组织合适的三级标题" in calls[1]["system_prompt"]
    assert "章节内必须按读者理解顺序拆分连续三级小节" in calls[1]["system_prompt"]
    assert "尽量原样保留" in calls[1]["system_prompt"]
    assert "不算冲突" in calls[1]["system_prompt"]
    assert "不要只做摘要" in calls[1]["system_prompt"]


def test_requirement_merge_agent_schemas_describe_output_contract() -> None:
    input_schema = RequirementMergeOutlineInput.model_json_schema()
    outline_schema = RequirementMergeOutlineOutput.model_json_schema()
    section_schema = RequirementMergeSectionOutput.model_json_schema()

    assert "source_documents" in input_schema["properties"]
    assert "按来源文档分组" in input_schema["properties"]["source_documents"]["description"]
    assert "归并摘要" in outline_schema["properties"]["outline_summary"]["description"]
    assert "必须且只能出现一次" in outline_schema["properties"]["placements"]["description"]
    assert "归并摘要" in section_schema["properties"]["merge_summary"]["description"]
    assert "每个输入来源块" in section_schema["properties"]["coverage"]["description"]
    assert "无冲突时返回空数组" in section_schema["properties"]["conflicts"]["description"]


def test_requirement_merge_input_schemas_reject_empty_source_blocks() -> None:
    with pytest.raises(ValidationError):
        RequirementMergeSectionInput(module_id="module-login", module_title="统一登录", source_blocks=[])

    with pytest.raises(ValidationError):
        RequirementMergeOutlineInput(
            requirement_name="统一登录需求",
            source_documents=[
                {
                    "document_name": "需求.md",
                    "source_blocks": [],
                }
            ],
        )


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
        "requirement_name": "统一登录需求",
        "source_documents": [
            {
                "document_name": "需求.md",
                "source_blocks": [
                    {"id": "A-01", "title": "登录", "children": ["手机验证码"]},
                    {"id": "A-02", "title": "账号映射", "children": []},
                ],
            }
        ],
    }
    assert debug["input"] == captured["input"].model_dump()
    assert target_outline[0].section_id == "root"
    assert target_outline[0].children[0].section_id == "module-login"
    assert target_outline[0].children[0].level == 2
    assert target_outline[0].children[0].source_node_ids == ["A-01", "A-02"]


@pytest.mark.anyio
async def test_generate_target_outline_preserves_source_document_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    source_documents = build_source_outline(
        [
            RequirementMergeSourceFile(
                mapping_id="map-1",
                original_filename="登录认证需求_PRD.md",
                markdown_content=(
                    "# 登录认证需求\n\n"
                    "## 登录\n\n"
                    "登录概述。\n\n"
                    "### 手机验证码\n\n"
                    "验证码规则。\n\n"
                ),
            ),
            RequirementMergeSourceFile(
                mapping_id="map-2",
                original_filename="登录认证补充说明.md",
                markdown_content=(
                    "# 补充说明\n\n"
                    "## 权限校验\n\n"
                    "权限规则。\n\n"
                    "### 角色权限\n\n"
                    "角色权限规则。\n\n"
                ),
            ),
        ]
    )
    captured = {}

    async def fake_generate_outline(input_data):
        captured["input"] = input_data
        return RequirementMergeOutlineOutput(
            outline=[
                RequirementMergeOutlineModule(id="module-login", title="统一登录"),
                RequirementMergeOutlineModule(id="module-authz", title="权限校验"),
            ],
            placements=[
                RequirementMergePlacement(source_id="A-01", target_id="module-login"),
                RequirementMergePlacement(source_id="B-01", target_id="module-authz"),
            ],
        )

    monkeypatch.setattr(outline_service, "generate_outline_and_placements", fake_generate_outline)

    _, errors, debug = await outline_service.generate_target_outline("统一登录需求", source_documents)

    assert errors == []
    assert captured["input"].model_dump() == {
        "requirement_name": "统一登录需求",
        "source_documents": [
            {
                "document_name": "登录认证需求_PRD.md",
                "source_blocks": [{"id": "A-01", "title": "登录", "children": ["手机验证码"]}],
            },
            {
                "document_name": "登录认证补充说明.md",
                "source_blocks": [{"id": "B-01", "title": "权限校验", "children": ["角色权限"]}],
            },
        ],
    }
    assert debug["input"] == captured["input"].model_dump()


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
                    section_heading="登录方式",
                    markdown_blocks=["系统应支持手机验证码登录。"],
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


def test_appendix_source_node_counts_as_processed_and_covered() -> None:
    source_documents = build_source_outline(
        [
            RequirementMergeSourceFile(
                mapping_id="doc-a",
                original_filename="总说明.docx",
                markdown_content="# 总说明\n\n## 阅读建议\n\n请查看附件配置表。",
            )
        ]
    )
    assignment = OutlineAssignment(
        source_node_id="A-01",
        target_section_id="module-background",
        assignment_type="appendix",
        reason="阅读建议放入附录。",
    )
    section_result = OutlineSectionMergeResult(
        section_id="module-background",
        blocks=[],
        decisions=[
            OutlineSectionDecision(
                section_id="module-background",
                source_node_id="A-01",
                status="appendix",
                target_heading="项目背景",
                reason="阅读建议作为附录保留。",
            )
        ],
    )

    quality_result, quality_issues = quality_service.evaluate_outline_merge_quality(
        source_documents=source_documents,
        target_outline=[TargetOutlineSection(section_id="module-background", level=2, title="项目背景")],
        assignments=[assignment],
        section_results=[section_result],
        conflicts=[],
        merged_markdown="# 合并稿\n\n## 附录\n\n请查看附件配置表。",
        stage_errors=[],
    )
    coverage_items = merge_orchestrator._outline_coverage_items(source_documents, [assignment], [section_result])

    assert quality_result == "passed"
    assert quality_issues == []
    assert coverage_items[0]["coverage_status"] == "appendix"


def test_quality_trace_matches_source_blocks_by_block_id_before_heading() -> None:
    source_blocks = [
        artifact_service.RequirementSourceBlock(
            block_id="A-02",
            source_code="A",
            mapping_id="doc-a",
            source_file="需求.md",
            original_heading="产品定位",
            heading_path=["产品定位"],
            markdown="## 2. 产品定位\n\n系统定位说明。",
        )
    ]
    coverage_items = [
        {
            "mapping_id": "doc-a",
            "source_block_id": "A-01",
            "source_heading": "1. 项目概述",
            "target_module": "项目背景",
            "target_heading": "项目背景",
            "coverage_status": "merged",
            "reason": "已合并",
        },
        {
            "mapping_id": "doc-a",
            "source_block_id": "A-02",
            "source_heading": "1. 项目概述 / 2. 产品定位",
            "target_module": "总体架构",
            "target_heading": "总体架构",
            "coverage_status": "merged",
            "reason": "已合并",
        }
    ]

    trace_lines = artifact_service._source_trace_lines(coverage_items, source_blocks)
    uncovered_lines = artifact_service._uncovered_source_lines(coverage_items, source_blocks)

    assert trace_lines == ["- 产品定位：已合入「总体架构 / 总体架构」"]
    assert uncovered_lines == []
