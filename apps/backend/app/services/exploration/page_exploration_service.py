"""页面探索服务层

提供页面探索的业务逻辑，包括：
- 创建和管理探索任务
- 启动探索流程
- 查询探索结果
"""

import asyncio
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from app.core import settings
from app.core.db import connect
from app.repositories import exploration_artifact_repo, exploration_page_repo, exploration_run_repo
from app.services.exploration import event_bus


CAPABILITY_ID = "page_exploration"

# 全局存储运行中的探索任务状态
_running_explorations: Dict[str, Dict[str, Any]] = {}
_exploration_lock = threading.Lock()


def create_exploration_run(
    actor,
    project_id: str,
    environment_id: str,
    title: str,
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
        artifacts = exploration_artifact_repo.list_by_run(db, run_id)
        run_dict = _normalize_exploration_run_detail(dict(run))

        # 转换为前端期望的modules结构
        modules = []
        if pages:
            modules.append({
                "id": "main-module",
                "module_key": "main",
                "module_name": "主探索模块",
                "entry_path": dict(run).get("scope", ""),
                "planned_page_count": dict(run).get("max_pages", 0),
                "explored_page_count": len(pages),
                "blocked_page_count": 0,
                "action_count": 0,
                "field_count": 0,
                "state_transition_count": 0,
                "completion_status": dict(run).get("status", "pending"),
                "completion_summary": dict(run).get("result_summary", ""),
                "pages": [
                    {
                        "id": p["id"],
                        "title": p.get("title", ""),
                        "url": p.get("url", ""),
                        "entry_path": p.get("normalized_path", ""),
                        "yaml_path": p.get("yaml_path", ""),
                        "status": p.get("status", "explored"),
                        "blocker_reason": "",
                        "recent_event": "",
                        "structure_summary": f"发现 {p.get('element_count', 0)} 个元素",
                        "steps": [],
                    }
                    for p in [dict(page) for page in pages]
                ],
                "elements": [],
                "blockers": [],
            })
        else:
            modules = _modules_from_artifacts(run_dict)

        return {
            "run": run_dict,
            "artifact_schema_version": 2 if modules else 1,
            "unsupported_artifact": False,
            "unsupported_reason": "",
            "modules": modules,
        }


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

        # 更新状态为queued（准备启动）
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

        # 只有运行中的任务才能停止
        if run_dict["status"] not in ["running", "queued"]:
            raise ValueError(f"探索任务当前状态为 {run_dict['status']}，无法停止")

        # 更新状态为stopping
        exploration_run_repo.update_status(db, run_id, "stopping")

        # 设置停止标志
        with _exploration_lock:
            if run_id in _running_explorations:
                _running_explorations[run_id]["should_stop"] = True

        updated_run = exploration_run_repo.find_by_id(db, run_id)
        return dict(updated_run) if updated_run else {}


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

    except Exception as e:
        # 更新状态为blocked（数据库约束不允许failed状态）
        with connect() as db:
            exploration_run_repo.update_status(
                db,
                run_id,
                "blocked",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=f"探索失败: {str(e)}",
            )
        event_bus.publish(
            run_id,
            "run_failed",
            {
                "status": "blocked",
                "error": str(e),
                "result_summary": f"探索失败: {str(e)}",
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
    from app.agents.model_selection import resolve_model_selection, build_agent_model, TOOL_CALLING_UNSUPPORTED_PROVIDERS
    from app.agents.page_exploration.agent import page_exploration_agent

    project_id = run_config["project_id"]
    start_url = _exploration_start_url(run_config)
    scope = str(run_config.get("scope") or "").strip()
    max_pages = run_config["max_pages"]

    try:
        # 1. 解析模型配置
        model_selection = resolve_model_selection("site_exploration")

        # 2. 提前检查模型是否支持工具调用
        if model_selection.provider.strip().lower() in TOOL_CALLING_UNSUPPORTED_PROVIDERS:
            raise ValueError(
                f"探索任务需要工具调用能力，但当前模型 {model_selection.provider}/{model_selection.model} "
                f"不支持 OpenAI tools/function calling 格式。"
                f"请为 'site_exploration' 能力分配支持工具调用的模型（如 OpenAI、Anthropic、DeepSeek 等）。"
            )

        model = build_agent_model(model_selection)

        # 2. 运行异步探索
        asyncio.run(_execute_exploration_async(
            model=model,
            project_id=project_id,
            run_id=run_id,
            start_url=start_url,
            max_pages=max_pages,
            scope=scope,
        ))

    except Exception as e:
        # 发生错误，更新状态为blocked（数据库约束不允许failed状态）
        with connect() as db:
            exploration_run_repo.update_status(
                db,
                run_id,
                "blocked",
                finished_at=datetime.now(timezone.utc).isoformat(),
                result_summary=f"探索阻塞: {str(e)}",
            )
        raise


def _exploration_start_url(run_config: dict) -> str:
    """Use the configured environment entry URL; scope is a module constraint, not a URL."""
    start_url = str(run_config.get("environment_site_url") or "").strip()
    if not start_url:
        raise ValueError("探索任务缺少环境站点入口 URL，请先配置项目环境的站点地址。")
    return start_url


def _exploration_agent_prompt(start_url: str, scope: str, max_pages: int) -> str:
    lines = [f"请探索网站: {start_url}"]
    if scope.strip():
        lines.append(f"探索范围: {scope.strip()}")
    lines.append(f"最多探索 {max_pages} 个页面。")
    return "\n".join(lines)


async def _execute_exploration_async(
    model,
    project_id: str,
    run_id: str,
    start_url: str,
    max_pages: int,
    scope: str = "",
) -> None:
    """异步执行探索"""
    from app.agents.page_exploration.agent import page_exploration_agent

    # 创建agent实例
    agent = page_exploration_agent(model, project_id, run_id)
    started_at = datetime.now(timezone.utc).isoformat()
    plan_steps = _initial_exploration_plan_steps(start_url, max_pages)
    event_bus.publish(
        run_id,
        "planning_completed",
        {
            "plan_id": f"{run_id}-plan",
            "goal_summary": f"探索 {start_url}",
            "scope_summary": scope or start_url,
            "strategy": "使用页面探索 Agent 调用浏览器和产物工具，逐步发现页面结构与可测元素。",
            "modules": [scope or "主探索模块"],
            "estimated_duration_minutes": None,
            "risk_assessment": "",
            "success_criteria": [f"最多探索 {max_pages} 个页面，并记录页面事实与关键操作。"],
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
                "content": _exploration_agent_prompt(start_url, scope, max_pages),
            }
        ]
    }
    result = await _invoke_agent_with_realtime_events(agent, payload, run_id, plan_steps)

    # 更新状态为完成
    with connect() as db:
        exploration_run_repo.update_status(
            db,
            run_id,
            "completed",
            finished_at=datetime.now(timezone.utc).isoformat(),
            result_summary=f"探索完成",
        )
    event_bus.publish(
        run_id,
        "run_completed",
        {
            "status": "completed",
            "result_summary": "探索完成",
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
    )


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


async def _invoke_agent_with_realtime_events(agent, payload: dict, run_id: str, plan_steps: list[dict]):
    agent_step = plan_steps[1]
    started_at = datetime.now(timezone.utc).isoformat()
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
    )
    try:
        if hasattr(agent, "astream_events"):
            final_result = None
            async for event in agent.astream_events(payload, version="v2"):
                _publish_agent_stream_event(run_id, event)
                data = event.get("data") if isinstance(event, dict) else {}
                if isinstance(data, dict) and "output" in data:
                    final_result = data["output"]
            result = final_result if final_result is not None else {}
        else:
            result = await agent.ainvoke(payload)
        event_bus.publish(
            run_id,
            "step_completed",
            {
                **agent_step,
                "total_steps": len(plan_steps),
                "attempt": 1,
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": None,
                "success": True,
                "message": _agent_result_summary(result),
            },
        )
        return result
    except Exception as exc:
        event_bus.publish(
            run_id,
            "step_failed",
            {
                **agent_step,
                "total_steps": len(plan_steps),
                "attempt": 1,
                "started_at": started_at,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "error": str(exc),
                "failure_type": exc.__class__.__name__,
                "retryable": False,
                "message": "页面探索 Agent 执行失败。",
            },
        )
        raise


def _publish_agent_stream_event(run_id: str, event: dict) -> None:
    event_name = str(event.get("event") or "")
    name = str(event.get("name") or "")
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    if event_name in {"on_tool_start", "on_chain_start"}:
        event_bus.publish(
            run_id,
            "step_started",
            {
                "step_id": f"agent-{event_name}-{event.get('run_id') or name}",
                "step_number": 2,
                "module_name": "主探索模块",
                "action_type": name or event_name,
                "description": f"执行 {name or event_name}",
                "target_description": _compact_event_payload(data.get("input")),
                "target_selector": "",
                "value": "",
                "expected_result": "",
                "execution_strategy": "deepagents",
                "is_critical": False,
                "retry_on_failure": False,
                "max_retries": 0,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "message": f"开始执行 {name or event_name}",
            },
        )
    elif event_name in {"on_tool_end", "on_chain_end"}:
        event_bus.publish(
            run_id,
            "step_completed",
            {
                "step_id": f"agent-{event_name.replace('_end', '_start')}-{event.get('run_id') or name}",
                "step_number": 2,
                "module_name": "主探索模块",
                "action_type": name or event_name,
                "description": f"完成 {name or event_name}",
                "target_description": "",
                "target_selector": "",
                "value": "",
                "expected_result": "",
                "execution_strategy": "deepagents",
                "is_critical": False,
                "retry_on_failure": False,
                "max_retries": 0,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "success": True,
                "message": _compact_event_payload(data.get("output")) or f"完成 {name or event_name}",
            },
        )
    elif event_name in {"on_tool_error", "on_chain_error"}:
        event_bus.publish(
            run_id,
            "step_failed",
            {
                "step_id": f"agent-{event_name}-{event.get('run_id') or name}",
                "step_number": 2,
                "module_name": "主探索模块",
                "action_type": name or event_name,
                "description": f"{name or event_name} 失败",
                "target_description": "",
                "target_selector": "",
                "value": "",
                "expected_result": "",
                "execution_strategy": "deepagents",
                "is_critical": False,
                "retry_on_failure": False,
                "max_retries": 0,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "success": False,
                "error": _compact_event_payload(data.get("error")),
                "message": f"{name or event_name} 执行失败",
            },
        )


def _agent_result_summary(result) -> str:
    if isinstance(result, dict):
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            content = getattr(last, "content", None)
            if content is None and isinstance(last, dict):
                content = last.get("content")
            summary = _compact_event_payload(content)
            if summary:
                return summary
    return "页面探索 Agent 已返回结果。"


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
        runs = exploration_run_repo.list_by_project(db, project_id, limit)
        return [dict(r) for r in runs]


def list_running_runs(actor, project_id: str | None = None) -> list[dict]:
    """列出运行中的探索任务"""
    with connect() as db:
        runs = exploration_run_repo.list_running(db, project_id)
        return [dict(r) for r in runs]


def list_all_runs(actor, project_id: str | None = None, limit: int = 100) -> list[dict]:
    """列出所有探索任务（支持全局和按项目筛选）"""
    with connect() as db:
        runs = exploration_run_repo.list_all(db, project_id, limit)
        return [dict(r) for r in runs]


def list_run_pages(actor, run_id: str) -> list[dict]:
    """列出探索任务的页面"""
    with connect() as db:
        pages = exploration_page_repo.list_by_run(db, run_id)
        return [dict(p) for p in pages]


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
            "artifact_schema_version": 1,
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
        - artifact_type: 产物类型（screenshot/accessibility/structure/log/report）
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


def build_artifact_tree(actor, project_id: str | None = None) -> dict:
    """构建探索产物树结构

    Args:
        actor: 当前用户
        project_id: 项目ID（可选）

    Returns:
        产物树结构：
        {
            "id": "root",
            "name": "探索产物",
            "type": "folder",
            "children": [
                {
                    "id": "{project_id}",
                    "name": "{project_name}",
                    "type": "folder",
                    "children": [
                        {
                            "id": "{run_id}",
                            "name": "{run_title}",
                            "type": "folder",
                            "metadata": {...},
                            "children": [
                                {
                                    "id": "{artifact_id}",
                                    "name": "{file_name}",
                                    "type": "file",
                                    "fileType": "screenshot|accessibility|structure|log|report",
                                    "path": "{file_path}",
                                    "size": file_size,
                                    "createdAt": "{created_at}"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    """
    with connect() as db:
        # 获取所有探索任务
        if project_id:
            runs = exploration_run_repo.list_by_project(db, project_id, limit=500)
        else:
            runs = exploration_run_repo.list_all(db, project_id=None, limit=500)

        # 按项目分组
        projects_dict = {}
        for run in runs:
            run_dict = dict(run)
            pid = run_dict.get("project_id", "unknown")
            pname = run_dict.get("project_name", "未知项目")

            if pid not in projects_dict:
                projects_dict[pid] = {
                    "id": pid,
                    "name": pname,
                    "type": "folder",
                    "children": []
                }

            # 获取该任务的产物
            artifacts = exploration_artifact_repo.list_by_run(db, run_dict["id"])
            artifact_children = []

            for artifact in artifacts:
                art_dict = dict(artifact)
                file_path = Path(art_dict.get("file_path", ""))
                artifact_children.append({
                    "id": art_dict.get("id", ""),
                    "name": file_path.name if file_path else art_dict.get("artifact_type", "unknown"),
                    "type": "file",
                    "fileType": art_dict.get("artifact_type", "unknown"),
                    "path": str(file_path),
                    "size": file_path.stat().st_size if file_path.exists() else 0,
                    "createdAt": art_dict.get("created_at", ""),
                    "runId": run_dict["id"],
                    "runTitle": run_dict.get("title", ""),
                })

            # 添加任务节点
            projects_dict[pid]["children"].append({
                "id": run_dict["id"],
                "name": run_dict.get("title", "未命名探索"),
                "type": "folder",
                "metadata": {
                    "status": run_dict.get("status", ""),
                    "created_at": run_dict.get("created_at", ""),
                    "finished_at": run_dict.get("finished_at", ""),
                },
                "children": artifact_children,
            })

        # 构建根节点
        return {
            "id": "root",
            "name": "探索产物",
            "type": "folder",
            "children": list(projects_dict.values()),
        }
