"""
澄清节点（集成 Agentic Search）

汇总质量问题，使用 Agentic Search 在辅助文档中查找答案
"""

import re
from typing import List, Dict
from app.agents.requirement_analysis.state import RequirementAnalysisState
from app.agents.requirement_analysis.services.auxiliary_search_service import search_for_answer
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

        # 🔥 使用 Agentic Search 查找答案
        search_result = await search_for_answer(
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
        questions.append({
            "id": f"NFR-{len(questions)+1}",
            "title": "缺失非功能需求",
            "issue_type": "missing",
            "category": nfr_gap.category,
            "question": f"缺少{nfr_gap.category}需求，需要定义什么指标？",
            "impact": nfr_gap.impact,
            "severity": nfr_gap.severity,
            "source": "completeness",
            "current_text": nfr_gap.description,
            "suggested_fix": nfr_gap.suggested_requirement,
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

    keywords = _extract_excerpt_keywords(question)
    if not keywords:
        return ""

    scored: list[tuple[int, int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        normalized = paragraph.lower()
        score = 0
        for keyword in keywords:
            if keyword in normalized:
                score += max(1, min(len(keyword), 12))
        if score:
            scored.append((score, -index, paragraph))

    if not scored:
        return ""

    scored.sort(reverse=True)
    return scored[0][2]


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


def _extract_excerpt_keywords(question: Dict) -> list[str]:
    source_text = " ".join(
        str(question.get(key) or "")
        for key in (
            "title",
            "issue_type",
            "question",
            "impact",
            "current_text",
            "suggested_fix",
            "module_key",
            "module_name",
            "source",
        )
    ).lower()
    stopwords = {
        "缺少",
        "缺失",
        "功能",
        "需求",
        "需要",
        "请确认",
        "确认",
        "以下",
        "相关",
        "补充",
        "影响",
        "待确认",
        "模糊",
        "表述",
        "验收",
        "标准",
        "测试",
        "覆盖",
        "问题",
        "什么",
        "如何",
        "是否",
        "以及",
        "或者",
        "如果",
        "没有",
        "未定义",
        "不明确",
        "会影响",
        "completeness",
        "clarity",
        "testability",
        "consistency",
        "missing",
        "confirmation",
        "conflict",
        "ambiguous",
        "major",
        "minor",
        "blocker",
    }
    keywords: list[str] = []

    for token in re.findall(r"[a-z0-9_./-]{2,}", source_text):
        if token not in stopwords:
            keywords.append(token)

    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", source_text):
        if segment in stopwords:
            continue
        if len(segment) <= 8:
            keywords.append(segment)
        for index in range(0, max(len(segment) - 1, 0)):
            token = segment[index:index + 2]
            if token not in stopwords:
                keywords.append(token)

    seen: set[str] = set()
    unique_keywords: list[str] = []
    for keyword in keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        unique_keywords.append(keyword)
    return unique_keywords


def _normalize_inline_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _create_clarification_item(question: Dict, search_result: Dict) -> ClarificationItem:
    """根据搜索结果创建 ClarificationItem"""
    title = question.get("title") or "待确认项"
    module_key = question.get("module_key") or question.get("source") or "general"
    module_name = question.get("module_name") or title
    fallback_options = _build_fallback_recommended_options(question)

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
            question=question["question"],
            impact=question["impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=search_result["answer"],
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
        recommended_options = _merge_recommended_options(recommended_options, fallback_options)
        return ClarificationItem(
            item_id=question["id"],
            title=title,
            issue_type=question.get("issue_type", "confirmation"),
            source=question["source"],
            module_key=module_key,
            module_name=module_name,
            question=question["question"],
            impact=question["impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=question.get("suggested_fix", ""),
            recommended_options=recommended_options,
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
            question=question["question"],
            impact=question["impact"],
            severity=question["severity"],
            current_text=question.get("current_text", ""),
            suggested_fix=question.get("suggested_fix", ""),
            recommended_options=fallback_options,
            evidence=[],
            resolution_status="has_suggestions" if fallback_options else "needs_manual"
        )


def _build_fallback_recommended_options(question: Dict) -> list[ClarificationOption]:
    """无辅助文档命中时，基于上下文推断两个最可能答案。

    recommended_options 是给人工确认的候选答案，answer_markdown 必须能直接写入
    需求文档；不要生成“请业务确认”“暂不纳入本期”这类处理动作。
    """
    suggested_fix = str(question.get("suggested_fix") or "").strip()

    options: list[ClarificationOption] = []
    if suggested_fix:
        options.append(
            ClarificationOption(
                option_id="opt1",
                label="候选答案 A",
                answer_markdown=suggested_fix,
                rationale="来自质量评估阶段的建议修正，可直接作为候选答案确认。",
                confidence="medium",
                source="质量评估建议",
            )
        )

    for answer in _infer_likely_answers(question):
        if _contains_same_answer(options, answer):
            continue
        options.append(
            ClarificationOption(
                option_id=f"opt{len(options) + 1}",
                label=f"候选答案 {chr(64 + len(options) + 1)}",
                answer_markdown=answer,
                rationale="未从辅助文档命中明确答案时，基于问题类型和上下文生成的最可能答案。",
                confidence="low",
                source="需求分析推断",
            )
        )
        if len(options) >= 2:
            break

    return options[:2]


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


def _infer_likely_answers(question: Dict) -> list[str]:
    issue_type = str(question.get("issue_type") or "")
    text = " ".join(
        str(question.get(key) or "")
        for key in ("category", "question", "current_text", "impact", "module_key", "module_name", "title")
    ).lower()

    if issue_type == "conflict":
        conflict_answers = _infer_conflict_answers(question)
        if conflict_answers:
            return conflict_answers

    nfr_answers = _infer_non_functional_answers(text)
    if nfr_answers:
        return nfr_answers

    if "验收" in text or "acceptance" in text:
        capability = _extract_capability_name(question) or "该功能"
        return [
            f"验收标准：{capability}应覆盖正常流程、异常输入、权限限制和结果可见性；用户操作后系统必须给出明确成功或失败反馈。",
            f"验收标准：{capability}采用 Given-When-Then 描述，至少包含前置条件、操作步骤、预期结果、错误提示和边界条件。",
        ]

    if "权限" in text or "permission" in text:
        return [
            "权限规则：仅授权角色可访问和操作该功能，未授权用户不可见入口或操作时返回无权限提示，并记录审计日志。",
            "权限规则：管理员拥有完整操作权限，普通用户仅可查看和操作本人权限范围内的数据，越权访问必须被拒绝。",
        ]

    if "字段" in text or "格式" in text or "参数" in text:
        subject = _extract_capability_name(question) or "该字段"
        return [
            f"{subject}格式：必填，使用字符串格式，长度 1-128 个字符，仅允许字母、数字、下划线和短横线。",
            f"{subject}格式：可选；为空时系统使用默认值，非空时必须通过格式校验，校验失败返回明确错误提示。",
        ]

    subject = _extract_capability_name(question) or "该需求"
    return [
        f"{subject}纳入本期范围，按主流程实现，并补充输入、处理规则、输出结果和异常提示。",
        f"{subject}仅覆盖核心场景，边界条件、异常流程和扩展规则按后续需求单独补充。",
    ]


def _infer_non_functional_answers(text: str) -> list[str]:
    if "performance" in text or "性能" in text or "响应" in text or "并发" in text:
        return [
            "性能指标：核心页面和核心接口 P95 响应时间不超过 2 秒，P99 不超过 5 秒；支持 1,000 并发用户；接口错误率不超过 0.1%。",
            "性能指标：核心交易类操作 P95 响应时间不超过 3 秒，批量或报表任务 60 秒内完成；系统支持峰值 QPS 200，并可水平扩展。",
        ]
    if "security" in text or "安全" in text or "认证" in text or "授权" in text or "加密" in text:
        return [
            "安全指标：所有接口必须经过身份认证和权限校验，敏感数据传输和存储需加密，关键操作记录审计日志。",
            "安全指标：登录态超时自动失效，连续失败操作触发限制；普通用户不得访问越权数据，管理员操作必须可追溯。",
        ]
    if "availability" in text or "可用" in text or "sla" in text or "容错" in text:
        return [
            "可用性指标：系统月可用性不低于 99.9%，单点故障不影响核心功能，故障恢复时间 RTO 不超过 30 分钟。",
            "可用性指标：核心服务支持健康检查和自动重试，非核心依赖异常时应降级处理并提示用户稍后重试。",
        ]
    if "scalability" in text or "扩展" in text or "增长" in text or "数据量" in text:
        return [
            "可扩展性指标：系统支持用户量和数据量按 10 倍增长扩容，核心服务可通过增加实例水平扩展。",
            "可扩展性指标：数据存储和查询需支持分区、分页和索引优化，单表数据增长不得显著影响核心查询性能。",
        ]
    if "compatibility" in text or "兼容" in text or "浏览器" in text or "设备" in text:
        return [
            "兼容性指标：支持最新版 Chrome、Edge、Safari 浏览器，页面在 1440px 桌面端和 390px 移动端下布局正常。",
            "兼容性指标：核心功能需兼容主流桌面浏览器，移动端至少支持查看和基础操作，异常兼容场景需给出明确提示。",
        ]
    if "usability" in text or "易用" in text or "可用性" in text:
        return [
            "易用性指标：核心任务应在 3 步内完成，表单校验错误需定位到字段并给出可理解的修正提示。",
            "易用性指标：页面文案、按钮和状态提示保持一致，关键操作需提供确认或撤销机制，避免误操作。",
        ]
    return []


def _infer_conflict_answers(question: Dict) -> list[str]:
    current_text = str(question.get("current_text") or "").strip()
    parts = [part.strip() for part in re.split(r"\n{2,}|[；;]", current_text) if part.strip()]
    if len(parts) >= 2:
        return [
            f"以口径 A 为准：{parts[0]}",
            f"以口径 B 为准：{parts[1]}",
        ]
    return []


def _extract_capability_name(question: Dict) -> str:
    for key in ("module_name", "module_key"):
        value = str(question.get(key) or "").strip()
        if value and value not in {"general", "completeness", "clarity", "testability", "consistency"}:
            return value
    question_text = str(question.get("question") or "")
    quoted = re.search(r"[“\"'](.+?)[”\"']", question_text)
    if quoted:
        return quoted.group(1).strip()
    cleaned = re.sub(r"^(缺少功能|以下细节需要确认|请确认测试覆盖缺口|发现冲突)[：:]\s*", "", question_text).strip()
    return cleaned[:40].strip(" ，。？?：:")


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
