from __future__ import annotations

import secrets
from typing import Any

from agents import RunConfig

from app.ai_agents.model_provider import build_model_provider, resolve_agent_model_selection


def build_run_config(
    agent_id: str,
    *,
    actor_id: str | None = None,
    trace_metadata: dict[str, Any] | None = None,
) -> RunConfig:
    selection = resolve_agent_model_selection(agent_id)
    metadata = {
        "agent_id": agent_id,
        "model": selection.model,
        "model_provider_id": selection.model_provider_id,
        "provider": selection.provider,
        "base_url": selection.base_url,
    }
    if actor_id:
        metadata["actor_id"] = actor_id
    if trace_metadata:
        metadata.update({key: str(value) for key, value in trace_metadata.items()})
    return RunConfig(
        model=selection.model,
        model_provider=build_model_provider(selection),
        workflow_name=f"ai-testing-{agent_id}",
        trace_id=f"agrun-{secrets.token_hex(8)}",
        group_id=agent_id,
        trace_metadata=metadata,
    )
