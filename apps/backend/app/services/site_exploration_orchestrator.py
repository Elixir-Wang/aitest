from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
import secrets

from app.core.db import connect
from app.core.storage import PROJECT_FILE_STORAGE_ROOT, store_path
from app.repositories import exploration_repo


def run_exploration(run_id: str) -> None:
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return
        artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
        _ensure_artifact_dirs(artifact_root)
        exploration_repo.clear_run_outputs(db, run_id)
        exploration_repo.update_run_state(
            db,
            run_id,
            status="running",
            artifact_root=store_path(artifact_root) or "",
            result_summary="站点探索已开始，正在调用 Playwright CLI。",
            started=True,
        )

    result = _execute_playwright_probe(run_id, artifact_root)

    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return
        exploration_repo.clear_run_outputs(db, run_id)
        if result["status"] == "blocked":
            _persist_blocked_result(db, run, artifact_root, result)
            return
        _persist_completed_result(db, run, artifact_root, result)


def _ensure_artifact_dirs(root: Path) -> None:
    for name in ("storage", "traces", "screenshots", "snapshots", "videos", "documents", "outputs", "logs"):
        (root / name).mkdir(parents=True, exist_ok=True)


def _execute_playwright_probe(run_id: str, artifact_root: Path) -> dict:
    log_path = artifact_root / "logs" / "run.log"
    if not _playwright_cli_available():
        message = "未检测到可用 Playwright CLI，无法执行真实站点探索。"
        log_path.write_text(f"{message}\n", encoding="utf-8")
        return {
            "status": "blocked",
            "summary": message,
            "reason_type": "runner_unavailable",
            "suggested_action": "在后端运行环境安装 Playwright，并执行 npx playwright install 后重试。",
            "log_path": store_path(log_path) or "",
        }

    # 第一版只执行 CLI 可用性验证和产物目录初始化。深度页面遍历后续在该边界内替换为真实脚本。
    message = "Playwright CLI 可用，已完成第一版探索执行骨架验证。"
    log_path.write_text(f"{message}\nrun_id={run_id}\n", encoding="utf-8")
    return {
        "status": "completed",
        "summary": message,
        "log_path": store_path(log_path) or "",
    }


def _playwright_cli_available() -> bool:
    if not shutil.which("npx"):
        return False
    try:
        completed = subprocess.run(
            ["npx", "playwright", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and "Version" in completed.stdout


def _persist_blocked_result(db, run, artifact_root: Path, result: dict) -> None:
    module_key = _module_key(run)
    markdown_path = artifact_root / "documents" / "exploration-v1.md"
    output_path = artifact_root / "outputs" / "result.json"
    markdown = _render_markdown(
        run=run,
        status="blocked",
        summary=result["summary"],
        module_status="blocked",
        page_url="",
        blocker=result["summary"],
    )
    payload = {
        "status": "blocked",
        "summary": result["summary"],
        "modules": [{"module_key": module_key, "module_name": _module_name(run), "completion_status": "blocked"}],
        "pages": [],
        "elements": [],
        "blockers": [
            {
                "module_key": module_key,
                "page_ref": run["environment_name"],
                "reason_type": result["reason_type"],
                "reason": result["summary"],
                "evidence_path": result["log_path"],
                "suggested_action": result["suggested_action"],
            }
        ],
        "artifacts": [{"artifact_type": "log", "file_path": result["log_path"]}],
    }
    markdown_path.write_text(markdown, encoding="utf-8")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    exploration_repo.create_module_coverage(
        db,
        coverage_id=_id("expcov"),
        exploration_run_id=run["id"],
        module_key=module_key,
        module_name=_module_name(run),
        entry_path=run["scope"] or run["environment_name"],
        planned_page_count=1,
        explored_page_count=0,
        blocked_page_count=1,
        action_count=0,
        field_count=0,
        state_transition_count=0,
        completion_status="blocked",
        completion_summary=result["summary"],
    )
    exploration_repo.create_blocker(
        db,
        blocker_id=_id("expblk"),
        exploration_run_id=run["id"],
        module_key=module_key,
        page_ref=run["environment_name"],
        reason_type=result["reason_type"],
        reason=result["summary"],
        evidence_path=result["log_path"],
        impact_scope="站点探索、候选需求、知识库、用例、自动化",
        suggested_action=result["suggested_action"],
    )
    _persist_common_artifacts(db, run["id"], markdown_path, output_path, result["log_path"])
    exploration_repo.update_run_state(
        db,
        run["id"],
        status="blocked",
        result_summary=result["summary"],
        finished=True,
    )


def _persist_completed_result(db, run, artifact_root: Path, result: dict) -> None:
    module_key = _module_key(run)
    page_id = _id("exppage")
    markdown_path = artifact_root / "documents" / "exploration-v1.md"
    output_path = artifact_root / "outputs" / "result.json"
    page_url = _safe_site_url(run)
    markdown = _render_markdown(
        run=run,
        status="completed",
        summary=result["summary"],
        module_status="completed",
        page_url=page_url,
        blocker="",
    )
    payload = {
        "status": "completed",
        "summary": result["summary"],
        "modules": [{"module_key": module_key, "module_name": _module_name(run), "completion_status": "completed"}],
        "pages": [{"id": page_id, "module_key": module_key, "title": run["environment_name"], "url": page_url}],
        "elements": [
            {
                "module_key": module_key,
                "element_name": "页面主体",
                "element_type": "page",
                "recommended_locator": "body",
                "fallback_locator": "",
                "stability_note": "第一版执行骨架只验证 Playwright CLI 可用性，后续深度探索补充稳定 locator。",
            }
        ],
        "blockers": [],
        "artifacts": [{"artifact_type": "log", "file_path": result["log_path"]}],
    }
    markdown_path.write_text(markdown, encoding="utf-8")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    exploration_repo.create_module_coverage(
        db,
        coverage_id=_id("expcov"),
        exploration_run_id=run["id"],
        module_key=module_key,
        module_name=_module_name(run),
        entry_path=run["scope"] or page_url,
        planned_page_count=1,
        explored_page_count=1,
        blocked_page_count=0,
        action_count=0,
        field_count=0,
        state_transition_count=0,
        completion_status="completed",
        completion_summary=result["summary"],
    )
    exploration_repo.create_page(
        db,
        page_id=page_id,
        exploration_run_id=run["id"],
        module_key=module_key,
        title=run["environment_name"],
        url=page_url,
        entry_path=run["scope"] or page_url,
        structure_summary="第一版探索执行骨架已验证 Playwright CLI，深度页面结构将在后续 Playwright 遍历脚本中补齐。",
    )
    exploration_repo.create_element(
        db,
        element_id=_id("expelem"),
        exploration_run_id=run["id"],
        page_id=page_id,
        module_key=module_key,
        element_name="页面主体",
        element_type="page",
        recommended_locator="body",
        fallback_locator="",
        stability_note="第一版仅作为 Playwright CLI 可用性验证 locator，不能作为自动化代码生成的稳定元素来源。",
        source_ref=page_url,
    )
    _persist_common_artifacts(db, run["id"], markdown_path, output_path, result["log_path"])
    exploration_repo.update_run_state(
        db,
        run["id"],
        status="completed",
        result_summary=result["summary"],
        finished=True,
    )


def _persist_common_artifacts(db, run_id: str, markdown_path: Path, output_path: Path, log_path: str) -> None:
    exploration_repo.create_document_version(
        db,
        version_id=_id("expdocv"),
        exploration_run_id=run_id,
        version_no=1,
        markdown_path=store_path(markdown_path) or "",
        change_summary="创建第一版探索文档。",
        created_by="system",
    )
    for artifact_type, path_value, title in (
        ("document", store_path(markdown_path) or "", "探索文档 v1"),
        ("json", store_path(output_path) or "", "探索结构化结果"),
        ("log", log_path, "探索执行日志"),
    ):
        exploration_repo.create_artifact(
            db,
            artifact_id=_id("expart"),
            exploration_run_id=run_id,
            artifact_type=artifact_type,
            file_path=path_value,
            title=title,
            summary="站点探索第一版产物。",
        )


def _render_markdown(*, run, status: str, summary: str, module_status: str, page_url: str, blocker: str) -> str:
    blocker_block = f"\n## 阻塞项\n\n- {blocker}\n" if blocker else "\n## 阻塞项\n\n- 无\n"
    return "\n".join(
        [
            f"# {run['title']} 探索文档",
            "",
            "## 探索摘要",
            "",
            f"- 状态：{status}",
            f"- 项目：{run['project_name']}",
            f"- 环境：{run['environment_name']}",
            f"- 站点：{page_url or '-'}",
            f"- 说明：{summary}",
            "",
            "## 模块覆盖矩阵",
            "",
            "| 模块 | 状态 | 说明 |",
            "| --- | --- | --- |",
            f"| {_module_name(run)} | {module_status} | {summary} |",
            "",
            "## 页面事实",
            "",
            f"- 起始页面：{page_url or '未完成访问'}",
            "- 第一版仅完成 Playwright CLI 执行骨架和产物链路验证，深度页面结构将在后续遍历脚本中补齐。",
            blocker_block,
            "## 附件",
            "",
            "- 执行日志：logs/run.log",
            "",
        ]
    )


def _module_name(run) -> str:
    scope = str(run["scope"] or "").strip()
    return scope.splitlines()[0][:80] if scope else "站点入口"


def _module_key(run) -> str:
    return "site-entry"


def _safe_site_url(run) -> str:
    return str(run["environment_site_url"] if "environment_site_url" in run.keys() else "")


def _id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"
