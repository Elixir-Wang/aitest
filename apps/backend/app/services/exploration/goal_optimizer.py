from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.core.db import connect
from app.core.exceptions import api_error
from app.repositories import project_repo
from app.schemas.exploration import ExplorationGoalOptimizeIn
from app.services.exploration.service import _ensure_project_visible

CAPABILITY_ID = "site_exploration"
MINIMAX_THINKING_DISABLED_EXTRA_BODY = {"thinking": {"type": "disabled"}}


def optimize_exploration_goal(project_id: str, payload: ExplorationGoalOptimizeIn, actor) -> dict:
    goal = payload.goal.strip()
    if not goal:
        raise api_error(400, "EXPLORATION_GOAL_REQUIRED", "请先输入探索目标。")

    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "NOT_FOUND", "项目不存在。")
        _ensure_project_visible(project, actor)

    try:
        selection = resolve_model_selection(CAPABILITY_ID)
        model = build_agent_model(selection, extra_body=_model_extra_body(selection))
        response = model.invoke(_build_prompt(goal))
    except Exception as error:
        raise api_error(502, "EXPLORATION_GOAL_OPTIMIZE_FAILED", f"大模型优化探索目标失败：{str(error)[:300]}") from error

    optimized_goal = _extract_response_text(response).strip()
    if not optimized_goal:
        raise api_error(502, "EXPLORATION_GOAL_OPTIMIZE_EMPTY", "大模型未返回有效探索目标。")

    return {"optimized_goal": optimized_goal}


def _model_extra_body(selection) -> dict | None:
    if selection.provider.strip().lower() == "minimax":
        return MINIMAX_THINKING_DISABLED_EXTRA_BODY
    return None


def _build_prompt(goal: str) -> str:
    return f"""你是 AI 测试系统中的探索目标润色助手。你的输出会被直接写入“探索目标”输入框。

任务：
只基于用户提供的原始探索目标，整理成清晰、有条理、可执行的 Web 站点探索目标。

整理原则：
1. 保留原始意图和关键对象，不改变用户想探索的方向。
2. 识别原始内容中的操作链路、页面区域、功能入口和验证意图，按合理执行顺序重组。
3. 将内容拆成合适的探索模块，每个模块下面列出有序步骤。
4. 合并重复步骤，避免把多个步骤写成一个长句。
5. 明确每个模块要探索的目标、关键操作和观察点；如果原文没有提供，不要凭空补充业务背景。
6. 不生成测试用例，不扩展为验收标准，不加入原文没有暗示的功能范围。

输出格式：
- 只输出可直接使用的探索目标正文。
- 第一行用一句话概括整体探索目标，格式为：整体目标：...
- 从第二行开始按模块输出，模块格式为：模块一：...
- 每个模块下面使用 1. 2. 3. 的有序步骤。
- 步骤必须是短句或中等长度句子，避免一个步骤包含多个独立动作。
- 模块数量根据原始内容决定，通常 2 到 5 个。
- 不要输出 Markdown 标题，不要使用 #、##、###。
- 不要输出“优化后的探索目标”“以下是”等引导语。
- 不要解释优化过程。
- 不要使用代码块。

原始探索目标：
{goal}
"""


def _extract_response_text(response) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content or "")
