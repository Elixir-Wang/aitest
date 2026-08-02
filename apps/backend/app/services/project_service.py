import secrets

from pydantic import SecretStr
from langchain_openai import ChatOpenAI

from app.agents.model_selection import build_agent_model, resolve_model_selection, thinking_disabled_extra_body
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import project_repo
from app.repositories.project_repo import SYSTEM_RESERVED_PROJECT_IDS
from app.schemas.project import ProjectCreateIn, ProjectUpdateIn
from app.presentation.serializers import serialize_project
from app.services import operation_log_service, project_version_service

STATUSES = {"active", "archived"}

# 使用站点探索的模型配置来优化探索目标
EXPLORATION_GOAL_OPTIMIZE_CAPABILITY_ID = "page_exploration"


def list_projects(actor) -> list[dict]:
    with connect() as db:
        if actor["role"] == "admin":
            rows = project_repo.list_all(db)
        else:
            rows = project_repo.list_visible(db, actor)
        return [
            serialize_project(
                row,
                actor["role"],
                project_repo.has_project_assets(db, row["id"]),
                _current_version_summary(db, row),
            )
            for row in rows
            if row["id"] not in SYSTEM_RESERVED_PROJECT_IDS
        ]


def create_project(payload: ProjectCreateIn, actor) -> dict:
    validate_status(payload.status)
    project_id = f"project-{secrets.token_hex(8)}"
    with connect() as db:
        try:
            project_repo.create(
                db,
                project_id=project_id,
                name=payload.name.strip(),
                status=payload.status,
                description=payload.description.strip(),
            )
            project_version_service.create_initial_version(db, project_id, actor["id"])
        except Exception as exc:
            raise api_error(409, "PROJECT_CONFLICT", "项目名称已存在。") from exc
        row = project_repo.find_by_id(db, project_id)
        result = serialize_project(row, actor["role"], False, _current_version_summary(db, row))
    operation_log_service.record_success(
        module="project",
        action="create",
        object_type="project",
        object_id=project_id,
        object_name=result["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=_actor_display_name(actor),
        source="web",
        summary=f"新建项目：{result['name']}",
        after={"name": result["name"], "description": result["description"], "status": result["status"]},
    )
    return result


def update_project(project_id: str, payload: ProjectUpdateIn, actor) -> dict:
    if project_id in SYSTEM_RESERVED_PROJECT_IDS:
        raise api_error(409, "PROJECT_SYSTEM_RESERVED", "系统保留项目不能编辑。")
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        validate_status(updates["status"])

    assignments, values = _build_update_assignments(updates)
    with connect() as db:
        existing = project_repo.find_by_id(db, project_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        if assignments:
            assignments.append("updated_at = CURRENT_TIMESTAMP")
            try:
                project_repo.update(db, project_id, assignments, values)
            except Exception as exc:
                raise api_error(409, "PROJECT_CONFLICT", "项目名称已存在。") from exc
        row = project_repo.find_by_id(db, project_id)
        result = serialize_project(
            row,
            actor["role"],
            project_repo.has_project_assets(db, project_id),
            _current_version_summary(db, row),
        )
        before = {"name": existing["name"], "description": existing["description"], "status": existing["status"]}
        after = {"name": result["name"], "description": result["description"], "status": result["status"]}
    operation_log_service.record_change(
        module="project",
        action="update",
        object_type="project",
        object_id=project_id,
        object_name=result["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=_actor_display_name(actor),
        source="web",
        summary=f"编辑项目：{result['name']}",
        before=before,
        after=after,
    )
    return result


def delete_project(project_id: str, actor) -> dict:
    if project_id in SYSTEM_RESERVED_PROJECT_IDS:
        raise api_error(409, "PROJECT_SYSTEM_RESERVED", "系统保留项目不能删除。")
    with connect() as db:
        existing = project_repo.find_by_id(db, project_id)
        if not existing:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        if project_repo.has_project_assets(db, project_id):
            requirement_names = project_repo.list_requirement_names(db, project_id)
            if requirement_names:
                raise api_error(409, "PROJECT_HAS_REQUIREMENTS", f"项目下存在需求：{'、'.join(requirement_names)}")
            raise api_error(409, "PROJECT_HAS_ASSETS", "项目下存在关联数据，不能删除项目。")
        snapshot = {"name": existing["name"], "description": existing["description"], "status": existing["status"]}
        project_repo.delete(db, project_id)
    operation_log_service.record_change(
        module="project",
        action="delete",
        object_type="project",
        object_id=project_id,
        object_name=snapshot["name"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=_actor_display_name(actor),
        source="web",
        summary=f"删除项目：{snapshot['name']}",
        before=snapshot,
        after={},
    )
    return {"success": True}


def validate_status(status: str) -> None:
    if status not in STATUSES:
        raise api_error(400, "INVALID_STATUS", "项目状态不合法。")


def _build_update_assignments(updates: dict) -> tuple[list[str], list[object]]:
    field_map = {
        "name": "name",
        "description": "description",
        "status": "status",
    }
    assignments = []
    values = []
    for key, column in field_map.items():
        if key in updates:
            assignments.append(f"{column} = ?")
            value = updates[key]
            values.append(value.strip() if isinstance(value, str) else value)
    return assignments, values


def _actor_display_name(actor) -> str:
    return operation_log_service.actor_display_name(actor)


def _current_version_summary(db, project) -> dict | None:
    if not project or not project["default_version_id"]:
        return None
    from app.repositories import project_version_repo

    row = project_version_repo.find_by_project_and_id(db, project["id"], project["default_version_id"])
    return project_version_service.version_summary(row) if row else None


def optimize_exploration_goal(project_id: str, goal: str, actor) -> dict:
    """使用AI优化探索目标

    Args:
        project_id: 项目ID
        goal: 原始探索目标
        actor: 当前用户

    Returns:
        包含优化后目标的字典
    """
    # 验证项目是否存在
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")

    # 获取模型配置
    try:
        selection = resolve_model_selection(EXPLORATION_GOAL_OPTIMIZE_CAPABILITY_ID)
        llm = build_agent_model(selection, extra_body=thinking_disabled_extra_body(selection))
    except (ValueError, KeyError) as e:
        raise api_error(500, "MODEL_NOT_CONFIGURED", f"AI模型未配置：{str(e)}")

    # 构建步骤整理提示词
    system_prompt = """你是一个页面探索目标整理助手。

你的任务是把用户输入的自然语言探索目标，整理成清晰、顺序明确、可执行的步骤清单。

要求：
- 只基于用户原始内容进行整理，不添加用户未提及的新目标、新验证点或业务假设
- 输出必须是步骤编号格式：1. 2. 3.
- 每一步只描述一个具体操作或等待结果，尽量包含页面位置、操作对象和预期结果
- 保留用户原文中的关键对象、页面、按钮、输入内容和动作
- 可以补足必要的连接词，让步骤更清晰，但不能扩展为“关键点”“验收点”“测试断言”
- 优先使用“打开界面、点击按钮、输入内容、等待结果”等可执行表达，例如“打开工作台界面，点击创建按钮，新建自主规划 Agent”
- 不要输出“验证以下关键点”
- 不要输出解释、前缀、总结或 Markdown 标题"""

    user_prompt = f"""请将以下探索目标整理为明确的执行步骤：

{goal}

请直接返回编号步骤清单。"""

    try:
        # 调用LLM进行优化
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        response = llm.invoke(messages)
        optimized_goal = response.content.strip()

        return {"optimized_goal": optimized_goal}
    except Exception as e:
        raise api_error(500, "OPTIMIZATION_FAILED", f"探索目标优化失败：{str(e)}")
