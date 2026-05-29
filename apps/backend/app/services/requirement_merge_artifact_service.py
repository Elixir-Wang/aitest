from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.storage import project_requirement_dir, store_path
from app.schemas.requirement_merge import RequirementMergeSourceFile, RequirementSourceBlock, RequirementSourceFragment


def evaluate_merge_quality(
    coverage_items: list[dict],
    conflicts: list[dict],
    markdown: str,
    source_files: list[RequirementMergeSourceFile],
    merge_summary: str = "",
) -> tuple[str, list[str]]:
    blocking_issues: list[str] = []
    if conflicts:
        blocking_issues.append(f"存在 {len(conflicts)} 个明显冲突。")
    statuses = [item.get("coverage_status", "") for item in coverage_items]
    if not coverage_items:
        blocking_issues.append("智能体未返回段落映射，无法证明来源内容已完整处理。")
    if "missing" in statuses:
        blocking_issues.append("段落映射存在未覆盖来源内容。")
    if contains_source_structure(markdown, source_files):
        blocking_issues.append("合并候选稿仍包含源文件名、docmap 或来源文档结构。")
    retention_issue = merge_retention_issue(markdown, source_files)
    if retention_issue:
        blocking_issues.append(retention_issue)
    structure_issue = markdown_structure_retention_issue(markdown, source_files)
    if structure_issue:
        blocking_issues.append(structure_issue)
    if blocking_issues:
        return "failed", blocking_issues

    summary_mismatches = summary_count_mismatches(merge_summary, coverage_counts(coverage_items))
    if summary_mismatches or any(status in {"conflict", "pending_clarification"} for status in statuses):
        return "warning", summary_mismatches
    return "passed", []


def write_merge_artifacts(
    project_id: str,
    document_id: str,
    run_id: str,
    *,
    preview_markdown: str,
    coverage_items: list[dict],
    conflicts: list[dict],
    merge_summary: str,
    diff_summary: str,
    affected_modules: list[str],
    source_files: list[RequirementMergeSourceFile],
    source_blocks: list[RequirementSourceBlock] | None = None,
    quality_result: str,
    blocking_issues: list[str] | None = None,
) -> list[dict]:
    mapping_markdown = build_mapping_markdown(coverage_items, source_files, source_blocks or [])
    quality_markdown = build_quality_markdown(
        coverage_items=coverage_items,
        source_files=source_files,
        source_blocks=source_blocks or [],
        preview_markdown=preview_markdown,
        quality_result=quality_result,
        blocking_issues=blocking_issues or [],
        merge_summary=merge_summary,
    )
    confirmations_markdown = build_confirmation_markdown(conflicts)
    mapping_path = merge_mapping_path(project_id, document_id, run_id)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(mapping_markdown, encoding="utf-8")
    artifacts = [
        ("merged", "合并后的文档", merge_merged_path(project_id, document_id, run_id), preview_markdown, quality_result),
        ("quality", "质量检测", merge_quality_path(project_id, document_id, run_id), quality_markdown, quality_result),
        ("confirmations", "待确认项", merge_confirmations_path(project_id, document_id, run_id), confirmations_markdown, quality_result),
    ]
    tabs = []
    document_dir = project_requirement_dir(project_id, document_id)
    for key, label, path, content, result in artifacts:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        tabs.append(
            {
                "key": key,
                "label": label,
                "path": str(path.relative_to(document_dir)),
                "stored_path": store_path(path) or str(path),
                "content": content,
                "quality_result": result,
            }
        )
    return tabs


def public_artifact_tabs(tabs: list[dict]) -> list[dict]:
    public_keys = {"quality", "confirmations"}
    return [{key: tab[key] for key in ("key", "label", "path", "content")} for tab in tabs if tab["key"] in public_keys]


def write_merge_machine_artifacts(
    project_id: str,
    document_id: str,
    run_id: str,
    *,
    source_fragments: list[RequirementSourceFragment],
    source_blocks: list[RequirementSourceBlock] | None = None,
    decisions: list[dict] | None = None,
) -> dict[str, str]:
    document_dir = project_requirement_dir(project_id, document_id)
    artifacts_dir = document_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    source_blocks_path = artifacts_dir / f"{run_id}-source-blocks.json"
    fragments_path = artifacts_dir / f"{run_id}-fragments.json"
    decisions_path = artifacts_dir / f"{run_id}-decisions.json"
    source_blocks_path.write_text(
        json.dumps([block.model_dump() for block in source_blocks or []], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fragments_path.write_text(
        json.dumps([fragment.model_dump() for fragment in source_fragments], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    decisions_path.write_text(json.dumps(decisions or [], ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "source_blocks_path": store_path(source_blocks_path) or str(source_blocks_path),
        "fragments_path": store_path(fragments_path) or str(fragments_path),
        "decisions_path": store_path(decisions_path) or str(decisions_path),
    }


def read_merge_artifact_tabs(project_id: str, document_id: str, run_id: str) -> list[dict]:
    artifacts = [
        ("quality", "质量检测", merge_quality_path(project_id, document_id, run_id)),
        ("confirmations", "待确认项", merge_confirmations_path(project_id, document_id, run_id)),
    ]
    tabs = []
    document_dir = project_requirement_dir(project_id, document_id)
    for key, label, path in artifacts:
        if not path.exists():
            continue
        tabs.append(
            {
                "key": key,
                "label": label,
                "path": str(path.relative_to(document_dir)),
                "content": path.read_text(encoding="utf-8"),
            }
        )
    if tabs:
        return tabs
    legacy_artifacts = [
        ("quality", "质量检测", merge_mapping_path(project_id, document_id, run_id)),
        ("confirmations", "待确认项", merge_conflicts_path(project_id, document_id, run_id)),
    ]
    for key, label, path in legacy_artifacts:
        if not path.exists():
            continue
        tabs.append(
            {
                "key": key,
                "label": label,
                "path": str(path.relative_to(document_dir)),
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return tabs


def merge_quality_result(
    coverage_items: list[dict],
    conflicts: list[dict],
    markdown: str,
    source_files: list[RequirementMergeSourceFile],
    merge_summary: str = "",
) -> str:
    result, _issues = evaluate_merge_quality(coverage_items, conflicts, markdown, source_files, merge_summary)
    return result


def contains_source_structure(markdown: str, source_files: list[RequirementMergeSourceFile]) -> bool:
    forbidden = ["docmap-", "来源文档", "源文档", "原始文件", "标准文件"]
    if any(token in markdown for token in forbidden):
        return True
    source_names = [Path(item.original_filename).name for item in source_files]
    source_stems = [Path(name).stem for name in source_names]
    return any(name and name in markdown for name in source_names + source_stems)


def merge_retention_issue(markdown: str, source_files: list[RequirementMergeSourceFile]) -> str:
    source_text = "\n".join(item.markdown_content for item in source_files)
    source_units = _meaningful_text_units(source_text)
    if len(source_units) < 20:
        return ""

    markdown_units = _meaningful_text_units(markdown)
    ratio = len(markdown_units) / len(source_units) if source_units else 1
    if ratio < 0.35:
        return (
            "合并候选稿相对标准文件内容异常过短，疑似只生成摘要而未保留大部分需求内容"
            f"（来源有效内容 {len(source_units)} 条，候选稿 {len(markdown_units)} 条）。"
        )
    return ""


def markdown_structure_retention_issue(markdown: str, source_files: list[RequirementMergeSourceFile]) -> str:
    source_text = "\n".join(item.markdown_content for item in source_files)
    source_metrics = markdown_structure_metrics(source_text)
    draft_metrics = markdown_structure_metrics(markdown)
    issues: list[str] = []

    for key, label, threshold, minimum in [
        ("fenced_blocks", "代码围栏", 0.5, 3),
        ("mermaid_blocks", "Mermaid 流程图", 0.5, 1),
        ("table_rows", "Markdown 表格行", 0.35, 8),
    ]:
        source_count = source_metrics[key]
        if source_count < minimum:
            continue
        draft_count = draft_metrics[key]
        ratio = draft_count / source_count if source_count else 1
        if ratio < threshold:
            issues.append(f"{label}保留不足（来源 {source_count}，候选稿 {draft_count}）")

    if not issues:
        return ""
    return "合并候选稿疑似丢失结构化 Markdown：" + "；".join(issues) + "。"


def markdown_structure_metrics(markdown: str) -> dict[str, int]:
    fenced_languages = _fenced_block_languages(markdown)
    return {
        "fenced_blocks": len(fenced_languages),
        "mermaid_blocks": sum(1 for language in fenced_languages if language.lower() == "mermaid"),
        "table_rows": len(re.findall(r"(?m)^\|.*\|$", markdown)),
    }


def _fenced_block_languages(markdown: str) -> list[str]:
    languages: list[str] = []
    in_fence = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("```"):
            continue
        if in_fence:
            in_fence = False
            continue
        languages.append(line[3:].strip().split(maxsplit=1)[0] if line[3:].strip() else "")
        in_fence = True
    return languages


def _meaningful_text_units(markdown: str) -> list[str]:
    units: list[str] = []
    in_fence = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith(("!", "<!--")):
            continue
        normalized = re.sub(r"^[#>*\-\d\.\s]+", "", line).strip()
        normalized = re.sub(r"\s+", "", normalized)
        if len(normalized) >= 8:
            units.append(normalized)
    return units


def build_mapping_markdown(
    coverage_items: list[dict],
    source_files: list[RequirementMergeSourceFile],
    source_blocks: list[RequirementSourceBlock] | None = None,
) -> str:
    counts = coverage_counts(coverage_items)
    source_blocks = source_blocks or []
    source_names = {item.mapping_id: item.original_filename for item in source_files}
    source_stems = {mapping_id: Path(filename).stem for mapping_id, filename in source_names.items()}
    coverage_by_block_id = {
        str(item.get("source_block_id") or item.get("block_id") or ""): item
        for item in coverage_items
        if item.get("source_block_id") or item.get("block_id")
    }
    rows = [
        "# 段落映射",
        "",
        "## 来源文档",
        "",
        "| 代号 | 源文档 |",
        "| --- | --- |",
    ]
    if source_blocks:
        seen_codes: set[str] = set()
        for block in source_blocks:
            if block.source_code in seen_codes:
                continue
            seen_codes.add(block.source_code)
            rows.append(f"| {md_cell(block.source_code)} | {md_cell(block.source_file)} |")
    else:
        for index, source_file in enumerate(source_files):
            rows.append(f"| {md_cell(_source_code(index))} | {md_cell(source_file.original_filename)} |")
    rows.extend(
        [
            "",
            "## 来源块清单",
            "",
            "| 来源块ID | 代号 | 原标题 | 内容类型 | 是否保留原文 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if source_blocks:
        for block in source_blocks:
            rows.append(
                "| {block_id} | {source_code} | {heading} | {content_types} | {preserve} |".format(
                    block_id=md_cell(block.block_id),
                    source_code=md_cell(block.source_code),
                    heading=md_cell(block.original_heading),
                    content_types=md_cell("、".join(block.content_types)),
                    preserve="是" if block.must_preserve_original else "否",
                )
            )
    else:
        rows.append("| - | - | - | - | - |")
    rows.extend(
        [
            "",
        "## 覆盖统计",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 来源文件数 | {len(source_files)} |",
        f"| 来源块数 | {len(coverage_items)} |",
        f"| 已合入 | {counts.get('merged', 0)} |",
        f"| 重复去重 | {counts.get('duplicate', 0)} |",
        f"| 明显冲突 | {counts.get('conflict', 0)} |",
        f"| 待澄清 | {counts.get('pending_clarification', 0)} |",
        f"| 已丢弃 | {counts.get('discarded', 0)} |",
        f"| 未覆盖 | {counts.get('missing', 0)} |",
        "",
            "## 来源块覆盖表",
        "",
            "| 来源块ID | 源文档 | 原二级标题 | 合并后位置 | 处理方式 | 是否保留原文 | 备注 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    if source_blocks:
        for block in source_blocks:
            item = coverage_by_block_id.get(block.block_id) or _coverage_item_for_block(coverage_items, block)
            rows.append(_coverage_row_for_block(block, item))
    elif coverage_items:
        for item in coverage_items:
            mapping_id = item.get("mapping_id", "")
            rows.append(
                "| {block_id} | {source_file} | {source_heading} | {target} | {status} | {preserve} | {reason} |".format(
                    block_id=md_cell(item.get("source_block_id", "")),
                    source_file=md_cell(source_names.get(mapping_id, source_stems.get(mapping_id, mapping_id))),
                    source_heading=md_cell(item.get("source_heading", "")),
                    target=md_cell(" / ".join(filter(None, [item.get("target_module", ""), item.get("target_heading", "")]))),
                    status=md_cell(_coverage_status_label(item.get("coverage_status", ""))),
                    preserve="否",
                    reason=md_cell(item.get("reason", "")),
                )
            )
    else:
        rows.append("| - | - | - | - | missing | - | 智能体未返回段落映射 |")
    uncovered_blocks = [
        block for block in source_blocks if block.block_id not in coverage_by_block_id and not _coverage_item_for_block(coverage_items, block)
    ]
    rows.extend(["", "## 未覆盖来源块清单", ""])
    if uncovered_blocks:
        rows.extend([f"- {block.block_id} {block.source_file} / {block.original_heading}" for block in uncovered_blocks])
    else:
        rows.append("无")
    rows.extend(["", "## 高保真内容保留清单", ""])
    preserve_blocks = [block for block in source_blocks if block.must_preserve_original]
    if preserve_blocks:
        for block in preserve_blocks:
            item = coverage_by_block_id.get(block.block_id) or _coverage_item_for_block(coverage_items, block) or {}
            rows.append(
                f"- {block.block_id} {block.original_heading}：{_preserve_status(item, block)}"
            )
    else:
        rows.append("无")
    return "\n".join(rows) + "\n"


def build_quality_markdown(
    *,
    coverage_items: list[dict],
    source_files: list[RequirementMergeSourceFile],
    source_blocks: list[RequirementSourceBlock],
    preview_markdown: str,
    quality_result: str,
    blocking_issues: list[str],
    merge_summary: str,
) -> str:
    counts = coverage_counts(coverage_items)
    source_unit_count = len(_meaningful_text_units("\n".join(item.markdown_content for item in source_files)))
    draft_unit_count = len(_meaningful_text_units(preview_markdown))
    retention_ratio = draft_unit_count / source_unit_count if source_unit_count else 1
    source_metrics = markdown_structure_metrics("\n".join(item.markdown_content for item in source_files))
    draft_metrics = markdown_structure_metrics(preview_markdown)
    coverage_by_block_id = {
        str(item.get("source_block_id") or item.get("block_id") or ""): item
        for item in coverage_items
        if item.get("source_block_id") or item.get("block_id")
    }
    rows = [
        "# 质量检测",
        "",
        "## 检测结论",
        "",
        "| 指标 | 结果 |",
        "| --- | --- |",
        f"| 合并质量 | {_quality_result_label(quality_result)} |",
        f"| 是否可确认写入版本 | {'否' if quality_result == 'failed' else '是'} |",
        f"| 质量摘要 | {md_cell(merge_summary or '已完成合并质量检测。')} |",
        "",
        "### 阻断原因",
        "",
    ]
    issue_lines = [f"- {_quality_issue_label(issue)}" for issue in blocking_issues]
    if not coverage_items:
        issue_lines.append("- 无法证明所有来源内容已被处理。")
    if _missing_coverage_count(coverage_items, source_blocks):
        issue_lines.append("- 存在来源内容未进入合并稿。")
    rows.extend(_dedupe_lines(issue_lines) or ["无"])
    rows.extend(
        [
            "",
            "## 来源覆盖",
            "",
            "| 指标 | 数量 |",
            "| --- | ---: |",
            f"| 来源文件数 | {len(source_files)} |",
            f"| 来源块总数 | {len(source_blocks) or len(coverage_items)} |",
            f"| 已合入 | {counts.get('merged', 0)} |",
            f"| 重复引用 | {counts.get('duplicate', 0)} |",
            f"| 进入待确认项 | {counts.get('conflict', 0) + counts.get('pending_clarification', 0)} |",
            f"| 未覆盖 | {_missing_coverage_count(coverage_items, source_blocks)} |",
            "",
            "### 未覆盖来源内容",
            "",
        ]
    )
    uncovered_lines = _uncovered_source_lines(coverage_items, source_blocks)
    rows.extend(uncovered_lines or ["无"])
    rows.extend(
        [
            "",
            "## 内容保留",
            "",
            "| 检查项 | 来源 | 合并稿 | 结果 |",
            "| --- | ---: | ---: | --- |",
            _structure_metric_row("Markdown 表格", source_metrics["table_rows"], draft_metrics["table_rows"], minimum=8, threshold=0.35),
            _structure_metric_row("Mermaid 流程图", source_metrics["mermaid_blocks"], draft_metrics["mermaid_blocks"], minimum=1, threshold=0.5),
            _structure_metric_row("代码块 / JSON 示例", source_metrics["fenced_blocks"], draft_metrics["fenced_blocks"], minimum=3, threshold=0.5),
            f"| 高保真来源块 | {len([block for block in source_blocks if block.must_preserve_original])} | - | {_preserve_summary(coverage_items, source_blocks)} |",
            "",
            "## 合并完整性",
            "",
            "| 指标 | 数值 |",
            "| --- | ---: |",
            f"| 来源有效内容 | {source_unit_count} |",
            f"| 合并稿有效内容 | {draft_unit_count} |",
            f"| 内容保留比例 | {retention_ratio:.0%} |",
            "",
            _retention_summary(source_unit_count, draft_unit_count, retention_ratio),
            "",
            "## 来源追溯摘要",
            "",
        ]
    )
    trace_lines = _source_trace_lines(coverage_items, source_blocks)
    rows.extend(trace_lines or ["无可展示的来源追溯摘要。"])
    return "\n".join(rows) + "\n"


def build_confirmation_markdown(conflicts: list[dict]) -> str:
    rows = ["# 待确认项", ""]
    if not conflicts:
        rows.append("本次未发现需要人工确认的差异。")
        return "\n".join(rows) + "\n"
    rows.extend(["## 待确认项统计", "", f"- 待确认项数量：{len(conflicts)}"])
    for index, conflict in enumerate(conflicts, start=1):
        rows.extend(
            [
                "",
                f"## C{index:03d} {conflict.get('title', '未命名待确认项')}",
                "",
                f"- 问题类型：{conflict.get('conflict_type', '口径不一致')}",
                f"- 严重级别：{conflict.get('severity', 'medium')}",
                f"- 涉及来源：{conflict.get('source_file_names', '') or '未提供来源文件名'}",
                "",
                "### 差异摘录",
                "",
                str(conflict.get("fragment_a", "")),
                "",
                str(conflict.get("fragment_b", "")),
                "",
                "### 需要确认的问题",
                "",
                str(conflict.get("agent_suggestion", "")) or "需要业务或测试人员确认采用哪一版口径。",
                "",
                "### 当前状态",
                "",
                str(conflict.get("status", "open")),
            ]
        )
    return "\n".join(rows) + "\n"


def _quality_result_label(result: str) -> str:
    return {"passed": "通过", "warning": "警告", "failed": "未通过"}.get(result, result)


def _quality_issue_label(issue: str) -> str:
    replacements = {
        "智能体未返回段落映射，无法证明来源内容已完整处理。": "无法证明所有来源内容已被处理。",
        "段落映射存在未覆盖来源内容。": "存在来源内容未进入合并稿。",
    }
    for old, new in replacements.items():
        issue = issue.replace(old, new)
    return issue


def _missing_coverage_count(coverage_items: list[dict], source_blocks: list[RequirementSourceBlock]) -> int:
    explicit_missing = sum(1 for item in coverage_items if item.get("coverage_status") == "missing")
    if not source_blocks:
        return explicit_missing
    covered_block_ids = {
        str(item.get("source_block_id") or item.get("block_id") or "")
        for item in coverage_items
        if item.get("source_block_id") or item.get("block_id")
    }
    implicit_missing = sum(1 for block in source_blocks if block.block_id not in covered_block_ids and not _coverage_item_for_block(coverage_items, block))
    return explicit_missing + implicit_missing


def _uncovered_source_lines(coverage_items: list[dict], source_blocks: list[RequirementSourceBlock]) -> list[str]:
    lines = [
        f"- {md_cell(str(item.get('source_heading') or item.get('source_excerpt') or '未命名来源内容'))}：未进入合并稿。"
        for item in coverage_items
        if item.get("coverage_status") == "missing"
    ]
    covered_block_ids = {
        str(item.get("source_block_id") or item.get("block_id") or "")
        for item in coverage_items
        if item.get("source_block_id") or item.get("block_id")
    }
    for block in source_blocks:
        if block.block_id in covered_block_ids or _coverage_item_for_block(coverage_items, block):
            continue
        lines.append(f"- {md_cell(block.original_heading)}：未进入合并稿。")
    return lines


def _structure_metric_row(label: str, source_count: int, draft_count: int, *, minimum: int, threshold: float) -> str:
    if source_count < minimum:
        result = "无明显风险"
    else:
        ratio = draft_count / source_count if source_count else 1
        result = "通过" if ratio >= threshold else "保留不足"
    return f"| {label} | {source_count} | {draft_count} | {result} |"


def _preserve_summary(coverage_items: list[dict], source_blocks: list[RequirementSourceBlock]) -> str:
    preserve_blocks = [block for block in source_blocks if block.must_preserve_original]
    if not preserve_blocks:
        return "无高保真来源块"
    failed = []
    for block in preserve_blocks:
        item = _coverage_item_for_block(coverage_items, block) or {}
        if _preserve_status(item, block) == "否":
            failed.append(block.original_heading)
    return "通过" if not failed else f"保留不足：{'、'.join(failed)}"


def _retention_summary(source_unit_count: int, draft_unit_count: int, ratio: float) -> str:
    if source_unit_count < 20:
        return "来源内容较少，未触发摘要化比例门禁。"
    if ratio < 0.35:
        return "合并稿疑似只生成摘要，不能确认写入版本。"
    return "未发现明显摘要化。"


def _source_trace_lines(coverage_items: list[dict], source_blocks: list[RequirementSourceBlock]) -> list[str]:
    if source_blocks:
        lines = []
        for block in source_blocks:
            item = _coverage_item_for_block(coverage_items, block) or {}
            status = str(item.get("coverage_status", "missing"))
            target = " / ".join(filter(None, [item.get("target_module", ""), item.get("target_heading", "")]))
            excerpt = _trace_excerpt(item, block)
            lines.append(f"- {md_cell(block.original_heading)}：{_trace_status_text(status, target)}{excerpt}")
        return lines
    return [
        f"- {md_cell(str(item.get('source_heading') or item.get('source_excerpt') or '未命名来源内容'))}："
        f"{_trace_status_text(str(item.get('coverage_status', 'missing')), ' / '.join(filter(None, [item.get('target_module', ''), item.get('target_heading', '')])))}"
        f"{_trace_excerpt(item, None)}"
        for item in coverage_items
    ]


def _trace_status_text(status: str, target: str) -> str:
    if status == "merged":
        return f"已合入「{md_cell(target or '合并稿')}」"
    if status == "duplicate":
        return f"已通过重复引用覆盖「{md_cell(target or '合并稿')}」"
    if status in {"conflict", "pending_clarification"}:
        return "进入「待确认项」"
    if status == "discarded":
        return "已放入附录或不纳入正文"
    return "未覆盖，需要重新合并或人工补充"


def _trace_excerpt(item: dict, block: RequirementSourceBlock | None) -> str:
    excerpt = str(item.get("source_excerpt") or "")
    if not excerpt and block is not None:
        excerpt = block.plain_text
    excerpt = md_cell(excerpt)
    if not excerpt:
        return ""
    return f"（{excerpt[:80]}）"


def _dedupe_lines(lines: list[str]) -> list[str]:
    result = []
    seen = set()
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        result.append(line)
    return result


def _coverage_item_for_block(coverage_items: list[dict], block: RequirementSourceBlock) -> dict | None:
    candidates = [item for item in coverage_items if item.get("mapping_id") == block.mapping_id]
    for item in candidates:
        heading = str(item.get("source_heading", ""))
        if heading == block.original_heading or heading == " / ".join(block.heading_path):
            return item
    return candidates[0] if len(candidates) == 1 else None


def _coverage_row_for_block(block: RequirementSourceBlock, item: dict | None) -> str:
    item = item or {}
    target = " / ".join(filter(None, [item.get("target_module", ""), item.get("target_heading", "")]))
    return (
        "| {block_id} | {source_file} | {heading} | {target} | {status} | {preserve} | {reason} |".format(
            block_id=md_cell(block.block_id),
            source_file=md_cell(block.source_file),
            heading=md_cell(block.original_heading),
            target=md_cell(target or "-"),
            status=md_cell(_coverage_status_label(item.get("coverage_status", "missing"))),
            preserve=_preserve_status(item, block),
            reason=md_cell(item.get("reason", "未覆盖") if item else "未覆盖"),
        )
    )


def _coverage_status_label(status: str) -> str:
    return {
        "merged": "合并",
        "duplicate": "引用",
        "conflict": "放入待确认",
        "pending_clarification": "放入待确认",
        "discarded": "放入附录",
        "missing": "未覆盖",
    }.get(status, status)


def _preserve_status(item: dict, block: RequirementSourceBlock) -> str:
    if not block.must_preserve_original:
        return "否"
    status = str(item.get("coverage_status", ""))
    if status in {"merged", "duplicate"}:
        return "是"
    if status in {"conflict", "pending_clarification"}:
        return "部分"
    return "否"


def _source_code(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = ""
    value = index
    while True:
        code = alphabet[value % 26] + code
        value = value // 26 - 1
        if value < 0:
            return code


def build_conflicts_markdown(conflicts: list[dict], blocking_issues: list[str] | None = None) -> str:
    rows = ["# 明显冲突", ""]
    issues = [issue for issue in blocking_issues or [] if issue]
    if not conflicts:
        rows.append("本次未发现明显冲突。")
        rows.extend(["", "## 阻断原因", ""])
        rows.extend([f"- {issue}" for issue in issues] or ["无"])
        return "\n".join(rows) + "\n"
    severity_counts: dict[str, int] = {}
    for conflict in conflicts:
        severity = conflict.get("severity", "medium")
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    rows.extend(["## 冲突统计", "", "| 严重级别 | 数量 |", "| --- | ---: |"])
    for severity in ("high", "medium", "low"):
        rows.append(f"| {severity} | {severity_counts.get(severity, 0)} |")
    for index, conflict in enumerate(conflicts, start=1):
        rows.extend(
            [
                "",
                f"## C{index:03d} {conflict.get('title', '未命名冲突')}",
                "",
                "### 冲突类型",
                "",
                str(conflict.get("conflict_type", "contradiction")),
                "",
                "### 严重级别",
                "",
                str(conflict.get("severity", "medium")),
                "",
                "### 来源",
                "",
                str(conflict.get("source_file_names", "")) or "未提供来源文件名。",
                "",
                "### 来源块 A",
                "",
                str(conflict.get("fragment_a", "")),
                "",
                "### 来源块 B",
                "",
                str(conflict.get("fragment_b", "")),
                "",
                "### 智能体建议",
                "",
                str(conflict.get("agent_suggestion", "")) or "需要人工确认。",
                "",
                "### 决策状态",
                "",
                str(conflict.get("status", "open")),
            ]
        )
    rows.extend(["", "## 阻断原因", ""])
    rows.extend([f"- {issue}" for issue in issues] or ["无"])
    return "\n".join(rows) + "\n"

def blocked_preview_markdown(document_name: str, reason: str) -> str:
    return f"# {document_name}\n\n## 合并候选稿未生成\n\n{reason}\n"


def coverage_counts(coverage_items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in coverage_items:
        status = item.get("coverage_status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def summary_count_mismatches(merge_summary: str, counts: dict[str, int]) -> list[str]:
    checks = [
        (r"去重\s*(\d+)\s*处", "duplicate", "重复去重"),
        (r"冲突\s*(\d+)\s*处", "conflict", "明显冲突"),
        (r"待澄清\s*(\d+)\s*处", "pending_clarification", "待澄清"),
    ]
    mismatches = []
    for pattern, status, label in checks:
        match = re.search(pattern, merge_summary)
        if not match:
            continue
        summary_count = int(match.group(1))
        coverage_count = counts.get(status, 0)
        if summary_count != coverage_count:
            mismatches.append(f"合并摘要称{label}{summary_count}处，但段落映射统计为{coverage_count}处。")
    return mismatches


def md_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def merge_merged_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "previews" / f"{run_id}.md"


def merge_preview_path(project_id: str, document_id: str, run_id: str) -> Path:
    return merge_merged_path(project_id, document_id, run_id)


def merge_mapping_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "mappings" / f"{run_id}.md"


def merge_conflicts_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "conflicts" / f"{run_id}.md"


def merge_quality_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "quality" / f"{run_id}.md"


def merge_confirmations_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "confirmations" / f"{run_id}.md"
