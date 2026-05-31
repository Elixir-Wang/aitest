from __future__ import annotations

from agents import set_tracing_disabled


def disable_sdk_tracing() -> None:
    set_tracing_disabled(True)
