from __future__ import annotations

import unittest

from app.schemas.requirement_merge import (
    RequirementFragmentDecision,
    RequirementMergeAuditOutput,
    RequirementSourceFragment,
)
from app.services.requirement_merge_validation_service import (
    validate_merge_audit_output,
    validate_merge_draft_markdown,
)


class RequirementMergeValidationServiceTest(unittest.TestCase):
    def test_validate_merge_audit_output_accepts_complete_decisions(self):
        fragments = [_fragment("frag-1"), _fragment("frag-2")]
        audit_output = RequirementMergeAuditOutput(
            status="ready_for_draft",
            merge_summary="合入 2 条。",
            fragment_decisions=[
                _decision("frag-1"),
                _decision("frag-2"),
            ],
        )

        self.assertEqual(validate_merge_audit_output(audit_output, fragments), [])

    def test_validate_merge_audit_output_rejects_missing_unknown_and_duplicate_fragments(self):
        fragments = [_fragment("frag-1"), _fragment("frag-2")]
        audit_output = RequirementMergeAuditOutput(
            status="ready_for_draft",
            merge_summary="合入 2 条。",
            fragment_decisions=[
                _decision("frag-1"),
                _decision("frag-1"),
                _decision("frag-unknown"),
            ],
        )

        issues = validate_merge_audit_output(audit_output, fragments)

        self.assertTrue(any("片段决策缺失：frag-2" in issue for issue in issues))
        self.assertTrue(any("未知片段：frag-unknown" in issue for issue in issues))
        self.assertTrue(any("片段决策重复：frag-1" in issue for issue in issues))

    def test_validate_merge_audit_output_rejects_invalid_status_contracts(self):
        fragments = [_fragment("frag-1"), _fragment("frag-2")]
        audit_output = RequirementMergeAuditOutput(
            status="ready_for_draft",
            merge_summary="合入 1 条，冲突 1 处。",
            fragment_decisions=[
                _decision("frag-1", target_module="", target_heading=""),
                RequirementFragmentDecision(
                    fragment_id="frag-2",
                    mapping_id="docmap-1",
                    coverage_status="conflict",
                    related_conflict_key="missing-conflict",
                    reason="存在冲突。",
                ),
            ],
            conflicts=[{"conflict_key": "conflict-1"}],
        )

        issues = validate_merge_audit_output(audit_output, fragments)

        self.assertTrue(any("缺少目标模块或目标标题" in issue for issue in issues))
        self.assertTrue(any("未关联有效冲突" in issue for issue in issues))

    def test_validate_merge_draft_markdown_rejects_source_structure_and_conflicts(self):
        fragments = [_fragment("frag-1", source_filename="登录需求.md")]
        audit_output = RequirementMergeAuditOutput(
            status="ready_for_draft",
            merge_summary="冲突 1 处。",
            fragment_decisions=[
                RequirementFragmentDecision(
                    fragment_id="frag-1",
                    mapping_id="docmap-1",
                    coverage_status="conflict",
                    related_conflict_key="conflict-1",
                    reason="存在冲突。",
                )
            ],
            conflicts=[{"conflict_key": "conflict-1"}],
        )

        issues = validate_merge_draft_markdown("# 合并稿\n\n## 登录需求\n\n- docmap-1 内容。", fragments, audit_output)

        self.assertTrue(any("源文件名" in issue for issue in issues))
        self.assertTrue(any("明显冲突片段" in issue for issue in issues))


def _fragment(fragment_id: str, *, source_filename: str = "来源.md") -> RequirementSourceFragment:
    return RequirementSourceFragment(
        fragment_id=fragment_id,
        mapping_id="docmap-1",
        source_filename=source_filename,
        heading_path=["登录"],
        fragment_type="requirement",
        content_hash="sha256:test",
        text="支持账号登录",
        markdown_block="- 支持账号登录",
    )


def _decision(
    fragment_id: str,
    *,
    target_module: str = "登录",
    target_heading: str = "账号登录",
) -> RequirementFragmentDecision:
    return RequirementFragmentDecision(
        fragment_id=fragment_id,
        mapping_id="docmap-1",
        coverage_status="merged",
        target_module=target_module,
        target_heading=target_heading,
        reason="合入登录模块。",
    )


if __name__ == "__main__":
    unittest.main()
