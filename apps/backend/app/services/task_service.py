from app.core.db import connect
from app.repositories import document_repo, requirement_analysis_run_repo
from app.services import operation_log_service

RUNNING_GROUP = "running"
WAITING_GROUP = "waiting"
FAILED_GROUP = "failed"
COMPLETED_GROUP = "completed"
REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES = 120

RUNNING_GROUPS = {RUNNING_GROUP}
RUNNING_INDICATOR_SOURCE_TYPES = {
    "exploration_run",
    "requirement_file",
    "requirement_analysis_run",
    "requirement_finalization_run",
    "test_case_generation_run",
    "api_automation_generation_run",
    "api_automation_run",
}

EXPLORATION_STATUS = {
    "pending": (WAITING_GROUP, "待启动"),
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "探索中"),
    "stopping": (RUNNING_GROUP, "停止中"),
    "cancelled": (COMPLETED_GROUP, "已取消"),
    "interrupted": (COMPLETED_GROUP, "已中断"),
    "completed": (COMPLETED_GROUP, "已完成"),
    "blocked": (FAILED_GROUP, "探索阻塞"),
    "failed": (FAILED_GROUP, "探索失败"),
}

REQUIREMENT_FILE_STATUS = {
    "pending": (RUNNING_GROUP, "等待转换"),
    "processing": (RUNNING_GROUP, "转换中"),
    "success": (COMPLETED_GROUP, "转换成功"),
    "warning": (COMPLETED_GROUP, "转换完成"),
    "failed": (FAILED_GROUP, "转换失败"),
}

REQUIREMENT_ANALYSIS_STATUS = {
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "分析中"),
    "stopping": (RUNNING_GROUP, "停止中"),
    "cancelled": (COMPLETED_GROUP, "已取消"),
    "completed": (COMPLETED_GROUP, "已完成"),
    "needs_clarification": (WAITING_GROUP, "等待澄清"),
    "failed": (FAILED_GROUP, "分析失败"),
}

REQUIREMENT_FINALIZATION_STATUS = {
    "running": (RUNNING_GROUP, "转换中"),
    "completed": (COMPLETED_GROUP, "转换完成"),
    "failed": (FAILED_GROUP, "转换失败"),
}

TEST_CASE_GENERATION_STATUS = {
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "生成中"),
    "completed": (COMPLETED_GROUP, "生成完成"),
    "failed": (FAILED_GROUP, "生成失败"),
}

API_AUTOMATION_GENERATION_STATUS = {
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "生成中"),
    "completed": (COMPLETED_GROUP, "生成完成"),
    "failed": (FAILED_GROUP, "生成失败"),
    "cancelled": (COMPLETED_GROUP, "已取消"),
    "interrupted": (COMPLETED_GROUP, "已中断"),
}

API_AUTOMATION_RUN_STATUS = {
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "执行中"),
    "passed": (COMPLETED_GROUP, "执行通过"),
    "failed": (FAILED_GROUP, "执行失败"),
    "cancelled": (COMPLETED_GROUP, "已取消"),
    "interrupted": (COMPLETED_GROUP, "已中断"),
}


STATUS_META_BY_SOURCE_TYPE = {
    "exploration_run": EXPLORATION_STATUS,
    "requirement_file": REQUIREMENT_FILE_STATUS,
    "requirement_analysis_run": REQUIREMENT_ANALYSIS_STATUS,
    "requirement_finalization_run": REQUIREMENT_FINALIZATION_STATUS,
    "test_case_generation_run": TEST_CASE_GENERATION_STATUS,
    "api_automation_generation_run": API_AUTOMATION_GENERATION_STATUS,
    "api_automation_run": API_AUTOMATION_RUN_STATUS,
}


def list_running_tasks(actor, *, project_id: str | None = None) -> list[dict]:
    recover_stale_requirement_analysis_runs(project_id=project_id)
    tasks = _collect_visible_tasks(actor)
    tasks = [
        task
        for task in _filter_tasks(tasks, project_id=project_id)
        if task["source_type"] in RUNNING_INDICATOR_SOURCE_TYPES
        and is_active_task_status(task["source_type"], task["status"])
    ]
    tasks.sort(key=lambda item: (item["created_at"], item["id"]), reverse=True)
    return tasks


def list_tasks(
    actor,
    *,
    project_id: str | None = None,
    status_group: str | None = None,
    module: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    recover_stale_requirement_analysis_runs(project_id=project_id)
    tasks = _collect_visible_tasks(actor)
    tasks = _filter_tasks(tasks, project_id=project_id, status_group=status_group, module=module, keyword=keyword)
    tasks.sort(key=lambda item: (item["updated_at"], item["created_at"], item["id"]), reverse=True)
    total = len(tasks)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    start = (page - 1) * page_size
    return {"items": tasks[start : start + page_size], "total": total, "page": page, "page_size": page_size}


def get_task_by_source(actor, *, source_type: str, source_id: str) -> dict | None:
    if source_type == "requirement_analysis_run":
        recover_stale_requirement_analysis_runs()
    for task in _collect_visible_tasks(actor):
        if task["source_type"] == source_type and task["source_id"] == source_id:
            return task
    return None


def get_task_by_source_for_event(*, source_type: str, source_id: str) -> dict | None:
    if source_type == "requirement_analysis_run":
        recover_stale_requirement_analysis_runs()
    with connect() as db:
        project_names = {
            row["id"]: row["name"]
            for row in db.execute("SELECT id, name FROM projects WHERE status != 'archived'").fetchall()
        }
        for task in [
            *_exploration_tasks(db, project_names),
            *_requirement_file_tasks(db, project_names),
            *_requirement_analysis_run_tasks(db, project_names),
            *_requirement_finalization_tasks(db, project_names),
            *_test_case_generation_tasks(db, project_names),
            *_api_automation_generation_tasks(db, project_names),
            *_api_automation_run_tasks(db, project_names),
        ]:
            if task["source_type"] == source_type and task["source_id"] == source_id:
                return task
    return None


def is_active_task_status(source_type: str, status: str) -> bool:
    if source_type == "exploration_run" and status == "pending":
        return False
    status_meta = STATUS_META_BY_SOURCE_TYPE.get(source_type)
    if not status_meta:
        return False
    status_group, _label = status_meta.get(status, (status, status))
    return status_group in RUNNING_GROUPS


def recover_stale_requirement_analysis_runs(*, project_id: str | None = None) -> None:
    failure_reason = _requirement_analysis_timeout_message()
    with connect() as db:
        rows = requirement_analysis_run_repo.list_stale_active_runs(
            db,
            project_id=project_id,
            timeout_minutes=REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES,
        )
        recovered_runs = [dict(row) for row in rows]
        for row in rows:
            latest_final_version = document_repo.find_latest_final_requirement_version(db, row["document_id"])
            if latest_final_version:
                document_repo.update_current_version(
                    db,
                    row["document_id"],
                    latest_final_version["id"],
                    "versioned",
                )
            requirement_analysis_run_repo.update_status(
                db,
                row["id"],
                status="failed",
                summary="需求分析失败。",
                failure_reason=failure_reason,
            )

    for row in recovered_runs:
        operation_log_service.record_task_event(
            module="requirement",
            action="fail_requirement_analysis",
            object_type="requirement_analysis_run",
            object_id=row["id"],
            object_name=row["document_name"],
            project_id=row["project_id"],
            actor_id="system",
            actor_name="系统",
            source="system",
            result="failed",
            failure_reason=failure_reason,
            summary="需求分析失败。",
            after={"status": "failed", "reason": "timeout_recovered"},
            task_id=row["id"],
        )


def recover_interrupted_requirement_analysis_runs(*, project_id: str | None = None) -> None:
    failure_reason = "服务已重启，内存中的需求分析后台任务已中断，请重新发起分析。"
    with connect() as db:
        rows = requirement_analysis_run_repo.list_active_runs(db, project_id=project_id)
        recovered_runs = [dict(row) for row in rows]
        for row in rows:
            latest_final_version = document_repo.find_latest_final_requirement_version(db, row["document_id"])
            if latest_final_version:
                document_repo.update_current_version(
                    db,
                    row["document_id"],
                    latest_final_version["id"],
                    "versioned",
                )
            requirement_analysis_run_repo.update_status(
                db,
                row["id"],
                status="failed",
                summary="需求分析已中断。",
                failure_reason=failure_reason,
            )

    for row in recovered_runs:
        operation_log_service.record_task_event(
            module="requirement",
            action="fail_requirement_analysis",
            object_type="requirement_analysis_run",
            object_id=row["id"],
            object_name=row["document_name"],
            project_id=row["project_id"],
            actor_id="system",
            actor_name="系统",
            source="system",
            result="failed",
            failure_reason=failure_reason,
            summary="需求分析已中断。",
            after={"status": "failed", "reason": "startup_recovered"},
            task_id=row["id"],
        )


def _requirement_analysis_timeout_message() -> str:
    return f"需求分析运行超过 {REQUIREMENT_ANALYSIS_RUN_TIMEOUT_MINUTES} 分钟，已自动标记为失败。"


def actor_can_see_project(actor, project_id: str) -> bool:
    with connect() as db:
        return project_id in _visible_project_names(db, actor)


def _collect_visible_tasks(actor) -> list[dict]:
    with connect() as db:
        project_names = _visible_project_names(db, actor)
        return [
            *_exploration_tasks(db, project_names),
            *_requirement_file_tasks(db, project_names),
            *_requirement_analysis_run_tasks(db, project_names),
            *_requirement_finalization_tasks(db, project_names),
            *_test_case_generation_tasks(db, project_names),
            *_api_automation_generation_tasks(db, project_names),
            *_api_automation_run_tasks(db, project_names),
        ]


def _visible_project_names(db, actor) -> dict[str, str]:
    if actor["role"] in {"admin", "guest"} or actor["project_scope"] == "全部项目":
        rows = db.execute("SELECT id, name FROM projects WHERE status != 'archived'").fetchall()
    else:
        rows = db.execute(
            "SELECT id, name FROM projects WHERE status != 'archived' AND name = ?",
            (actor["project_scope"],),
        ).fetchall()
    return {row["id"]: row["name"] for row in rows}


def _exploration_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names:
        return []
    rows = db.execute(
        """
        SELECT id, project_id, title, status, result_summary, updated_at, created_at
        FROM exploration_runs
        WHERE project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=f"exploration:{row['id']}",
            source_type="exploration_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="exploration",
            module_label="站点探索",
            title=row["title"],
            status=row["status"],
            status_meta=EXPLORATION_STATUS,
            summary=row["result_summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/projects/{row['project_id']}/exploration/{row['id']}",
        )
        for row in rows
    ]


def _requirement_file_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names:
        return []
    rows = db.execute(
        """
        SELECT m.id, m.document_id, m.original_filename, m.conversion_status, m.conversion_summary,
               m.created_at, d.project_id, d.name AS document_name
        FROM source_document_file_mappings m
        JOIN source_documents d ON d.id = m.document_id
        WHERE d.project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=f"requirement_file:{row['id']}",
            source_type="requirement_file",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="requirement",
            module_label="需求标准化",
            title=row["original_filename"] or row["document_name"],
            status=row["conversion_status"],
            status_meta=REQUIREMENT_FILE_STATUS,
            summary=row["conversion_summary"],
            created_at=row["created_at"],
            updated_at=row["created_at"],
            detail_url=f"/projects/{row['project_id']}/requirements/{row['document_id']}",
        )
        for row in rows
    ]


def _requirement_analysis_run_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names:
        return []
    rows = db.execute(
        """
        SELECT r.id, r.project_id, r.document_id, r.status, r.summary, r.failure_reason,
               r.created_at, r.updated_at, d.name AS document_name
        FROM requirement_analysis_runs r
        JOIN source_documents d ON d.id = r.document_id
        WHERE r.project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=f"requirement_analysis:{row['id']}",
            source_type="requirement_analysis_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="requirement",
            module_label="需求分析",
            title=row["document_name"],
            status=row["status"],
            status_meta=REQUIREMENT_ANALYSIS_STATUS,
            summary=row["failure_reason"] if row["status"] == "failed" and row["failure_reason"] else row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/projects/{row['project_id']}/requirements/{row['document_id']}",
        )
        for row in rows
    ]


def _requirement_finalization_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names or not _table_exists(db, "requirement_finalization_runs"):
        return []
    rows = db.execute(
        """
        SELECT r.id, r.project_id, r.document_id, r.status, r.summary, r.failure_reason,
               r.created_at, r.updated_at, d.name AS document_name
        FROM requirement_finalization_runs r
        JOIN source_documents d ON d.id = r.document_id
        WHERE r.project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=f"requirement_finalization:{row['id']}",
            source_type="requirement_finalization_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="requirement",
            module_label="最终需求",
            title=row["document_name"],
            status=row["status"],
            status_meta=REQUIREMENT_FINALIZATION_STATUS,
            summary=row["failure_reason"] if row["status"] == "failed" and row["failure_reason"] else row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/projects/{row['project_id']}/requirements/{row['document_id']}?tab=final",
        )
        for row in rows
    ]


def _test_case_generation_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names or not _table_exists(db, "test_case_generation_runs"):
        return []
    rows = db.execute(
        """
        SELECT r.id, r.test_case_set_id, r.task_id, r.status, r.error_message, r.created_at, r.updated_at,
               s.project_id, s.name AS test_case_set_name
        FROM test_case_generation_runs r
        JOIN test_case_sets s ON s.id = r.test_case_set_id
        WHERE s.project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=row["task_id"],
            source_type="test_case_generation_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="test_case",
            module_label="测试用例",
            title=row["test_case_set_name"],
            status=row["status"],
            status_meta=TEST_CASE_GENERATION_STATUS,
            summary=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/test-cases?set={row['test_case_set_id']}",
        )
        for row in rows
    ]


def _api_automation_generation_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names or not _table_exists(db, "api_generation_runs"):
        return []
    rows = db.execute(
        """
        SELECT id, project_id, task_id, status, generation_goal, error_message, created_at, updated_at
        FROM api_generation_runs
        WHERE project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=row["task_id"],
            source_type="api_automation_generation_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="api_automation",
            module_label="接口自动化",
            title=row["generation_goal"] or "接口自动化用例生成",
            status=row["status"],
            status_meta=API_AUTOMATION_GENERATION_STATUS,
            summary=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/projects/{row['project_id']}/automation/api?generationRun={row['id']}",
        )
        for row in rows
    ]


def _api_automation_run_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names or not _table_exists(db, "api_automation_runs"):
        return []
    rows = db.execute(
        """
        SELECT id, project_id, task_id, status, command_summary, error_message, created_at, updated_at
        FROM api_automation_runs
        WHERE project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=row["task_id"],
            source_type="api_automation_run",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="api_automation",
            module_label="接口自动化",
            title="接口自动化执行",
            status=row["status"],
            status_meta=API_AUTOMATION_RUN_STATUS,
            summary=row["error_message"] or row["command_summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url=f"/projects/{row['project_id']}/automation/api?run={row['id']}",
        )
        for row in rows
    ]


def _task(
    *,
    task_id: str,
    source_type: str,
    source_id: str,
    project_id: str,
    project_name: str,
    module: str,
    module_label: str,
    title: str,
    status: str,
    status_meta: dict[str, tuple[str, str]],
    summary: str | None,
    created_at: str,
    updated_at: str,
    detail_url: str,
) -> dict:
    status_group, status_label = status_meta.get(status, (status, status))
    return {
        "id": task_id,
        "source_type": source_type,
        "source_id": source_id,
        "project_id": project_id,
        "project_name": project_name,
        "module": module,
        "module_label": module_label,
        "title": title,
        "status": status,
        "status_label": status_label,
        "status_group": status_group,
        "summary": summary or "",
        "created_at": created_at,
        "updated_at": updated_at,
        "detail_url": detail_url,
    }


def _filter_tasks(
    tasks: list[dict],
    *,
    project_id: str | None = None,
    status_group: str | None = None,
    module: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    normalized_keyword = (keyword or "").strip().lower()
    return [
        task
        for task in tasks
        if (not project_id or task["project_id"] == project_id)
        and (not status_group or task["status_group"] == status_group)
        and (not module or task["module"] == module)
        and (
            not normalized_keyword
            or any(
                normalized_keyword in str(task[key]).lower()
                for key in ("project_name", "module_label", "title", "status_label", "summary")
            )
        )
    ]


def _placeholders(values: dict) -> str:
    return ", ".join("?" for _ in values)


def _table_exists(db, table: str) -> bool:
    return db.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None
