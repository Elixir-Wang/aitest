"""Recover malformed model tool calls without breaking chat message ordering."""

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from typing_extensions import override


class InvalidToolCallRecoveryError(RuntimeError):
    """Raised when a model repeatedly returns malformed tool call arguments."""


class InvalidToolCallRecoveryMiddleware(AgentMiddleware):
    """Turn invalid tool calls into protocol-complete error responses and retry."""

    def __init__(self, *, max_retries: int = 2) -> None:
        super().__init__()
        if max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return "InvalidToolCallRecoveryMiddleware"

    @hook_config(can_jump_to=["model"])
    @override
    def after_model(
        self,
        state: AgentState[Any],
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages or not isinstance(messages[-1], AIMessage):
            return None

        assistant_message = messages[-1]
        invalid_calls = assistant_message.invalid_tool_calls
        if not invalid_calls:
            return None

        retry_count = sum(
            1
            for message in messages
            if isinstance(message, AIMessage) and message.invalid_tool_calls
        )
        if retry_count > self.max_retries:
            raise InvalidToolCallRecoveryError(
                f"模型连续 {retry_count} 次返回无法解析的工具调用参数，已停止重试。"
            )

        # A provider can return valid and invalid calls in the same assistant
        # message. Every call must have a corresponding ToolMessage before a
        # retry; acknowledging only invalid_tool_calls causes the provider to
        # reject the next request with "insufficient tool messages".
        calls_by_id = {
            call.get("id"): call
            for call in [*assistant_message.tool_calls, *invalid_calls]
            if call.get("id")
        }
        tool_messages = [
            ToolMessage(
                content=(
                    "Structured output arguments were invalid or incomplete. "
                    "Regenerate the complete response as valid JSON matching the tool schema."
                ),
                tool_call_id=call_id,
                name=call.get("name"),
                status="error",
            )
            for call_id, call in calls_by_id.items()
        ]
        if not tool_messages:
            raise InvalidToolCallRecoveryError("模型返回了无法关联 tool_call_id 的无效工具调用。")

        return {"messages": tool_messages, "jump_to": "model"}


__all__ = ["InvalidToolCallRecoveryError", "InvalidToolCallRecoveryMiddleware"]
