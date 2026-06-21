from pathlib import Path
import json
import re

import yaml

from app.core.storage import store_path


ARTIFACT_SCHEMA_VERSION = 2
UNSUPPORTED_ARTIFACT_REASON = "历史产物格式不支持新版详情，请重新探索。"


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
    reports_dir = artifact_root / "reports"
    checks_dir = artifact_root / "checks"
    pages_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    checks_dir.mkdir(parents=True, exist_ok=True)

    run_path = artifact_root / "run.yaml"
    summary_path = artifact_root / "summary.yaml"
    graph_path = artifact_root / "graph.yaml"
    blockers_path = artifact_root / "blockers.yaml"
    goal_validation_path = checks_dir / "goal-validation.yaml"
    log_path = logs_dir / "run.log"
    report_path = reports_dir / "exploration-report.md"
    log_path.write_text(log_content.rstrip() + "\n", encoding="utf-8")

    page_payloads = _build_page_payloads(page_artifacts)
    for payload in page_payloads:
        payload["file_path"] = f"pages/{payload['file_name']}"
        (pages_dir / payload["file_name"]).write_text(
            yaml.safe_dump(payload["content"], allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    combined_blockers = _with_action_failure_blockers(blockers, page_payloads)
    run_yaml = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run": _run_section(run, summary, page_payloads, combined_blockers),
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
        "report_path": "reports/exploration-report.md",
        "log_path": "logs/run.log",
    }
    run_path.write_text(yaml.safe_dump(run_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")

    summary_yaml = _summary_yaml(summary, run, page_payloads, combined_blockers, goal_validation)
    goal_validation_yaml = summary_yaml["goal_validation"]
    graph_yaml = _graph_yaml(graph)
    blockers_yaml = {"artifact_schema_version": ARTIFACT_SCHEMA_VERSION, "blockers": combined_blockers}
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


def write_live_exploration_snapshot(
    artifact_root: Path,
    *,
    run: dict,
    summary: dict,
    page_artifacts: list[dict],
    graph: dict,
    blockers: list[dict],
    log_content: str,
) -> dict[str, str]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    live_dir = artifact_root / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    state_path = live_dir / "state.json"

    page_payloads = _build_page_payloads(page_artifacts)
    for payload in page_payloads:
        payload["file_path"] = f"live/pages/{payload['file_name']}"

    state = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run": _json_compatible(run),
        "summary": _json_compatible(summary),
        "graph": _json_compatible(graph),
        "blockers": {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "blockers": _json_compatible(blockers),
        },
        "pages": [
            {
                "file_path": page["file_path"],
                "page_url": page["content"]["page"]["url"],
                "title": page["content"]["page"]["title"],
                "content": _json_compatible(page["content"]),
            }
            for page in page_payloads
        ],
        "log_content": log_content,
    }
    _write_json_atomic(state_path, state)
    return {"live_state_path": store_path(state_path) or ""}


def read_yaml_artifact(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def read_text_artifact(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json_artifact(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_exploration_run_artifacts(artifact_root: Path) -> dict:
    run = read_yaml_artifact(artifact_root / "run.yaml")
    summary = read_yaml_artifact(artifact_root / "summary.yaml")
    graph = read_yaml_artifact(artifact_root / "graph.yaml")
    blockers = read_yaml_artifact(artifact_root / "blockers.yaml")
    goal_validation = read_yaml_artifact(artifact_root / "checks" / "goal-validation.yaml")
    schema_version = _artifact_schema_version(run, summary)
    has_versioned_artifacts = bool(run or summary)
    if has_versioned_artifacts and schema_version != ARTIFACT_SCHEMA_VERSION:
        return _unsupported_bundle(schema_version, artifact_root)
    if not has_versioned_artifacts:
        live_bundle = _load_live_snapshot_bundle(artifact_root)
        if live_bundle:
            return live_bundle
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
    report_path = artifact_root / "reports" / "exploration-report.md"
    return {
        "artifact_schema_version": schema_version,
        "unsupported_artifact": False,
        "unsupported_reason": "",
        "run": run,
        "summary": summary,
        "graph": graph,
        "blockers": blockers,
        "goal_validation": goal_validation,
        "pages": page_items,
        "log_content": read_text_artifact(artifact_root / "logs" / "run.log"),
        "report_content": read_text_artifact(report_path),
        "report_path": store_path(report_path) or "",
    }


def _load_live_snapshot_bundle(artifact_root: Path) -> dict:
    state = read_json_artifact(artifact_root / "live" / "state.json")
    if not state:
        return {}
    schema_version = _artifact_schema_version(state, state.get("summary", {}))
    if schema_version != ARTIFACT_SCHEMA_VERSION:
        return _unsupported_bundle(schema_version, artifact_root)
    blockers = state.get("blockers") if isinstance(state.get("blockers"), dict) else {}
    pages = state.get("pages") if isinstance(state.get("pages"), list) else []
    page_items = []
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            continue
        content = page.get("content") if isinstance(page.get("content"), dict) else {}
        if not content:
            continue
        page_items.append(
            {
                "file_path": str(page.get("file_path") or f"live/pages/page-{index:03d}.yaml"),
                "content": content,
            }
        )
    return {
        "artifact_schema_version": schema_version,
        "unsupported_artifact": False,
        "unsupported_reason": "",
        "run": state.get("run") if isinstance(state.get("run"), dict) else {},
        "summary": state.get("summary") if isinstance(state.get("summary"), dict) else {},
        "graph": state.get("graph") if isinstance(state.get("graph"), dict) else {},
        "blockers": blockers,
        "goal_validation": {},
        "pages": page_items,
        "log_content": read_text_artifact(artifact_root / "logs" / "run.log") or str(state.get("log_content") or ""),
        "report_content": "",
        "report_path": "",
    }


def _artifact_schema_version(run: dict, summary: dict) -> int:
    for source in (run, summary):
        value = source.get("artifact_schema_version") if isinstance(source, dict) else None
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _unsupported_bundle(schema_version: int, artifact_root: Path) -> dict:
    return {
        "artifact_schema_version": schema_version,
        "unsupported_artifact": True,
        "unsupported_reason": UNSUPPORTED_ARTIFACT_REASON,
        "run": {},
        "summary": {},
        "graph": {},
        "blockers": {},
        "goal_validation": {},
        "pages": [],
        "log_content": read_text_artifact(artifact_root / "logs" / "run.log"),
        "report_content": "",
        "report_path": "",
    }


def _write_json_atomic(path: Path, payload: dict) -> None:
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _json_compatible(value):
    if isinstance(value, dict):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if hasattr(value, "keys") and not isinstance(value, (str, bytes)):
        return {str(key): _json_compatible(value[key]) for key in value.keys()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


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
    report_status = _normalize_report_status(report_status, goal_validation_status, blocker_items)
    page_title_map = _page_title_map(graph, page_items)

    page_rows = []
    module_rows = []
    relation_rows = []
    intra_page_relation_rows = []
    blocking_rows = []
    skipped_rows = []
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
        module_name = _page_module_name(page)
        page_rows.append(
            [
                module_name,
                _page_display_title(page),
                _text(page.get("url")),
                _text(page.get("status")) or "pending",
                _rel_path(page_item.get("file_path")),
            ]
        )
        if bool(quality.get("needs_confirmation")):
            confirm_rows.append(
                [
                    _page_display_title(page),
                    "页面事实需要确认",
                    module_name,
                    "页面事实或状态含义暂不确定",
                ]
            )

    relation_rows, intra_page_relation_rows = _page_relation_rows(graph, page_title_map)

    for blocker in blocker_items:
        if not isinstance(blocker, dict):
            continue
        row = _blocker_report_row(blocker, page_title_map)
        if blocker.get("is_blocking"):
            blocking_rows.append(row)
        else:
            skipped_rows.append(row)
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
        f"| 阻塞数 | {len(blocking_rows)} |",
        f"| 跳过/未验证数 | {len(skipped_rows)} |",
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
            "## 7. 页面关系与路径",
            "",
            "### 7.1 跳转路径",
            "",
            "| 源页面 | 目标页面 | 关联关系 | 触发动作 | 次数 | 证据 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in relation_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")
    if not relation_rows:
        lines.append("| - | - | 未发现跨页面关联 | - | 0 | graph.yaml |")

    lines.extend(
        [
            "",
            "### 7.2 页面内关系",
            "",
            "| 页面 | 类型 | 说明 | 证据 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in intra_page_relation_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")
    if not intra_page_relation_rows:
        lines.append("| - | - | 未发现页面内状态关系 | graph.yaml |")

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
            "### 8.1 阻塞项",
            "",
            "| 位置 | 动作/范围 | 原因 | 对下游影响 | 下一步 | 证据 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in blocking_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")
    if not blocking_rows:
        lines.append("| - | - | 无阻塞项 | 不影响下游使用 | 无需处理 | blockers.yaml |")

    lines.extend(
        [
            "",
            "### 8.2 已跳过或未验证",
            "",
            "| 位置 | 动作/范围 | 原因 | 对下游影响 | 下一步 | 证据 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in skipped_rows:
        lines.append("| " + " | ".join(_table_cell(value) for value in row) + " |")
    if not skipped_rows:
        lines.append("| - | - | 无跳过或未验证项 | 不影响下游使用 | 无需处理 | blockers.yaml |")

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
            "| 阻塞记录 | `blockers.yaml` | 无法探索、动作跳过 |",
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
        key = _page_module_name(page_item)
        fallback_modules.setdefault(
            key,
            {
                "module_name": key,
                "status": "pending",
                "page_coverage": f"1/{len(pages)}" if pages else "0/0",
                "latest_page": _page_display_title(page_item),
                "main_facts": _page_key_note(page),
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
        return _compact_text(_text(page.get("structure_summary")), 120) or _page_display_title(page) or "已采集页面事实"
    return "暂无可用发现"


def _blocker_report_row(blocker: dict, page_title_map: dict[str, str]) -> list[str]:
    page_ref = _text(blocker.get("page_ref"))
    page_text = _text(blocker.get("page")) or page_ref or _text(blocker.get("module_key"))
    page_title = page_title_map.get(page_ref, "")
    location = _join_parts([page_title, page_text], " / ") or "未知位置"
    action = _text(blocker.get("action")) or _text(blocker.get("action_target")) or _text(blocker.get("element_name"))
    scope = action or _text(blocker.get("impact_scope")) or _text(blocker.get("type")) or "未说明"
    reason = _text(blocker.get("reason")) or _blocker_type_label(_text(blocker.get("type")))
    impact = _text(blocker.get("impact_scope")) or ("阻塞相关页面进入知识库" if blocker.get("is_blocking") else "该动作未完成自动验证")
    suggested_action = _text(blocker.get("suggested_action")) or ("人工处理后重新探索" if blocker.get("is_blocking") else "按需人工确认")
    evidence = _rel_path(_text(blocker.get("evidence_path")) or "blockers.yaml")
    return [location, scope, reason, impact, suggested_action, evidence]


def _blocker_type_label(reason_type: str) -> str:
    labels = {
        "action_failed": "动作执行失败",
        "forbidden_path": "命中禁止路径",
        "scope_boundary": "超出探索范围",
        "crud_scope_violation": "涉及业务数据修改",
        "permission_denied": "权限不足",
        "captcha_required": "需要验证码",
        "login_required": "需要登录",
        "navigation_failed": "页面无法访问",
        "run_timeout": "探索超时",
    }
    return labels.get(reason_type, reason_type or "未说明")


def _join_parts(parts: list[str], separator: str) -> str:
    values = []
    for part in parts:
        text = _text(part)
        if text and text not in values:
            values.append(text)
    return separator.join(values)


def _limit_text(run: dict, key: str) -> str:
    source = run.get("run") if isinstance(run.get("run"), dict) else run
    limits = source.get("limits") if isinstance(source.get("limits"), dict) else {}
    return _text(source.get(key)) or _text(limits.get(key)) or "-"


def _count_modules(module_map: dict[str, dict]) -> int:
    return len(module_map)


def _count_module_status(module_map: dict[str, dict], statuses: set[str]) -> int:
    return sum(1 for module in module_map.values() if _text(module.get("status")) in statuses)


def _page_action_summary(content: dict) -> str:
    actions = content.get("actions") if isinstance(content.get("actions"), list) else []
    action_names = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        name = _text(action.get("name")) or _text(action.get("element_name")) or _text(action.get("action_target"))
        if name:
            action_names.append(name)
    states = content.get("states") if isinstance(content.get("states"), list) else []
    for state in states:
        if not isinstance(state, dict):
            continue
        elements = state.get("elements") if isinstance(state.get("elements"), list) else []
        for element in elements:
            if not isinstance(element, dict):
                continue
            name = _text(element.get("name"))
            if name and name not in action_names:
                action_names.append(name)
            if len(action_names) >= 5:
                break
        if len(action_names) >= 5:
            break
    return "、".join(action_names[:5]) or "-"


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
    return _compact_text(_text(page.get("structure_summary")), 120) or "页面业务含义待确认"


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
            if _page_module_name(page_info) == module_name:
                matched_pages.append(_page_display_title(page_info))
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


def _first_page_url(pages: list[dict]) -> str:
    for page in pages:
        content = page.get("content") if isinstance(page.get("content"), dict) else {}
        page_meta = content.get("page") if isinstance(content.get("page"), dict) else {}
        url = _text(page_meta.get("url"))
        if url:
            return url
    return ""


def _run_started_url(log_content: str) -> str:
    for line in str(log_content or "").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("event") == "run_started":
            return _text(payload.get("url"))
    return ""


def _site_url_text(run: dict, page_items: list[dict], log_content: str) -> str:
    source = run.get("run") if isinstance(run.get("run"), dict) else run
    return _text(source.get("site_url")) or _first_page_url(page_items) or _run_started_url(log_content) or "缺失来源"


def _page_display_title(page: dict) -> str:
    explicit = _text(page.get("semantic_title"))
    if explicit:
        return explicit
    inferred = _infer_page_title(page)
    return inferred or _text(page.get("title")) or _text(page.get("url")) or "-"


def _page_module_name(page: dict) -> str:
    inferred = _infer_module_name(page)
    explicit = _text(page.get("module"))
    title = _text(page.get("title"))
    if inferred and (not explicit or explicit == title):
        return inferred
    return explicit or inferred or "未分组模块"


def _page_title_map(graph: dict, page_items: list[dict]) -> dict[str, str]:
    title_map: dict[str, str] = {}
    for node in graph.get("nodes") if isinstance(graph.get("nodes"), list) else []:
        if not isinstance(node, dict):
            continue
        node_id = _text(node.get("id"))
        if node_id:
            title_map[node_id] = _text(node.get("semantic_title")) or _text(node.get("title")) or _text(node.get("url")) or node_id
    for page_item in page_items:
        if not isinstance(page_item, dict):
            continue
        content = page_item.get("content") if isinstance(page_item.get("content"), dict) else {}
        page = content.get("page") if isinstance(content.get("page"), dict) else {}
        page_id = _text(page.get("id"))
        if page_id:
            title_map[page_id] = _page_display_title(page)
    return title_map


def _page_relation_rows(graph: dict, page_title_map: dict[str, str]) -> tuple[list[list[object]], list[list[object]]]:
    grouped_relations: dict[tuple[str, str, str], dict[str, object]] = {}
    intra_page_relations: dict[tuple[str, str, str], dict[str, object]] = {}
    for edge in graph.get("edges") if isinstance(graph.get("edges"), list) else []:
        if not isinstance(edge, dict):
            continue
        source_ref = _text(edge.get("source")) or _text(edge.get("from"))
        target_ref = _text(edge.get("target")) or _text(edge.get("to"))
        if not source_ref and not target_ref:
            continue
        source_title = _text(edge.get("source_title")) or page_title_map.get(source_ref, source_ref)
        target_title = _text(edge.get("target_title")) or page_title_map.get(target_ref, target_ref)
        relation_type = _relation_type_text(edge)
        action_text = _edge_action_text(edge)
        if source_ref and target_ref and source_ref != target_ref:
            key = (source_ref, target_ref, relation_type)
            row = grouped_relations.setdefault(
                key,
                {
                    "source_title": source_title,
                    "target_title": target_title,
                    "relation_type": relation_type,
                    "actions": [],
                    "count": 0,
                },
            )
            row["count"] = int(row["count"]) + 1
            if action_text != "-" and action_text not in row["actions"]:
                row["actions"].append(action_text)
            continue
        page_ref = source_ref or target_ref
        page_title = source_title or target_title or page_title_map.get(page_ref, page_ref)
        key = (page_ref, relation_type, action_text)
        row = intra_page_relations.setdefault(
            key,
            {
                "page_title": page_title,
                "relation_type": relation_type,
                "action": action_text,
                "count": 0,
            },
        )
        row["count"] = int(row["count"]) + 1

    relation_rows = [
        [
            row["source_title"],
            row["target_title"],
            row["relation_type"],
            _join_limited(row["actions"], 5),
            row["count"],
            "graph.yaml",
        ]
        for row in grouped_relations.values()
    ]
    intra_page_rows = [
        [
            row["page_title"],
            row["relation_type"],
            _intra_page_relation_summary(_text(row["action"]), int(row["count"])),
            "graph.yaml",
        ]
        for row in intra_page_relations.values()
    ]
    return relation_rows, intra_page_rows


def _relation_type_text(edge: dict) -> str:
    edge_type = _text(edge.get("type"))
    if edge_type == "agent_action":
        result = edge.get("result") if isinstance(edge.get("result"), dict) else {}
        if bool(result.get("url_changed")):
            return "页面跳转"
        if bool(result.get("state_signature_changed")):
            return "状态流转"
        return "动作验证"
    if edge_type == "navigation":
        return "页面跳转"
    if edge_type == "external_link":
        return "外部链接"
    if edge_type == "data_dependency":
        return "数据依赖"
    return edge_type or "页面关联"


def _join_limited(values: list[str], limit: int) -> str:
    clean_values = [_text(value) for value in values if _text(value)]
    if not clean_values:
        return "-"
    shown = clean_values[:limit]
    suffix = f" 等 {len(clean_values)} 个动作" if len(clean_values) > limit else ""
    return "、".join(shown) + suffix


def _intra_page_relation_summary(action: str, count: int) -> str:
    action_text = action if action and action != "-" else "页面内动作"
    if count <= 1:
        return action_text
    return f"{action_text}，出现 {count} 次"


def _edge_action_text(edge: dict) -> str:
    return " ".join(item for item in [_text(edge.get("action")), _text(edge.get("action_target"))] if item) or "-"


def _infer_module_name(page: dict) -> str:
    return _route_label(_text(page.get("url")), prefer_deep=True) or _business_keyword_label(_text(page.get("structure_summary")))


def _infer_page_title(page: dict) -> str:
    title = _text(page.get("title"))
    url = _text(page.get("url"))
    summary = _text(page.get("structure_summary"))
    keyword_label = _business_keyword_label(summary)
    route_label = _route_label(url, prefer_deep=True)
    if keyword_label in {"用户洞察", "数据统计"}:
        return keyword_label
    return route_label or keyword_label or title


def _route_label(url: str, *, prefer_deep: bool = False) -> str:
    try:
        from urllib.parse import urlparse

        segments = [segment for segment in urlparse(url).path.split("/") if segment]
    except Exception:
        return ""
    labels = {
        "agentStore": "探索广场",
        "workspace": "工作台",
        "agentAnalysis": "效果评测",
        "resource": "资源库",
        "publish": "发布管理",
        "manage": "管理中心",
    }
    iterable = reversed(segments) if prefer_deep else segments
    for segment in iterable:
        if segment in labels:
            return labels[segment]
    return ""


def _business_keyword_label(page_text: str) -> str:
    text = _text(page_text)
    keyword_labels = [
        (("数据统计", "用户洞察"), "用户洞察"),
        (("Token 消耗量", "用户"), "数据统计"),
        (("结果即刻交付", "探索广场"), "探索广场"),
        (("收藏", "探索广场"), "探索广场"),
        (("资源库", "效果评测", "发布管理"), "创作中心"),
        (("空间管理", "文档中心"), "管理中心"),
    ]
    for keywords, label in keyword_labels:
        if all(keyword in text for keyword in keywords):
            return label
    return ""


def _business_headline(content: dict) -> str:
    business_summary = content.get("business_summary") if isinstance(content.get("business_summary"), dict) else {}
    return _text(business_summary.get("headline"))


def _compact_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", _text(value))
    text = re.sub(r"^标题：[^。]*。", "", text).strip()
    text = re.sub(r"^可交互元素：\d+。链接：\d+。表单：\d+。表格：\d+。", "", text).strip()
    text = text.replace("正文：", "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _page_key_note(content: dict) -> str:
    page = content.get("page") if isinstance(content.get("page"), dict) else {}
    return _business_headline(content) or _compact_text(_text(page.get("structure_summary")), 120) or "-"


def _normalize_report_status(status: str, goal_validation_status: str, blocker_items: list[dict]) -> str:
    normalized = _text(status) or "pending"
    if normalized == "completed" and _text(goal_validation_status) == "pending":
        return "partial"
    if normalized == "completed" and blocker_items:
        return "partial"
    return normalized


def _with_action_failure_blockers(blockers: list[dict], page_payloads: list[dict]) -> list[dict]:
    combined = [dict(blocker) for blocker in blockers if isinstance(blocker, dict)]
    seen = {
        (
            _text(blocker.get("reason_type") or blocker.get("type")),
            _text(blocker.get("page_ref") or blocker.get("page")),
            _text(blocker.get("action") or blocker.get("action_target")),
        )
        for blocker in combined
    }
    for payload in page_payloads:
        content = payload.get("content") if isinstance(payload.get("content"), dict) else {}
        page = content.get("page") if isinstance(content.get("page"), dict) else {}
        for action in content.get("actions") if isinstance(content.get("actions"), list) else []:
            if not isinstance(action, dict) or _text(action.get("status")) != "failed":
                continue
            action_name = _text(action.get("element_name")) or _text(action.get("action_target")) or _text(action.get("element_id")) or _text(action.get("type")) or "动作"
            page_ref = _text(page.get("id")) or _text(page.get("url"))
            key = ("action_failed", page_ref, action_name)
            if key in seen:
                continue
            result = action.get("result") if isinstance(action.get("result"), dict) else {}
            reason = _text(result.get("error_summary")) or _text(result.get("error")) or "动作执行失败。"
            combined.append(
                {
                    "id": f"blocker-{len(combined) + 1:03d}",
                    "type": "action_failed",
                    "reason_type": "action_failed",
                    "module_key": _text(page.get("module")) or "site-entry",
                    "page_ref": page_ref,
                    "page": _text(page.get("url")),
                    "action": action_name,
                    "reason": reason,
                    "severity": "warning",
                    "impact_scope": f"{action_name} 未验证",
                    "suggested_action": "人工确认页面状态、locator 稳定性或弹层遮挡后重新探索。",
                    "evidence_path": _rel_path(payload.get("file_path")) or "logs/run.log",
                    "is_blocking": False,
                }
            )
            seen.add(key)
    return combined


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
        page_content["artifact_schema_version"] = ARTIFACT_SCHEMA_VERSION
        page_content["page"] = dict(page_content["page"])
        page_content["page"].pop("page_type", None)
        page_meta = page_content["page"]
        if not _text(page_meta.get("semantic_title")):
            page_meta["semantic_title"] = _page_display_title(page_meta)
        page_meta["module"] = _page_module_name(page_meta)
        if not isinstance(page_content.get("business_summary"), dict):
            page_content["business_summary"] = {
                "headline": _page_key_note(page_content),
                "primary_actions": _page_action_summary(page_content).split("、")
                if _page_action_summary(page_content) != "-"
                else [],
                "filters": [],
                "observed_states": [],
            }
        slug = _slugify(page_meta.get("semantic_title") or page_meta.get("title") or page_meta.get("url") or f"page-{index}")
        file_name = f"{page_meta.get('id') or f'page-{index:03d}'}-{slug}.yaml"
        payloads.append({"file_name": file_name, "content": page_content})
    return payloads


def _run_section(run: dict, summary: dict, pages: list[dict], blockers: list[dict]) -> dict:
    site_url = _mapping_get(run, "site_url", "") or _first_page_url(pages)
    return {
        "id": run["id"],
        "project_id": run["project_id"],
        "project_name": run["project_name"],
        "environment_id": run["environment_id"],
        "environment_name": run["environment_name"],
        "title": run["title"],
        "site_url": site_url,
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
    modules = summary.get("modules") if isinstance(summary.get("modules"), list) else []
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "run_id": run["id"],
        "title": "探索概览 v2",
        "status": summary["status"],
        "summary": summary["summary"],
        "goal": _mapping_get(run, "goal", ""),
        "goal_validation": goal_validation or _default_goal_validation(_mapping_get(run, "goal", "")),
        "markdown_content": summary["markdown_content"],
        "page_count": len(pages),
        "blocker_count": len(blockers),
        "modules": _summary_modules(modules, run, pages, blockers, summary["status"]),
    }


def _default_goal_validation(goal: str) -> dict:
    if goal:
        return {
            "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
            "goal": goal,
            "status": "pending",
            "summary": "目标验证尚未执行。",
            "stats": {},
            "items": [],
        }
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "goal": "",
        "status": "skipped",
        "summary": "未设置探索目标。",
        "stats": {},
        "items": [],
    }


def _summary_modules(modules: list[dict], run: dict, pages: list[dict], blockers: list[dict], status: str) -> list[dict]:
    normalized = [_normalize_summary_module(module, index) for index, module in enumerate(modules, start=1) if isinstance(module, dict)]
    if normalized:
        return normalized

    target_module = _target_module_name(run)
    page_titles = _unique_texts(
        _page_display_title(page["content"]["page"])
        for page in pages
        if isinstance(page, dict) and isinstance(page.get("content"), dict) and isinstance(page["content"].get("page"), dict)
    )
    blocking_count = sum(1 for blocker in blockers if bool(blocker.get("is_blocking", True)))
    explored = len(pages)
    planned = max(explored, 1)
    blocker_summary = _text(blockers[0].get("reason")) if blockers else "无"
    return [
        {
            "module_key": "planned-01",
            "module_name": target_module,
            "status": _module_status_from_run(status, blockers),
            "page_progress": f"{explored}/{planned}",
            "planned_page_count": planned,
            "explored_page_count": explored,
            "blocked_page_count": blocking_count,
            "action_count": sum(
                len(page["content"].get("actions")) if isinstance(page.get("content"), dict) and isinstance(page["content"].get("actions"), list) else 0
                for page in pages
                if isinstance(page, dict)
            ),
            "field_count": 0,
            "state_transition_count": 0,
            "latest_page": page_titles[-1] if page_titles else "-",
            "main_facts": "、".join(page_titles[:5]) if page_titles else "-",
            "blocker_summary": blocker_summary,
            "knowledge_base_availability": "部分可用" if status == "partial" else ("不可用" if status == "blocked" else "可用"),
            "entry_path": _mapping_get(run, "scope", "") or _first_page_url(pages),
        }
    ]


def _normalize_summary_module(module: dict, index: int) -> dict:
    module_key = _text(module.get("module_key")) or f"planned-{index:02d}"
    module_name = _text(module.get("module_name")) or _text(module.get("business_module")) or module_key
    explored = module.get("explored_page_count")
    planned = module.get("planned_page_count")
    page_progress = _text(module.get("page_progress"))
    if not page_progress and isinstance(explored, int) and isinstance(planned, int) and planned > 0:
        page_progress = f"{explored}/{planned}"
    return {
        "module_key": module_key,
        "module_name": module_name,
        "status": _text(module.get("status")) or _text(module.get("completion_status")) or "pending",
        "page_progress": page_progress or "-",
        "planned_page_count": planned,
        "explored_page_count": explored,
        "blocked_page_count": module.get("blocked_page_count"),
        "action_count": module.get("action_count"),
        "field_count": module.get("field_count"),
        "state_transition_count": module.get("state_transition_count"),
        "latest_page": _text(module.get("latest_page")) or _text(module.get("recent_page_title")),
        "main_facts": _text(module.get("main_facts")) or _text(module.get("completion_summary")),
        "blocker_summary": _text(module.get("blocker_summary")) or "无",
        "knowledge_base_availability": _text(module.get("knowledge_base_availability")) or "待确认",
        "entry_path": _text(module.get("entry_path")),
    }


def _module_status_from_run(status: str, blockers: list[dict]) -> str:
    if status == "blocked":
        return "blocked"
    if status == "partial" or blockers:
        return "partial"
    if status == "completed":
        return "completed"
    return status or "pending"


def _target_module_name(run: dict) -> str:
    scope = _text(_mapping_get(run, "scope", ""))
    if scope:
        return scope.splitlines()[0][:80]
    title = _text(_mapping_get(run, "title", ""))
    return title[:80] if title else "站点入口"


def _unique_texts(items) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        text = _text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def _graph_yaml(graph: dict) -> dict:
    return {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "nodes": graph.get("nodes") if isinstance(graph.get("nodes"), list) else [],
        "edges": graph.get("edges") if isinstance(graph.get("edges"), list) else [],
        "paths": graph.get("paths") if isinstance(graph.get("paths"), list) else [],
    }


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return slug[:40] or "page"
