"""
澄清节点（集成 Agentic Search）

汇总质量问题，使用 Agentic Search 在辅助文档中查找答案
"""

import re
from typing import List, Dict
from app.agents.requirement_analysis.state import RequirementAnalysisState
from app.agents.requirement_analysis.schemas import (
    ClarificationOutput,
    ClarificationItem,
    ClarificationOption,
    EvidenceReference,
    ClarificationSummary,
)


async def clarify_node(state: RequirementAnalysisState) -> RequirementAnalysisState:
    """
    澄清节点（带 Agentic Search）

    Args:
        state: 工作流状态

    Returns:
        更新后的状态（添加 clarification 结果）
    """
    # 获取 LLM 模型
    from app.agents.model_selection import build_agent_model, resolve_model_selection

    model_selection = resolve_model_selection("requirement_analysis")
    model = build_agent_model(model_selection)

    # 1. 从质量评估中提取问题
    questions = _extract_questions_from_quality(state["quality"])

    # 2. 为每个问题补充可核对的主需求原文段落，并执行 Agentic Search
    clarification_items = []

    for q in questions:
        q["current_text"] = _resolve_primary_source_excerpt(q, state["primary_content"])
        if not _is_useful_clarification_question(q):
            continue

        # 🔥 使用 Agentic Search 查找答案
        search_result = await _search_for_answer(
            model=model,
            question=q["question"],
            auxiliary_documents=state["auxiliary_docs"]
        )

        # 根据搜索结果生成 ClarificationItem
        item = _create_clarification_item(q, search_result)
        clarification_items.append(item)

    # 3. 生成汇总
    summary = _calculate_summary(clarification_items)

    # 4. 构建输出
    clarification_output = ClarificationOutput(
        items=clarification_items,
        summary=summary,
        clarification_summary_text=_generate_summary_text(summary)
    )

    # 更新状态
    state["clarification"] = clarification_output

    return state


async def _search_for_answer(model, question: str, auxiliary_documents: list[dict]) -> Dict:
    """Lazy wrapper so pure clarification helpers do not import LangChain search deps."""
    from app.agents.requirement_analysis.services.auxiliary_search_service import search_for_answer

    return await search_for_answer(
        model=model,
        question=question,
        auxiliary_documents=auxiliary_documents,
    )


def _extract_questions_from_quality(quality_result) -> List[Dict]:
    """从质量评估结果中提取问题"""
    questions = []

    # 从完整性检查提取
    for gap in quality_result.completeness.functional_gaps:
        questions.append({
            "id": f"FG-{len(questions)+1}",
            "title": "缺失功能",
            "issue_type": "missing",
            "question": f"缺少功能：{gap}，请补充相关需求",
            "impact": "影响功能设计",
            "severity": "major",
            "source": "completeness",
            "current_text": str(gap),
        })

    for nfr_gap in quality_result.completeness.nfr_gaps:
        evidence_text = str(getattr(nfr_gap, "evidence_text", "") or "").strip()
        if not evidence_text:
            continue
        category_label = _nfr_category_label(nfr_gap.category)
        questions.append({
            "id": f"NFR-{len(questions)+1}",
            "title": "缺失非功能需求",
            "issue_type": "missing",
            "category": nfr_gap.category,
            "question": f"请确认“{category_label}”指标：{nfr_gap.description}",
            "impact": nfr_gap.impact,
            "severity": nfr_gap.severity,
            "source": "completeness",
            "current_text": evidence_text,
            "suggested_fix": nfr_gap.suggested_requirement,
            "evidence_reason": getattr(nfr_gap, "evidence_reason", ""),
        })

    for detail in quality_result.completeness.missing_details:
        questions.append({
            "id": f"MD-{len(questions)+1}",
            "title": "待确认细节",
            "issue_type": "confirmation",
            "question": f"以下细节需要确认：{detail}",
            "impact": "细节未确认会影响后续设计、开发和验收口径",
            "severity": "major",
            "source": "completeness",
            "current_text": str(detail),
        })

    # 从清晰度检查提取
    for fuzzy in quality_result.clarity.fuzzy_terms:
        questions.append({
            "id": f"FZ-{len(questions)+1}",
            "title": "模糊表述",
            "issue_type": "ambiguous",
            "question": f"'{fuzzy.term}' 的具体定义是什么？",
            "impact": fuzzy.issue,
            "severity": "major",
            "source": "clarity",
            "current_text": fuzzy.current_text,
            "suggested_fix": fuzzy.suggested_fix
        })

    for ambiguous in quality_result.clarity.ambiguous_statements:
        questions.append({
            "id": f"AS-{len(questions)+1}",
            "title": "歧义表述",
            "issue_type": "ambiguous",
            "question": f"请确认这句话的准确含义：{ambiguous.statement}",
            "impact": "存在多种理解会导致设计、开发或验收口径不一致",
            "severity": "major",
            "source": "clarity",
            "current_text": ambiguous.statement,
            "suggested_fix": ambiguous.suggested_clarification,
        })

    for criteria_gap in quality_result.testability.acceptance_criteria_gaps:
        capability = criteria_gap.capability or criteria_gap.module_key
        questions.append({
            "id": f"AC-{len(questions)+1}",
            "title": "验收标准待确认",
            "issue_type": "confirmation",
            "module_key": criteria_gap.module_key,
            "module_name": capability or "验收标准",
            "criteria_issue": criteria_gap.issue,
            "question": f"请确认“{capability}”的验收标准。",
            "impact": "验收标准不明确会影响测试设计、验收结论和交付范围判断",
            "severity": "major",
            "source": "testability",
            "current_text": criteria_gap.current_text,
            "suggested_fix": criteria_gap.suggested_criteria,
        })

    for test_gap in quality_result.testability.test_coverage_gaps:
        questions.append({
            "id": f"TC-{len(questions)+1}",
            "title": "测试覆盖待确认",
            "issue_type": "confirmation",
            "module_key": test_gap.module_key,
            "module_name": test_gap.module_key or "测试覆盖",
            "gap_type": test_gap.gap_type,
            "question": f"请确认测试覆盖缺口：{test_gap.description}",
            "impact": test_gap.impact,
            "severity": "major",
            "source": "testability",
            "current_text": test_gap.description,
        })

    # 从一致性检查提取
    for conflict in quality_result.consistency.conflicts:
        questions.append({
            "id": f"CF-{len(questions)+1}",
            "title": "需求冲突",
            "issue_type": "conflict",
            "question": f"发现冲突：{conflict.description}，以哪个为准？",
            "impact": conflict.impact,
            "severity": conflict.severity,
            "source": "consistency",
            "current_text": "\n\n".join(
                text for text in [conflict.evidence_1, conflict.evidence_2] if text
            ),
        })

    for terminology in quality_result.consistency.terminology_issues:
        questions.append({
            "id": f"TM-{len(questions)+1}",
            "title": "术语不一致",
            "issue_type": "ambiguous",
            "question": f"请确认“{terminology.concept}”统一使用哪个术语？",
            "impact": "术语不一致会影响需求理解、字段命名、页面文案和测试用例表达",
            "severity": "minor",
            "source": "consistency",
            "current_text": "、".join(terminology.variations),
            "suggested_fix": terminology.suggested_standard_term,
        })

    return questions


def _is_useful_clarification_question(question: Dict) -> bool:
    """澄清项准入规则：必须可追溯、可回答、影响测试或交付决策。"""
    question_text = str(question.get("question") or "").strip()
    impact = str(question.get("impact") or "").strip()
    current_text = str(question.get("current_text") or "").strip()

    if not question_text or not impact:
        return False

    if not _has_delivery_or_test_impact(question):
        return False

    if question.get("issue_type") == "conflict":
        return bool(current_text)

    return bool(current_text)


def _has_delivery_or_test_impact(question: Dict) -> bool:
    text = " ".join(
        str(question.get(key) or "")
        for key in ("question", "impact", "suggested_fix", "evidence_reason", "source", "issue_type")
    )
    valuable_terms = (
        "设计",
        "开发",
        "测试",
        "验收",
        "接口",
        "字段",
        "状态",
        "性能",
        "响应",
        "时间",
        "时长",
        "权限",
        "认证",
        "登录",
        "会话",
        "数据",
        "规则",
        "异常",
        "边界",
        "用例",
        "契约",
        "交付",
        "上线",
        "风险",
        "断言",
        "错误",
        "失败",
        "成功",
        "回滚",
        "补偿",
        "并发",
        "重复",
        "幂等",
        "审批",
        "导入",
        "导出",
        "任务",
        "消息",
        "日志",
        "审计",
    )
    return any(term in text for term in valuable_terms)


def _nfr_category_label(category: str) -> str:
    labels = {
        "performance": "性能",
        "security": "安全",
        "availability": "可用性",
        "scalability": "可扩展性",
        "compatibility": "兼容性",
        "compliance": "合规",
        "usability": "易用性",
        "maintainability": "可维护性",
    }
    return labels.get(category, category)


def _resolve_primary_source_excerpt(question: Dict, primary_content: str) -> str:
    """定位待澄清项在主需求中的相关段落。

    current_text 面向前端会作为 source_excerpt 展示，因此这里必须返回真实来自
    主需求的段落。质量评估对“缺失类”问题常返回的是缺口描述，不一定存在于原文。
    """
    if not primary_content.strip():
        return ""

    paragraphs = _split_markdown_paragraphs(primary_content)
    if not paragraphs:
        return ""

    direct_candidates = [
        question.get("current_text", ""),
        question.get("module_name", ""),
        question.get("module_key", ""),
    ]
    for candidate in direct_candidates:
        excerpt = _paragraph_containing_text(paragraphs, candidate)
        if excerpt:
            return excerpt

    return ""


def _split_markdown_paragraphs(markdown_content: str) -> list[str]:
    """按 Markdown 标题和空行切分，同时把标题带入后续段落上下文。"""
    blocks: list[str] = []
    heading_stack: list[tuple[int, str]] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        nonlocal buffer
        text = "\n".join(line.rstrip() for line in buffer).strip()
        buffer = []
        if not text:
            return
        heading_text = "\n".join(title for _, title in heading_stack)
        blocks.append(f"{heading_text}\n\n{text}".strip() if heading_text else text)

    for raw_line in markdown_content.splitlines():
        line = raw_line.rstrip()
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match:
            flush_buffer()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = [(item_level, item_title) for item_level, item_title in heading_stack if item_level < level]
            heading_stack.append((level, title))
            continue
        if not line.strip():
            flush_buffer()
            continue
        buffer.append(line)

    flush_buffer()
    return blocks


def _paragraph_containing_text(paragraphs: list[str], text: str) -> str:
    candidate = str(text or "").strip()
    if not candidate:
        return ""
    normalized_candidate = _normalize_inline_text(candidate)
    if not normalized_candidate:
        return ""
    for paragraph in paragraphs:
        if normalized_candidate in _normalize_inline_text(paragraph):
            return paragraph
    return ""


def _normalize_inline_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _create_clarification_item(question: Dict, search_result: Dict) -> ClarificationItem:
    """根据搜索结果创建 ClarificationItem"""
    title = question.get("title") or "待确认项"
    module_key = question.get("module_key") or question.get("source") or "general"
    module_name = question.get("module_name") or title
    quality_options = _build_quality_recommended_options(question)
    decision_fields = _build_test_decision_fields(question, module_name)

    # 根据搜索结果决定状态
    if search_result["found"] and search_result["confidence"] == "high":
        # 高置信度答案 → auto_resolved
        return ClarificationItem(
            item_id=question["id"],
            title=title,
            issue_type=question.get("issue_type", "confirmation"),
            source=question["source"],
            module_key=module_key,
            module_name=module_name,
            question=decision_fields["human_question"],
            impact=decision_fields["test_impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=search_result["answer"],
            **decision_fields,
            evidence=[
                EvidenceReference(
                    mapping_id="",
                    filename=search_result["source"],
                    excerpt=search_result["answer"][:200],
                    confidence="high"
                )
            ] if search_result["source"] else [],
            resolution_status="auto_resolved",
            recommended_options=[]
        )

    elif search_result["found"]:
        # 中等置信度 → has_suggestions
        recommended_options = [
            ClarificationOption(
                option_id="opt1",
                label=f"基于 {search_result['source']}",
                answer_markdown=search_result["answer"],
                confidence=search_result["confidence"],
                source=search_result["source"]
            )
        ] if search_result["source"] else []
        recommended_options = _merge_recommended_options(recommended_options, quality_options)
        return ClarificationItem(
            item_id=question["id"],
            title=title,
            issue_type=question.get("issue_type", "confirmation"),
            source=question["source"],
            module_key=module_key,
            module_name=module_name,
            question=decision_fields["human_question"],
            impact=decision_fields["test_impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=question.get("suggested_fix", ""),
            recommended_options=recommended_options,
            decision_options=_merge_decision_options(
                decision_fields["decision_options"],
                recommended_options,
            ),
            **{key: value for key, value in decision_fields.items() if key != "decision_options"},
            evidence=[],
            resolution_status="has_suggestions"
        )

    else:
        # 未找到 → needs_manual
        return ClarificationItem(
            item_id=question["id"],
            title=title,
            issue_type=question.get("issue_type", "confirmation"),
            source=question["source"],
            module_key=module_key,
            module_name=module_name,
            question=decision_fields["human_question"],
            impact=decision_fields["test_impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=question.get("suggested_fix", ""),
            recommended_options=quality_options,
            **decision_fields,
            evidence=[],
            resolution_status="has_suggestions" if quality_options else "needs_manual"
        )


def _build_test_decision_fields(question: Dict, module_name: str) -> dict:
    """把质量事实转换为通用测试裁决字段。"""
    raw_question = str(question.get("question") or "").strip()
    description = _decision_description(question)
    source_excerpt = str(question.get("current_text") or "").strip()
    impact = str(question.get("impact") or "").strip()
    surfaces = _infer_affected_surfaces(question)
    bucket = _infer_clarification_bucket(question, surfaces)
    decision_point = _build_decision_point(question, description)
    human_question = _build_human_question(question, decision_point)
    test_impact = _build_test_impact(impact, surfaces)
    current_gap = _build_current_gap(question, description)
    risk_scenario = _build_risk_scenario(module_name, decision_point, surfaces)
    decision_options = _build_decision_options(surfaces)
    recommended_decision = _build_recommended_decision(surfaces)
    draft_tests = _build_draft_acceptance_tests(decision_point, surfaces)

    return {
        "clarification_bucket": bucket,
        "decision_point": decision_point,
        "source_excerpt": source_excerpt,
        "current_gap": current_gap,
        "test_impact": test_impact,
        "risk_scenario": risk_scenario,
        "affected_surfaces": surfaces,
        "decision_options": decision_options,
        "recommended_decision": recommended_decision,
        "human_question": human_question or raw_question,
        "draft_acceptance_tests": draft_tests,
    }


def _decision_description(question: Dict) -> str:
    for key in ("description", "suggested_fix", "question", "current_text"):
        value = str(question.get(key) or "").strip()
        if value:
            return value
    return "该需求的可测试规则"


def _build_decision_point(question: Dict, description: str) -> str:
    capability = str(question.get("module_name") or question.get("module_key") or "").strip()
    text = description.strip("。？? ")
    prefixes = (
        "请确认",
        "以下细节需要确认：",
        "请确认测试覆盖缺口：",
        "请确认这句话的准确含义：",
        "发现冲突：",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip("：:，, ")
    if "，以哪个为准" in text:
        text = text.split("，以哪个为准", 1)[0]
    if capability and capability not in text:
        return f"{capability}的{text}"
    return text or capability or "待确认规则"


def _build_human_question(question: Dict, decision_point: str) -> str:
    if question.get("issue_type") == "conflict":
        return f"请确认“{decision_point}”应以哪条规则为准？"
    if question.get("source") == "testability":
        return f"请确认“{decision_point}”的预期结果、失败处理和可观察断言是什么？"
    return f"请确认“{decision_point}”的明确业务规则是什么？"


def _build_current_gap(question: Dict, description: str) -> str:
    if question.get("issue_type") == "conflict":
        return f"当前需求存在冲突或多种解释：{description}"
    if question.get("source") == "clarity":
        return f"当前表述不够明确，存在多种测试解释：{description}"
    return f"当前需求未明确说明：{description}"


def _build_test_impact(impact: str, surfaces: list[str]) -> str:
    impact_text = impact or "不确认会影响测试设计和验收结论。"
    if any(term in impact_text for term in ("测试", "验收", "断言", "用例")):
        return impact_text
    surface_text = "、".join(_surface_label(surface) for surface in surfaces) or "相关"
    return f"{impact_text}；同时会导致{surface_text}测试无法形成明确断言。"


def _infer_clarification_bucket(question: Dict, surfaces: list[str]) -> str:
    severity = str(question.get("severity") or "")
    source = str(question.get("source") or "")
    blocking_surfaces = {"api", "state_flow", "data_consistency", "permission", "security", "migration"}
    if severity == "blocker" or question.get("issue_type") == "conflict":
        return "blocker"
    if source == "testability" and blocking_surfaces.intersection(surfaces):
        return "blocker"
    if source == "testability":
        return "risk"
    if severity == "minor":
        return "acceptance"
    return "risk"


def _infer_affected_surfaces(question: Dict) -> list[str]:
    text = " ".join(
        str(question.get(key) or "")
        for key in (
            "question",
            "impact",
            "suggested_fix",
            "evidence_reason",
            "current_text",
            "module_key",
            "module_name",
            "category",
            "criteria_issue",
            "gap_type",
            "issue_type",
        )
    ).lower()
    gap_type = str(question.get("gap_type") or "").lower()
    surfaces: list[str] = []

    def add(surface: str) -> None:
        if surface not in surfaces:
            surfaces.append(surface)

    if any(term in text for term in ("接口", "api", "响应", "错误码", "参数", "字段", "提交", "回调")):
        add("api")
    if any(term in text for term in ("状态", "流转", "审批", "撤回", "驳回", "取消", "终态", "初始")):
        add("state_flow")
    if any(term in text for term in ("数据", "唯一", "重复", "并发", "幂等", "回滚", "补偿", "库存", "余额", "额度", "映射", "关联", "导入")) or gap_type in {"concurrency", "data_dependency", "boundary_value"}:
        add("data_consistency")
    if any(term in text for term in ("权限", "角色", "越权", "租户", "可见", "授权", "未登录")) or gap_type == "permission":
        add("permission")
    if any(term in text for term in ("安全", "认证", "敏感", "脱敏", "加密", "隐私")):
        add("security")
    if any(term in text for term in ("日志", "审计", "trace", "告警", "留痕")):
        add("audit_log")
    if any(term in text for term in ("迁移", "历史", "存量", "回填")):
        add("migration")
    if any(term in text for term in ("提示", "页面", "展示", "用户可见", "前端")) or gap_type == "error_message":
        add("ui_feedback")
    if any(term in text for term in ("异步", "任务", "消息", "队列", "重试", "超时")):
        add("async_task")
    if any(term in text for term in ("第三方", "外部", "依赖", "网络")):
        add("external_dependency")
    if any(term in text for term in ("性能", "并发", "吞吐", "容量", "可用", "兼容", "合规", "响应时间")):
        add("non_functional")
    if not surfaces:
        add("regression")
    elif "regression" not in surfaces:
        add("regression")
    return surfaces


def _build_risk_scenario(module_name: str, decision_point: str, surfaces: list[str]) -> str:
    trigger = _scenario_trigger(surfaces)
    expected = _scenario_expected(surfaces)
    return (
        f"Given {module_name}处于可执行前置条件\n"
        f"When {trigger}：{decision_point}\n"
        f"Then 系统应按确认后的规则{expected}"
    )


def _scenario_trigger(surfaces: list[str]) -> str:
    if "state_flow" in surfaces:
        return "发生状态转换、重复操作或非法流转"
    if "data_consistency" in surfaces:
        return "发生重复提交、并发操作或关联数据变化"
    if "permission" in surfaces or "security" in surfaces:
        return "发生无权限、越权或敏感操作"
    if "async_task" in surfaces:
        return "异步任务执行、失败、重试或超时"
    if "external_dependency" in surfaces:
        return "外部依赖成功、失败或超时"
    return "用户或系统触发该业务场景"


def _scenario_expected(surfaces: list[str]) -> str:
    expected = ["返回可观察结果"]
    if "api" in surfaces:
        expected.append("提供明确响应或错误码")
    if "state_flow" in surfaces:
        expected.append("更新到明确状态")
    if "data_consistency" in surfaces:
        expected.append("保持关联数据一致")
    if "permission" in surfaces or "security" in surfaces:
        expected.append("执行权限或安全控制")
    if "audit_log" in surfaces:
        expected.append("记录可追溯日志")
    return "，".join(expected)


def _build_decision_options(surfaces: list[str]) -> list[ClarificationOption]:
    if "data_consistency" in surfaces:
        options = [
            ("按幂等处理", "重复或并发请求返回已有结果，不产生重复业务结果。"),
            ("拒绝重复或非法操作", "重复或非法请求返回明确失败结果，业务数据不变。"),
            ("允许继续处理", "系统允许生成新的业务结果，并由后续流程处理重复数据。"),
        ]
    elif "state_flow" in surfaces:
        options = [
            ("拒绝非法流转", "对象处于不允许状态时拒绝操作，并保持原状态。"),
            ("忽略重复动作", "重复动作返回当前状态，不创建新的流转记录。"),
            ("开启新流程", "重复或后续动作生成新的流程轮次，并保留历史记录。"),
        ]
    elif "permission" in surfaces or "security" in surfaces:
        options = [
            ("隐藏入口", "无权限用户不可见入口或敏感数据。"),
            ("拒绝操作", "无权限或安全校验失败时返回明确失败结果。"),
            ("允许只读", "无操作权限时仅允许查看授权范围内的数据。"),
        ]
    elif "async_task" in surfaces or "external_dependency" in surfaces:
        options = [
            ("自动重试", "失败或超时时按约定次数重试，并记录任务状态。"),
            ("立即失败", "失败或超时时返回明确失败结果，不自动重试。"),
            ("进入人工处理", "失败或超时时进入待处理状态，由人工补偿。"),
        ]
    else:
        options = [
            ("明确成功结果", "满足条件时返回可观察的成功结果。"),
            ("明确失败结果", "不满足条件时返回可观察的失败结果。"),
            ("补充边界规则", "为边界输入或异常路径补充独立处理规则。"),
        ]

    return [
        ClarificationOption(
            option_id=f"decision-{index}",
            label=label,
            answer_markdown=answer,
            rationale="基于通用测试裁决维度生成的候选裁决，需人工确认。",
            confidence="low",
            source="测试视角推理",
        )
        for index, (label, answer) in enumerate(options, 1)
    ]


def _merge_decision_options(
    decision_options: list[ClarificationOption],
    recommended_options: list[ClarificationOption],
) -> list[ClarificationOption]:
    merged: list[ClarificationOption] = []
    for option in [*decision_options, *recommended_options]:
        if _contains_same_answer(merged, option.answer_markdown):
            continue
        merged.append(option.model_copy(update={"option_id": f"decision-{len(merged) + 1}"}))
        if len(merged) >= 3:
            break
    return merged


def _build_recommended_decision(surfaces: list[str]) -> str:
    if "data_consistency" in surfaces:
        return "推荐优先确认幂等、拒绝或回滚规则。该判断来自数据一致性测试推理，需业务确认。"
    if "state_flow" in surfaces:
        return "推荐优先确认非法流转和重复动作处理规则。该判断来自状态流转测试推理，需业务确认。"
    if "permission" in surfaces or "security" in surfaces:
        return "推荐优先确认拒绝策略、可见范围和审计要求。该判断来自权限安全测试推理，需业务确认。"
    if "async_task" in surfaces or "external_dependency" in surfaces:
        return "推荐优先确认失败、重试、超时和人工补偿规则。该判断来自异常路径测试推理，需业务确认。"
    return ""


def _build_draft_acceptance_tests(decision_point: str, surfaces: list[str]) -> list[str]:
    tests = [f"{decision_point}的正常路径应返回明确成功结果"]
    if "api" in surfaces:
        tests.append(f"{decision_point}的失败路径应返回明确错误码或错误提示")
    if "state_flow" in surfaces:
        tests.append(f"{decision_point}触发后状态应按确认规则流转")
    if "data_consistency" in surfaces:
        tests.append(f"{decision_point}在重复或并发场景下不应产生未确认的数据副作用")
    if "permission" in surfaces or "security" in surfaces:
        tests.append(f"{decision_point}在无权限或安全校验失败时应被拒绝")
    if "async_task" in surfaces or "external_dependency" in surfaces:
        tests.append(f"{decision_point}在失败、重试或超时时应有明确任务状态")
    if "audit_log" in surfaces:
        tests.append(f"{decision_point}成功或失败后应记录可追溯日志")
    if len(tests) == 1:
        tests.append(f"{decision_point}的异常路径应有明确可观察结果")
    return tests[:5]


def _surface_label(surface: str) -> str:
    labels = {
        "api": "接口契约",
        "state_flow": "状态流转",
        "data_consistency": "数据一致性",
        "permission": "权限",
        "security": "安全",
        "audit_log": "审计日志",
        "regression": "回归",
        "migration": "迁移",
        "ui_feedback": "用户反馈",
        "async_task": "异步任务",
        "external_dependency": "外部依赖",
        "non_functional": "非功能",
    }
    return labels.get(surface, surface)


def _build_quality_recommended_options(question: Dict) -> list[ClarificationOption]:
    """只把质量评估明确给出的修正文案转成候选项，不做业务推断。"""
    suggested_fix = str(question.get("suggested_fix") or "").strip()

    options: list[ClarificationOption] = []
    if suggested_fix:
        options.append(
            ClarificationOption(
                option_id="opt1",
                label="建议修正",
                answer_markdown=suggested_fix,
                rationale="来自质量评估阶段的建议修正，可直接作为候选答案确认。",
                confidence="medium",
                source="质量评估建议",
            )
        )
    return options


def _merge_recommended_options(
    primary_options: list[ClarificationOption],
    fallback_options: list[ClarificationOption],
) -> list[ClarificationOption]:
    merged: list[ClarificationOption] = []
    for option in [*primary_options, *fallback_options]:
        if _contains_same_answer(merged, option.answer_markdown):
            continue
        merged.append(
            option.model_copy(update={"option_id": f"opt{len(merged) + 1}"})
        )
        if len(merged) >= 2:
            break
    return merged


def _contains_same_answer(options: list[ClarificationOption], answer: str) -> bool:
    normalized_answer = _normalize_inline_text(answer)
    return any(_normalize_inline_text(option.answer_markdown) == normalized_answer for option in options)


def _calculate_summary(items: List[ClarificationItem]) -> ClarificationSummary:
    """计算汇总统计"""
    total = len(items)
    auto_resolved = len([i for i in items if i.resolution_status == "auto_resolved"])
    has_suggestions = len([i for i in items if i.resolution_status == "has_suggestions"])
    needs_manual = len([i for i in items if i.resolution_status == "needs_manual"])

    by_severity = {"blocker": 0, "major": 0, "minor": 0}
    for item in items:
        by_severity[item.severity] += 1

    by_source = {
        "understanding": 0,
        "completeness": 0,
        "clarity": 0,
        "testability": 0,
        "consistency": 0
    }
    for item in items:
        if item.source in by_source:
            by_source[item.source] += 1

    return ClarificationSummary(
        total=total,
        auto_resolved=auto_resolved,
        has_suggestions=has_suggestions,
        needs_manual=needs_manual,
        by_severity=by_severity,
        by_source=by_source
    )


def _generate_summary_text(summary: ClarificationSummary) -> str:
    """生成汇总文本"""
    return (
        f"共发现 {summary.total} 个待澄清项：\n"
        f"- 自动解决：{summary.auto_resolved} 个\n"
        f"- 有建议选项：{summary.has_suggestions} 个\n"
        f"- 需人工确认：{summary.needs_manual} 个\n\n"
        f"按严重程度：blocker {summary.by_severity['blocker']} 个，"
        f"major {summary.by_severity['major']} 个，"
        f"minor {summary.by_severity['minor']} 个"
    )


__all__ = ["clarify_node"]
