from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.site_exploration.agent import site_exploration_agent
from app.agents.site_exploration.schemas import SiteExplorationInput, SiteExplorationOutput


CAPABILITY_ID = "site_exploration"


async def plan_site_exploration(input_data: SiteExplorationInput) -> SiteExplorationOutput:
    if not input_data.site_url.strip():
        raise ValueError("探索站点 URL 为空，无法规划站点探索。")
    if not input_data.artifact_root.strip():
        raise ValueError("探索产物目录为空，无法规划站点探索。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = site_exploration_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_site_exploration_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("站点探索智能体未返回结构化结果。")
    return output


def _build_site_exploration_input(input_data: SiteExplorationInput) -> str:
    include_paths = _split_lines(input_data.scope)
    exclude_paths = _split_lines(input_data.forbidden_paths)
    return "\n".join(
        [
            f"run_id: {input_data.run_id}",
            f"project_name: {input_data.project_name}",
            f"environment_name: {input_data.environment_name}",
            f"site_url: {input_data.site_url}",
            f"artifact_root: {input_data.artifact_root}",
            "",
            "goal:",
            input_data.goal.strip() or "未设置",
            "",
            "include_paths:",
            "\n".join(f"- {item}" for item in include_paths) if include_paths else "- 未设置",
            "",
            "exclude_paths:",
            "\n".join(f"- {item}" for item in exclude_paths) if exclude_paths else "- 未设置",
            "",
            "limits:",
            f"- max_pages: {input_data.max_pages}",
            f"- max_actions: {input_data.max_actions}",
            f"- timeout_minutes: {input_data.timeout_minutes}",
            "",
            "runner_contract_required:",
            "- runner: ts_playwright",
            "- artifact_schema_version: 2",
            "- expected_artifacts: run.yaml, summary.yaml, graph.yaml, blockers.yaml, pages/*.yaml, checks/goal-validation.yaml, reports/exploration-report.md, logs/run.log",
        ]
    )


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.replace(",", "\n").splitlines() if line.strip()]
