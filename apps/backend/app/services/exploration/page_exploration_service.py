"""页面探索服务层

提供页面探索的业务逻辑，包括：
- 创建和管理探索任务
- 启动探索流程
- 查询探索结果
"""

import asyncio
import hashlib
import inspect
import json
import secrets
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from app.core import settings
from app.core.db import connect
from app.core.environment_auth_state import auth_state_path, auth_state_summary
from app.repositories import exploration_artifact_repo, exploration_page_repo, exploration_run_repo
from app.services.exploration import event_bus


CAPABILITY_ID = "page_exploration"

# 全局存储运行中的探索任务状态
_running_explorations: Dict[str, Dict[str, Any]] = {}
_exploration_lock = threading.Lock()


class ExplorationCancelledError(Exception):
    """Raised when a user-requested exploration stop is observed."""


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

        modules = _modules_from_db_pages(run_dict, [dict(page) for page in pages]) if pages else _modules_from_artifacts(run_dict)

        return {
            "run": run_dict,
            "artifact_schema_version": 2 if modules else 1,
            "unsupported_artifact": False,
            "unsupported_reason": "",
            "modules": modules,
            "timeline_events": _read_recent_timeline_events(run_dict),
        }


def _read_recent_timeline_events(run: dict, *, limit: int = 200) -> list[dict]:
    """Read persisted UI timeline events for exploration detail restoration."""
    project_id = _string(run.get("project_id"))
    run_id = _string(run.get("id"))
    if not project_id or not run_id:
        return []
    events_path = (
        settings.PROJECT_FILE_STORAGE_ROOT
        / project_id
        / "page_exploration"
        / "runs"
        / run_id
        / "timeline_events.jsonl"
    )
    if not events_path.exists():
        return []
    events: list[dict] = []
    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _modules_from_artifacts(run: dict) -> list[dict]:
    """Build frontend module progress from v2 artifact files when DB pages are empty."""
    artifact_root = _artifact_root_path(run)
    if not artifact_root:
        return []

    state = _read_json_file(artifact_root / "live" / "state.json")
    if state:
        modules = _modules_from_live_state(run, state)
        if modules:
            return modules

    progress = _read_json_file(artifact_root / "live" / "progress.json")
    if progress:
        modules = _modules_from_progress_json(run, progress)
        if modules:
            return modules

    summary = _read_yaml_file(artifact_root / "summary.yaml")
    page_artifacts = _read_page_artifacts(artifact_root / "pages")
    return _modules_from_summary_and_pages(run, summary, page_artifacts)


def _modules_from_db_pages(run: dict, pages: list[dict]) -> list[dict]:
    """Build frontend module progress from registered exploration_pages rows."""
    modules_by_key: dict[str, dict] = {}
    for page in pages:
        module_key = _string(page.get("module_key") or "main")
        module = modules_by_key.setdefault(
            module_key,
            _module_shell(
                run,
                {
                    "module_key": module_key,
                    "module_name": module_key,
                    "entry_path": run.get("scope", ""),
                    "planned_page_count": run.get("max_pages", 0),
                },
                len(modules_by_key),
            ),
        )
        module["pages"].append(_page_from_db_page(page))

    _refresh_module_counts(modules_by_key.values())
    return list(modules_by_key.values())


def _normalize_exploration_run_detail(run: dict) -> dict:
    """Use the linked environment as the display source for mutable environment fields."""
    environment_login_strategy = run.get("environment_login_strategy")
    if environment_login_strategy:
        run["login_strategy"] = environment_login_strategy
    return run


def _artifact_root_path(run: dict) -> Path | None:
    raw_root = str(run.get("artifact_root") or "").strip()
    if not raw_root:
        return None
    root = Path(raw_root)
    candidates = [root]
    if not root.is_absolute():
        candidates.extend([
            settings.PROJECT_FILE_STORAGE_ROOT / raw_root,
            settings.DATA_DIR / "projects" / raw_root,
            settings.DATA_DIR / raw_root,
        ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_yaml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (ImportError, OSError):
        return {}
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _read_page_artifacts(pages_dir: Path) -> list[dict]:
    if not pages_dir.exists():
        return []
    pages = []
    for path in sorted(pages_dir.glob("*.yaml")):
        artifact = _read_yaml_file(path)
        if artifact:
            artifact["_artifact_path"] = str(path)
            pages.append(artifact)
    return pages


def _modules_from_live_state(run: dict, state: dict) -> list[dict]:
    summary_modules = ((state.get("summary") or {}).get("modules") or [])
    pages = state.get("pages") or []
    if not isinstance(pages, list):
        pages = []

    modules_by_key = {
        _string(module.get("module_key") or module.get("module_name") or f"module-{index + 1}"): _module_shell(run, module, index)
        for index, module in enumerate(summary_modules)
        if isinstance(module, dict)
    }

    progress_pages = _progress_pages_from_state(state)
    for page in pages:
        if not isinstance(page, dict):
            continue
        frontend_page = _page_from_live_state(page)
        page_content = page.get("content") if isinstance(page.get("content"), dict) else {}
        page_info = page_content.get("page") if isinstance(page_content.get("page"), dict) else page
        module_key = _artifact_module_key(
            modules_by_key,
            _string(page.get("module_key") or page_info.get("module_key") or page_info.get("module") or frontend_page["title"] or "main"),
        )
        module = modules_by_key.setdefault(module_key, _module_shell(run, {"module_key": module_key, "module_name": module_key}, len(modules_by_key)))
        module["pages"].append(frontend_page)

    for module_key, pages_by_id in progress_pages.items():
        module = modules_by_key.setdefault(module_key, _module_shell(run, {"module_key": module_key, "module_name": module_key}, len(modules_by_key)))
        existing_ids = {page["id"] for page in module["pages"]}
        for page in pages_by_id.values():
            if page["id"] in existing_ids:
                continue
            module["pages"].append(page)

    _refresh_module_counts(modules_by_key.values())
    return list(modules_by_key.values())


def _modules_from_progress_json(run: dict, progress: dict) -> list[dict]:
    modules = []
    raw_modules = progress.get("modules") or {}
    if not isinstance(raw_modules, dict):
        return []
    for index, (module_key, module_progress) in enumerate(raw_modules.items()):
        module = _module_shell(run, {"module_key": module_key, "module_name": module_key}, index)
        pages_by_id = ((module_progress or {}).get("pages") or {}) if isinstance(module_progress, dict) else {}
        if isinstance(pages_by_id, dict):
            module["pages"] = [_normalize_progress_page(page_id, page) for page_id, page in pages_by_id.items() if isinstance(page, dict)]
        modules.append(module)
    _refresh_module_counts(modules)
    return modules


def _modules_from_summary_and_pages(run: dict, summary: dict, page_artifacts: list[dict]) -> list[dict]:
    summary_modules = summary.get("modules") or []
    modules_by_key = {
        _string(module.get("module_key") or module.get("module_name") or f"module-{index + 1}"): _module_shell(run, module, index)
        for index, module in enumerate(summary_modules)
        if isinstance(module, dict)
    }

    for page_artifact in page_artifacts:
        page_info = page_artifact.get("page") or {}
        if not isinstance(page_info, dict):
            continue
        module_key = _string(page_info.get("module") or page_info.get("module_key") or "main")
        module = modules_by_key.setdefault(module_key, _module_shell(run, {"module_key": module_key, "module_name": module_key}, len(modules_by_key)))
        module["pages"].append(_page_from_page_artifact(page_artifact))

    _refresh_module_counts(modules_by_key.values())
    return list(modules_by_key.values())


def _progress_pages_from_state(state: dict) -> dict[str, dict[str, dict]]:
    modules = (state.get("live_progress") or state.get("progress") or {}).get("modules") if isinstance(state.get("live_progress") or state.get("progress"), dict) else None
    if not modules:
        modules = state.get("modules")
    if not isinstance(modules, dict):
        return {}
    result: dict[str, dict[str, dict]] = {}
    for module_key, module_progress in modules.items():
        pages = module_progress.get("pages") if isinstance(module_progress, dict) else None
        if not isinstance(pages, dict):
            continue
        result[_string(module_key)] = {
            _string(page_id): _normalize_progress_page(_string(page_id), page)
            for page_id, page in pages.items()
            if isinstance(page, dict)
        }
    return result


def _module_shell(run: dict, source: dict, index: int) -> dict:
    module_key = _string(source.get("module_key") or source.get("module_name") or f"module-{index + 1}")
    return {
        "id": module_key,
        "module_key": module_key,
        "module_name": _string(source.get("module_name") or module_key),
        "entry_path": _string(source.get("entry_path") or run.get("scope")),
        "planned_page_count": _int(source.get("planned_page_count")),
        "explored_page_count": _int(source.get("explored_page_count")),
        "blocked_page_count": _int(source.get("blocked_page_count")),
        "action_count": _int(source.get("action_count")),
        "field_count": _int(source.get("field_count")),
        "state_transition_count": _int(source.get("state_transition_count")),
        "completion_status": _string(source.get("completion_status") or source.get("status") or run.get("status") or "pending"),
        "completion_summary": _string(source.get("completion_summary") or source.get("summary") or run.get("result_summary")),
        "pages": [],
        "elements": [],
        "blockers": [],
    }


def _page_from_live_state(page: dict) -> dict:
    content = page.get("content") if isinstance(page.get("content"), dict) else {}
    page_info = content.get("page") if isinstance(content.get("page"), dict) else page
    return {
        "id": _string(page_info.get("id") or page.get("id") or page.get("page_id")),
        "title": _string(page_info.get("semantic_title") or page_info.get("title") or page.get("title") or page_info.get("id") or "探索页面"),
        "url": _string(page_info.get("url") or page.get("page_url") or page.get("url")),
        "entry_path": _string(page_info.get("entry_path") or page_info.get("normalized_url") or page_info.get("normalized_path")),
        "yaml_path": _string(page.get("file_path") or page_info.get("yaml_path") or page.get("yaml_path") or page.get("_artifact_path")),
        "status": _string(page_info.get("status") or page.get("status") or "completed"),
        "blocker_reason": _string(page_info.get("blocker_reason") or page.get("blocker_reason")),
        "recent_event": _string(page_info.get("recent_event") or page.get("recent_event")),
        "structure_summary": _string(page_info.get("structure_summary") or page.get("structure_summary")),
        "steps": _normalize_steps(content.get("steps") or page.get("steps")),
    }


def _page_from_page_artifact(artifact: dict) -> dict:
    page = artifact.get("page") or {}
    actions = artifact.get("actions")
    return {
        "id": _string(page.get("id") or "page"),
        "title": _string(page.get("semantic_title") or page.get("title") or page.get("id") or "探索页面"),
        "url": _string(page.get("url")),
        "entry_path": _string(page.get("normalized_url") or page.get("normalized_path")),
        "yaml_path": _string(artifact.get("_artifact_path")),
        "status": _string(page.get("status") or "completed"),
        "blocker_reason": "",
        "recent_event": "",
        "structure_summary": _string(page.get("structure_summary")),
        "steps": _steps_from_actions(actions),
    }


def _page_from_db_page(page: dict) -> dict:
    return {
        "id": _string(page.get("id")),
        "title": _string(page.get("title")),
        "url": _string(page.get("url")),
        "entry_path": _string(page.get("entry_path")),
        "yaml_path": _string(page.get("snapshot_path")),
        "status": _string(page.get("status") or "completed"),
        "blocker_reason": "",
        "recent_event": "",
        "structure_summary": _string(page.get("structure_summary")),
        "steps": [],
    }


def _normalize_progress_page(page_id: str, page: dict) -> dict:
    return {
        "id": _string(page.get("id") or page_id),
        "title": _string(page.get("title") or page_id),
        "url": _string(page.get("url")),
        "entry_path": _string(page.get("entry_path")),
        "yaml_path": _string(page.get("yaml_path")),
        "status": _string(page.get("status") or "running"),
        "blocker_reason": _string(page.get("blocker_reason")),
        "recent_event": _string(page.get("recent_event")),
        "structure_summary": _string(page.get("structure_summary")),
        "steps": _normalize_steps(page.get("steps")),
    }


def _steps_from_actions(actions: Any) -> list[dict]:
    if not isinstance(actions, list):
        return []
    steps = []
    for index, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            continue
        steps.append({
            "id": _string(action.get("id") or f"action-{index:03d}"),
            "type": _string(action.get("type") or "action"),
            "title": _string(action.get("target") or action.get("title") or action.get("type") or "探索动作"),
            "detail": _string(action.get("result") or action.get("detail")),
            "status": _string(action.get("status") or "completed"),
            "occurred_at": action.get("occurred_at"),
            "artifact_path": _string(action.get("artifact_path")),
            "source": _string(action.get("source")),
        })
    return steps


def _normalize_steps(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    steps = []
    for index, step in enumerate(value, start=1):
        if not isinstance(step, dict):
            continue
        steps.append({
            "id": _string(step.get("id") or step.get("step_id") or f"step-{index:03d}"),
            "type": _string(step.get("type") or step.get("action_type") or "event"),
            "title": _string(step.get("title") or step.get("description") or "探索步骤"),
            "detail": _string(step.get("detail") or step.get("message") or step.get("expected_result")),
            "status": _string(step.get("status") or "pending"),
            "occurred_at": step.get("occurred_at") or step.get("completed_at") or step.get("started_at"),
            "artifact_path": _string(step.get("artifact_path")),
            "source": _string(step.get("source")),
        })
    return steps


def _refresh_module_counts(modules) -> None:
    for module in modules:
        page_count = len(module["pages"])
        if page_count:
            module["explored_page_count"] = max(module["explored_page_count"], page_count)
            module["planned_page_count"] = max(module["planned_page_count"], page_count)


def _artifact_module_key(modules_by_key: dict[str, dict], raw_key: str) -> str:
    if raw_key in modules_by_key:
        return raw_key
    if len(modules_by_key) == 1:
        return next(iter(modules_by_key))
    return raw_key


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

        # 检查是否已经在运行
        if run_dict["status"] in ["running", "queued"]:
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


def _exploration_run_is_stopping(run_id: str) -> bool:
    with _exploration_lock:
        runtime = _running_explorations.get(run_id)
        if runtime and runtime.get("should_stop"):
            return True

    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        return bool(run and run["status"] in {"stopping", "cancelled"})


def _ensure_exploration_not_stopping(run_id: str) -> None:
    if _exploration_run_is_stopping(run_id):
        raise ExplorationCancelledError("用户已停止探索任务。")


def _finalize_cancelled_exploration_run(run_id: str) -> None:
    finished_at = datetime.now(timezone.utc).isoformat()
    artifact_summary = ""
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if not run:
            return
        if run["status"] == "cancelled":
            event_bus.close(run_id)
            return
    artifact_summary = _register_failed_exploration_outputs(run_id)
    result_summary = "探索任务已由用户停止。"
    if artifact_summary:
        result_summary = f"探索任务已由用户停止；{artifact_summary}"
    with connect() as db:
        exploration_run_repo.update_status(
            db,
            run_id,
            "cancelled",
            finished_at=finished_at,
            result_summary=result_summary,
        )
    _publish_run_terminal_event(
        _project_id_from_run(run),
        run_id,
        "run_cancelled",
        {
            "status": "cancelled",
            "result_summary": result_summary,
            "finished_at": finished_at,
        },
    )


def _run_exploration_background(run_id: str) -> None:
    """后台执行探索任务"""
    try:
        # 注册到运行列表
        with _exploration_lock:
            _running_explorations[run_id] = {
                "should_stop": False,
                "current_page": None,
            }

        # 更新状态为running
        with connect() as db:
            run = exploration_run_repo.find_by_id(db, run_id)
            if run and run["status"] in {"stopping", "cancelled"}:
                raise ExplorationCancelledError("用户已停止探索任务。")
            exploration_run_repo.update_status(
                db,
                run_id,
                "running",
                started_at=datetime.now(timezone.utc).isoformat(),
            )
            run = exploration_run_repo.find_detail_by_id(db, run_id)
            if not run:
                return
            run_dict = dict(run)
        event_bus.publish(
            run_id,
            "run_started",
            {
                "status": "running",
                "started_at": run_dict.get("started_at"),
                "result_summary": "探索任务已开始。",
            },
        )

        # 执行探索逻辑（简化版）
        _execute_exploration(run_id, run_dict)

    except ExplorationCancelledError:
        _finalize_cancelled_exploration_run(run_id)
    except Exception as e:
        artifact_summary = _register_failed_exploration_outputs(run_id)
        result_summary = f"探索失败: {str(e)}"
        if artifact_summary:
            result_summary = f"{result_summary}；{artifact_summary}"
        # 更新状态为blocked（数据库约束不允许failed状态）
        with connect() as db:
            exploration_run_repo.update_status(
                db,
                run_id,
                "blocked",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=result_summary,
            )
        _publish_run_terminal_event(
            str(run_dict.get("project_id") or ""),
            run_id,
            "run_failed",
            {
                "status": "blocked",
                "error": str(e),
                "result_summary": result_summary,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    finally:
        event_bus.close(run_id)
        # 清理运行列表
        with _exploration_lock:
            _running_explorations.pop(run_id, None)


def _execute_exploration(run_id: str, run_config: dict) -> None:
    """执行探索逻辑 - 集成deepagents Agent"""
    import asyncio
    from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
    from app.agents.page_exploration.agent import page_exploration_agent

    project_id = run_config["project_id"]
    start_url = _exploration_start_url(run_config)
    scope = str(run_config.get("scope") or "").strip()
    goal = str(run_config.get("goal") or "").strip()
    exploration_mode = str(run_config["exploration_mode"]).strip()
    max_pages = run_config["max_pages"]
    storage_state_path = _exploration_auth_state_path(run_config)

    try:
        # 1. 解析模型配置
        model_selection = resolve_model_selection(CAPABILITY_ID)

        model = build_agent_model(model_selection, extra_body=thinking_disabled_extra_body(model_selection))

        # 2. 运行异步探索
        asyncio.run(_execute_exploration_async(
            model=model,
            project_id=project_id,
            run_id=run_id,
            start_url=start_url,
            exploration_mode=exploration_mode,
            max_pages=max_pages,
            scope=scope,
            goal=goal,
            storage_state_path=storage_state_path,
        ))

    except ExplorationCancelledError:
        raise
    except Exception:
        raise


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
        db.execute("DELETE FROM exploration_elements WHERE exploration_run_id = ?", (run_id,))
        db.execute("DELETE FROM exploration_blockers WHERE exploration_run_id = ?", (run_id,))
        db.execute("DELETE FROM exploration_module_coverages WHERE exploration_run_id = ?", (run_id,))
        db.execute("DELETE FROM exploration_pages WHERE exploration_run_id = ?", (run_id,))


def _is_run_artifact_dir(path: Path, run_id: str) -> bool:
    parts = path.parts
    return path.name == run_id and "page_exploration" in parts and "runs" in parts


def _register_failed_exploration_outputs(run_id: str) -> str:
    """失败时登记本轮已写出的部分产物，供探索概览展示完整上下文。"""
    try:
        with connect() as db:
            run = exploration_run_repo.find_detail_by_id(db, run_id)
            if not run:
                return ""
            run_dict = _normalize_exploration_run_detail(dict(run))

        return _register_exploration_outputs(
            project_id=run_dict["project_id"],
            run_id=run_id,
            start_url=_exploration_start_url(run_dict),
            scope=str(run_dict.get("scope") or "").strip(),
            exploration_mode=str(run_dict.get("exploration_mode") or "goal").strip(),
            max_pages=int(run_dict.get("max_pages") or 0),
            result_status="failed",
        )
    except Exception:
        return ""


def _exploration_start_url(run_config: dict) -> str:
    """Use the configured environment entry URL; scope is a module constraint, not a URL."""
    start_url = str(run_config.get("environment_site_url") or "").strip()
    if not start_url:
        raise ValueError("探索任务缺少环境站点入口 URL，请先配置项目环境的站点地址。")
    return start_url


def _exploration_auth_state_path(run_config: dict) -> Path | None:
    environment_id = str(run_config.get("environment_id") or "").strip()
    if not environment_id:
        return None

    summary = auth_state_summary(
        environment_id=environment_id,
        login_strategy=str(run_config.get("environment_login_strategy") or ""),
        reuse_auth_state=bool(run_config.get("environment_reuse_auth_state")),
    )
    if summary.get("status") != "valid":
        return None

    path = auth_state_path(environment_id)
    return path if path.exists() else None


def _exploration_mode_label(exploration_mode: str) -> str:
    return "自主探索" if exploration_mode == "autonomous" else "目标探索"


def _exploration_agent_prompt(
    start_url: str,
    exploration_mode: str,
    scope: str,
    max_pages: int,
    goal: str = "",
) -> str:
    lines = [f"请探索网站: {start_url}"]
    mode_label = _exploration_mode_label(exploration_mode)
    lines.append(f"探索方式: {mode_label}")
    if scope.strip():
        lines.append(f"探索范围: {scope.strip()}")
    if goal.strip():
        lines.append(f"探索目标: {goal.strip()}")
    lines.append("")
    if exploration_mode == "autonomous":
        lines.extend(
            [
                "执行策略:",
                "- 这是自主探索：以探索范围为覆盖边界，自动识别范围内的主要模块、页面、入口和可测元素。",
                "- 如果提供了探索目标，它只是补充关注点，不作为单一路径完成条件。",
                "- 按模块盘点，不要因为某个具体动作完成就提前停止；达到范围覆盖或预算上限后总结。",
            ]
        )
    else:
        lines.extend(
            [
                "执行策略:",
                "- 这是目标探索：以探索目标为主线和完成条件，优先执行目标描述的页面流程。",
                "- 不要扩展为全量功能盘点；只探索完成目标所必需的页面、弹窗、字段和状态。",
                "- 目标完成、被阻塞或达到预算上限后停止并总结，不要继续无关分支。",
            ]
        )
    lines.append(f"最多探索 {max_pages} 个页面。")
    return "\n".join(lines)


async def _execute_exploration_async(
    model,
    project_id: str,
    run_id: str,
    start_url: str,
    exploration_mode: str,
    max_pages: int,
    scope: str = "",
    goal: str = "",
    storage_state_path: Path | None = None,
) -> None:
    """异步执行探索"""
    from app.agents.page_exploration.agent import page_exploration_agent
    from app.agents.page_exploration.tools.runtime_context import browser_session_context

    _ensure_exploration_not_stopping(run_id)

    # 创建agent实例（带工具调用硬截断：单次 run 最多 max_actions 步）
    agent = page_exploration_agent(model, max_actions=max(40, min(int(max_pages or 80) * 6, 200)))
    started_at = datetime.now(timezone.utc).isoformat()
    plan_steps = _initial_exploration_plan_steps(start_url, max_pages)
    event_bus.publish(
        run_id,
        "planning_completed",
        {
            "plan_id": f"{run_id}-plan",
            "goal_summary": goal or f"{_exploration_mode_label(exploration_mode)}：探索 {start_url}",
            "scope_summary": scope or start_url,
            "strategy": (
                "围绕明确探索目标执行页面流程，并在目标完成或阻塞后停止。"
                if exploration_mode == "goal"
                else "按探索范围自动盘点主要模块、页面入口和可测元素。"
            ),
            "modules": [scope or "主探索模块"],
            "estimated_duration_minutes": None,
            "risk_assessment": "",
            "success_criteria": [
                goal or f"最多探索 {max_pages} 个页面，并记录页面事实与关键操作。"
            ],
            "total_steps": len(plan_steps),
            "steps": plan_steps,
        },
    )

    event_bus.publish(
        run_id,
        "step_started",
        {
            **plan_steps[0],
            "total_steps": len(plan_steps),
            "attempt": 1,
            "started_at": started_at,
            "message": f"准备探索入口：{start_url}",
        },
    )
    event_bus.publish(
        run_id,
        "step_completed",
        {
            **plan_steps[0],
            "total_steps": len(plan_steps),
            "attempt": 1,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "message": "入口和探索约束已确认。",
        },
    )

    # 调用agent进行探索
    payload = {
        "messages": [
            {
                "role": "user",
                "content": _exploration_agent_prompt(
                    start_url,
                    exploration_mode,
                    scope,
                    max_pages,
                    goal=goal,
                ),
            }
        ]
    }
    with browser_session_context(start_url=start_url, storage_state_path=storage_state_path):
        result = await _invoke_agent_with_realtime_events(
            agent,
            payload,
            run_id,
            plan_steps,
            project_id=project_id,
            max_pages=max_pages,
        )
    _ensure_exploration_not_stopping(run_id)

    artifact_summary = _register_exploration_outputs(
        project_id=project_id,
        run_id=run_id,
        start_url=start_url,
        scope=scope,
        exploration_mode=exploration_mode,
        max_pages=max_pages,
    )
    _ensure_exploration_not_stopping(run_id)

    # 更新状态为完成
    with connect() as db:
        run = exploration_run_repo.find_by_id(db, run_id)
        if run and run["status"] in {"stopping", "cancelled"}:
            raise ExplorationCancelledError("用户已停止探索任务。")
        exploration_run_repo.update_status(
            db,
            run_id,
            "completed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_summary=artifact_summary,
        )
    _publish_run_terminal_event(
        project_id,
        run_id,
        "run_completed",
        {
            "status": "completed",
            "result_summary": artifact_summary,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def _register_exploration_outputs(
    *,
    project_id: str,
    run_id: str,
    start_url: str,
    scope: str,
    exploration_mode: str,
    max_pages: int,
    result_status: str = "completed",
) -> str:
    """Register file artifacts produced by the new page exploration agent."""
    run_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration" / "runs" / run_id
    pages_dir = run_dir / "pages"
    run_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_artifacts = _collect_page_artifact_files(pages_dir)
    if not (run_dir / "summary.yaml").exists():
        _write_exploration_summary(
            run_dir=run_dir,
            run_id=run_id,
            start_url=start_url,
            scope=scope,
            exploration_mode=exploration_mode,
            max_pages=max_pages,
            page_artifacts=page_artifacts,
        )

    report_path = _write_exploration_report(
        run_dir=run_dir,
        run_id=run_id,
        start_url=start_url,
        exploration_mode=exploration_mode,
        page_artifacts=page_artifacts,
    )

    with connect() as db:
        exploration_run_repo.update_artifact_root(db, run_id, str(run_dir))
        for path, artifact in page_artifacts:
            _register_page_artifact_file(
                db,
                project_id=project_id,
                run_dir=run_dir,
                run_id=run_id,
                path=path,
                artifact=artifact,
                scope=scope,
            )

        _upsert_exploration_artifact(
            db,
            artifact_id=f"{run_id}-report",
            run_id=run_id,
            artifact_type="report",
            file_path=str(report_path),
            title="探索报告",
            summary=f"本次探索记录 {len(page_artifacts)} 个页面。",
        )

    if result_status == "failed":
        return f"已保留本次失败前生成的 {len(page_artifacts)} 个页面产物。"
    return f"探索完成，已登记 {len(page_artifacts)} 个页面产物。"


def _collect_page_artifact_files(*directories: Path) -> list[tuple[Path, dict]]:
    artifacts: list[tuple[Path, dict]] = []
    seen: set[Path] = set()
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            artifact = _read_yaml_file(path)
            if artifact.get("page"):
                artifacts.append((path, artifact))
    return artifacts


def _write_exploration_summary(
    *,
    run_dir: Path,
    run_id: str,
    start_url: str,
    scope: str,
    exploration_mode: str,
    max_pages: int,
    page_artifacts: list[tuple[Path, dict]],
) -> None:
    module_counts: dict[str, int] = {}
    for _, artifact in page_artifacts:
        page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
        module_key = _string(page.get("module_key") or page.get("module") or scope or "主探索模块")
        module_counts[module_key] = module_counts.get(module_key, 0) + 1
    modules = [
        {
            "module_key": module_key,
            "module_name": module_key,
            "status": "completed",
            "entry_path": scope or start_url,
            "planned_page_count": max_pages,
            "explored_page_count": count,
        }
        for module_key, count in module_counts.items()
    ]
    _write_yaml_file(
        run_dir / "summary.yaml",
        {
            "run_id": run_id,
            "artifact_schema_version": 2,
            "start_url": start_url,
            "exploration_mode": exploration_mode,
            "scope": scope,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "modules": modules,
        },
    )


def _write_exploration_report(
    *,
    run_dir: Path,
    run_id: str,
    start_url: str,
    exploration_mode: str,
    page_artifacts: list[tuple[Path, dict]],
) -> Path:
    report_path = run_dir / "report.md"
    lines = [
        "# 探索报告",
        "",
        f"- 运行 ID：`{run_id}`",
        f"- 入口 URL：`{start_url}`",
        f"- 探索方式：{_exploration_mode_label(exploration_mode)}",
        f"- 页面产物数：{len(page_artifacts)}",
        "",
        "## 页面清单",
        "",
    ]
    if page_artifacts:
        for path, artifact in page_artifacts:
            page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
            title = _string(page.get("semantic_title") or page.get("title") or path.stem)
            url = _string(page.get("url") or "")
            lines.append(f"- {title}：`{url}`（{path.name}）")
    else:
        lines.append("- 本次探索未登记页面产物。")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _write_yaml_file(path: Path, payload: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _checkpoint_snapshot_artifact_from_event(event: dict, *, project_id: str, run_id: str) -> Path | None:
    """Persist a minimal page artifact whenever the browser snapshot tool succeeds."""
    if not project_id or not run_id or not isinstance(event, dict):
        return None
    if event.get("event") != "on_tool_end" or event.get("name") != "playwright_snap_tool":
        return None

    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    snapshot = _coerce_tool_output_dict(data.get("output"))
    if not snapshot or snapshot.get("error"):
        return None

    url = _string(snapshot.get("url")).strip()
    title = _string(snapshot.get("title")).strip() or url or "探索页面"
    if not url:
        return None

    normalized_path = _normalize_snapshot_url_path(url)
    page_id = _snapshot_page_id(normalized_path)
    run_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration" / "runs" / run_id
    pages_dir = run_dir / "pages"
    elements = snapshot.get("elements") if isinstance(snapshot.get("elements"), list) else []
    artifact_elements = _snapshot_elements_for_artifact(elements)
    accessibility_tree = snapshot.get("accessibility_tree") if isinstance(snapshot.get("accessibility_tree"), list) else []
    visible_text_blocks = snapshot.get("visible_text_blocks") if isinstance(snapshot.get("visible_text_blocks"), list) else []
    captured_at = datetime.now(timezone.utc).isoformat()
    artifact = {
        "page": {
            "id": page_id,
            "title": title,
            "url": url,
            "normalized_url": normalized_path,
            "normalized_path": normalized_path,
            "module": "主探索模块",
            "status": "explored",
            "structure_summary": f"自动保存页面快照，发现 {len(artifact_elements)} 个元素。",
            "elements": artifact_elements,
            "accessibility_tree": accessibility_tree,
            "visible_text_blocks": visible_text_blocks,
            "last_explored": {
                "run_id": run_id,
                "timestamp": captured_at,
            },
        },
        "states": [
            {
                "id": "snapshot-current",
                "title": title,
                "url": url,
                "elements": artifact_elements,
                "accessibility_tree": accessibility_tree,
                "visible_text_blocks": visible_text_blocks,
            }
        ],
        "actions": [
            {
                "id": "snapshot-captured",
                "type": "snapshot",
                "target": title,
                "result": "浏览器快照已自动保存为页面产物。",
                "status": "completed",
                "occurred_at": captured_at,
                "source": "playwright_snap_tool",
            }
        ],
        "metadata": {
            "captured_at": captured_at,
            "source": "snapshot_checkpoint",
        },
    }

    path = _unique_snapshot_artifact_path(pages_dir / f"{page_id}.yaml")
    _write_yaml_file(path, artifact)
    try:
        with connect() as db:
            _register_page_artifact_file(
                db,
                project_id=project_id,
                run_dir=run_dir,
                run_id=run_id,
                path=path,
                artifact=artifact,
                scope="主探索模块",
            )
    except Exception:
        # Snapshot checkpoints are best-effort. The final exploration output
        # registration re-indexes all run-scoped page artifacts.
        pass
    return path


def _unique_snapshot_artifact_path(path: Path) -> Path:
    """Resolve a non-conflicting snapshot artifact path.

    修改：原来在已存在时生成 `page-workspace-2.yaml` / `-3.yaml` ...
    的序号化重名，是当前 run 中产生 22 个重复 yaml 的直接源头。
    改为：同 run 内同 normalized_path 已写过则直接覆盖原文件（最
    新快照胜出），避免序号化重复；新文件则按原名创建。
    """
    return path


def _register_page_artifact_file(
    db,
    *,
    project_id: str,
    run_dir: Path,
    run_id: str,
    path: Path,
    artifact: dict,
    scope: str,
) -> None:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    page_id = _string(page.get("id") or path.stem)
    title = _string(page.get("semantic_title") or page.get("title") or path.stem)
    url = _string(page.get("url") or page.get("env_url") or "")
    entry_path = _string(page.get("normalized_url") or page.get("normalized_path") or page.get("entry_path") or "")
    module_key = _string(page.get("module_key") or page.get("module") or scope or "主探索模块")
    structure_summary = _string(page.get("structure_summary") or _page_structure_summary(artifact))

    exploration_run_repo.update_artifact_root(db, run_id, str(run_dir))
    _upsert_exploration_page(
        db,
        page_id=page_id,
        run_id=run_id,
        title=title,
        url=url,
        entry_path=entry_path,
        module_key=module_key,
        structure_summary=structure_summary,
        snapshot_path=str(path),
    )
    _upsert_exploration_artifact(
        db,
        artifact_id=f"{run_id}-{path.stem}-yaml",
        run_id=run_id,
        artifact_type="page_yaml",
        file_path=_save_project_page_artifact(
            project_id=project_id,
            run_id=run_id,
            artifact=artifact,
            source_path=path,
            scope=scope,
        ),
        title=title,
        summary=structure_summary,
    )


# --- Inlined from ProjectPagesService ---
_HOME_DISPLAY_NAME = "首页"


def _inline_save_page(
    *,
    project_id: str,
    page_id: str,
    page_data: dict,
    run_id: str,
    url: str,
    normalized_path: str,
    env: str = "test",
) -> bool:
    """Inlined from ProjectPagesService.save_page."""
    import yaml

    base_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration"
    pages_dir = base_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_file = pages_dir / f"{page_id}.yaml"

    env_urls = {env: url}
    if page_file.exists():
        try:
            existing = yaml.safe_load(open(page_file, encoding="utf-8"))
            if existing:
                env_urls = existing.get("page", {}).get("env_urls", {})
                env_urls[env] = url
        except Exception:
            pass

    full_page_data = {
        "page": {
            "id": page_id,
            "title": page_data.get("title", ""),
            "display_name": page_data.get("display_name") or _inline_display_name_from_path(normalized_path),
            "breadcrumb": page_data.get("breadcrumb") or _inline_breadcrumb_from_path(normalized_path),
            "normalized_path": normalized_path,
            "structure_summary": page_data.get("structure_summary", ""),
            "path_hash": _inline_path_hash(normalized_path),
            "env_urls": env_urls,
            "last_explored": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "run_id": run_id,
            },
            "elements": page_data.get("elements", []),
        },
        "states": page_data.get("states", []),
        "quality": page_data.get("quality", {}),
        "metadata": page_data.get("metadata", {}),
    }

    with open(page_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(full_page_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return True


def _inline_list_pages(project_id: str):
    """Inlined from ProjectPagesService.list_pages."""
    import yaml

    base_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration"
    pages_dir = base_dir / "pages"
    pages = []
    if not pages_dir.exists():
        return pages
    for page_file in pages_dir.glob("*.yaml"):
        if page_file.name == "pages-index.yaml":
            continue
        try:
            page_data = yaml.safe_load(open(page_file, encoding="utf-8"))
            page_info = page_data.get("page", {})
            pages.append(
                {
                    "page_id": page_info.get("id"),
                    "title": page_info.get("title"),
                    "display_name": page_info.get("display_name")
                    or _inline_display_name_from_path(page_info.get("normalized_path") or ""),
                    "breadcrumb": page_info.get("breadcrumb")
                    or _inline_breadcrumb_from_path(page_info.get("normalized_path") or ""),
                    "normalized_path": page_info.get("normalized_path"),
                    "structure_summary": page_info.get("structure_summary"),
                    "last_explored": page_info.get("last_explored"),
                    "file": page_file.name,
                }
            )
        except Exception:
            pass
    return pages


def _inline_breadcrumb_from_path(normalized_path: str) -> list:
    segments = [s for s in normalized_path.strip("/").split("/") if s]
    return segments or [_HOME_DISPLAY_NAME]


def _inline_display_name_from_path(normalized_path: str) -> str:
    breadcrumb = _inline_breadcrumb_from_path(normalized_path)
    return breadcrumb[-1] if breadcrumb else _HOME_DISPLAY_NAME


def _inline_path_hash(normalized_path: str) -> str:
    import hashlib
    h = hashlib.sha256(normalized_path.encode("utf-8"))
    return f"sha256-{h.hexdigest()[:16]}"


# --- End inlined helpers ---


def _save_project_page_artifact(
    *,
    project_id: str,
    run_id: str,
    artifact: dict,
    source_path: Path,
    scope: str,
) -> str:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    page_id = _string(page.get("id") or source_path.stem)
    title = _string(page.get("semantic_title") or page.get("title") or source_path.stem)
    url = _string(page.get("url") or page.get("env_url") or "")
    normalized_path = _string(page.get("normalized_url") or page.get("normalized_path") or page.get("entry_path") or "")
    structure_summary = _string(page.get("structure_summary") or _page_structure_summary(artifact))
    if not normalized_path and url:
        normalized_path = _normalize_snapshot_url_path(url)

    _inline_save_page(
        project_id=project_id,
        page_id=page_id,
        page_data={
            "title": title,
            "structure_summary": structure_summary,
            "states": artifact.get("states", []),
            "quality": artifact.get("quality", {}),
            "metadata": {
                **(artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}),
                "source": "page_exploration_run",
                "source_run_id": run_id,
                "source_artifact_path": str(source_path),
                "module": _string(page.get("module_key") or page.get("module") or scope),
            },
        },
        run_id=run_id,
        url=url,
        normalized_path=normalized_path,
    )
    base_dir = settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration"
    return str(base_dir / "pages" / f"{page_id}.yaml")


def _coerce_tool_output_dict(output) -> dict:
    if isinstance(output, dict):
        return output
    content = getattr(output, "content", None)
    if content is None and isinstance(output, str):
        content = output
    if not isinstance(content, str):
        return {}
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _normalize_snapshot_url_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path


def _snapshot_page_id(normalized_path: str) -> str:
    value = normalized_path.strip("/") or "home"
    for char in ("?", "&", "=", "#", "%", ":"):
        value = value.replace(char, "-")
    value = value.replace("/", "-")
    value = "-".join(part for part in value.split("-") if part)
    return f"page-{value or 'home'}"


def _snapshot_elements_for_artifact(elements: list) -> list[dict]:
    result = []
    for index, element in enumerate(elements, start=1):
        if not isinstance(element, dict):
            continue
        name = _string(element.get("name") or element.get("text") or element.get("ref") or f"element-{index}")
        role = _string(element.get("role") or "element")
        result.append(
            {
                "id": _string(element.get("ref") or f"element-{index}"),
                "name": name,
                "role": role,
                "text": element.get("text"),
                "visible": bool(element.get("visible", True)),
                "locators": _semantic_locator_candidates(role, name),
            }
        )
    return result


def _semantic_locator_candidates(role: str, name: str) -> list[dict]:
    if not role or role == "element" or not name:
        return []
    escaped_name = name.replace("\\", "\\\\").replace("'", "\\'")
    return [
        {
            "kind": "role",
            "code": f"getByRole('{role}', {{ name: '{escaped_name}' }})",
            "priority": 1,
        }
    ]


def _upsert_exploration_page(db, **kwargs) -> None:
    db.execute(
        """
        INSERT INTO exploration_pages (
            id, exploration_run_id, module_key, title, url,
            entry_path, structure_summary, screenshot_path,
            snapshot_path, trace_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            module_key = excluded.module_key,
            title = excluded.title,
            url = excluded.url,
            entry_path = excluded.entry_path,
            structure_summary = excluded.structure_summary,
            snapshot_path = excluded.snapshot_path
        """,
        (
            kwargs["page_id"],
            kwargs["run_id"],
            kwargs["module_key"],
            kwargs["title"],
            kwargs["url"],
            kwargs["entry_path"],
            kwargs["structure_summary"],
            "",
            kwargs["snapshot_path"],
            "",
        ),
    )


def _upsert_exploration_artifact(db, **kwargs) -> None:
    db.execute(
        """
        INSERT INTO exploration_artifacts (
            id, exploration_run_id, artifact_type, file_path, title, summary
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            artifact_type = excluded.artifact_type,
            file_path = excluded.file_path,
            title = excluded.title,
            summary = excluded.summary
        """,
        (
            kwargs["artifact_id"],
            kwargs["run_id"],
            kwargs["artifact_type"],
            kwargs["file_path"],
            kwargs["title"],
            kwargs["summary"],
        ),
    )


def _page_structure_summary(artifact: dict) -> str:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    elements = page.get("elements")
    if not isinstance(elements, list):
        states = artifact.get("states")
        elements = []
        if isinstance(states, list):
            for state in states:
                if isinstance(state, dict) and isinstance(state.get("elements"), list):
                    elements.extend(state["elements"])
    return f"发现 {len(elements)} 个元素"


def _initial_exploration_plan_steps(start_url: str, max_pages: int) -> list[dict]:
    return [
        {
            "step_id": "exploration-entry",
            "step_number": 1,
            "module_name": "主探索模块",
            "action_type": "prepare",
            "description": "准备探索入口",
            "target_description": start_url,
            "target_selector": "",
            "value": "",
            "expected_result": "完成入口和探索约束确认。",
            "execution_strategy": "agent",
            "is_critical": True,
            "retry_on_failure": False,
            "max_retries": 0,
        },
        {
            "step_id": "exploration-agent-run",
            "step_number": 2,
            "module_name": "主探索模块",
            "action_type": "agent_run",
            "description": "执行页面探索",
            "target_description": f"最多 {max_pages} 个页面",
            "target_selector": "",
            "value": "",
            "expected_result": "生成页面事实、元素定位器和探索产物。",
            "execution_strategy": "deepagents",
            "is_critical": True,
            "retry_on_failure": False,
            "max_retries": 0,
        },
    ]


async def _invoke_agent_with_realtime_events(
    agent,
    payload: dict,
    run_id: str,
    plan_steps: list[dict],
    *,
    project_id: str = "",
    max_pages: int = 50,
):
    agent_step = plan_steps[1]
    started_at = datetime.now(timezone.utc).isoformat()
    timeline_log = _ExplorationEventLog(project_id=project_id, run_id=run_id, filename="timeline_events.jsonl")
    raw_log = _ExplorationEventLog(project_id=project_id, run_id=run_id, filename="raw_events.jsonl")
    started_display = _status_display("agent_run", "开始页面探索", "页面探索 Agent 已开始执行。")
    event_bus.publish(
        run_id,
        "step_started",
        {
            **agent_step,
            "total_steps": len(plan_steps),
            "attempt": 1,
            "started_at": started_at,
            "message": "页面探索 Agent 已开始执行。",
        },
        display=started_display,
    )
    timeline_log.append(
        "agent_step_started",
        {"step": agent_step, "message": "页面探索 Agent 已开始执行。"},
        display=started_display,
    )
    config = _agent_recursion_config(max_pages)
    result = await _astream_agent_with_timeline_events(
        agent,
        payload,
        run_id,
        config,
        timeline_log=timeline_log,
        raw_log=raw_log,
        project_id=project_id,
    )
    _ensure_exploration_not_stopping(run_id)
    return result


async def _astream_agent_with_timeline_events(
    agent,
    payload: dict,
    run_id: str,
    config: dict,
    *,
    timeline_log: "_ExplorationEventLog",
    raw_log: "_ExplorationEventLog",
    project_id: str,
) -> dict:
    if not hasattr(agent, "astream"):
        raise TypeError("页面探索 Agent 必须支持 projection stream: astream(..., stream_mode=[...])")
    final_result: dict | None = None
    tool_inputs: dict[str, dict] = {}
    seen_projection_keys: set[str] = set()
    async for chunk in agent.astream(payload, config=config, stream_mode=["updates", "messages", "values"]):
        _ensure_exploration_not_stopping(run_id)
        mode, data = _stream_chunk_parts(chunk)
        raw_event = raw_log.append(
            "agent_projection_event",
            {
                "mode": mode or "unknown",
                "data": _compact_event_payload(data),
            },
        )
        for readable_event in _projection_chunk_to_timeline_events(
            mode,
            data,
            raw_event_id=raw_event.get("event_id"),
            tool_inputs=tool_inputs,
            seen_projection_keys=seen_projection_keys,
        ):
            display = readable_event.get("display")
            persisted_event = timeline_log.append(
                readable_event["type"],
                readable_event["payload"],
                display=display,
            )
            event_bus.publish(
                run_id,
                readable_event["type"],
                readable_event["payload"],
                display=display,
                timeline_event_id=persisted_event.get("event_id"),
            )
            snapshot_event = readable_event.get("snapshot_event")
            if isinstance(snapshot_event, dict):
                _checkpoint_snapshot_artifact_from_event(snapshot_event, project_id=project_id, run_id=run_id)
        if mode == "values" and isinstance(data, dict):
            final_result = data
    return final_result or {}


def _stream_chunk_parts(chunk) -> tuple[str | None, object]:
    if isinstance(chunk, tuple):
        if len(chunk) == 2 and isinstance(chunk[0], str):
            return chunk[0], chunk[1]
        if len(chunk) == 3 and isinstance(chunk[1], str):
            return chunk[1], chunk[2]
    return None, chunk


def _projection_chunk_to_timeline_events(
    mode: str | None,
    data,
    *,
    raw_event_id: str | None,
    tool_inputs: dict[str, dict],
    seen_projection_keys: set[str] | None = None,
) -> list[dict]:
    if mode != "updates":
        return []
    events: list[dict] = []
    for message in _messages_from_projection_update(data):
        thought = _projection_message_to_thought_event(message, raw_event_id=raw_event_id)
        if thought:
            projection_key = _projection_message_key(message, thought["display"]["summary"])
            if not _projection_seen(projection_key, seen_projection_keys):
                events.append(thought)
        for tool_call in _message_tool_calls(message):
            tool_id = _tool_call_id(tool_call)
            tool_name = _tool_call_name(tool_call)
            tool_args = _tool_call_args(tool_call)
            if tool_id:
                tool_inputs[tool_id] = {"name": tool_name, "args": tool_args}
            projection_key = f"tool:{tool_id or tool_name}:start"
            if _projection_seen(projection_key, seen_projection_keys):
                continue
            readable = _projection_tool_event_to_timeline_event(
                tool_name=tool_name,
                tool_id=tool_id,
                status="running",
                input_data=tool_args,
                output_data={},
                raw_event_id=raw_event_id,
            )
            if readable:
                events.append(readable)
        if _is_projection_tool_message(message):
            tool_id = _message_field(message, "tool_call_id")
            remembered = tool_inputs.get(tool_id, {})
            tool_name = _message_field(message, "name") or _string(remembered.get("name"))
            output_data = _coerce_tool_output_dict(_message_field(message, "content"))
            projection_key = f"tool:{tool_id or tool_name}:end"
            if _projection_seen(projection_key, seen_projection_keys):
                continue
            readable = _projection_tool_event_to_timeline_event(
                tool_name=tool_name,
                tool_id=tool_id,
                status="completed" if not output_data.get("error") else "failed",
                input_data=remembered.get("args") if isinstance(remembered.get("args"), dict) else {},
                output_data=output_data,
                raw_event_id=raw_event_id,
            )
            if readable:
                if tool_name == "playwright_snap_tool":
                    readable["snapshot_event"] = {
                        "event": "on_tool_end",
                        "name": tool_name,
                        "data": {"output": output_data},
                    }
                events.append(readable)
    return events


def _projection_seen(projection_key: str, seen_projection_keys: set[str] | None) -> bool:
    if seen_projection_keys is None:
        return False
    if projection_key in seen_projection_keys:
        return True
    seen_projection_keys.add(projection_key)
    return False


def _projection_message_key(message, content: str) -> str:
    message_id = _string(_message_field(message, "id"))
    if message_id:
        return f"message:{message_id}"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"message-content:{digest}"


def _projection_message_to_thought_event(message, *, raw_event_id: str | None) -> dict | None:
    if _is_projection_tool_message(message):
        return None
    thought = _public_agent_thought(_message_field(message, "content"))
    if not thought:
        return None
    return {
        "type": "agent_thought",
        "payload": _clean_compact_payload(
            {
                "status": "completed",
                "raw_event_id": raw_event_id,
            }
        ),
        "display": {
            "kind": "thought",
            "title": "Agent",
            "summary": thought,
        },
    }


def _public_agent_thought(content) -> str:
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") if item.get("type") in {"text", "output_text"} else ""
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        content = "\n".join(parts)
    text = _compact_event_payload(content).strip()
    if not text:
        return ""
    import re

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    text = re.sub(r"```(?:json|text)?\s*.*?```", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    if not text or text.startswith("{") or text.startswith("["):
        return ""
    return text[:500]


def _projection_tool_event_to_timeline_event(
    *,
    tool_name: str,
    tool_id: str,
    status: str,
    input_data: dict,
    output_data: dict,
    raw_event_id: str | None,
) -> dict | None:
    event_name = "on_tool_start" if status == "running" else "on_tool_error" if status == "failed" else "on_tool_end"
    display = _readable_tool_display(
        tool_name,
        event_name,
        {"input": input_data, "output": output_data},
        status,
    )
    stream_type = "agent_tool_started" if status == "running" else "agent_tool_failed" if status == "failed" else "agent_tool_completed"
    if tool_name == "write_todos":
        if status != "completed":
            return None
        return {
            "type": "agent_plan_updated",
            "payload": _clean_compact_payload(
                {
                    "step_id": f"agent-tool-{tool_id or tool_name}",
                    "tool_name": tool_name,
                    "status": status,
                    "raw_event_id": raw_event_id,
                    "error_summary": _compact_event_payload(output_data.get("error")),
                    "plan_steps": _todo_plan_steps(input_data.get("todos")),
                }
            ),
        }
    if display is None:
        return None
    payload = {
        "step_id": f"agent-tool-{tool_id or tool_name}",
        "tool_name": tool_name,
        "status": status,
        "raw_event_id": raw_event_id,
        "error_summary": _compact_event_payload(output_data.get("error")),
    }
    return {
        "type": stream_type,
        "payload": _clean_compact_payload(payload),
        "display": display,
    }


def _todo_plan_steps(todos) -> list[dict]:
    if not isinstance(todos, list):
        return []
    steps = []
    for index, todo in enumerate(todos, start=1):
        if not isinstance(todo, dict):
            continue
        content = _readable_todo_description(_compact_event_payload(todo.get("content")))
        if not content:
            continue
        steps.append(
            {
                "step_id": _compact_event_payload(todo.get("id")) or f"agent-todo-{index}",
                "step_number": index,
                "description": content,
                "status": _compact_event_payload(todo.get("status")) or "pending",
                "action_type": "todo",
                "execution_strategy": "agent_plan",
            }
        )
    return steps


def _readable_todo_description(content: str) -> str:
    """Polish agent todos for UI display without changing the requested action."""
    if not content:
        return ""
    description = content.strip()
    description = _replace_once(description, "进入工作台页面", "打开工作台界面")
    description = _replace_once(description, "进入工作台", "打开工作台界面")
    description = _replace_once(description, "进入该 Agent 的草稿编辑页面", "打开该 Agent 的草稿编辑界面")
    description = _replace_once(description, "进入该Agent的草稿编辑页面", "打开该 Agent 的草稿编辑界面")
    description = _replace_once(description, "在草稿编辑页面调试预览找到对话框", "在草稿编辑界面打开调试预览，找到对话框")
    description = _replace_once(description, "在预览对话框的输入框中输入", "在预览对话框中点击输入框，输入")
    description = _replace_once(description, "发送对话", "点击发送按钮发送对话")
    if "新建" in description and "Agent" in description and "点击" not in description:
        description = description.replace("新建", "点击创建按钮，新建", 1)
    return description


def _replace_once(value: str, old: str, new: str) -> str:
    return value.replace(old, new, 1) if old in value else value


def _messages_from_projection_update(data) -> list:
    if not isinstance(data, dict):
        return []
    messages = []
    for value in data.values():
        if isinstance(value, dict):
            node_messages = value.get("messages")
            if isinstance(node_messages, list):
                messages.extend(node_messages)
        elif isinstance(value, list):
            messages.extend(value)
    return messages


def _message_tool_calls(message) -> list:
    calls = _message_field(message, "tool_calls") or _message_field(message, "tool_call_chunks")
    return calls if isinstance(calls, list) else []


def _is_projection_tool_message(message) -> bool:
    message_type = _message_field(message, "type") or _message_field(message, "role")
    return message_type == "tool" or message.__class__.__name__ == "ToolMessage"


def _message_field(message, key: str):
    if isinstance(message, dict):
        return message.get(key)
    return getattr(message, key, None)


def _tool_call_id(tool_call) -> str:
    return _string(_message_field(tool_call, "id") or _message_field(tool_call, "tool_call_id"))


def _tool_call_name(tool_call) -> str:
    return _string(_message_field(tool_call, "name"))


def _tool_call_args(tool_call) -> dict:
    args = _message_field(tool_call, "args")
    return args if isinstance(args, dict) else {}


def _status_display(kind: str, title: str, summary: str) -> dict:
    return {"kind": kind, "title": title, "summary": summary}


def _publish_run_terminal_event(project_id: str, run_id: str, event_type: str, payload: dict) -> dict:
    result_summary = _compact_event_payload(payload.get("result_summary"))
    fallback_summary = {
        "run_completed": "探索任务已完成。",
        "run_failed": "探索任务失败。",
        "run_cancelled": "探索任务已停止。",
    }.get(event_type, "探索任务已结束。")
    display = _status_display("agent_run", _terminal_event_title(event_type), result_summary or fallback_summary)
    timeline_event = (
        _ExplorationEventLog(
            project_id=project_id,
            run_id=run_id,
            filename="timeline_events.jsonl",
        ).append(event_type, payload, display=display)
        if project_id
        else {}
    )
    try:
        event_bus.publish(
            run_id,
            event_type,
            payload,
            display=display,
            timeline_event_id=timeline_event.get("event_id"),
        )
    except TypeError:
        event_bus.publish(run_id, event_type, payload)
    return timeline_event


def _project_id_from_run(run) -> str:
    if not run:
        return ""
    if isinstance(run, dict):
        return _string(run.get("project_id"))
    try:
        return _string(run["project_id"])
    except (KeyError, TypeError):
        return ""


def _terminal_event_title(event_type: str) -> str:
    if event_type == "run_completed":
        return "探索完成"
    if event_type == "run_failed":
        return "探索失败"
    if event_type == "run_cancelled":
        return "探索停止"
    return "探索结束"


def _agent_recursion_config(max_pages: int) -> dict:
    try:
        page_budget = int(max_pages or 0)
    except (TypeError, ValueError):
        page_budget = 0
    return {"recursion_limit": max(100, page_budget * 8)}


async def _ainvoke_agent(agent, payload: dict, config: dict):
    signature = inspect.signature(agent.ainvoke)
    parameters = signature.parameters.values()
    accepts_config = "config" in signature.parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters
    )
    if accepts_config:
        return await agent.ainvoke(payload, config=config)
    return await agent.ainvoke(payload)


class _ExplorationEventLog:
    def __init__(self, *, project_id: str, run_id: str, filename: str) -> None:
        self.project_id = project_id
        self.run_id = run_id
        self.filename = filename
        self.path = self._resolve_path()
        self.sequence = self._last_sequence()

    def append(self, event_type: str, payload: dict, *, display: dict | None = None) -> dict:
        if self.path is None:
            return {}
        self.sequence += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event_id": f"evt-{self.sequence:06d}",
            "run_id": self.run_id,
            "type": event_type,
            "payload": payload,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        if display:
            event["display"] = display
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def _resolve_path(self) -> Path | None:
        if not self.project_id or not self.run_id:
            return None
        return (
            settings.PROJECT_FILE_STORAGE_ROOT
            / self.project_id
            / "page_exploration"
            / "runs"
            / self.run_id
            / self.filename
        )

    def _last_sequence(self) -> int:
        if self.path is None or not self.path.exists():
            return 0
        last_sequence = 0
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                event_id = _string(event.get("event_id"))
                if event_id.startswith("evt-"):
                    last_sequence = max(last_sequence, int(event_id.removeprefix("evt-")))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return last_sequence
        return last_sequence


def _clean_compact_payload(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value not in ("", None, [], {})}


def _readable_tool_display(tool_name: str, event_name: str, data: dict, status: str) -> dict | None:
    """生成工具调用的前端显示信息。

    只为关键工具生成显示信息，过滤辅助性工具：
    - 保留：页面操作（导航、点击、快照）、页面事实写入、计划更新
    - 过滤：内部文件读取、URL记录等辅助操作
    """
    input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
    output_data = data.get("output") if isinstance(data.get("output"), dict) else {}
    error = _compact_event_payload(data.get("error")) or _compact_event_payload(output_data.get("error"))

    # 过滤掉辅助性工具：read_file（内部配置读取）、update_explored_url_tool（URL记录）
    if tool_name in {"read_file", "update_explored_url_tool"}:
        return None

    if tool_name == "write_todos":
        todos = input_data.get("todos") if isinstance(input_data, dict) else []
        current = next((todo for todo in todos if isinstance(todo, dict) and todo.get("status") == "in_progress"), None) if isinstance(todos, list) else None
        pending = [todo for todo in todos if isinstance(todo, dict) and todo.get("status") == "pending"][:3] if isinstance(todos, list) else []
        current_content = _readable_todo_description(_tool_field(current or {}, "content"))
        return _tool_display(
            "todo_update",
            "探索计划更新",
            current_content or "更新探索待办计划。",
            status,
            [
                {"label": "当前进行", "value": current_content},
                {
                    "label": "待处理",
                    "value": "\n".join(
                        f"{index + 1}. {_readable_todo_description(_tool_field(todo, 'content'))}"
                        for index, todo in enumerate(pending)
                    ),
                },
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )
    if tool_name == "playwright_navigate_tool":
        url = _tool_field(input_data, "url") or _tool_field(output_data, "url")
        return _tool_display(
            "navigate",
            "打开页面",
            f"打开 {_compact_url_for_display(url) or '目标页面'}",
            status,
            [{"label": "目标 URL", "value": _compact_url_for_display(url), "mono": True}, {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)}],
            error,
        )
    if tool_name == "playwright_click_tool":
        locator = _tool_field(input_data, "locator") or _compact_event_payload(data.get("input"))
        target = _locator_label(locator) or "页面元素"
        return _tool_display(
            "click",
            "点击元素",
            f"点击 {target}",
            status,
            [
                {"label": "目标", "value": target},
                {"label": "定位器", "value": locator, "mono": True},
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )
    if tool_name == "playwright_snap_tool":
        page_title = _tool_field(output_data, "title")
        page_url = _compact_url_for_display(_tool_field(output_data, "url"))
        page_identity = page_title or page_url or "当前页面"
        return _tool_display(
            "snapshot",
            "采集页面快照",
            f"采集 {page_identity} 的页面结构",
            status,
            [
                {"label": "页面", "value": page_title or page_identity},
                {"label": "URL", "value": page_url, "mono": True},
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )
    if tool_name == "write_page_artifact_tool":
        path = _tool_field(output_data, "path") or _tool_field(input_data, "path") or _tool_field(input_data, "artifact_path")
        page_label = _tool_field(input_data, "title") or _tool_field(input_data, "page_title")
        return _tool_display(
            "artifact_write",
            "写入页面事实",
            f"写入 {page_label} 的页面事实（{Path(path).name}）" if page_label and path else f"写入 {Path(path).name}" if path else "写入页面事实",
            status,
            [
                {"label": "页面", "value": page_label},
                {"label": "产物", "value": path, "mono": True},
                {"label": "结果", "value": _status_label(status), "tone": _status_tone(status)},
            ],
            error,
        )

    # 如果有错误，显示错误信息（即使是未识别的工具）
    if error:
        return _tool_display("error", "执行失败", _error_reason(error), status, [{"label": "原因", "value": error, "tone": "danger"}], error)

    # 未识别的工具不生成显示信息，会被上层过滤掉
    return None


def _tool_display(kind: str, title: str, summary: str, status: str, fields: list[dict], error: str = "") -> dict:
    if error:
        title = f"{title}失败" if not title.endswith("失败") else title
        if not summary or summary == title or "失败" not in summary:
            summary = _error_reason(error) or summary
        if not any(field.get("label") == "原因" for field in fields):
            fields = [*fields, {"label": "原因", "value": error, "tone": "danger"}]
    return {
        "kind": kind,
        "title": title,
        "summary": summary,
        "fields": [field for field in fields if field.get("value")],
    }


def _tool_field(record: dict, key: str) -> str:
    return _compact_event_payload(record.get(key)) if isinstance(record, dict) else ""


def _status_label(status: str) -> str:
    return {"running": "执行中", "completed": "完成", "failed": "失败"}.get(status, status)


def _status_tone(status: str) -> str:
    return "danger" if status == "failed" else "success"


def _compact_url_for_display(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlparse(value)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.path or '/'}{('?' + parsed.query) if parsed.query else ''}"
    except Exception:
        pass
    return value[:96]


def _locator_label(locator: str) -> str:
    if not locator:
        return ""
    import re

    match = re.match(r"^[a-zA-Z]+-(.+?)-\d+$", locator)
    if match:
        return " / ".join(part for part in match.group(1).split("-") if part)
    return locator[:64]


def _summarize_element_roles(elements: list) -> str:
    labels = {"button": "按钮", "link": "链接", "textbox": "输入框", "checkbox": "复选框", "tab": "标签"}
    counts: dict[str, int] = {}
    for element in elements:
        if isinstance(element, dict):
            role = _compact_event_payload(element.get("role"))
            if role:
                counts[role] = counts.get(role, 0) + 1
    return " · ".join(f"{labels.get(role, role)} {count}" for role, count in counts.items())


def _summarize_key_elements(elements: list) -> str:
    names = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        name = _compact_event_payload(element.get("name") or element.get("text"))
        if name and name not in names:
            names.append(name)
        if len(names) >= 5:
            break
    return "、".join(names)


def _error_reason(error: str) -> str:
    if not error:
        return ""
    lowered = error.lower()
    if "429" in error or "rate_limit_exceeded" in error:
        return "模型配额限制"
    if "stale_ref" in lowered or "unknown element id" in lowered or "element is not attached" in lowered:
        return "元素引用已失效（页面已刷新）"
    if "timeout" in lowered or "timed out" in lowered:
        return "操作超时"
    if "not visible" in lowered or "not attached" in lowered or "intercept" in lowered:
        return "元素当前不可点击"
    if "no element" in lowered or "no node" in lowered or "not found" in lowered or "selector" in lowered and "resolved" in lowered:
        return "未找到匹配元素"
    if "navigation" in lowered and "fail" in lowered:
        return "页面导航失败"
    if "permission" in lowered or "denied" in lowered:
        return "权限不足或被拒绝"
    return "执行失败"


def _compact_event_payload(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except TypeError:
            value = str(value)
    value = " ".join(value.split())
    return value[:240]


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
            "version_no": 1,
            "title": f"{run_dict['title']} - 探索报告",
            "markdown_content": report_content,
            "change_summary": "",
            "created_at": run_dict.get("finished_at") or run_dict.get("updated_at"),
            "artifact_schema_version": 2,
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
