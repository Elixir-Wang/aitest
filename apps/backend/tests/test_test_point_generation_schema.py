import pytest
from pydantic import ValidationError

from app.agents.test_point_generation.schemas import (
    GeneratedTestPoint,
    GeneratedTestPointDraft,
    RequirementObligation,
    TestPointGenerationResult as GenerationResult,
)
from app.agents.test_point_generation.service import _validate_generation_result


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


def test_model_draft_contains_only_module_test_point_and_priority():
    draft = GeneratedTestPointDraft(module="模型配置", test_point="显示思考模式开关", priority="P0")
    assert draft.model_dump() == {
        "module": "模型配置",
        "test_point": "显示思考模式开关",
        "priority": "P0",
    }
    with pytest.raises(ValidationError):
        GeneratedTestPointDraft(
            module="模型配置",
            test_point="显示思考模式开关",
            priority="P0",
            description="不应由模型生成",
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
