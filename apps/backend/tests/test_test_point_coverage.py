from app.agents.test_point_generation.coverage import evaluate_test_point_coverage
from app.agents.test_point_generation.schemas import GeneratedTestPoint, RequirementObligation


def _obligation(key: str) -> RequirementObligation:
    return RequirementObligation(
        obligation_key=key,
        source_section="最终需求",
        statement=f"需求 {key}",
        obligation_type="business_rule",
    )


def _point(key: str, obligation_keys: list[str]) -> GeneratedTestPoint:
    return GeneratedTestPoint(
        point_key=key,
        title=key,
        module="模块",
        category="功能",
        priority="P0",
        description="描述",
        verification_points=["操作 → 预期结果"],
        requirement_obligation_keys=obligation_keys,
    )


def test_coverage_is_complete_when_every_required_obligation_is_linked():
    result = evaluate_test_point_coverage(
        [_obligation("REQ-001"), _obligation("REQ-002")],
        [_point("point-1", ["REQ-001"]), _point("point-2", ["REQ-002"])],
        [],
    )

    assert result.status == "complete"
    assert result.missing_obligation_keys == []
    assert result.covered_obligation_count == 2


def test_coverage_reports_missing_required_obligations():
    result = evaluate_test_point_coverage(
        [_obligation("REQ-001"), _obligation("REQ-002")],
        [_point("point-1", ["REQ-001"])],
        [],
    )

    assert result.status == "incomplete"
    assert result.missing_obligation_keys == ["REQ-002"]


def test_coverage_rejects_unknown_obligation_links():
    result = evaluate_test_point_coverage(
        [_obligation("REQ-001")],
        [_point("point-1", ["REQ-999"])],
        [],
    )

    assert result.status == "invalid"
    assert result.unknown_obligation_keys == ["REQ-999"]


def test_coverage_rejects_unsupported_assumptions():
    result = evaluate_test_point_coverage(
        [_obligation("REQ-001")],
        [_point("point-1", ["REQ-001"])],
        ["数据库失败时自动重试"],
    )

    assert result.status == "invalid"
    assert result.unsupported_assumptions == ["数据库失败时自动重试"]


def test_atomized_module_obligation_is_covered_by_its_explicit_link():
    obligation = RequirementObligation(
        obligation_key="REQ-001",
        source_section="配置入口",
        statement="支持模型显示开关",
        obligation_type="display",
        modules=["自主规划Agent"],
    )
    point = GeneratedTestPoint(
        point_key="planning.switch",
        title="自主规划Agent显示开关",
        module="模型配置弹窗",
        category="功能",
        priority="P0",
        description="验证",
        verification_points=["查看 → 显示"],
        requirement_obligation_keys=["REQ-001"],
    )

    result = evaluate_test_point_coverage([obligation], [point], [])

    assert result.status == "complete"
    assert result.missing_obligation_keys == []
    assert result.covered_obligation_count == 1
