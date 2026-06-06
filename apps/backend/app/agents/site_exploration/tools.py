from langchain.tools import tool

from app.agents.site_exploration.schemas import PlaywrightExplorerContract, PlaywrightExplorerResult


@tool
def prepare_playwright_explorer_contract(contract: PlaywrightExplorerContract) -> PlaywrightExplorerResult:
    """Prepare the TS Playwright runner contract without performing browser actions."""
    return PlaywrightExplorerResult(
        status="planned",
        contract=contract,
        expected_artifacts=[
            "run.yaml",
            "summary.yaml",
            "graph.yaml",
            "blockers.yaml",
            "pages/*.yaml",
            "checks/goal-validation.yaml",
            "reports/exploration-report.md",
            "logs/run.log",
        ],
    )


tools = [prepare_playwright_explorer_contract]
