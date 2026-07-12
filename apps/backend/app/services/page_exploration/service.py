"""页面探索服务层

提供页面探索的业务逻辑，包括：
- 创建和管理探索任务
- 启动探索流程
- 查询探索结果
"""

import secrets
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core import settings
from app.core.db import connect
from app.repositories import environment_repo, exploration_artifact_repo, exploration_page_repo, exploration_run_repo
from app.services.page_exploration import event_bus
from app.services.page_exploration.event_log import _publish_run_terminal_event
from app.services.page_exploration.output_registry import (
    _checkpoint_snapshot_artifact_from_event,
    _inline_list_pages,
    _list_project_page_edges,
    _register_exploration_outputs,
    _snapshot_elements_for_artifact,
)
from app.services.page_exploration.run_detail import (
    _module_shell,
    _modules_from_db_pages,
    _normalize_exploration_run_detail,
    _page_from_db_page,
    _read_recent_timeline_events,
    _refresh_module_counts,
)
from app.services.page_exploration.report_writer import (
    _exploration_completion_status,
    _read_timeline_events_from_run_dir,
    _write_exploration_report,
)
from app.services.page_exploration.runner import (
    ExplorationCancelledError,
    _agent_recursion_config,
    _astream_agent_with_timeline_events,
    _execute_exploration,
    _execute_exploration_async,
    _ensure_exploration_not_stopping,
    _exploration_agent_prompt,
    _exploration_auth_state_path,
    _exploration_lock,
    _exploration_mode_label,
    _exploration_run_is_stopping,
    _exploration_start_url,
    _finalize_cancelled_exploration_run,
    _initial_subgoal_hints,
    _invoke_agent_with_realtime_events,
    _project_id_from_run,
    _register_failed_exploration_outputs,
    _run_exploration_background,
    _running_explorations,
    _stream_chunk_parts,
)
from app.services.page_exploration.timeline_projection import _projection_chunk_to_timeline_events


CAPABILITY_ID = "page_exploration"

def create_exploration_run(
    actor,
    project_id: str,
    environment_id: str,
    title: str,
    exploration_mode: str,
    scope: str,
    goal: str = "",
    forbidden_paths: str = "",
    max_pages: int = 50,
    max_actions: int = 1000,
    timeout_minutes: int = 120,
    login_strategy: str = "skip_login",
    requirement_doc_id: str = "",
    notes: str = "",
) -> dict:
    """创建页面探索任务"""
    run_id = f"exp_{secrets.token_urlsafe(16)}"

    with connect() as db:
        if not environment_repo.belongs_to_project(db, environment_id, project_id):
            raise ValueError("所选环境不属于当前项目")
        exploration_run_repo.create(
            db,
            run_id=run_id,
            project_id=project_id,
            environment_id=environment_id,
            title=title,
            created_by=actor["id"],
            exploration_mode=exploration_mode,
            scope=scope,
            forbidden_paths=forbidden_paths,
            goal=goal,
            login_strategy=login_strategy,
            max_pages=max_pages,
            max_actions=max_actions,
            timeout_minutes=timeout_minutes,
            requirement_doc_id=requirement_doc_id,
            notes=notes,
        )

        run = exploration_run_repo.find_detail_by_id(db, run_id)

    return _normalize_exploration_run_detail(dict(run)) if run else {}


def get_exploration_run(actor, run_id: str) -> dict:
    """获取探索任务详情（适配前端期望的数据结构）"""
    with connect() as db:
        run = exploration_run_repo.find_detail_by_id(db, run_id)
        if not run:
            raise ValueError(f"探索任务不存在: {run_id}")

        pages = exploration_page_repo.list_by_run(db, run_id)
        run_dict = _normalize_exploration_run_detail(dict(run))

        modules = _modules_from_db_pages(run_dict, [dict(page) for page in pages])

        return {
            "run": run_dict,
            "artifact_schema_version": 3,
            "unsupported_artifact": False,
            "unsupported_reason": "",
            "modules": modules,
            "timeline_events": _read_recent_timeline_events(run_dict),
        }




def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def update_exploration_run(actor, run_id: str, update_data: dict) -> dict:
    """更新探索任务配置"""
    with connect() as db:
        run = exploration_run_repo.find_detail_by_id(db, run_id)
        if not run:
            raise ValueError(f"探索任务不存在: {run_id}")

        # 检查状态：只有非运行状态才能更新
        if dict(run)["status"] in ["running", "queued", "stopping"]:
            raise ValueError("探索任务正在运行，无法更新配置")

        environment_id = update_data.get("environment_id")
        if environment_id and not environment_repo.belongs_to_project(db, environment_id, run["project_id"]):
            raise ValueError("所选环境不属于当前项目")

        # 更新字段
        exploration_run_repo.update(db, run_id, **update_data)

        # 返回更新后的数据
        updated_run = exploration_run_repo.find_detail_by_id(db, run_id)
        return _normalize_exploration_run_detail(dict(updated_run)) if updated_run else {}


def start_exploration_async(actor, run_id: str) -> dict:
    """启动/重新启动探索任务（异步执行）"""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            raise ValueError(f"探索任务不存在: {run_id}")

        run_dict = dict(run)

        # running 一定不可重复启动；queued 只有在本进程已登记运行实例时才是幂等请求。
        # 新建任务和服务重启后恢复的任务都可能是 queued，但尚未真正调度。
        with _exploration_lock:
            queued_in_process = run_id in _running_explorations
        if run_dict["status"] == "running" or (
            run_dict["status"] == "queued" and queued_in_process
        ):
            return run_dict

        event_bus.clear(run_id)
        _clear_previous_exploration_outputs(run_dict)

        exploration_run_repo.reset_completion_state(db, run_id)
        exploration_run_repo.update_status(db, run_id, "queued")
        run = exploration_run_repo.find_by_id(db, run_id)
        event_bus.publish(
            run_id,
            "run_status_updated",
            {
                "status": "queued",
                "result_summary": "探索任务已进入队列。",
            },
        )

    # 在后台线程启动探索
    thread = threading.Thread(
        target=_run_exploration_background,
        args=(run_id,),
        daemon=True
    )
    thread.start()

    return dict(run) if run else {}


def stop_exploration_async(actor, run_id: str) -> dict:
    """停止探索任务"""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            raise ValueError(f"探索任务不存在: {run_id}")

        run_dict = dict(run)

        # 已终止任务直接返回
        if run_dict["status"] == "cancelled":
            return run_dict
        if run_dict["status"] == "stopping":
            return run_dict
        if run_dict["status"] not in ["running", "queued"]:
            raise ValueError(f"探索任务当前状态为 {run_dict['status']}，无法停止")

        finished_at = datetime.now(timezone.utc).isoformat()
        exploration_run_repo.update_status(
            db,
            run_id,
            "cancelled",
            finished_at=finished_at,
            result_summary="探索任务已由用户停止。",
        )

        # 设置停止标志
        with _exploration_lock:
            if run_id in _running_explorations:
                _running_explorations[run_id]["should_stop"] = True

        updated_run = exploration_run_repo.find_by_id(db, run_id)
        updated_run_dict = dict(updated_run) if updated_run else run_dict

    _publish_run_terminal_event(
        _project_id_from_run(updated_run_dict) or _project_id_from_run(run_dict),
        run_id,
        "run_cancelled",
        {
            "status": "cancelled",
            "result_summary": "探索任务已由用户停止。",
            "finished_at": finished_at,
        },
    )
    event_bus.close(run_id)

    return updated_run_dict


def _clear_previous_exploration_outputs(run: dict) -> None:
    """重新探索开始前清空上一轮展示产物，避免旧结果混入本轮。"""
    run_id = str(run.get("id") or "")
    project_id = str(run.get("project_id") or "")
    if not run_id:
        return

    artifact_root = str(run.get("artifact_root") or "").strip()
    candidates: list[Path] = []
    if artifact_root:
        root = Path(artifact_root)
        candidates.append(root)
        if not root.is_absolute():
            candidates.append(settings.PROJECT_FILE_STORAGE_ROOT / artifact_root)
            candidates.append(settings.DATA_DIR / "projects" / artifact_root)
            candidates.append(settings.DATA_DIR / artifact_root)
    if project_id:
        candidates.append(settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration" / "runs" / run_id)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if _is_run_artifact_dir(resolved, run_id) and resolved.exists() and resolved.is_dir():
            shutil.rmtree(resolved)

    with connect() as db:
        db.execute("DELETE FROM exploration_artifacts WHERE exploration_run_id = ?", (run_id,))
        db.execute("DELETE FROM exploration_blockers WHERE exploration_run_id = ?", (run_id,))
        db.execute("DELETE FROM exploration_module_coverages WHERE exploration_run_id = ?", (run_id,))
        db.execute("DELETE FROM exploration_pages WHERE exploration_run_id = ?", (run_id,))


def _is_run_artifact_dir(path: Path, run_id: str) -> bool:
    parts = path.parts
    return path.name == run_id and "page_exploration" in parts and "runs" in parts


def get_exploration_status(run_id: str) -> dict:
    """获取探索任务实时状态（用于SSE）"""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            return {}

        run_dict = dict(run)

        # 获取运行时信息
        runtime_info = {}
        with _exploration_lock:
            if run_id in _running_explorations:
                runtime_info = {
                    "current_page": _running_explorations[run_id].get("current_page"),
                    "is_stopping": _running_explorations[run_id].get("should_stop", False),
                }

        return {
            "run_id": run_id,
            "status": run_dict["status"],
            "result_summary": run_dict.get("result_summary", ""),
            "started_at": run_dict.get("started_at"),
            "finished_at": run_dict.get("finished_at"),
            "updated_at": run_dict.get("updated_at"),
            **runtime_info,
        }


def list_exploration_runs(actor, project_id: str, limit: int = 100) -> list[dict]:
    """列出项目的探索任务"""
    with connect() as db:
        runs = db.execute(
            """
            SELECT er.*,
                   p.name AS project_name,
                   pe.name AS environment_name,
                   COALESCE(sd.name, '') AS requirement_doc_title
            FROM exploration_runs er
            JOIN projects p ON p.id = er.project_id
            JOIN project_environments pe ON pe.id = er.environment_id
            LEFT JOIN source_documents sd ON sd.id = er.requirement_doc_id
            WHERE er.project_id = ?
            ORDER BY er.created_at DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [dict(r) for r in runs]


def list_all_runs(actor, project_id: str | None = None, limit: int = 100) -> list[dict]:
    """列出所有探索任务（支持全局和按项目筛选）"""
    with connect() as db:
        if project_id:
            runs = db.execute(
                """
                SELECT er.*,
                       p.name AS project_name,
                       pe.name AS environment_name,
                       COALESCE(sd.name, '') AS requirement_doc_title
                FROM exploration_runs er
                JOIN projects p ON p.id = er.project_id
                JOIN project_environments pe ON pe.id = er.environment_id
                LEFT JOIN source_documents sd ON sd.id = er.requirement_doc_id
                WHERE er.project_id = ?
                ORDER BY er.created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        else:
            runs = db.execute(
                """
                SELECT er.*,
                       p.name AS project_name,
                       pe.name AS environment_name,
                       COALESCE(sd.name, '') AS requirement_doc_title
                FROM exploration_runs er
                JOIN projects p ON p.id = er.project_id
                JOIN project_environments pe ON pe.id = er.environment_id
                LEFT JOIN source_documents sd ON sd.id = er.requirement_doc_id
                ORDER BY er.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in runs]


def list_run_pages(actor, run_id: str) -> list[dict]:
    """列出探索任务的页面"""
    with connect() as db:
        pages = exploration_page_repo.list_by_run(db, run_id)
        return [dict(p) for p in pages]


def list_project_pages(actor, project_id: str) -> list[dict]:
    """列出项目级探索页面产物。"""
    base_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration"
    parent_by_page_id = _project_page_parent_index(project_id)
    rows = []
    for page in _inline_list_pages(project_id):
        last_explored = page.get("last_explored") if isinstance(page.get("last_explored"), dict) else {}
        page_id = _string(page.get("page_id") or Path(_string(page.get("file"))).stem)
        file_name = _string(page.get("file") or f"{page_id}.yaml")
        timestamp = _string(last_explored.get("timestamp"))
        rows.append(
            {
                "id": page_id,
                "exploration_run_id": _string(last_explored.get("run_id")),
                "module_key": "",
                "title": _string(page.get("title") or page_id),
                "display_name": _string(page.get("display_name") or page_id),
                "breadcrumb": page.get("breadcrumb") if isinstance(page.get("breadcrumb"), list) else [],
                "parent_id": parent_by_page_id.get(page_id, ""),
                "url": "",
                "entry_path": _string(page.get("normalized_path") or ""),
                "structure_summary": _string(page.get("structure_summary") or ""),
                "screenshot_path": "",
                "snapshot_path": str(base_dir / "pages" / file_name),
                "trace_path": "",
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
    return rows


def clear_project_artifacts(actor, project_id: str) -> dict:
    """清空项目级探索产物文件和索引，不删除探索任务本身。"""
    with connect() as db:
        running_runs = exploration_run_repo.list_running(db, project_id)
        if running_runs:
            raise ValueError("项目下存在运行中的探索任务，无法清空产物")

        run_ids = [str(row["id"]) for row in exploration_run_repo.list_by_project(db, project_id, limit=10000)]
        if run_ids:
            placeholders = ",".join("?" for _ in run_ids)
            db.execute(f"DELETE FROM exploration_artifacts WHERE exploration_run_id IN ({placeholders})", run_ids)
            db.execute(f"DELETE FROM exploration_blockers WHERE exploration_run_id IN ({placeholders})", run_ids)
            db.execute(f"DELETE FROM exploration_module_coverages WHERE exploration_run_id IN ({placeholders})", run_ids)
            db.execute(f"DELETE FROM exploration_pages WHERE exploration_run_id IN ({placeholders})", run_ids)
            db.execute(f"UPDATE exploration_runs SET artifact_root = '', updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", run_ids)

    project_artifact_root = (settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration").resolve()
    storage_root = settings.PROJECT_FILE_STORAGE_ROOT.resolve()
    try:
        project_artifact_root.relative_to(storage_root)
    except ValueError:
        raise ValueError("项目产物路径非法")

    removed_files = 0
    if project_artifact_root.exists():
        removed_files = sum(1 for path in project_artifact_root.rglob("*") if path.is_file())
        if project_artifact_root.is_dir():
            shutil.rmtree(project_artifact_root)

    event_bus.clear(project_id)
    return {
        "project_id": project_id,
        "cleared_run_count": len(run_ids),
        "removed_file_count": removed_files,
    }


def _project_page_parent_index(project_id: str) -> dict[str, str]:
    parent_by_page_id: dict[str, str] = {}
    for edge in _list_project_page_edges(project_id):
        from_page_id = _string(edge.get("from_page_id"))
        to_page_id = _string(edge.get("to_page_id"))
        if from_page_id and to_page_id and from_page_id != to_page_id:
            parent_by_page_id[to_page_id] = from_page_id
    return parent_by_page_id


def list_run_artifacts(actor, run_id: str) -> list[dict]:
    """列出探索任务的产物"""
    with connect() as db:
        artifacts = exploration_artifact_repo.list_by_run(db, run_id)
        return [dict(a) for a in artifacts]


def get_exploration_report(actor, run_id: str) -> dict:
    """获取探索报告"""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            raise ValueError(f"探索任务不存在: {run_id}")

        run_dict = dict(run)
        artifact_root = run_dict.get("artifact_root", "")

        # 查找报告文件
        report_content = ""
        if artifact_root:
            report_path = Path(artifact_root) / "report.md"
            if report_path.exists():
                report_content = report_path.read_text(encoding="utf-8")
            else:
                report_content = f"# 探索报告\n\n{run_dict.get('result_summary', '暂无报告内容')}"
        else:
            report_content = f"# 探索报告\n\n{run_dict.get('result_summary', '探索任务尚未执行或未生成报告')}"

        return {
            "run_id": run_id,
            "title": f"{run_dict['title']} - 探索报告",
            "markdown_content": report_content,
            "change_summary": "",
            "artifact_schema_version": 3,
            "unsupported_artifact": False,
            "unsupported_reason": "",
        }


def get_artifact_content(actor, artifact_id: str) -> str:
    """获取产物内容"""
    with connect() as db:
        artifact = exploration_artifact_repo.find_by_id(db, artifact_id)
        if not artifact:
            raise ValueError(f"产物不存在: {artifact_id}")

        file_path = Path(artifact["file_path"])
        if not file_path.exists():
            raise ValueError(f"产物文件不存在: {file_path}")

        return file_path.read_text(encoding="utf-8")


def get_project_page_yaml_content(actor, project_id: str, page_id: str) -> dict:
    """获取项目级页面 YAML 产物内容。"""
    base_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration"
    pages_dir = (base_dir / "pages").resolve()
    page_path = (pages_dir / f"{page_id}.yaml").resolve()

    try:
        page_path.relative_to(pages_dir)
    except ValueError:
        raise ValueError("页面产物路径非法")
    if not page_path.exists() or not page_path.is_file():
        raise ValueError(f"页面产物不存在: {page_id}")

    return {
        "page_id": page_id,
        "file_name": page_path.name,
        "file_path": str(page_path),
        "content": page_path.read_text(encoding="utf-8"),
    }


def delete_exploration_run(actor, run_id: str) -> None:
    """删除探索任务"""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            raise ValueError(f"探索任务不存在: {run_id}")

        # 删除任务（级联删除相关记录）
        exploration_run_repo.delete(db, run_id)


def list_all_artifacts(actor, project_id: str | None = None, run_id: str | None = None) -> list[dict]:
    """列出所有探索产物（支持按项目和任务筛选）

    Args:
        actor: 当前用户
        project_id: 项目ID（可选）
        run_id: 探索任务ID（可选）

    Returns:
        产物列表，每个产物包含：
        - id: 产物ID
        - run_id: 所属探索任务ID
        - run_title: 所属探索任务标题
        - project_id: 所属项目ID
        - project_name: 所属项目名称
        - artifact_type: 产物类型（page_yaml/accessibility/structure/log/report）
        - file_path: 文件路径
        - file_name: 文件名
        - file_size: 文件大小（字节）
        - created_at: 创建时间
    """
    with connect() as db:
        # 如果指定了run_id，直接返回该任务的产物
        if run_id:
            run = exploration_run_repo.find_by_id(db, run_id)
            if not run:
                raise ValueError(f"探索任务不存在: {run_id}")

            artifacts = exploration_artifact_repo.list_by_run(db, run_id)
            run_dict = dict(run)

            return [
                {
                    **dict(artifact),
                    "run_title": run_dict.get("title", ""),
                    "project_id": run_dict.get("project_id", ""),
                    "project_name": run_dict.get("project_name", ""),
                }
                for artifact in artifacts
            ]

        # 否则，根据project_id筛选
        if project_id:
            runs = exploration_run_repo.list_by_project(db, project_id, limit=500)
        else:
            runs = exploration_run_repo.list_all(db, project_id=None, limit=500)

        # 收集所有产物
        all_artifacts = []
        for run in runs:
            run_dict = dict(run)
            run_id = run_dict["id"]
            artifacts = exploration_artifact_repo.list_by_run(db, run_id)

            for artifact in artifacts:
                all_artifacts.append({
                    **dict(artifact),
                    "run_title": run_dict.get("title", ""),
                    "project_id": run_dict.get("project_id", ""),
                    "project_name": run_dict.get("project_name", ""),
                })

        # 按创建时间倒序排序
        all_artifacts.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return all_artifacts


def recover_interrupted_exploration_runs(*, project_id: str | None = None) -> None:
    """恢复被中断的探索任务

    当服务重启时，将所有处于运行状态（running/queued/stopping）的探索任务
    标记为已中断（interrupted），因为内存中的后台任务已经丢失。

    Args:
        project_id: 可选的项目ID，只恢复该项目的任务
    """
    from app.services import operation_log_service

    with connect() as db:
        # 查找所有运行中的探索任务
        runs = exploration_run_repo.list_running(db, project_id)
        recovered_runs = [dict(row) for row in runs]

        # 将这些任务标记为已中断
        for row in runs:
            exploration_run_repo.update_status(
                db,
                row["id"],
                status="interrupted",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary="服务已重启，探索任务已中断。",
            )

    # 记录操作日志
    for row in recovered_runs:
        try:
            operation_log_service.record_task_event(
                module="exploration",
                action="interrupt_exploration",
                object_type="exploration_run",
                object_id=row["id"],
                object_name=row["title"],
                project_id=row["project_id"],
                actor_id="system",
                actor_name="系统",
                source="system",
                result="failed",
                failure_reason="服务已重启，内存中的探索后台任务已中断",
                summary="探索任务已中断。",
                after={"status": "interrupted", "reason": "startup_recovered"},
                task_id=row["id"],
            )
        except Exception:
            # 如果记录日志失败，不影响恢复流程
            pass
