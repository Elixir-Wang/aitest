import json
import re
from pathlib import Path

from app.agents.requirement_analysis_codex.schemas import RequirementAnalysisOutput


def read_analysis_output(workdir: Path) -> RequirementAnalysisOutput:
    output_path = workdir / "output" / "analysis.json"
    if not output_path.exists():
        raise ValueError("需求分析智能体未生成 output/analysis.json。")
    raw_output = json.loads(output_path.read_text(encoding="utf-8"))
    report_path = workdir / "output" / "analysis.md"
    if report_path.exists():
        report = report_path.read_text(encoding="utf-8").strip()
        if report:
            raw_output["analysis_report_markdown"] = report
    clarification_path = workdir / "output" / "clarification.md"
    if clarification_path.exists():
        clarification_report = clarification_path.read_text(encoding="utf-8").strip()
        if clarification_report:
            raw_output["clarification_report_markdown"] = clarification_report
    quality_path = workdir / "output" / "quality.md"
    if quality_path.exists():
        quality_report = quality_path.read_text(encoding="utf-8").strip()
        if quality_report:
            raw_output["quality_assurance_report_markdown"] = quality_report
    normalized_output = normalize_analysis_output(raw_output)
    return RequirementAnalysisOutput.model_validate(normalized_output)


def normalize_analysis_output(value: dict) -> dict:
    output = dict(value)
    raw_status = output.get("status")
    output["status"] = normalize_analysis_status(output.get("status"), output.get("quality_gate"), output.get("clarification_questions"))
    output["quality_gate"] = normalize_quality_gate(output.get("quality_gate"), raw_status)
    output["applied_supplements"] = []
    output["maturity_assessment"] = normalize_maturity_assessment(output.get("maturity_assessment"))
    output["key_gaps"] = normalize_key_gaps(output.get("key_gaps"))
    output["assumptions"] = normalize_assumptions(output.get("assumptions"))
    output["modules"] = normalize_modules(output.get("modules"))
    clarification_report = str(output.get("clarification_report_markdown") or "").strip()
    parsed_questions: list[dict] = []
    parsed_conflicts: list[dict] = []
    if clarification_report:
        parsed_questions, parsed_conflicts = parse_clarification_markdown(clarification_report)
    if parsed_questions and not output.get("clarification_questions"):
        output["clarification_questions"] = parsed_questions
    if parsed_conflicts and not output.get("conflicts"):
        output["conflicts"] = parsed_conflicts
    output["clarification_questions"] = normalize_findings(output.get("clarification_questions"), default_issue_type="clarification")
    output["conflicts"] = normalize_findings(output.get("conflicts"), default_issue_type="conflict")
    output["coverage_audit"] = normalize_coverage_audit(output.get("coverage_audit"))
    output["next_actions"] = normalize_string_list(output.get("next_actions"))
    return output


def normalize_analysis_status(value, quality_gate, clarification_questions) -> str:
    if value in {"completed", "needs_clarification", "blocked"}:
        return value
    gate_result = quality_gate.get("result") if isinstance(quality_gate, dict) else None
    if gate_result == "blocked" or value in {"BLOCKED", "FAILED", "FAIL"}:
        return "blocked"
    if clarification_questions:
        return "needs_clarification"
    if value in {"CONDITIONAL_PASS", "WARNING", "WARN"}:
        return "needs_clarification"
    return "completed"


def normalize_quality_gate(value, raw_status) -> dict:
    gate = dict(value) if isinstance(value, dict) else {}
    result = gate.get("result")
    if result not in {"passed", "warning", "blocked"}:
        decision = str(gate.get("decision") or raw_status or "").lower()
        blocking_items = gate.get("blocking_items") or gate.get("blocking_issues") or []
        if "blocked" in decision or "阻塞" in decision:
            result = "blocked"
        elif "conditional" in decision or "有条件" in decision or blocking_items or gate.get("pass") is False:
            result = "warning"
        else:
            result = "passed"
    return {
        "result": result,
        "testability_score": bounded_int(gate.get("testability_score") or gate.get("score") or 0, 0, 100),
        "blocking_issues": normalize_string_list(gate.get("blocking_issues") or gate.get("blocking_items")),
        "warning_issues": normalize_string_list(gate.get("warning_issues") or gate.get("non_blocking_items")),
        "passed_checks": normalize_string_list(gate.get("passed_checks")),
    }


def normalize_maturity_assessment(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        return {"level": "RA2", "label": str(value), "reason": str(value), "evidence": []}
    level = value.get("level")
    if level not in {"RA0", "RA1", "RA2", "RA3", "RA4", "RA5"}:
        level = "RA2"
    label = value.get("label") or value.get("overall_level") or level
    evidence = value.get("evidence")
    if not evidence and isinstance(value.get("dimensions"), list):
        evidence = [f"{item.get('name', '维度')}：{item.get('notes', '')}" for item in value["dimensions"] if isinstance(item, dict)]
    return {"level": level, "label": str(label), "reason": str(value.get("reason") or label), "evidence": normalize_string_list(evidence)}


def normalize_key_gaps(value) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for item in items:
        if isinstance(item, dict):
            category = item.get("category")
            normalized.append(
                {
                    "category": category if category in _GAP_CATEGORIES else "other",
                    "description": str(item.get("description") or item.get("gap") or item),
                    "impact": str(item.get("impact") or "影响后续设计、开发或测试确认。"),
                    "severity": item.get("severity") if item.get("severity") in {"blocker", "major", "minor"} else "major",
                }
            )
        else:
            normalized.append({"category": "other", "description": str(item), "impact": "影响后续设计、开发或测试确认。", "severity": "major"})
    return normalized


def normalize_assumptions(value) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(
                {
                    "description": str(item.get("description") or item.get("assumption") or item),
                    "validation_needed": str(item.get("validation_needed") or "需要业务负责人确认。"),
                    "risk": str(item.get("risk") or "假设不成立会影响需求分析结论。"),
                }
            )
        else:
            normalized.append({"description": str(item), "validation_needed": "需要业务负责人确认。", "risk": "假设不成立会影响需求分析结论。"})
    return normalized


def normalize_modules(value) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            item = {"module_name": str(item), "summary": str(item)}
        module_name = str(item.get("module_name") or item.get("name") or f"模块 {index}")
        normalized.append(
            {
                "module_key": str(item.get("module_key") or slug(module_name) or f"module-{index:03d}"),
                "module_name": module_name,
                "summary": str(item.get("summary") or item.get("scope") or module_name),
                "business_objects": normalize_string_list(item.get("business_objects")),
                "capabilities": normalize_string_list(item.get("capabilities")),
                "rules": normalize_string_list(item.get("rules")),
                "fields": normalize_string_list(item.get("fields")),
                "state_flows": normalize_string_list(item.get("state_flows")),
                "dependencies": normalize_string_list(item.get("dependencies")),
                "risks": normalize_string_list(item.get("risks") or item.get("open_points")),
            }
        )
    return normalized


def parse_clarification_markdown(markdown: str) -> tuple[list[dict], list[dict]]:
    questions: list[dict] = []
    conflicts: list[dict] = []
    sections = re.split(r"(?m)^\s*##\s+", markdown or "")
    for raw_section in sections[1:]:
        lines = [line.strip() for line in raw_section.splitlines() if line.strip()]
        if not lines:
            continue
        heading = lines[0]
        heading_match = re.match(r"(?P<id>(?:CQ|CF)-\d+)\s*(?P<module>.*)", heading)
        if not heading_match:
            continue
        item_id = heading_match.group("id")
        default_module_name = heading_match.group("module").strip() or "通用"
        fields = _parse_clarification_markdown_fields(lines[1:])
        module_name = fields.get("模块") or default_module_name
        module_key = fields.get("模块Key") or slug(module_name) or "general"
        severity = normalize_severity(fields.get("严重级别"))
        source_excerpt = fields.get("来源") or fields.get("摘录") or ""
        question = fields.get("问题") or "需要人工确认。"
        impact = fields.get("影响") or "不确认会影响后续设计、开发、测试或验收判断。"
        options = _parse_clarification_markdown_options(fields)
        if item_id.startswith("CF-") or fields.get("类型") == "conflict":
            conflicts.append(
                {
                    "id": item_id,
                    "module_key": module_key,
                    "module_name": module_name,
                    "issue_type": "conflict",
                    "question": question,
                    "impact": impact,
                    "severity": severity,
                    "primary_excerpt": source_excerpt,
                    "recommended_options": options,
                }
            )
        else:
            dimension = fields.get("维度") if fields.get("维度") in _DIMENSIONS else "other"
            questions.append(
                {
                    "id": item_id,
                    "module_key": module_key,
                    "module_name": module_name,
                    "question": question,
                    "impact": impact,
                    "dimension": dimension,
                    "severity": severity,
                    "source_excerpt": source_excerpt,
                    "recommended_options": options,
                }
            )
    return questions, conflicts


def _parse_clarification_markdown_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        match = re.match(r"^[-*]\s*([^：:]+)[：:]\s*(.*)$", line)
        if not match:
            continue
        key = match.group(1).strip()
        value = match.group(2).strip()
        fields[key] = value
    return fields


def _parse_clarification_markdown_options(fields: dict[str, str]) -> list[dict]:
    options: list[dict] = []
    for index, key in enumerate(("选项A", "选项B"), start=1):
        raw = fields.get(key, "").strip()
        if not raw:
            continue
        label, _, answer = raw.partition("|")
        answer_markdown = answer.strip() or label.strip()
        options.append(
            {
                "id": f"OPT-{index:03d}",
                "label": label.strip() or f"选项 {index}",
                "answer_markdown": answer_markdown,
                "rationale": "",
                "confidence": "medium",
            }
        )
    return options


def normalize_findings(value, *, default_issue_type: str) -> list[dict]:
    items = value if isinstance(value, list) else ([value] if value else [])
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            item = {"question": str(item)}
        question = str(item.get("question") or item.get("resolution_needed") or item.get("description") or item.get("topic") or "需要人工确认。")
        module_name = str(item.get("module_name") or item.get("topic") or "通用")
        is_conflict = default_issue_type == "conflict"
        issue_type = item.get("issue_type") or default_issue_type
        normalized_item = {
            "id": str(item.get("id") or f"{'CF' if is_conflict else 'CQ'}-{index:03d}"),
            "module_key": str(item.get("module_key") or slug(module_name) or "general"),
            "module_name": module_name,
            "question": question,
            "impact": str(item.get("impact") or "不确认会影响后续设计、开发、测试或验收判断。"),
            "severity": normalize_severity(item.get("severity") or item.get("priority")),
            "evidence": normalize_evidence_list(item),
            "recommended_options": normalize_options(item.get("recommended_options")),
        }
        excerpt = str(item.get("primary_excerpt") or item.get("source_excerpt") or item.get("description") or "")
        if is_conflict:
            normalized_item["issue_type"] = issue_type if issue_type in _ISSUE_TYPES else default_issue_type
            normalized_item["primary_excerpt"] = excerpt
        else:
            normalized_item["dimension"] = item["dimension"] if item.get("dimension") in _DIMENSIONS else "other"
            normalized_item["source_excerpt"] = excerpt
        normalized.append(normalized_item)
    return normalized


def normalize_coverage_audit(value) -> list[dict]:
    if isinstance(value, dict):
        items = []
        for status_key, entries in value.items():
            analysis_status = {"covered": "analyzed", "partial": "missing_detail", "missing": "pending_clarification"}.get(status_key, "missing_detail")
            for entry in normalize_string_list(entries):
                items.append(
                    {
                        "module_key": slug(entry) or "general",
                        "module_name": entry,
                        "source_excerpt": entry,
                        "analysis_status": analysis_status,
                        "reason": entry,
                    }
                )
        return items
    items = value if isinstance(value, list) else []
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            item = {"module_name": str(item), "reason": str(item)}
        status = item.get("analysis_status")
        normalized.append(
            {
                "module_key": str(item.get("module_key") or slug(item.get("module_name") or item.get("reason") or "") or f"coverage-{index:03d}"),
                "module_name": str(item.get("module_name") or item.get("reason") or f"覆盖项 {index}"),
                "source_excerpt": str(item.get("source_excerpt") or item.get("reason") or ""),
                "analysis_status": status if status in _COVERAGE_STATUSES else "missing_detail",
                "reason": str(item.get("reason") or item.get("source_excerpt") or ""),
            }
        )
    return normalized


def normalize_options(value) -> list[dict]:
    items = value if isinstance(value, list) else []
    normalized = []
    for index, item in enumerate(items[:2], start=1):
        if not isinstance(item, dict):
            item = {"label": str(item), "answer_markdown": str(item)}
        normalized.append(
            {
                "id": str(item.get("id") or f"OPT-{index:03d}"),
                "label": str(item.get("label") or f"选项 {index}"),
                "answer_markdown": str(item.get("answer_markdown") or item.get("answer") or ""),
                "rationale": str(item.get("rationale") or ""),
                "confidence": item.get("confidence") if item.get("confidence") in {"high", "medium", "low"} else "medium",
            }
        )
    return normalized


def normalize_evidence_list(item: dict) -> list[dict]:
    evidence = item.get("evidence")
    if isinstance(evidence, list):
        return [normalize_evidence(entry, item) for entry in evidence]
    if evidence or item.get("sources"):
        return [normalize_evidence(evidence, item)]
    return []


def normalize_evidence(value, fallback: dict) -> dict:
    if isinstance(value, dict):
        source_file = value.get("filename") or value.get("source_file") or fallback.get("source_file") or ""
        return {
            "mapping_id": str(value.get("mapping_id") or fallback.get("mapping_id") or mapping_id_from_source(source_file)),
            "filename": str(source_file or "unknown"),
            "excerpt": str(value.get("excerpt") or value.get("evidence") or fallback.get("evidence") or ""),
            "section_hint": str(value.get("section_hint") or value.get("section") or ""),
        }
    source = fallback.get("source_file")
    sources = fallback.get("sources")
    if not source and isinstance(sources, list) and sources:
        source = sources[-1]
    return {
        "mapping_id": str(fallback.get("mapping_id") or mapping_id_from_source(str(source or ""))),
        "filename": str(source or "unknown"),
        "excerpt": str(value or fallback.get("evidence") or fallback.get("description") or ""),
        "section_hint": "",
    }


def mapping_id_from_source(value: str) -> str:
    filename = Path(value).name
    if filename.startswith(("001-", "002-", "003-")):
        parts = filename.split("-", 2)
        if len(parts) >= 2:
            return parts[1]
    return Path(filename).stem or "unknown"


def normalize_string_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def normalize_severity(value) -> str:
    normalized = str(value or "").lower()
    if normalized in {"blocker", "major", "minor"}:
        return normalized
    if normalized in {"high", "critical", "p0", "p1"}:
        return "blocker"
    if normalized in {"low", "p3"}:
        return "minor"
    return "major"


def bounded_int(value, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def slug(value) -> str:
    return str(value or "").strip().lower().replace(" ", "_")[:60]


_GAP_CATEGORIES = {
    "problem_statement",
    "stakeholder",
    "scope",
    "business_rule",
    "acceptance_criteria",
    "data",
    "permission",
    "integration",
    "non_functional",
    "constraint",
    "other",
}
_ISSUE_TYPES = {"conflict", "out_of_scope", "weak_evidence", "source_unclear", "other"}
_DIMENSIONS = {
    "boundary_value",
    "exception_path",
    "state_flow",
    "permission",
    "data_dependency",
    "message",
    "validation_rule",
    "concurrency",
    "time_related",
    "data_consistency",
    "scope",
    "other",
}
_COVERAGE_STATUSES = {"analyzed", "pending_clarification", "not_testable", "missing_detail"}
