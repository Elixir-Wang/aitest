from __future__ import annotations

import json
import shutil
import subprocess
import traceback
from pathlib import Path
import secrets
import time

from app.core.settings import (
    PLAYWRIGHT_BROWSER_CHANNEL,
    PLAYWRIGHT_CLI_COMMAND,
    PLAYWRIGHT_CLI_TIMEOUT_SECONDS,
    PLAYWRIGHT_RUNNER_DIR,
)
from app.core.db import connect
from app.core.storage import PROJECT_FILE_STORAGE_ROOT, store_path
from app.repositories import exploration_repo
from app.services import exploration_service, operation_log_service


def run_exploration(run_id: str) -> None:
    try:
        _run_exploration(run_id)
    except Exception as error:
        _mark_run_failed_after_unhandled_error(run_id, error)


def _run_exploration(run_id: str) -> None:
    start_event = None
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return
        if run["status"] in {"stopping", "cancelled"}:
            _mark_cancelled(db, run, "用户已停止探索，任务未继续执行。")
            return
        if run["status"] != "queued":
            return
        artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
        _ensure_artifact_dirs(artifact_root)
        exploration_repo.clear_run_outputs(db, run_id)
        exploration_service.seed_planned_modules_for_run(db, run)
        exploration_repo.update_run_state(
            db,
            run_id,
            status="running",
            artifact_root=store_path(artifact_root) or "",
            result_summary="站点探索已开始，正在调用 Playwright CLI。",
            started=True,
        )
        start_event = (
            run,
            {
                "action": "start",
                "result": "success",
                "summary": f"站点探索开始执行：{run['title']}",
                "after": {"status": "running", "artifact_root": store_path(artifact_root) or ""},
            },
        )

    if start_event:
        _record_runner_event(start_event[0], **start_event[1])

    result = _execute_playwright_probe(run_id, artifact_root)

    finish_event = None
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return
        if run["status"] == "stopping":
            _mark_cancelled(db, run, "用户已停止探索，已保留停止前生成的日志和产物。")
            finish_event = (
                run,
                {
                    "action": "finish",
                    "result": "cancelled",
                    "summary": f"站点探索已停止：{run['title']}",
                    "after": {"status": "cancelled", "result_summary": "用户已停止探索，已保留停止前生成的日志和产物。"},
                    "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                },
            )
        else:
            exploration_repo.clear_run_outputs(db, run_id)
            if result["status"] == "cancelled":
                _mark_cancelled(db, run, result["summary"])
                finish_event = (
                    run,
                    {
                        "action": "finish",
                        "result": "cancelled",
                        "summary": f"站点探索已停止：{run['title']}，{result['summary']}",
                        "after": {"status": "cancelled", "result_summary": result["summary"], "log_path": result.get("log_path", "")},
                        "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                    },
                )
            elif result["status"] == "blocked":
                _persist_blocked_result(db, run, artifact_root, result)
                finish_event = (
                    run,
                    {
                        "action": "finish",
                        "result": "failed",
                        "summary": f"站点探索阻塞：{run['title']}，{result['summary']}",
                        "failure_reason": result.get("failure_detail", result["summary"]),
                        "after": {"status": "blocked", "result_summary": result["summary"], "log_path": result.get("log_path", "")},
                        "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                    },
                )
            else:
                _persist_completed_result(db, run, artifact_root, result)
                finish_event = (
                    run,
                    {
                        "action": "finish",
                        "result": "success",
                        "summary": f"站点探索执行完成：{run['title']}，{result['summary']}",
                        "after": {"status": "completed", "result_summary": result["summary"], "log_path": result.get("log_path", "")},
                        "artifact_path": [result.get("log_path", "")] if result.get("log_path") else [],
                    },
                )

    if finish_event:
        _record_runner_event(finish_event[0], **finish_event[1])


def _mark_run_failed_after_unhandled_error(run_id: str, error: Exception) -> None:
    error_detail = f"{type(error).__name__}: {error}"
    summary = f"探索执行异常中断：{error_detail[:500]}"
    try:
        with connect() as db:
            run = exploration_repo.find_by_id(db, run_id)
            if not run or run["status"] not in {"queued", "running", "stopping", "waiting_human"}:
                return
            artifact_root = PROJECT_FILE_STORAGE_ROOT / run["project_id"] / "exploration" / run_id
            _ensure_artifact_dirs(artifact_root)
            log_path = artifact_root / "logs" / "run.log"
            log_path.write_text(
                "\n".join(
                    [
                        "Unhandled site exploration error.",
                        error_detail,
                        traceback.format_exc(),
                    ]
                ).strip()
                + "\n",
                encoding="utf-8",
            )
            exploration_repo.update_run_state(
                db,
                run_id,
                status="blocked",
                artifact_root=store_path(artifact_root) or run["artifact_root"],
                result_summary=summary,
                finished=True,
            )
            failure_event = (
                run,
                {
                    "action": "finish",
                    "result": "failed",
                    "summary": f"站点探索异常中断：{run['title']}，{summary}",
                    "failure_reason": summary,
                    "after": {
                        "status": "blocked",
                        "result_summary": summary,
                        "log_path": store_path(log_path) or "",
                    },
                    "artifact_path": [store_path(log_path) or ""],
                },
            )
    except Exception:
        return
    _record_runner_event(failure_event[0], **failure_event[1])


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

    page_url, forbidden_paths = _safe_run_context_from_db(run_id)
    exploration_result = _run_site_explorer(page_url, artifact_root, forbidden_paths)
    if exploration_result["status"] == "blocked":
        log_path.write_text(exploration_result["log"], encoding="utf-8")
        failure_detail = _failure_detail_from_log(exploration_result["log"])
        summary = _summary_with_failure_detail(exploration_result["summary"], failure_detail)
        return {
            "status": "blocked",
            "summary": summary,
            "reason_type": "browser_smoke_failed",
            "failure_detail": failure_detail,
            "suggested_action": _suggested_action_with_failure_detail(
                "检查 Playwright 浏览器安装、浏览器 channel 配置、网络连通性和目标站点可访问性后重试。",
                failure_detail,
            ),
            "log_path": store_path(log_path) or "",
        }

    log_path.write_text(exploration_result["log"], encoding="utf-8")
    exploration_result["log_path"] = store_path(log_path) or ""
    return exploration_result


def _playwright_cli_available() -> bool:
    if not _npx_command_path():
        return False
    if not PLAYWRIGHT_RUNNER_DIR.exists():
        return False
    try:
        completed = subprocess.run(
            _playwright_command("--version"),
            check=False,
            capture_output=True,
            cwd=PLAYWRIGHT_RUNNER_DIR,
            text=True,
            timeout=PLAYWRIGHT_CLI_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and "Version" in completed.stdout


def _playwright_command(*args: str) -> list[str]:
    return [_npx_command_path() or "npx", "--no-install", PLAYWRIGHT_CLI_COMMAND, *args]


def _npx_command_path() -> str | None:
    return shutil.which("npx")


def _capture_entry_screenshot(page_url: str, screenshot_path: Path) -> dict:
    command = _playwright_command("screenshot")
    if PLAYWRIGHT_BROWSER_CHANNEL:
        command.extend(["--channel", PLAYWRIGHT_BROWSER_CHANNEL])
    command.extend([page_url, str(screenshot_path)])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            cwd=PLAYWRIGHT_RUNNER_DIR,
            text=True,
            timeout=PLAYWRIGHT_CLI_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "status": "blocked",
            "summary": "Playwright CLI 启动浏览器访问站点失败。",
            "log": f"Playwright smoke test failed: {error}\n",
        }
    if completed.returncode != 0:
        return {
            "status": "blocked",
            "summary": "Playwright CLI 启动浏览器访问站点失败。",
            "log": "\n".join([completed.stdout, completed.stderr]).strip() + "\n",
        }
    return {"status": "completed", "summary": "站点入口截图生成成功。", "log": completed.stdout}


def _run_site_explorer(page_url: str, artifact_root: Path, forbidden_paths: str = "") -> dict:
    script_path = PLAYWRIGHT_RUNNER_DIR / "site-explorer.mjs"
    command = ["node", str(script_path), page_url, str(artifact_root), PLAYWRIGHT_BROWSER_CHANNEL, forbidden_paths]
    timeout_seconds = max(PLAYWRIGHT_CLI_TIMEOUT_SECONDS, 30)
    try:
        process = subprocess.Popen(
            command,
            cwd=PLAYWRIGHT_RUNNER_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        started_at = time.monotonic()
        while process.poll() is None:
            if _run_cancel_requested(artifact_root):
                process.terminate()
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                return {
                    "status": "cancelled",
                    "summary": "用户已停止探索。",
                    "log": "\n".join(["Playwright site exploration cancelled by user.", stdout, stderr]).strip() + "\n",
                }
            if time.monotonic() - started_at > timeout_seconds:
                process.kill()
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(command, timeout_seconds, output=stdout, stderr=stderr)
            time.sleep(1)
        stdout, stderr = process.communicate()
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "status": "blocked",
            "summary": "Playwright 探索脚本执行失败。",
            "log": f"Playwright site exploration failed: {error}\n",
        }
    if process.returncode != 0:
        return {
            "status": "blocked",
            "summary": "Playwright 探索脚本执行失败。",
            "log": "\n".join([stdout, stderr]).strip() + "\n",
        }
    try:
        payload = json.loads(stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        return {
            "status": "blocked",
            "summary": "Playwright 探索脚本未返回有效结构化结果。",
            "log": f"{stdout}\n{stderr}\nJSON parse error: {error}\n",
        }
    payload["log"] = "\n".join(
        [
            "Playwright site exploration completed.",
            f"url={page_url}",
            stderr.strip(),
            stdout.strip(),
        ]
    ).strip() + "\n"
    return payload


def _run_cancel_requested(artifact_root: Path) -> bool:
    run_id = artifact_root.name
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        return bool(run and run["status"] == "stopping")


def _safe_run_context_from_db(run_id: str) -> tuple[str, str]:
    with connect() as db:
        run = exploration_repo.find_by_id(db, run_id)
        if not run:
            return "about:blank", ""
        return _safe_site_url(run) or "about:blank", str(run["forbidden_paths"] or "")


def _record_runner_event(
    run,
    *,
    action: str,
    result: str,
    summary: str,
    after: dict,
    artifact_path: list[str] | None = None,
    failure_reason: str = "",
) -> None:
    operation_log_service.record_task_event(
        module="exploration",
        action=action,
        object_type="exploration_run",
        object_id=run["id"],
        object_name=run["title"],
        project_id=run["project_id"],
        actor_id="system",
        actor_name="系统",
        source="runner",
        result=result,
        failure_reason=failure_reason,
        summary=summary,
        after=after,
        task_id=run["id"],
        artifact_path=artifact_path or [],
    )


def _mark_cancelled(db, run, summary: str) -> None:
    exploration_repo.update_run_state(
        db,
        run["id"],
        status="cancelled",
        result_summary=summary,
        finished=True,
    )


def _failure_detail_from_log(log: str) -> str:
    for raw_line in log.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        return line[:500]
    return ""


def _summary_with_failure_detail(summary: str, failure_detail: str) -> str:
    if not failure_detail or failure_detail in summary:
        return summary
    return f"{summary} 真实原因：{failure_detail}"


def _suggested_action_with_failure_detail(suggested_action: str, failure_detail: str) -> str:
    if not failure_detail:
        return suggested_action
    return f"{suggested_action} 真实失败原因：{failure_detail}"


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
    markdown_path = artifact_root / "documents" / "exploration-v1.md"
    output_path = artifact_root / "outputs" / "result.json"
    page_url = _safe_site_url(run)
    pages = _result_pages(result)
    result_status, coverage_gap_blocker = _completion_status_with_coverage_gate(run, result, pages)
    page_id_by_url: dict[str, str] = {}
    payload_pages = []
    for page in pages:
        page_id = _id("exppage")
        page_id_by_url[page["url"]] = page_id
        payload_pages.append(
            {
                "id": page_id,
                "module_key": module_key,
                "title": page["title"],
                "url": page["url"],
                "entry_path": page["entry_path"],
                "structure_summary": page["structure_summary"],
                "screenshot_path": _stored_artifact_path(artifact_root, page.get("screenshot_path", "")),
                "snapshot_path": _stored_artifact_path(artifact_root, page.get("snapshot_path", "")),
            }
        )
    payload_elements = [
        {
            "module_key": module_key,
            "page_id": page_id_by_url.get(element.get("page_url", "")),
            "element_name": element.get("name") or element.get("locator") or "未命名元素",
            "element_type": element.get("type") or "element",
            "recommended_locator": element.get("locator") or "",
            "fallback_locator": element.get("href") or "",
            "stability_note": "由 Playwright 真实页面探索抽取，仍需在生成自动化脚本前按目标环境复验稳定性。",
            "source_ref": element.get("page_url") or page_url,
        }
        for element in result.get("elements", [])
    ]
    screenshot_path = payload_pages[0]["screenshot_path"] if payload_pages else None
    markdown = _render_markdown(
        run=run,
        status=result_status,
        summary=result["summary"],
        module_status="partial" if result_status == "partial" else "completed",
        page_url=page_url,
        blocker="",
        pages=payload_pages,
        elements=payload_elements,
    )
    result_blockers = list(result.get("blockers", []))
    if coverage_gap_blocker:
        result_blockers.append(coverage_gap_blocker)
    payload_blockers = [
        {
            "module_key": module_key,
            "page_ref": blocker.get("page_ref") or page_url,
            "reason_type": blocker.get("reason_type") or "exploration_gap",
            "reason": blocker.get("reason") or "探索过程中存在未覆盖项。",
            "evidence_path": result["log_path"],
            "suggested_action": blocker.get("suggested_action") or "人工确认后重新探索。",
        }
        for blocker in result_blockers
    ]
    payload = {
        "status": result_status,
        "summary": result["summary"],
        "modules": [
            {
                "module_key": module_key,
                "module_name": _module_name(run),
                "completion_status": "partial" if result_status == "partial" else "completed",
            }
        ],
        "pages": payload_pages,
        "elements": payload_elements,
        "blockers": payload_blockers,
        "artifacts": [
            {"artifact_type": "log", "file_path": result["log_path"]},
            {"artifact_type": "screenshot", "file_path": screenshot_path or ""},
        ],
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
        planned_page_count=0 if result_status == "partial" and coverage_gap_blocker else max(len(payload_pages), 1),
        explored_page_count=len(payload_pages),
        blocked_page_count=1 if coverage_gap_blocker else 0,
        action_count=int(result.get("action_count") or 0),
        field_count=int(result.get("field_count") or 0),
        state_transition_count=int(result.get("state_transition_count") or 0),
        completion_status="partial" if result_status == "partial" else "completed",
        completion_summary=result["summary"],
    )
    for page in payload_pages:
        exploration_repo.create_page(
            db,
            page_id=page["id"],
            exploration_run_id=run["id"],
            module_key=module_key,
            title=page["title"],
            url=page["url"],
            entry_path=page["entry_path"],
            structure_summary=page["structure_summary"],
            screenshot_path=page["screenshot_path"],
            snapshot_path=page["snapshot_path"],
        )
    for element in payload_elements:
        exploration_repo.create_element(
            db,
            element_id=_id("expelem"),
            exploration_run_id=run["id"],
            page_id=element["page_id"],
            module_key=module_key,
            element_name=element["element_name"],
            element_type=element["element_type"],
            recommended_locator=element["recommended_locator"],
            fallback_locator=element["fallback_locator"],
            stability_note=element["stability_note"],
            source_ref=element["source_ref"],
        )
    for blocker in payload_blockers:
        exploration_repo.create_blocker(
            db,
            blocker_id=_id("expblk"),
            exploration_run_id=run["id"],
            module_key=module_key,
            page_ref=blocker["page_ref"],
            reason_type=blocker["reason_type"],
            reason=blocker["reason"],
            evidence_path=blocker["evidence_path"],
            impact_scope="站点探索覆盖完整性",
            suggested_action=blocker["suggested_action"],
            is_blocking=False,
        )
    _persist_common_artifacts(db, run["id"], markdown_path, output_path, result["log_path"], screenshot_path)
    exploration_repo.update_run_state(
        db,
        run["id"],
        status=result_status,
        result_summary=result["summary"],
        finished=True,
    )


def _completion_status_with_coverage_gate(run, result: dict, pages: list[dict]) -> tuple[str, dict | None]:
    status = str(result.get("status") or "completed")
    if status != "completed" or not _is_full_site_scope(run):
        return status, None
    if len(pages) != 1:
        return status, None

    discovery = result.get("discovery") if isinstance(result.get("discovery"), dict) else {}
    discovered_link_count = int(discovery.get("discovered_link_count") or 0)
    same_origin_link_count = int(discovery.get("same_origin_link_count") or 0)
    action_count = int(result.get("action_count") or 0)
    state_transition_count = int(result.get("state_transition_count") or 0)
    has_existing_blocker = bool(result.get("blockers"))
    if has_existing_blocker or discovered_link_count > 0 or same_origin_link_count > 0 or action_count > 0 or state_transition_count > 0:
        return status, None

    reason = str(discovery.get("reason_if_stopped") or "探索范围要求覆盖全部站点，但本次仅覆盖入口页，未发现可继续递归探索的页面入口。")
    return "partial", {
        "page_ref": pages[0].get("url") or _safe_site_url(run),
        "reason_type": "coverage_gap",
        "reason": f"仅覆盖入口页：{reason}",
        "suggested_action": "补充目录解析、搜索探测、站点地图或人工入口清单后重新探索。",
    }


def _is_full_site_scope(run) -> bool:
    scope = str(run["scope"] or "").lower()
    full_site_terms = ("全部站点", "全部内容", "所有内容", "所有页面", "全站", "遍历")
    return any(term in scope for term in full_site_terms)


def _persist_common_artifacts(
    db,
    run_id: str,
    markdown_path: Path,
    output_path: Path,
    log_path: str,
    screenshot_path: str | None = None,
) -> None:
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
    if screenshot_path:
        exploration_repo.create_artifact(
            db,
            artifact_id=_id("expart"),
            exploration_run_id=run_id,
            artifact_type="screenshot",
            file_path=screenshot_path,
            title="入口页截图",
            summary="Playwright 访问站点入口后生成的截图。",
        )


def _render_markdown(
    *,
    run,
    status: str,
    summary: str,
    module_status: str,
    page_url: str,
    blocker: str,
    pages: list[dict] | None = None,
    elements: list[dict] | None = None,
) -> str:
    blocker_block = f"\n## 阻塞项\n\n- {blocker}\n" if blocker else "\n## 阻塞项\n\n- 无\n"
    page_lines = ["## 页面事实", ""]
    if pages:
        for page in pages:
            page_lines.extend(
                [
                    f"### {page['title'] or page['url']}",
                    "",
                    f"- URL：{page['url']}",
                    f"- 结构摘要：{page['structure_summary']}",
                    f"- 截图：{page['screenshot_path'] or '-'}",
                    f"- 快照：{page['snapshot_path'] or '-'}",
                    "",
                ]
            )
    else:
        page_lines.extend([f"- 起始页面：{page_url or '未完成访问'}", ""])
    element_lines = ["## 元素事实", ""]
    if elements:
        for element in elements[:80]:
            element_lines.append(
                f"- {element['element_type']}｜{element['element_name']}｜{element['recommended_locator'] or '-'}"
            )
    else:
        element_lines.append("- 未识别可交互元素")
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
            *page_lines,
            *element_lines,
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


def _result_pages(result: dict) -> list[dict]:
    pages = result.get("pages") or []
    return [
        {
            "title": str(page.get("title") or page.get("url") or "未命名页面"),
            "url": str(page.get("url") or ""),
            "entry_path": str(page.get("entry_path") or page.get("url") or ""),
            "structure_summary": str(page.get("structure_summary") or "未生成页面结构摘要。"),
            "screenshot_path": str(page.get("screenshot_path") or ""),
            "snapshot_path": str(page.get("snapshot_path") or ""),
        }
        for page in pages
        if page.get("url")
    ]


def _stored_artifact_path(artifact_root: Path, relative_path: str) -> str:
    if not relative_path:
        return ""
    return store_path(artifact_root / relative_path) or ""


def _id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(8)}"
