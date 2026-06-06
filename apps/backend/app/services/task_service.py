from app.core.db import connect

RUNNING_GROUP = "running"
WAITING_GROUP = "waiting"
FAILED_GROUP = "failed"
COMPLETED_GROUP = "completed"

RUNNING_GROUPS = {RUNNING_GROUP, WAITING_GROUP}
RUNNING_INDICATOR_SOURCE_TYPES = {"knowledge_build", "requirement_file"}

EXPLORATION_STATUS = {
    "pending": (WAITING_GROUP, "待启动"),
    "queued": (RUNNING_GROUP, "排队中"),
    "running": (RUNNING_GROUP, "探索中"),
    "waiting_human": (WAITING_GROUP, "等待人工"),
    "stopping": (RUNNING_GROUP, "停止中"),
    "cancelled": (COMPLETED_GROUP, "已取消"),
    "partial": (COMPLETED_GROUP, "部分完成"),
    "completed": (COMPLETED_GROUP, "已完成"),
    "blocked": (FAILED_GROUP, "探索阻塞"),
}

KNOWLEDGE_STATUS = {
    "building": (RUNNING_GROUP, "构建中"),
    "blocked": (FAILED_GROUP, "构建阻塞"),
    "draft": (COMPLETED_GROUP, "草稿"),
    "published": (COMPLETED_GROUP, "已发布"),
}

REQUIREMENT_FILE_STATUS = {
    "pending": (RUNNING_GROUP, "等待转换"),
    "processing": (RUNNING_GROUP, "转换中"),
    "success": (COMPLETED_GROUP, "转换成功"),
    "warning": (COMPLETED_GROUP, "转换完成"),
    "failed": (FAILED_GROUP, "转换失败"),
}

STATUS_META_BY_SOURCE_TYPE = {
    "exploration_run": EXPLORATION_STATUS,
    "knowledge_build": KNOWLEDGE_STATUS,
    "requirement_file": REQUIREMENT_FILE_STATUS,
}


def list_running_tasks(actor, *, project_id: str | None = None) -> list[dict]:
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
    tasks = _collect_visible_tasks(actor)
    tasks = _filter_tasks(tasks, project_id=project_id, status_group=status_group, module=module, keyword=keyword)
    tasks.sort(key=lambda item: (item["created_at"], item["id"]), reverse=True)
    total = len(tasks)
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    start = (page - 1) * page_size
    return {"items": tasks[start : start + page_size], "total": total, "page": page, "page_size": page_size}


def get_task_by_source(actor, *, source_type: str, source_id: str) -> dict | None:
    for task in _collect_visible_tasks(actor):
        if task["source_type"] == source_type and task["source_id"] == source_id:
            return task
    return None


def get_task_by_source_for_event(*, source_type: str, source_id: str) -> dict | None:
    with connect() as db:
        project_names = {
            row["id"]: row["name"]
            for row in db.execute("SELECT id, name FROM projects WHERE status != 'archived'").fetchall()
        }
        for task in [
            *_exploration_tasks(db, project_names),
            *_knowledge_tasks(db, project_names),
            *_requirement_file_tasks(db, project_names),
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


def actor_can_see_project(actor, project_id: str) -> bool:
    with connect() as db:
        return project_id in _visible_project_names(db, actor)


def _collect_visible_tasks(actor) -> list[dict]:
    with connect() as db:
        project_names = _visible_project_names(db, actor)
        return [
            *_exploration_tasks(db, project_names),
            *_knowledge_tasks(db, project_names),
            *_requirement_file_tasks(db, project_names),
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


def _knowledge_tasks(db, project_names: dict[str, str]) -> list[dict]:
    if not project_names:
        return []
    rows = db.execute(
        """
        SELECT id, project_id, build_no, status, summary, updated_at, created_at
        FROM knowledge_builds
        WHERE project_id IN ({})
        """.format(_placeholders(project_names)),
        tuple(project_names),
    ).fetchall()
    return [
        _task(
            task_id=f"knowledge:{row['id']}",
            source_type="knowledge_build",
            source_id=row["id"],
            project_id=row["project_id"],
            project_name=project_names[row["project_id"]],
            module="knowledge",
            module_label="知识库",
            title=row["build_no"],
            status=row["status"],
            status_meta=KNOWLEDGE_STATUS,
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"] or row["created_at"],
            detail_url="/knowledge",
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
