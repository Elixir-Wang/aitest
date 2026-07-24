import pytest
from pydantic import ValidationError

from app.agents.test_point_generation.schemas import (
    GeneratedTestPoint,
    GeneratedTestPointDraft,
    RequirementObligation,
    TestPointGenerationResult as GenerationResult,
)
from app.agents.test_point_generation.service import _enrich_drafts, _validate_generation_result


def _point(**overrides):
    values = {
        "point_key": "model.think.toggle",
        "title": "支持思考模式的模型显示开关",
        "module": "对话模型配置弹窗",
        "category": "功能",
        "priority": "P0",
        "description": "验证开关显示。",
        "verification_points": ["打开弹窗 → 显示开关"],
        "requirement_obligation_keys": ["REQ-001"],
    }
    values.update(overrides)
    return GeneratedTestPoint(**values)


def test_generation_result_requires_a_non_empty_points_array():
    with pytest.raises(ValidationError):
        GenerationResult(points=[])


def test_model_draft_contains_only_supported_generation_fields():
    draft = GeneratedTestPointDraft(
        module="模型配置",
        test_point="显示思考模式开关",
        priority="P0",
        requirement_obligation_keys=["REQ-001"],
    )
    assert draft.model_dump() == {
        "module": "模型配置",
        "test_point": "显示思考模式开关",
        "priority": "P0",
        "requirement_obligation_keys": ["REQ-001"],
    }
    with pytest.raises(ValidationError):
        GeneratedTestPointDraft(
            module="模型配置",
            test_point="显示思考模式开关",
            priority="P0",
            requirement_obligation_keys=["REQ-001"],
            description="不应由模型生成",
        )


def test_model_draft_requires_explicit_obligation_keys():
    with pytest.raises(ValidationError):
        GeneratedTestPointDraft(module="模型配置", test_point="显示思考模式开关", priority="P0")


def test_enrich_drafts_uses_explicit_obligation_link_and_canonical_module():
    obligation = RequirementObligation(
        obligation_key="REQ-001.M01",
        source_section="配置入口",
        statement="显示开关",
        obligation_type="display",
        modules=["自主规划Agent - 对话模型配置弹窗"],
    )
    points = _enrich_drafts(
        [
            GeneratedTestPointDraft(
                module="对话模型配置弹窗",
                test_point="显示思考模式开关",
                priority="P0",
                requirement_obligation_keys=["REQ-001.M01"],
            )
        ],
        obligations=[obligation],
        missing_obligation_keys=["REQ-001.M01"],
    )

    assert points[0].module == "自主规划Agent - 对话模型配置弹窗"
    assert points[0].title == "显示思考模式开关"
    assert points[0].requirement_obligation_keys == ["REQ-001.M01"]


def test_enrich_drafts_merges_same_module_and_title_obligation_links():
    obligations = [
        RequirementObligation(
            obligation_key=key,
            source_section="配置入口",
            statement=key,
            obligation_type="display",
            modules=["对话模型配置弹窗"],
        )
        for key in ["REQ-001", "REQ-002"]
    ]
    points = _enrich_drafts(
        [
            GeneratedTestPointDraft(
                module="对话模型配置弹窗",
                test_point="显示思考模式开关",
                priority="P0",
                requirement_obligation_keys=[key],
            )
            for key in ["REQ-001", "REQ-002"]
        ],
        obligations=obligations,
        missing_obligation_keys=["REQ-001", "REQ-002"],
    )

    assert len(points) == 1
    assert points[0].title == "显示思考模式开关"
    assert points[0].requirement_obligation_keys == ["REQ-001", "REQ-002"]


def test_enrich_drafts_rejects_obligation_outside_supplement_scope():
    obligations = [
        RequirementObligation(
            obligation_key=key,
            source_section="配置入口",
            statement=key,
            obligation_type="display",
        )
        for key in ["REQ-001", "REQ-002"]
    ]

    with pytest.raises(ValueError, match="本轮范围外"):
        _enrich_drafts(
            [
                GeneratedTestPointDraft(
                    module="模型配置",
                    test_point="显示开关",
                    priority="P0",
                    requirement_obligation_keys=["REQ-001"],
                )
            ],
            obligations=obligations,
            missing_obligation_keys=["REQ-002"],
        )


def test_generated_test_point_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        _point(verificationPoints=["错误字段名"])


def test_generation_result_rejects_duplicate_point_keys():
    result = GenerationResult(points=[_point(), _point()])
    obligation = RequirementObligation(
        obligation_key="REQ-001",
        source_section="需求",
        statement="支持思考模式",
        obligation_type="display",
    )

    with pytest.raises(ValueError, match="重复"):
        _validate_generation_result(result, [obligation])


def test_generation_result_rejects_duplicate_titles_with_different_keys():
    result = GenerationResult(
        points=[
            _point(point_key="point-1"),
            _point(point_key="point-2"),
        ]
    )
    obligation = RequirementObligation(
        obligation_key="REQ-001",
        source_section="需求",
        statement="支持思考模式",
        obligation_type="display",
    )

    with pytest.raises(ValueError, match="重复的测试点标题"):
        _validate_generation_result(result, [obligation])


def test_generation_result_rejects_title_already_used_by_existing_point():
    result = GenerationResult(
        points=[
            _point(
                point_key="new-point",
                module="Multi-Agent - Agent节点",
                requirement_obligation_keys=["REQ-002"],
            )
        ]
    )
    obligations = [
        RequirementObligation(
            obligation_key=key,
            source_section="需求",
            statement="支持思考模式",
            obligation_type="display",
        )
        for key in ["REQ-001", "REQ-002"]
    ]

    with pytest.raises(ValueError, match="重复的测试点标题"):
        _validate_generation_result(result, obligations, existing_points=[_point()])


def test_generation_result_rejects_unknown_obligation_keys():
    result = GenerationResult(points=[_point(requirement_obligation_keys=["REQ-999"])])
    obligation = RequirementObligation(
        obligation_key="REQ-001",
        source_section="需求",
        statement="支持思考模式",
        obligation_type="display",
    )

    with pytest.raises(ValueError, match="不存在的需求义务"):
        _validate_generation_result(result, [obligation])
