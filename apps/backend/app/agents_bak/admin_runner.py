from app.agents.runtime import AgentRunResult, run_agent


async def run_ad_hoc_agent(agent_id: str, prompt: str) -> AgentRunResult:
    return await run_agent(agent_id, prompt)
