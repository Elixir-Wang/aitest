from __future__ import annotations

import unittest
from pydantic import ValidationError
from unittest.mock import patch

from app.schemas.requirement_analysis import (
    RequirementAnalysisInput,
    RequirementAnalysisOutput,
    RequirementMaturityAssessment,
    RequirementQualityGate,
)
from app.services import requirement_analysis_service
from app.services.requirement_analysis_service import _parse_agent_output, run_requirement_analysis


class RequirementAnalysisServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_analysis_output_accepts_quality_gate(self):
        output = RequirementAnalysisOutput(
            status="completed",
            analysis_summary="识别 1 个模块。",
            maturity_assessment=RequirementMaturityAssessment(
                level="RA2",
                label="需求模糊",
                reason="缺少可测试规则。",
                evidence=["支持账号登录"],
            ),
            quality_gate=RequirementQualityGate(
                result="passed",
                testability_score=90,
                passed_checks=["模块识别完成"],
            ),
        )

        self.assertEqual(output.quality_gate.result, "passed")

    def test_analysis_output_rejects_invalid_score(self):
        with self.assertRaises(ValidationError):
            RequirementAnalysisOutput(
                status="completed",
                analysis_summary="invalid",
                quality_gate=RequirementQualityGate(result="passed", testability_score=101),
            )

    def test_parse_agent_output_accepts_json_string(self):
        output = _parse_agent_output(
            """
            {
              "status": "needs_clarification",
              "analysis_summary": "识别登录模块，存在 1 个澄清问题。",
              "maturity_assessment": {
                "level": "RA2",
                "label": "需求模糊",
                "reason": "缺少提示语细节。",
                "evidence": ["提示语不明确"]
              },
              "key_gaps": [
                {
                  "category": "acceptance_criteria",
                  "description": "缺少提示语验收标准。",
                  "impact": "无法判断实现是否符合预期。",
                  "severity": "major"
                }
              ],
              "assumptions": [
                {
                  "description": "登录失败后需要展示提示语。",
                  "validation_needed": "确认产品是否要求统一提示文案。",
                  "risk": "提示语不一致会影响测试断言。"
                }
              ],
              "modules": [],
              "clarification_questions": [],
              "coverage_audit": [],
              "quality_gate": {
                "result": "warning",
                "testability_score": 82,
                "blocking_issues": [],
                "warning_issues": ["提示语不明确"],
                "passed_checks": ["模块识别完成"]
              },
              "next_actions": ["补充提示语"]
            }
            """
        )

        self.assertEqual(output.status, "needs_clarification")
        self.assertEqual(output.maturity_assessment.level, "RA2")
        self.assertEqual(output.key_gaps[0].category, "acceptance_criteria")
        self.assertEqual(output.assumptions[0].validation_needed, "确认产品是否要求统一提示文案。")
        self.assertEqual(output.quality_gate.testability_score, 82)

    def test_agent_prompt_scopes_analysis_after_merge(self):
        prompt = requirement_analysis_service._build_agent_prompt(
            RequirementAnalysisInput(
                project_id="project-1",
                document_id="doc-1",
                document_name="登录需求",
                version_id="docver-1",
                version_no=1,
                markdown_content="# 登录需求\n\n- 支持账号登录",
            )
        )

        self.assertIn("已经归并完成", prompt)
        self.assertIn("不得重新归并来源文件", prompt)
        self.assertIn("不得生成知识库", prompt)
        self.assertIn("不得生成测试用例", prompt)
        self.assertIn("先判断需求成熟度", prompt)
        self.assertIn("key_gaps", prompt)
        self.assertIn("assumptions", prompt)

    async def test_run_requirement_analysis_uses_agent_output(self):
        async def fake_run_agent(agent_id, prompt):
            class Result:
                output = {
                    "status": "completed",
                    "analysis_summary": "智能体完成分析。",
                    "quality_gate": {
                        "result": "passed",
                        "testability_score": 90,
                        "blocking_issues": [],
                        "warning_issues": [],
                        "passed_checks": ["模块识别完成"],
                    },
                }

            self.assertEqual(agent_id, "requirement_analysis")
            self.assertIn("只返回一个 JSON 对象", prompt)
            return Result()

        with patch("app.services.requirement_analysis_service.run_agent", fake_run_agent):
            output = await run_requirement_analysis(
                RequirementAnalysisInput(
                    project_id="project-1",
                    document_id="doc-1",
                    document_name="登录需求",
                    version_id="docver-1",
                    version_no=1,
                    markdown_content="# 登录需求\n\n- 支持账号登录",
                )
            )

        self.assertEqual(output.analysis_summary, "智能体完成分析。")
        self.assertEqual(output.quality_gate.result, "passed")


if __name__ == "__main__":
    unittest.main()
