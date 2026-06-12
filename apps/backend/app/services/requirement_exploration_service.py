import json
from pathlib import Path

from app.agents.requirement_exploration.schemas import (
    RequirementExplorationInput,
    RequirementExplorationPlan,
)
from app.agents.requirement_exploration.service import generate_exploration_plan_from_requirement_sync
from app.core.db import connect
from app.core.exceptions import api_error
from app.core.storage import resolve_stored_path
from app.repositories import project_repo, requirement_analysis_run_repo


def generate_exploration_plan_from_requirement(
    project_id: str,
    document_id: str,
    run_id: str,
    actor,
) -> dict:
    """
    从需求分析结果生成探索计划

    Args:
        project_id: 项目ID
        document_id: 需求文档ID
        run_id: 需求分析运行ID
        actor: 当前用户

    Returns:
        dict: 生成的探索计划（JSON格式）
    """
    with connect() as db:
        # 1. 验证项目存在
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")

        # 2. 获取需求分析结果
        analysis_run = requirement_analysis_run_repo.find_run_by_id(db, run_id)
        if not analysis_run:
            raise api_error(404, "NOT_FOUND", "需求分析运行不存在。")

        if analysis_run["document_id"] != document_id:
            raise api_error(404, "NOT_FOUND", "需求分析运行不属于该文档。")

        if analysis_run["status"] != "completed":
            raise api_error(409, "ANALYSIS_NOT_COMPLETED", "需求分析尚未完成，无法生成探索计划。")

        # 3. 读取分析结果
        result_path = resolve_stored_path(analysis_run["result_path"])
        if not result_path.exists():
            raise api_error(404, "RESULT_NOT_FOUND", "需求分析结果文件不存在。")

        with open(result_path, "r", encoding="utf-8") as f:
            analysis_result = json.load(f)

        enhanced_requirement = analysis_result.get("output", {}).get("enhanced_requirement_markdown", "")
        if not enhanced_requirement:
            raise api_error(409, "NO_ENHANCED_REQUIREMENT", "需求分析结果中没有增强版需求文档。")

        # 4. 获取项目上下文
        project_context = {
            "project_id": project_id,
            "project_name": project.get("name", ""),
            "project_description": project.get("description", ""),
            "document_id": document_id,
            "analysis_run_id": run_id,
        }

        # 5. 调用agent生成探索计划
        input_data = RequirementExplorationInput(
            requirement_markdown=enhanced_requirement,
            project_context=project_context,
        )

        try:
            plan_output: RequirementExplorationPlan = generate_exploration_plan_from_requirement_sync(input_data)
        except Exception as error:
            raise api_error(
                502,
                "PLAN_GENERATION_FAILED",
                f"生成探索计划失败：{str(error)[:300]}",
            ) from error

        # 6. 补充document_id和run_id到plan对象
        plan_dict = plan_output.model_dump()
        plan_dict["requirement_doc_id"] = document_id
        plan_dict["requirement_run_id"] = run_id

        # 7. 保存探索计划到需求分析产物目录
        _save_exploration_plan(analysis_run, plan_dict)

        return plan_dict


def get_exploration_plan_from_requirement(
    project_id: str,
    document_id: str,
    run_id: str,
    actor,
) -> dict:
    """
    获取已生成的探索计划

    Args:
        project_id: 项目ID
        document_id: 需求文档ID
        run_id: 需求分析运行ID
        actor: 当前用户

    Returns:
        dict: 探索计划（JSON格式）
    """
    with connect() as db:
        # 验证项目和分析运行
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")

        analysis_run = requirement_analysis_run_repo.find_run_by_id(db, run_id)
        if not analysis_run:
            raise api_error(404, "NOT_FOUND", "需求分析运行不存在。")

        if analysis_run["document_id"] != document_id:
            raise api_error(404, "NOT_FOUND", "需求分析运行不属于该文档。")

        # 读取探索计划
        plan_path = _get_exploration_plan_path(analysis_run)
        if not plan_path.exists():
            raise api_error(404, "PLAN_NOT_FOUND", "探索计划不存在，请先生成。")

        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)

        return plan


def _save_exploration_plan(analysis_run: dict, plan: dict) -> None:
    """保存探索计划到文件"""
    plan_path = _get_exploration_plan_path(analysis_run)
    plan_path.parent.mkdir(parents=True, exist_ok=True)

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def _get_exploration_plan_path(analysis_run: dict) -> Path:
    """获取探索计划文件路径"""
    artifact_root = resolve_stored_path(analysis_run["artifact_root"])
    return artifact_root / "exploration-plan.json"
