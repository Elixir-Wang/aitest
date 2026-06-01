from typing import Any

from app.agents.runtime import run_agent


AGENT_ID = "requirement_merge"


async def run_requirement_merge_prompt(prompt: str) -> Any:
    result = await run_agent(AGENT_ID, prompt)
    return result.output
