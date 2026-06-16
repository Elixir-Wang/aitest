"""
需求分析 LangGraph 端到端集成测试
"""

import pytest
from app.agents.requirement_analysis.core.schemas import (
    RequirementAnalysisInputV2,
    AuxiliaryDocument,
)


@pytest.mark.anyio
async def test_requirement_analysis_end_to_end(monkeypatch):
    """端到端测试：LangGraph 完整流程"""

    # Mock LLM 和各个 Agent（避免实际调用 API）
    from app.agents.requirement_analysis.core.schemas import (
        RequirementUnderstandingOutput,
        QualityAssessmentOutput,
        QualityIssueSummary,
        QualityDecision,
        CompletenessAssessment,
        ClarityAssessment,
        TestabilityAssessment,
        ConsistencyAssessment,
        FuzzyTerm,
    )

    # Mock understanding agent
    async def mock_understanding_agent(model, primary_markdown_content, **kwargs):
        return RequirementUnderstandingOutput(
            modules=[],
            dependencies=[],
            risks=[],
            assumptions=[],
            understanding_summary="需求理解完成",
        ), {
            "business_insight": {"domain": "测试领域", "summary": "需求理解完成"},
            "domain_model": {"summary": "领域模型"},
            "risk_profile": {"summary": "风险分析"},
            "explanation_markdown": "",
        }

    monkeypatch.setattr(
        "app.agents.requirement_analysis.agents.understanding.run_understanding_agent",
        mock_understanding_agent,
    )
    async def mock_quality(model, primary_markdown_content, understanding_result):
        return QualityAssessmentOutput(
            summary=QualityIssueSummary(
                completeness_issues=2,
                clarity_issues=3,
                testability_issues=2,
                consistency_issues=1,
                total_issues=8,
                by_severity={"blocker": 0, "major": 4, "minor": 4},
                has_blocker=False,
                can_proceed=True,
            ),
            decision=QualityDecision(
                result="conditional",
                rationale="需要澄清部分模糊词",
                blocking_issues=[],
                recommended_actions=["澄清模糊词"]
            ),
            completeness=CompletenessAssessment(),
            clarity=ClarityAssessment(
                fuzzy_terms=[
                    FuzzyTerm(
                        term="快速",
                        location="登录模块",
                        current_text="用户可以使用验证码快速登录",
                        issue="未定义具体时间",
                        suggested_fix="系统响应时间 < 2秒"
                    )
                ]
            ),
            testability=TestabilityAssessment(),
            consistency=ConsistencyAssessment(),
            assessment_summary="质量评估完成"
        )


    # Mock 质量评估
    async def mock_quality_agent(model, primary_markdown_content, understanding_result):
        # 返回简化格式，让转换函数处理
        from app.agents.requirement_analysis.core.schemas import QualityAssessmentSimple, QualityIssueFlat
        from app.agents.requirement_analysis.agents.quality import convert_to_full_assessment

        simple = QualityAssessmentSimple(
            issues=[
                QualityIssueFlat(
                    issue_id="COMP-001",
                    dimension="completeness",
                    category="nfr_gap",
                    severity="major",
                    title="缺少性能要求",
                    description="系统未定义响应时间要求",
                    location="登录模块",
                    current_text="用户可以使用验证码快速登录",
                    issue_reason="查询接口需要性能指标",
                    suggested_fix="响应时间 < 2秒",
                    impact="无法设计性能测试",
                    extra={"nfr_category": "performance"}
                ),
                QualityIssueFlat(
                    issue_id="CLAR-001",
                    dimension="clarity",
                    category="fuzzy_term",
                    severity="major",
                    title="模糊词：快速",
                    description="'快速'无法度量",
                    location="登录模块",
                    current_text="用户可以使用验证码快速登录",
                    issue_reason="无法度量具体时间",
                    suggested_fix="系统响应时间 < 2秒",
                    impact="无法设计性能测试",
                    extra={"term": "快速"}
                ),
                QualityIssueFlat(
                    issue_id="TEST-001",
                    dimension="testability",
                    category="boundary_undefined",
                    severity="major",
                    title="缺少边界值定义",
                    description="验证码长度未定义",
                    location="登录模块",
                    current_text="用户输入验证码",
                    issue_reason="无法设计边界测试",
                    suggested_fix="验证码长度：6位数字",
                    impact="无法测试边界情况",
                    extra={}
                ),
                QualityIssueFlat(
                    issue_id="TEST-002",
                    dimension="testability",
                    category="exception_missing",
                    severity="major",
                    title="缺少异常处理",
                    description="验证码错误处理未定义",
                    location="登录模块",
                    current_text="",
                    issue_reason="无法设计异常测试",
                    suggested_fix="验证码错误时提示用户重新输入",
                    impact="无法测试异常路径",
                    extra={}
                ),
                QualityIssueFlat(
                    issue_id="CONS-001",
                    dimension="consistency",
                    category="terminology",
                    severity="minor",
                    title="术语不一致",
                    description="'登录'和'登陆'混用",
                    location="全文",
                    current_text="",
                    issue_reason="术语不统一影响理解",
                    suggested_fix="统一使用'登录'",
                    impact="轻微影响",
                    extra={"concept": "登录", "variations": ["登录", "登陆"]}
                ),
                QualityIssueFlat(
                    issue_id="COMP-002",
                    dimension="completeness",
                    category="missing_detail",
                    severity="minor",
                    title="缺少错误提示",
                    description="未定义错误提示内容",
                    location="登录模块",
                    current_text="",
                    issue_reason="前端无法显示友好提示",
                    suggested_fix="定义所有错误场景的提示文案",
                    impact="用户体验影响",
                    extra={}
                ),
            ],
            assessment_summary="识别出6个问题：4个major、2个minor"
        )
        return convert_to_full_assessment(simple)

    monkeypatch.setattr(
        "app.agents.requirement_analysis.agents.quality.run_quality_assessment_agent",
        mock_quality_agent
    )

    monkeypatch.setattr(
        "app.agents.model_selection.resolve_model_selection",
        lambda capability_id: object()
    )
    monkeypatch.setattr(
        "app.agents.model_selection.build_agent_model",
        lambda model_selection: object()
    )

    # Mock clarification agent
    async def mock_clarification_agent(model, understanding_result, quality_assessment_result, auxiliary_documents):
        from datetime import datetime
        from app.agents.requirement_analysis.core.schemas import (
            ClarificationOutput,
            ClarificationSummary,
            ClarificationItem
        )

        # Return a simple clarification with one auto-resolved item
        return ClarificationOutput(
            items=[
                ClarificationItem(
                    item_id="CLR-001",
                    source_stage="clarity",
                    module_key="login",
                    module_name="登录模块",
                    title="模糊词澄清",
                    decision_point="'快速'的具体定义",
                    why_clarify="需要明确性能要求",
                    priority="P1",
                    issue_category="boundary_undefined",
                    test_impact="无法验证性能指标",
                    risk_scenario="Given 用户登录\nWhen 系统响应\nThen 需要明确响应时间",
                    resolution_status="auto_resolved",
                    auto_resolution="API响应时间要求 < 2秒",
                    auto_resolution_source="性能规范.md",
                    options=[],
                    question="请明确'快速'的具体响应时间要求？",
                    impact="无法设计性能测试用例",
                    severity="major",
                    current_text="用户可以使用验证码快速登录",
                )
            ],
            summary=ClarificationSummary(
                total=1,
                by_priority={"P0": 0, "P1": 1, "P2": 0, "P3": 0},
                by_category={"boundary_undefined": 1},
                by_resolution={"auto_resolved": 1, "has_options": 0, "needs_input": 0, "needs_research": 0}
            ),
            overall_assessment="发现1个澄清项，已自动解决",
            test_strategy_recommendations=[],
            generated_at=datetime.now().isoformat(),
            model_version="test-driven"
        )

    monkeypatch.setattr(
        "app.agents.requirement_analysis.agents.clarification.run_clarification_agent",
        mock_clarification_agent
    )

    # 准备测试输入
    input_data = RequirementAnalysisInputV2(
        project_id="test-project",
        document_id="test-doc",
        document_name="登录需求",
        run_id="test-run-001",
        primary_mapping_id="primary",
        primary_filename="登录需求.md",
        primary_markdown_content="# 登录需求\n\n用户可以使用验证码快速登录。",
        auxiliary_documents=[
            AuxiliaryDocument(
                mapping_id="aux-1",
                filename="性能规范.md",
                document_type="standard",
                markdown_content="# 性能规范\n\nAPI响应时间要求 < 2秒"
            )
        ],
        config={}
    )

    # 执行 LangGraph 分析
    from app.agents.requirement_analysis.workflow.workflow import run_requirement_analysis

    result = await run_requirement_analysis(input_data)

    # 验证结果
    assert result.status in ["completed", "needs_clarification", "blocked"]
    assert result.understanding is not None
    assert result.quality_assessment is not None
    assert result.clarification is not None

    # 调试：打印实际返回的clarification
    print(f"\n=== DEBUG ===")
    print(f"Status: {result.status}")
    print(f"Clarification items count: {len(result.clarification.items)}")
    print(f"Clarification summary: {result.clarification.summary}")
    if result.clarification.items:
        for item in result.clarification.items:
            print(f"  - {item.item_id}: {item.resolution_status}")

    # 验证自动解决生效
    auto_resolved = [
        item for item in result.clarification.items
        if item.resolution_status == "auto_resolved"
    ]
    assert len(auto_resolved) > 0, f"应该有自动解决的问题，但实际有 {len(result.clarification.items)} 个items"

    # 验证搜索结果
    first_resolved = auto_resolved[0]
    assert first_resolved.auto_resolution, "应该有自动解决方案"
    assert first_resolved.auto_resolution_source == "性能规范.md"

    # 验证元数据
    assert result.metadata["version"] == "2.0"
    assert result.metadata["engine"] == "langchain_langgraph"
    assert result.metadata["execution_time_ms"] > 0


@pytest.mark.skip(reason="Internal implementation details changed - function no longer exists")
def test_resolve_primary_source_excerpt_uses_real_primary_paragraph():
    """没有原文直接证据时，不用关键词猜一个看似相关的段落。"""
    from app.agents.requirement_analysis.workflow.nodes.clarify_node import (
        _resolve_primary_source_excerpt,
    )

    primary_content = """
# 登录需求

用户可以使用手机号和验证码登录系统。
验证码错误时，系统提示用户重新输入。

## 会话管理

登录成功后系统创建会话。
""".strip()
    question = {
        "title": "缺失非功能需求",
        "issue_type": "missing",
        "question": "缺少安全需求，需要定义什么指标？",
        "impact": "无法确认验证码安全策略",
        "source": "completeness",
        "current_text": "未定义验证码有效期、重试次数和锁定策略",
    }

    excerpt = _resolve_primary_source_excerpt(question, primary_content)

    assert excerpt == ""


@pytest.mark.skip(reason="Internal implementation details changed - function no longer exists")
def test_resolve_primary_source_excerpt_expands_direct_match_to_paragraph():
    """质量评估给出短原文时，前端仍能看到完整相关段落。"""
    from app.agents.requirement_analysis.workflow.nodes.clarify_node import (
        _resolve_primary_source_excerpt,
    )

    primary_content = """
# 性能需求

系统需要快速响应，用户提交订单后应立即看到处理结果。
失败时需要展示可理解的错误提示。
""".strip()
    question = {
        "title": "模糊表述",
        "issue_type": "ambiguous",
        "question": "'快速' 的具体定义是什么？",
        "impact": "无法度量响应时间",
        "source": "clarity",
        "current_text": "系统需要快速响应",
    }

    excerpt = _resolve_primary_source_excerpt(question, primary_content)

    assert "系统需要快速响应，用户提交订单后应立即看到处理结果。" in excerpt
    assert "失败时需要展示可理解的错误提示。" in excerpt


@pytest.mark.skip(reason="Internal implementation details changed - function no longer exists")
def test_nfr_clarification_requires_explicit_primary_evidence():
    """NFR 缺口没有主需求证据时，不进入澄清问题。"""
    from app.agents.requirement_analysis.core.schemas import (
        QualityAssessmentOutput,
        QualityIssueSummary,
        QualityDecision,
        CompletenessAssessment,
        ClarityAssessment,
        TestabilityAssessment,
        ConsistencyAssessment,
        NFRGap,
    )
    from app.agents.requirement_analysis.workflow.nodes.clarify_node import (
        _extract_questions_from_quality,
    )

    quality = QualityAssessmentOutput(
        summary=QualityIssueSummary(
            completeness_issues=2,
            clarity_issues=0,
            testability_issues=0,
            consistency_issues=0,
            total_issues=2,
            by_severity={"blocker": 0, "major": 2, "minor": 0},
            has_blocker=False,
            can_proceed=True,
        ),
        decision=QualityDecision(result="conditional", rationale="需要补充", blocking_issues=[], recommended_actions=[]),
        completeness=CompletenessAssessment(
            nfr_gaps=[
                NFRGap(
                    category="compatibility",
                    description="未定义浏览器兼容范围",
                    impact="无法设计兼容性测试",
                    suggested_requirement="",
                ),
                NFRGap(
                    category="security",
                    description="未定义会话过期策略",
                    impact="无法设计登录态失效测试",
                    suggested_requirement="Session 过期策略需要明确。",
                    evidence_text="建立产品本地 Session",
                    evidence_reason="本地会话需要可测试的过期和失效规则。",
                ),
            ],
        ),
        clarity=ClarityAssessment(),
        testability=TestabilityAssessment(),
        consistency=ConsistencyAssessment(),
        assessment_summary="",
    )

    questions = _extract_questions_from_quality(quality)

    assert [question["category"] for question in questions] == ["security"]
    assert "缺少compatibility" not in questions[0]["question"]
    assert questions[0]["current_text"] == "建立产品本地 Session"


@pytest.mark.skip(reason="Internal implementation details changed - function no longer exists")
def test_clarification_item_without_search_result_does_not_guess_options():
    """无辅助文档命中时，不生成通用猜测候选答案。"""
    from app.agents.requirement_analysis.workflow.nodes.clarify_node import (
        _create_clarification_item,
    )

    item = _create_clarification_item(
        {
            "id": "FG-1",
            "title": "缺失功能",
            "issue_type": "missing",
            "question": "缺少performance需求，需要定义什么指标？",
            "impact": "无法评估系统是否能满足业务连续性要求",
            "severity": "major",
            "source": "completeness",
            "current_text": "performance需求未定义",
            "category": "performance",
        },
        {
            "found": False,
            "answer": "",
            "source": "",
            "confidence": "none",
            "search_steps": [],
        },
    )

    assert item.resolution_status == "needs_manual"
    assert item.recommended_options == []


@pytest.mark.anyio
async def test_requirement_analysis_always_runs_clarification(monkeypatch):
    """质量评估完成后始终进入澄清阶段"""

    from app.agents.requirement_analysis.core.schemas import (
        RequirementUnderstandingOutput,
        ClarificationOutput,
        ClarificationSummary,
    )

    async def mock_understanding_agent(model, primary_markdown_content, **kwargs):
        return RequirementUnderstandingOutput(
            modules=[],
            dependencies=[],
            risks=[],
            assumptions=[],
            understanding_summary="高质量需求",
        ), {
            "business_insight": {"domain": "测试领域", "summary": "高质量需求"},
            "domain_model": {"summary": "领域模型"},
            "risk_profile": {"summary": "风险分析"},
            "explanation_markdown": "",
        }

    monkeypatch.setattr(
        "app.agents.requirement_analysis.agents.understanding.run_understanding_agent",
        mock_understanding_agent,
    )

    async def mock_quality_agent(model, primary_markdown_content, understanding_result):
        from app.agents.requirement_analysis.core.schemas import QualityAssessmentSimple, QualityIssueFlat
        from app.agents.requirement_analysis.agents.quality import convert_to_full_assessment

        simple = QualityAssessmentSimple(
            issues=[
                QualityIssueFlat(
                    issue_id="COMP-001",
                    dimension="completeness",
                    category="missing_detail",
                    severity="minor",
                    title="缺少字段长度",
                    description="名称字段未定义长度",
                    location="用户模块",
                    current_text="用户名称字段",
                    issue_reason="无法验证边界值",
                    suggested_fix="名称字段：1-50个字符",
                    impact="无法设计边界测试",
                    extra={}
                ),
            ],
            assessment_summary="识别出1个minor问题，质量优秀"
        )
        return convert_to_full_assessment(simple)

    monkeypatch.setattr(
        "app.agents.requirement_analysis.agents.quality.run_quality_assessment_agent",
        mock_quality_agent
    )

    monkeypatch.setattr(
        "app.agents.model_selection.resolve_model_selection",
        lambda capability_id: object()
    )
    monkeypatch.setattr(
        "app.agents.model_selection.build_agent_model",
        lambda model_selection: object()
    )

    clarification_called = {"value": False}

    async def mock_clarification_agent(model, understanding_result, quality_assessment_result, auxiliary_documents):
        clarification_called["value"] = True
        from datetime import datetime
        return ClarificationOutput(
            items=[],
            summary=ClarificationSummary(
                total=0,
                by_priority={"P0": 0, "P1": 0, "P2": 0, "P3": 0},
                by_category={},
                by_resolution={
                    "auto_resolved": 0,
                    "has_options": 0,
                    "needs_input": 0,
                    "needs_research": 0
                },
                test_surfaces_coverage={},
                total_test_cases=0,
                blocking_count=0,
                high_risk_count=0,
                recommended_actions=[]
            ),
            overall_assessment="澄清完成，无待补充项。",
            test_strategy_recommendations=[],
            generated_at=datetime.now().isoformat(),
            model_version="test-driven"
        )

    monkeypatch.setattr(
        "app.agents.requirement_analysis.agents.clarification.run_clarification_agent",
        mock_clarification_agent
    )

    input_data = RequirementAnalysisInputV2(
        project_id="test-project",
        document_id="test-doc",
        document_name="完善的需求",
        primary_mapping_id="primary",
        primary_filename="需求.md",
        primary_markdown_content="# 完善的需求\n\n所有细节都很清晰。",
        auxiliary_documents=[],
        config={}
    )

    from app.agents.requirement_analysis.workflow.workflow import run_requirement_analysis
    result = await run_requirement_analysis(input_data)

    assert clarification_called["value"] is True
    assert result.status == "completed"
    assert result.quality_assessment.decision.result == "approved"
    assert result.clarification is not None
    assert result.clarification.items == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
