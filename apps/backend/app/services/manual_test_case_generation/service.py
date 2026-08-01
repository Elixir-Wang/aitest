from app.agents.manual_test_case_generation.schemas import (
    ManualTestCaseAiGenerateIn,
    ManualTestCaseAiGenerateOut,
    ManualTestCaseAiSourceSummaryOut,
    ManualTestCaseGenerationInput,
)
from app.agents.manual_test_case_generation.service import generate_manual_test_case
from app.core.exceptions import api_error
from app.services.manual_test_case_generation.exploration_context_builder import build_exploration_context


async def generate_manual_test_case_preview(
    actor,
    project_id: str,
    payload: ManualTestCaseAiGenerateIn,
) -> ManualTestCaseAiGenerateOut:
    if not payload.description.strip():
        raise api_error(422, "INVALID_INPUT", "测试描述不能为空。")

    context = build_exploration_context(
        actor=actor,
        project_id=project_id,
        description=payload.description,
        include_exploration_artifacts=payload.include_exploration_artifacts,
    )
    result = await generate_manual_test_case(
        ManualTestCaseGenerationInput(
            description=payload.description,
            exploration_context=context,
        )
    )
    warnings = context.warnings if context else []
    result_payload = result.model_dump()
    result_payload["generation_notes"] = [*result.generation_notes, *warnings]
    return ManualTestCaseAiGenerateOut(
        **result_payload,
        source_summary=ManualTestCaseAiSourceSummaryOut(
            exploration_artifacts_requested=payload.include_exploration_artifacts,
            exploration_artifacts_used=bool(context and context.source_count),
            page_count=len(context.pages) if context else 0,
            truncated=bool(context and context.truncated),
        ),
    )
