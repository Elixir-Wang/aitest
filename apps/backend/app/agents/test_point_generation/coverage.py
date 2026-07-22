from app.agents.test_point_generation.schemas import (
    GeneratedTestPoint,
    RequirementObligation,
    TestPointCoverageResult,
)


def evaluate_test_point_coverage(
    obligations: list[RequirementObligation],
    points: list[GeneratedTestPoint],
    unsupported_assumptions: list[str],
) -> TestPointCoverageResult:
    all_keys = {obligation.obligation_key for obligation in obligations}
    required_keys = {
        obligation.obligation_key
        for obligation in obligations
        if obligation.test_required
    }
    linked_keys = {
        obligation_key
        for point in points
        for obligation_key in point.requirement_obligation_keys
    }
    missing = sorted(required_keys - linked_keys)
    unknown = sorted(linked_keys - all_keys)
    if unknown or unsupported_assumptions:
        status = "invalid"
    elif missing:
        status = "incomplete"
    else:
        status = "complete"
    return TestPointCoverageResult(
        status=status,
        obligation_count=len(required_keys),
        covered_obligation_count=len(required_keys & linked_keys),
        missing_obligation_keys=missing,
        unknown_obligation_keys=unknown,
        unsupported_assumptions=unsupported_assumptions,
    )


__all__ = ["evaluate_test_point_coverage"]
