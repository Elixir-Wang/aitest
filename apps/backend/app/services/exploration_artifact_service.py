from __future__ import annotations

from pathlib import Path
import re

import yaml

from app.core.storage import store_path


def write_exploration_artifacts(
    artifact_root: Path,
    *,
    run: dict,
    summary: dict,
    page_artifacts: list[dict],
    graph: dict,
    blockers: list[dict],
    log_content: str,
    goal_validation: dict | None = None,
) -> dict[str, str]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    pages_dir = artifact_root / "pages"
    logs_dir = artifact_root / "logs"
    documents_dir = artifact_root / "documents"
    checks_dir = artifact_root / "checks"
    pages_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    documents_dir.mkdir(parents=True, exist_ok=True)
    checks_dir.mkdir(parents=True, exist_ok=True)

    run_path = artifact_root / "run.yaml"
    summary_path = artifact_root / "summary.yaml"
    graph_path = artifact_root / "graph.yaml"
    blockers_path = artifact_root / "blockers.yaml"
    goal_validation_path = checks_dir / "goal-validation.yaml"
    log_path = logs_dir / "run.log"
    report_path = documents_dir / "exploration-v1.md"
    log_path.write_text(log_content.rstrip() + "\n", encoding="utf-8")

    page_payloads = _build_page_payloads(page_artifacts)
    for payload in page_payloads:
        payload["file_path"] = f"pages/{payload['file_name']}"
        (pages_dir / payload["file_name"]).write_text(
            yaml.safe_dump(payload["content"], allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    run_yaml = {
        "run": _run_section(run, summary, page_payloads, blockers),
        "summary": summary,
        "pages": [
            {
                "file_path": page["file_path"],
                "page_url": page["content"]["page"]["url"],
                "title": page["content"]["page"]["title"],
            }
            for page in page_payloads
        ],
        "graph_path": "graph.yaml",
        "blockers_path": "blockers.yaml",
        "log_path": "logs/run.log",
    }
    run_path.write_text(yaml.safe_dump(run_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")

    summary_yaml = _summary_yaml(summary, run, page_payloads, blockers, goal_validation)
    goal_validation_yaml = summary_yaml["goal_validation"]
    graph_yaml = _graph_yaml(graph)
    blockers_yaml = {"blockers": blockers}
    summary_path.write_text(yaml.safe_dump(summary_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")
    goal_validation_path.write_text(
        yaml.safe_dump(goal_validation_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    graph_path.write_text(
        yaml.safe_dump(graph_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    blockers_path.write_text(
        yaml.safe_dump(blockers_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    report_path.write_text(
        build_exploration_report_markdown(
            {
                "run": run_yaml,
                "summary": summary_yaml,
                "graph": graph_yaml,
                "blockers": blockers_yaml,
                "pages": [{"file_path": page["file_path"], "content": page["content"]} for page in page_payloads],
                "log_content": log_content,
                "goal_validation": goal_validation_yaml,
            }
        ),
        encoding="utf-8",
    )

    return {
        "run_path": store_path(run_path) or "",
        "summary_path": store_path(summary_path) or "",
        "graph_path": store_path(graph_path) or "",
        "blockers_path": store_path(blockers_path) or "",
        "goal_validation_path": store_path(goal_validation_path) or "",
        "report_path": store_path(report_path) or "",
        "log_path": store_path(log_path) or "",
    }


def read_yaml_artifact(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def read_text_artifact(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_exploration_run_artifacts(artifact_root: Path) -> dict:
    run = read_yaml_artifact(artifact_root / "run.yaml")
    summary = read_yaml_artifact(artifact_root / "summary.yaml")
    graph = read_yaml_artifact(artifact_root / "graph.yaml")
    blockers = read_yaml_artifact(artifact_root / "blockers.yaml")
    goal_validation = read_yaml_artifact(artifact_root / "checks" / "goal-validation.yaml")
    page_items = []
    pages_dir = artifact_root / "pages"
    if pages_dir.exists():
        for path in sorted(pages_dir.glob("page-*.yaml")):
            page_items.append(
                {
                    "file_path": store_path(path) or "",
                    "content": read_yaml_artifact(path),
                }
            )
    return {
        "run": run,
        "summary": summary,
        "graph": graph,
        "blockers": blockers,
        "goal_validation": goal_validation,
        "pages": page_items,
        "log_content": read_text_artifact(artifact_root / "logs" / "run.log"),
    }


def build_exploration_report_markdown(bundle: dict) -> str:
    run = bundle.get("run") if isinstance(bundle.get("run"), dict) else {}
    summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
    graph = bundle.get("graph") if isinstance(bundle.get("graph"), dict) else {}
    blockers = bundle.get("blockers") if isinstance(bundle.get("blockers"), dict) else {}
    goal_validation = bundle.get("goal_validation") if isinstance(bundle.get("goal_validation"), dict) else {}
    page_items = bundle.get("pages") if isinstance(bundle.get("pages"), list) else []
    pages = [item.get("content", {}) for item in page_items if isinstance(item, dict)]
    blocker_items = blockers.get("blockers") if isinstance(blockers.get("blockers"), list) else []

    run_title = _text(run.get("run", {}).get("title") if isinstance(run.get("run"), dict) else run.get("title") if isinstance(run.get("title"), str) else "")
    report_title = run_title or _text(run.get("title")) or _text(summary.get("title")) or "探索报告"
    report_status = _text(summary.get("status")) or _text(run.get("run", {}).get("status") if isinstance(run.get("run"), dict) else run.get("status")) or "pending"
    report_summary = _text(summary.get("summary")) or _text(run.get("run", {}).get("summary") if isinstance(run.get("run"), dict) else run.get("summary")) or "暂无摘要。"
    goal_text = _text(run.get("run", {}).get("goal") if isinstance(run.get("run"), dict) else run.get("goal")) or _text(summary.get("goal"))
    goal_validation_status = _text(goal_validation.get("status")) or _text(summary.get("goal_validation", {}).get("status") if isinstance(summary.get("goal_validation"), dict) else "")
    goal_validation_summary = _text(goal_validation.get("summary")) or _text(summary.get("goal_validation", {}).get("summary") if isinstance(summary.get("goal_validation"), dict) else "")
    goal_validation_stats = goal_validation.get("stats") if isinstance(goal_validation.get("stats"), dict) else {}

    page_rows = []
    module_rows = []
    relation_rows = []
    blocker_rows = []
    confirm_rows = []

    module_map = _build_module_report_map(summary, blocker_items, pages)
    for module in module_map.values():
        module_rows.append(
            [
                module["module_name"],
                module["status"],
                module["page_coverage"],
                module["latest_page"],
                module["main_facts"],
                module["blocker_summary"],
                module["kb_availability"],
            ]
        )

    for page_item in page_items:
        if not isinstance(page_item, dict):
            continue
        content = page_item.get("content") if isinstance(page_item.get("content"), dict) else {}
        page = content.get("page") if isinstance(content.get("page"), dict) else {}
        quality = content.get("quality") if isinstance(content.get("quality"), dict) else {}
        module_name = _text(page.get("module")) or "未分组模块"
        page_rows.append(
            [
                module_name,
                _text(page.get("title")),
                _text(page.get("url")),
                _text(page.get("status")) or "pending",
                _rel_path(page_item.get("file_path")),
            ]
        )
        if bool(quality.get("needs_confirmation")):
            confirm_rows.append(
                [
                    _text(page.get("title")),
                    "页面事实需要确认",
                    module_name,
                    "页面事实或状态含义暂不确定",
                ]
            )

    for edge in graph.get("edges") if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        relation_rows.append(
            [
                _text(edge.get("from")),
                _text(edge.get("action")),
                _text(edge.get("to")),
                _text(edge.get("type")),
                _rel_path("graph.yaml"),
            ]
        )

    for blocker in blocker_items:
        if not isinstance(blocker, dict):
            continue
        blocker_rows.append(
            [
                _text(blocker.get("type")),
                _text(blocker.get("page")) or _text(blocker.get("page_ref")) or _text(blocker.get("module_key")),
                _text(blocker.get("reason")),
                _text(blocker.get("impact_scope")),
                _text(blocker.get("suggested_action")),
                _rel_path(_text(blocker.get("evidence_path")) or "blockers.yaml"),
            ]
        )
        if blocker.get("type") in {"permission_denied", "captcha_required", "login_required"}:
            confirm_rows.append(
                [
                    _text(blocker.get("page")) or _text(blocker.get("page_ref")) or _text(blocker.get("module_key")),
                    "阻塞原因需要确认",
                    _text(blocker.get("impact_scope")),
                    _text(blocker.get("reason")),
                ]
            )

    lines = [
        f"# {report_title}",
        "",
        "## 1. 报告摘要",
        "",
        f"- 项目：{_text(run.get('run', {}).get('project_name') if isinstance(run.get('run'), dict) else run.get('project_name'))}",
        f"- 站点：{_text(run.get('run', {}).get('title') if isinstance(run.get('run'), dict) else run.get('title'))}",
        f"- 环境：{_text(run.get('run', {}).get('environment_name') if isinstance(run.get('run'), dict) else run.get('environment_name'))}",
        f"- 探索时间：{_text(run.get('run', {}).get('started_at') if isinstance(run.get('run'), dict) else run.get('started_at'))}",
        f"- 探索范围：{_text(run.get('run', {}).get('scope') if isinstance(run.get('run'), dict) else run.get('scope'))}",
        f"- 探索目标：{goal_text}",
        f"- 报告状态：{report_status}",
        f"- 一句话结论：{report_summary}",
        "",
        "## 2. 探索结论",
        "",
        f"- 总体结论：{report_summary}",
        f"- 是否覆盖目标范围：{_coverage_text(summary)}",
        f"- 是否具备下游可用性：{_downstream_text(summary, blocker_items)}",
        f"- 关键阻塞：{_top_blockers(blocker_items)}",
        f"- 关键收获：{_top_findings(summary, pages)}",
        "",
        "## 目标验证结果",
        "",
        f"- 目标：{goal_text or '未设置'}",
        f"- 结论：{goal_validation_status or '未验证'}",
        f"- 说明：{goal_validation_summary or '目标验证未执行。'}",
        f"- 页面：{_text(goal_validation_stats.get('page_count')) or '0'}",
        f"- 链接验证：{_text(goal_validation_stats.get('link_checked_count')) or '0'}/{_text(goal_validation_stats.get('link_total_count')) or '0'}，失败 {_text(goal_validation_stats.get('link_failed_count')) or '0'}",
        f"- 按钮验证：{_text(goal_validation_stats.get('button_checked_count')) or '0'}/{_text(goal_validation_stats.get('button_total_count')) or '0'}，未验证 {_text(goal_validation_stats.get('button_unverified_count')) or '0'}，失败 {_text(goal_validation_stats.get('button_failed_count')) or '0'}",
        f"- 未验证项：{_text(goal_validation_stats.get('unverified_count')) or '0'}",
        "",
        "## 3. 探索范围与边界",
        "",
        f"- 站点 URL：{_text(run.get('run', {}).get('site_url') if isinstance(run.get('run'), dict) else run.get('site_url'))}",
        f"- 登录方式：{_text(run.get('run', {}).get('login_strategy') if isinstance(run.get('run'), dict) else run.get('login_strategy'))}",
        f"- 验证码处理方式：{_text(run.get('run', {}).get('captcha_strategy') if isinstance(run.get('run'), dict) else run.get('captcha_strategy'))}",
        f"- 默认角色：{_text(run.get('run', {}).get('default_role') if isinstance(run.get('run'), dict) else run.get('default_role'))}",
        f"- 探索范围：{_text(run.get('run', {}).get('scope') if isinstance(run.get('run'), dict) else run.get('scope'))}",
        f"- 禁止路径：{_text(run.get('run', {}).get('forbidden_paths') if isinstance(run.get('run'), dict) else run.get('forbidden_paths'))}",
        f"- 页面上限：{_limit_text(run, 'max_pages')}",
        f"- 动作上限：{_limit_text(run, 'max_actions')}",
        f"- 超时时间：{_limit_text(run, 'timeout_minutes')}",
        "",
        "## 4. 覆盖概览",
        "",
        "| 指标 | 数量 |",
        "| --- | --- |",
        f"| 模块总数 | {_count_modules(module_map)} |",
        f"| 已完成模块 | {_count_module_status(module_map, {'completed'})} |",
        f"| 部分完成模块 | {_count_module_status(module_map, {'partial'})} |",
        f"| 无法探索模块 | {_count_module_status(module_map, {'blocked'})} |",
        f"| 已跳过模块 | {_count_module_status(module_map, {'skipped'})} |",
        f"| 页面数 | {len(page_rows)} |",
        f"| 页面关系数 | {len(relation_rows)} |",
        f"| 阻塞数 | {len(blocker_rows)} |",
        "",
        "## 5. 模块覆盖矩阵",
        "",
        "| 模块 | 状态 | 页面覆盖 | 最近页面 | 主要事实 | 阻塞说明 | 知识库可用性 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in module_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")

    lines.extend(
        [
            "",
            "## 6. 页面事实摘要",
            "",
            "### 6.1 页面基本信息",
            "",
            "| 模块 | 页面 | URL | 状态 | 证据 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in page_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")

    lines.extend(
        [
            "",
            "### 6.2 页面核心事实",
            "",
            "| 页面 | 主要字段 | 主要操作 | 主要状态 | 关键说明 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for page_item in page_items:
        if not isinstance(page_item, dict):
            continue
        content = page_item.get("content") if isinstance(page_item.get("content"), dict) else {}
        page = content.get("page") if isinstance(content.get("page"), dict) else {}
        fields = _page_field_summary(content)
        actions = _page_action_summary(content)
        states = _page_state_summary(content)
        lines.append(
            "| "
            + " | ".join(
                _table_cell(value)
                for value in [
                    _text(page.get("title")),
                    fields,
                    actions,
                    states,
                    _text(page.get("structure_summary")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 7. 页面关系与路径",
            "",
            "### 7.1 跳转路径",
            "",
            "| 起点页面 | 动作 | 目标页面 | 关系类型 | 证据 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in relation_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")

    lines.extend(
        [
            "",
            "### 7.2 页面内关系",
            "",
            "| 页面 | 类型 | 说明 | 证据 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for page_item in page_items:
        if not isinstance(page_item, dict):
            continue
        content = page_item.get("content") if isinstance(page_item.get("content"), dict) else {}
        page = content.get("page") if isinstance(content.get("page"), dict) else {}
        relations = content.get("relations") if isinstance(content.get("relations"), dict) else {}
        for outgoing in relations.get("outgoing_edges") if isinstance(relations.get("outgoing_edges"), list) else []:
            if not isinstance(outgoing, dict):
                continue
            lines.append(
                "| "
                + " | ".join(
                    _table_cell(value)
                    for value in [
                        _text(page.get("title")),
                        _text(outgoing.get("type")),
                        _text(outgoing.get("action")),
                        _rel_path(page_item.get("file_path")),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "### 7.3 数据依赖",
            "",
            "| 生产页面 | 消费页面 | 依赖内容 | 说明 | 证据 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for edge in graph.get("edges") if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict) or _text(edge.get("type")) != "data_dependency":
            continue
        lines.append(
            "| "
            + " | ".join(
                _table_cell(value)
                for value in [
                    _text(edge.get("from")),
                    _text(edge.get("to")),
                    _text(edge.get("entity")),
                    _text(edge.get("action")),
                    _rel_path("graph.yaml"),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 8. 阻塞与跳过",
            "",
            "| 类型 | 模块/页面/动作 | 原因 | 影响 | 建议 | 证据 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in blocker_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")

    lines.extend(
        [
            "",
            "## 9. 风险与缺口",
            "",
            f"- 权限风险：{_risk_summary(blocker_items, 'permission_denied')}",
            f"- 登录风险：{_risk_summary(blocker_items, 'login_required')}",
            f"- 验证码风险：{_risk_summary(blocker_items, 'captcha_required')}",
            f"- 页面事实缺口：{_fact_gap_summary(pages)}",
            f"- locator 稳定性风险：{_locator_risk_summary(pages)}",
            f"- 业务理解缺口：{_business_gap_summary(pages)}",
            f"- 下游使用风险：{_downstream_risk_summary(summary, blocker_items)}",
            "",
            "## 10. 待人工确认事项",
            "",
            "| 事项 | 原因 | 影响范围 | 建议确认人 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in confirm_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")

    lines.extend(
        [
            "",
            "## 11. 证据索引",
            "",
            "| 类型 | 文件 | 说明 |",
            "| --- | --- | --- |",
            "| 探索计划 | `run.yaml` | 本次探索范围、目标、边界 |",
            "| 覆盖摘要 | `summary.yaml` | 模块与页面概览 |",
            "| 页面事实 | `pages/*.yaml` | 页面结构、字段、操作、定位提示 |",
            "| 页面关系 | `graph.yaml` | 跳转、提交、弹窗、数据依赖 |",
            "| 阻塞记录 | `blockers.yaml` | 无法探索、跳过、安全拦截 |",
            "| 运行日志 | `logs/run.log` | 探索过程审计 |",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _build_module_report_map(summary: dict, blocker_items: list[dict], pages: list[dict]) -> dict[str, dict]:
    modules = summary.get("modules") if isinstance(summary.get("modules"), list) else []
    module_map: dict[str, dict] = {}
    for index, module in enumerate(modules, start=1):
        if not isinstance(module, dict):
            continue
        key = _text(module.get("module_key")) or f"module-{index:02d}"
        module_map[key] = {
            "module_name": _text(module.get("module_name")) or key,
            "status": _text(module.get("status")) or "pending",
            "page_coverage": _text(module.get("page_progress")) or _coverage_ratio(module),
            "latest_page": _text(module.get("latest_page")) or "-",
            "main_facts": _text(module.get("main_facts")) or _module_fact_hint(module, pages),
            "blocker_summary": _text(module.get("blocker_summary")) or _module_blocker_hint(module, blocker_items),
            "kb_availability": _text(module.get("knowledge_base_availability")) or "待确认",
        }
    if module_map:
        return module_map
    fallback_modules = {}
    for page in pages:
        page_item = page.get("page") if isinstance(page.get("page"), dict) else {}
        key = _text(page_item.get("module")) or "未分组模块"
        fallback_modules.setdefault(
            key,
            {
                "module_name": key,
                "status": "pending",
                "page_coverage": f"1/{len(pages)}" if pages else "0/0",
                "latest_page": _text(page_item.get("title")) or "-",
                "main_facts": _text(page_item.get("structure_summary")) or "-",
                "blocker_summary": _module_blocker_hint({"module_name": key}, blocker_items),
                "kb_availability": "待确认",
            },
        )
    return fallback_modules


def _coverage_text(summary: dict) -> str:
    status = _text(summary.get("status"))
    if status == "completed":
        return "已覆盖目标范围"
    if status == "partial":
        return "部分覆盖目标范围"
    if status == "blocked":
        return "未完整覆盖，存在阻塞"
    return "覆盖状态待确认"


def _downstream_text(summary: dict, blocker_items: list[dict]) -> str:
    if _text(summary.get("status")) == "completed" and not blocker_items:
        return "可用"
    if _text(summary.get("status")) == "partial":
        return "部分可用"
    if blocker_items:
        return "受阻"
    return "待确认"


def _top_blockers(blocker_items: list[dict]) -> str:
    if not blocker_items:
        return "无"
    reasons = [_text(item.get("reason")) for item in blocker_items[:3]]
    return "；".join(reason for reason in reasons if reason) or "存在阻塞项"


def _top_findings(summary: dict, pages: list[dict]) -> str:
    if _text(summary.get("summary")):
        return _text(summary.get("summary"))
    if pages:
        page = pages[0].get("page") if isinstance(pages[0].get("page"), dict) else {}
        return _text(page.get("structure_summary")) or _text(page.get("title")) or "已采集页面事实"
    return "暂无可用发现"


def _limit_text(run: dict, key: str) -> str:
    source = run.get("run") if isinstance(run.get("run"), dict) else run
    return _text(source.get(key)) or "-"


def _count_modules(module_map: dict[str, dict]) -> int:
    return len(module_map)


def _count_module_status(module_map: dict[str, dict], statuses: set[str]) -> int:
    return sum(1 for module in module_map.values() if _text(module.get("status")) in statuses)


def _page_field_summary(content: dict) -> str:
    page = content.get("page") if isinstance(content.get("page"), dict) else {}
    tree = content.get("accessibility_tree") if isinstance(content.get("accessibility_tree"), list) else []
    field_names = []
    for node in tree:
        if not isinstance(node, dict):
            continue
        role = _text(node.get("role"))
        name = _text(node.get("name"))
        if role in {"textbox", "combobox", "checkbox", "radio", "date", "textarea"} and name:
            field_names.append(name)
    if field_names:
        return "、".join(field_names[:5])
    return _text(page.get("structure_summary")) or "-"


def _page_action_summary(content: dict) -> str:
    actions = content.get("actions") if isinstance(content.get("actions"), list) else []
    action_names = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        name = _text(action.get("name"))
        if name:
            action_names.append(name)
    return "、".join(action_names[:5]) or "-"


def _page_state_summary(content: dict) -> str:
    relations = content.get("relations") if isinstance(content.get("relations"), dict) else {}
    outgoing = relations.get("outgoing_edges") if isinstance(relations.get("outgoing_edges"), list) else []
    types = []
    for edge in outgoing:
        if not isinstance(edge, dict):
            continue
        edge_type = _text(edge.get("type"))
        if edge_type:
            types.append(edge_type)
    return "、".join(types[:5]) or "-"


def _risk_summary(blocker_items: list[dict], reason_type: str) -> str:
    matched = [item for item in blocker_items if _text(item.get("type")) == reason_type]
    if not matched:
        return "无"
    return _text(matched[0].get("reason")) or "存在风险"


def _fact_gap_summary(pages: list[dict]) -> str:
    if not pages:
        return "未采集页面事实"
    gaps = []
    for page_item in pages:
        page = page_item.get("page") if isinstance(page_item.get("page"), dict) else {}
        quality = page_item.get("quality") if isinstance(page_item.get("quality"), dict) else {}
        if quality.get("needs_confirmation"):
            gaps.append(_text(page.get("title")))
    return "、".join(gaps[:3]) or "暂无明显缺口"


def _locator_risk_summary(pages: list[dict]) -> str:
    for page_item in pages:
        content = page_item if isinstance(page_item, dict) else {}
        tree = content.get("accessibility_tree") if isinstance(content.get("accessibility_tree"), list) else []
        if any(isinstance(node, dict) and not _text(node.get("locator_hint")) for node in tree):
            page = content.get("page") if isinstance(content.get("page"), dict) else {}
            return _text(page.get("title")) or "存在 locator 缺失"
    return "暂无明显风险"


def _business_gap_summary(pages: list[dict]) -> str:
    if not pages:
        return "暂无页面事实"
    page = pages[0].get("page") if isinstance(pages[0].get("page"), dict) else {}
    return _text(page.get("structure_summary")) or "页面业务含义待确认"


def _downstream_risk_summary(summary: dict, blocker_items: list[dict]) -> str:
    if _text(summary.get("status")) == "blocked" or blocker_items:
        return "下游生成需先处理阻塞或缺口"
    return "当前风险较低"


def _module_fact_hint(module: dict, pages: list[dict]) -> str:
    module_name = _text(module.get("module_name"))
    if module_name:
        matched_pages = []
        for page in pages:
            content = page if isinstance(page, dict) else {}
            page_info = content.get("page") if isinstance(content.get("page"), dict) else {}
            if _text(page_info.get("module")) == module_name:
                matched_pages.append(_text(page_info.get("title")))
        if matched_pages:
            return "、".join(matched_pages[:3])
    return "-"


def _module_blocker_hint(module: dict, blocker_items: list[dict]) -> str:
    module_name = _text(module.get("module_name"))
    for item in blocker_items:
        if module_name and module_name in (_text(item.get("module_key")) or _text(item.get("page_ref"))):
            return _text(item.get("reason")) or "-"
    return "无"


def _coverage_ratio(module: dict) -> str:
    explored = module.get("explored_page_count")
    planned = module.get("planned_page_count")
    if isinstance(explored, int) and isinstance(planned, int) and planned > 0:
        return f"{explored}/{planned}"
    return "-"


def _mapping_get(mapping: object, key: str, default: object = "") -> object:
    if not hasattr(mapping, "keys"):
        return default
    try:
        return mapping[key] if key in mapping.keys() else default
    except (KeyError, TypeError):
        return default


def _rel_path(value: str) -> str:
    normalized = _text(value)
    return normalized or "-"


def _table_cell(value: object) -> str:
    text = _text(value)
    return text.replace("|", "\\|") or "-"


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _build_page_payloads(page_artifacts: list[dict]) -> list[dict]:
    payloads = []
    for index, page_content in enumerate(page_artifacts, start=1):
        if not isinstance(page_content, dict) or not isinstance(page_content.get("page"), dict):
            raise ValueError("page_artifacts must contain structured page dictionaries with a page section")
        page_content = dict(page_content)
        page_content["page"] = dict(page_content["page"])
        page_content["page"].pop("page_type", None)
        page_meta = page_content["page"]
        slug = _slugify(page_meta.get("title") or page_meta.get("url") or f"page-{index}")
        file_name = f"{page_meta.get('id') or f'page-{index:03d}'}-{slug}.yaml"
        payloads.append({"file_name": file_name, "content": page_content})
    return payloads


def _run_section(run: dict, summary: dict, pages: list[dict], blockers: list[dict]) -> dict:
    return {
        "id": run["id"],
        "project_id": run["project_id"],
        "project_name": run["project_name"],
        "environment_id": run["environment_id"],
        "environment_name": run["environment_name"],
        "title": run["title"],
        "site_url": _mapping_get(run, "site_url", ""),
        "scope": _mapping_get(run, "scope", ""),
        "goal": _mapping_get(run, "goal", ""),
        "forbidden_paths": _mapping_get(run, "forbidden_paths", ""),
        "login_strategy": _mapping_get(run, "login_strategy", ""),
        "captcha_strategy": _mapping_get(run, "captcha_strategy", ""),
        "default_role": _mapping_get(run, "default_role", ""),
        "started_at": _mapping_get(run, "started_at", ""),
        "status": summary["status"],
        "summary": summary["summary"],
        "page_count": len(pages),
        "blocker_count": len(blockers),
        "log_path": "logs/run.log",
        "limits": {
            "max_pages": _mapping_get(run, "max_pages", 50),
            "max_actions": _mapping_get(run, "max_actions", 1000),
            "timeout_minutes": _mapping_get(run, "timeout_minutes", 120),
        },
    }


def _summary_yaml(summary: dict, run: dict, pages: list[dict], blockers: list[dict], goal_validation: dict | None = None) -> dict:
    return {
        "run_id": run["id"],
        "title": f"探索报告 v1",
        "status": summary["status"],
        "summary": summary["summary"],
        "goal": _mapping_get(run, "goal", ""),
        "goal_validation": goal_validation or _default_goal_validation(_mapping_get(run, "goal", "")),
        "markdown_content": summary["markdown_content"],
        "page_count": len(pages),
        "blocker_count": len(blockers),
    }


def _default_goal_validation(goal: str) -> dict:
    if goal:
        return {
            "goal": goal,
            "status": "pending",
            "summary": "目标验证尚未执行。",
            "stats": {},
            "items": [],
        }
    return {
        "goal": "",
        "status": "skipped",
        "summary": "未设置探索目标。",
        "stats": {},
        "items": [],
    }


def _graph_yaml(graph: dict) -> dict:
    return {
        "nodes": graph.get("nodes") if isinstance(graph.get("nodes"), list) else [],
        "edges": graph.get("edges") if isinstance(graph.get("edges"), list) else [],
        "paths": graph.get("paths") if isinstance(graph.get("paths"), list) else [],
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return slug[:40] or "page"
