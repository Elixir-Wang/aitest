"""Independent local-decision agent for loop exploration."""

from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain_core.language_models import BaseChatModel

from app.agents.page_exploration_loop.prompts.system_prompt import LOOP_SYSTEM_PROMPT
from app.agents.page_exploration_loop.schemas import ActionDecision
from app.agents.page_exploration_loop.tools import get_loop_tools
from app.agents.shared.invalid_tool_call_recovery import InvalidToolCallRecoveryMiddleware
from app.agents.shared.structured_output import structured_output_runnable


def page_exploration_loop_agent(model, *, tools=None, max_actions: int = 80):
    """Create the independent Loop Agent; existing page Agent is intentionally not imported."""
    backend_root = Path(__file__).resolve().parents[3]
    backend = FilesystemBackend(root_dir=str(backend_root), virtual_mode=True)
    all_tools = list(get_loop_tools())
    if tools:
        all_tools.extend(tools)
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=LOOP_SYSTEM_PROMPT,
        backend=backend,
        middleware=[
            InvalidToolCallRecoveryMiddleware(max_retries=2),
            ToolCallLimitMiddleware(thread_limit=max_actions, run_limit=max_actions),
        ],
    )


def loop_action_decider(model: BaseChatModel):
    """Return a cross-provider structured-output runnable for local decisions."""
    return structured_output_runnable(model, ActionDecision)
