from __future__ import annotations

import re
from pathlib import Path

from app.core.storage import project_requirement_dir, store_path
from app.schemas.requirement_merge import RequirementMergeSourceFile


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
    quality_result: str,
    blocking_issues: list[str] | None = None,
) -> list[dict]:
    mapping_markdown = build_mapping_markdown(coverage_items, source_files)
    conflicts_markdown = build_conflicts_markdown(conflicts)
    report_markdown = build_merge_report_markdown(
        run_id,
        quality_result=quality_result,
        source_files=source_files,
        coverage_items=coverage_items,
        conflicts=conflicts,
        preview_markdown=preview_markdown,
        merge_summary=merge_summary,
        diff_summary=diff_summary,
        affected_modules=affected_modules,
        blocking_issues=blocking_issues,
    )
    artifacts = [
        ("preview", "合并候选稿", merge_preview_path(project_id, document_id, run_id), preview_markdown, quality_result),
        ("mapping", "段落映射", merge_mapping_path(project_id, document_id, run_id), mapping_markdown, quality_result),
        ("conflicts", "明显冲突", merge_conflicts_path(project_id, document_id, run_id), conflicts_markdown, quality_result),
        ("report", "质量报告", merge_report_path(project_id, document_id, run_id), report_markdown, quality_result),
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
    return [{key: tab[key] for key in ("key", "label", "path", "content")} for tab in tabs]


def read_merge_artifact_tabs(project_id: str, document_id: str, run_id: str) -> list[dict]:
    artifacts = [
        ("preview", "合并候选稿", merge_preview_path(project_id, document_id, run_id)),
        ("mapping", "段落映射", merge_mapping_path(project_id, document_id, run_id)),
        ("conflicts", "明显冲突", merge_conflicts_path(project_id, document_id, run_id)),
        ("report", "质量报告", merge_report_path(project_id, document_id, run_id)),
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
    return tabs


def merge_quality_result(
    coverage_items: list[dict],
    conflicts: list[dict],
    markdown: str,
    source_files: list[RequirementMergeSourceFile],
    merge_summary: str = "",
) -> str:
    if conflicts:
        return "failed"
    statuses = [item.get("coverage_status", "") for item in coverage_items]
    if not coverage_items or "missing" in statuses:
        return "failed"
    if contains_source_structure(markdown, source_files):
        return "failed"
    if summary_count_mismatches(merge_summary, coverage_counts(coverage_items)):
        return "warning"
    if any(status in {"conflict", "pending_clarification"} for status in statuses):
        return "warning"
    return "passed"


def contains_source_structure(markdown: str, source_files: list[RequirementMergeSourceFile]) -> bool:
    forbidden = ["docmap-", "来源文档", "源文档", "原始文件", "标准文件"]
    if any(token in markdown for token in forbidden):
        return True
    source_names = [Path(item.original_filename).name for item in source_files]
    source_stems = [Path(name).stem for name in source_names]
    return any(name and name in markdown for name in source_names + source_stems)


def build_mapping_markdown(coverage_items: list[dict], source_files: list[RequirementMergeSourceFile]) -> str:
    counts = coverage_counts(coverage_items)
    rows = [
        "# 段落映射",
        "",
        "## 覆盖统计",
        "",
        "| 指标 | 数量 |",
        "| --- | ---: |",
        f"| 来源文件数 | {len(source_files)} |",
        f"| 来源片段数 | {len(coverage_items)} |",
        f"| 已合入 | {counts.get('merged', 0)} |",
        f"| 重复去重 | {counts.get('duplicate', 0)} |",
        f"| 明显冲突 | {counts.get('conflict', 0)} |",
        f"| 待澄清 | {counts.get('pending_clarification', 0)} |",
        f"| 不可测试 | {counts.get('not_testable', 0)} |",
        f"| 已丢弃 | {counts.get('discarded', 0)} |",
        f"| 未覆盖 | {counts.get('missing', 0)} |",
        "",
        "## 映射明细",
        "",
        "| 来源文件 | 来源标题 | 来源摘要 | 状态 | 目标章节 | 原因 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not coverage_items:
        rows.append("| - | - | - | missing | - | 智能体未返回段落映射 |")
    for item in coverage_items:
        rows.append(
            "| {mapping_id} | {source_heading} | {source_excerpt} | {coverage_status} | {target} | {reason} |".format(
                mapping_id=md_cell(item.get("mapping_id", "")),
                source_heading=md_cell(item.get("source_heading", "")),
                source_excerpt=md_cell(item.get("source_excerpt", "")),
                coverage_status=md_cell(item.get("coverage_status", "")),
                target=md_cell(" / ".join(filter(None, [item.get("target_module", ""), item.get("target_heading", "")]))),
                reason=md_cell(item.get("reason", "")),
            )
        )
    return "\n".join(rows) + "\n"


def build_conflicts_markdown(conflicts: list[dict]) -> str:
    rows = ["# 明显冲突", ""]
    if not conflicts:
        return "# 明显冲突\n\n本次未发现明显冲突。\n"
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
                "### 片段 A",
                "",
                str(conflict.get("fragment_a", "")),
                "",
                "### 片段 B",
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
    return "\n".join(rows) + "\n"


def build_merge_report_markdown(
    run_id: str,
    *,
    quality_result: str,
    source_files: list[RequirementMergeSourceFile],
    coverage_items: list[dict],
    conflicts: list[dict],
    preview_markdown: str,
    merge_summary: str,
    diff_summary: str,
    affected_modules: list[str],
    blocking_issues: list[str] | None,
) -> str:
    issues = list(blocking_issues or [])
    summary_mismatches = summary_count_mismatches(merge_summary, coverage_counts(coverage_items))
    if not coverage_items:
        issues.append("智能体未返回段落映射，无法证明来源内容已完整处理。")
    if conflicts:
        issues.append(f"存在 {len(conflicts)} 个明显冲突。")
    if contains_source_structure(preview_markdown, source_files):
        issues.append("合并候选稿仍包含源文件名、docmap 或来源文档结构。")
    issues.extend(summary_mismatches)
    rows = [
        "# 归并质量报告",
        "",
        "## 结论",
        "",
        quality_result,
        "",
        "## 输入信息",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 合并运行 | {run_id} |",
        f"| 来源文件数 | {len(source_files)} |",
        f"| 来源片段数 | {len(coverage_items)} |",
        f"| 合并摘要 | {md_cell(merge_summary)} |",
        f"| 差异摘要 | {md_cell(diff_summary)} |",
        f"| 影响模块 | {md_cell('、'.join(affected_modules))} |",
        "",
        "## 质量检查",
        "",
        "| 检查项 | 结果 | 说明 |",
        "| --- | --- | --- |",
        f"| 段落映射存在 | {'passed' if coverage_items else 'failed'} | 覆盖项 {len(coverage_items)} 条 |",
        f"| 候选稿无源文档结构 | {'failed' if contains_source_structure(preview_markdown, source_files) else 'passed'} | 检查源文件名、docmap 和来源文档分组 |",
        f"| 明显冲突已隔离 | {'failed' if conflicts else 'passed'} | 明显冲突 {len(conflicts)} 个 |",
        f"| 摘要与映射统计一致 | {'warning' if summary_mismatches else 'passed'} | {md_cell('；'.join(summary_mismatches) if summary_mismatches else '一致')} |",
        "",
        "## 阻塞问题",
        "",
    ]
    rows.extend([f"- {issue}" for issue in issues] or ["- 无"])
    rows.extend(["", "## 非阻塞问题", "", "- 后续可接入需求分析，继续检查不可测试、范围不清和验收缺失。"])
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


def merge_preview_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "previews" / f"{run_id}.md"


def merge_mapping_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "mappings" / f"{run_id}.md"


def merge_conflicts_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "conflicts" / f"{run_id}.md"


def merge_report_path(project_id: str, document_id: str, run_id: str) -> Path:
    return project_requirement_dir(project_id, document_id) / "reports" / f"{run_id}.md"
