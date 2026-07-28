"""Controlled tool adapter for Loop mode.

The adapter reuses the existing browser tool implementations while keeping the
Loop Agent's dependency boundary explicit and allowing stricter tools later.
"""

from app.agents.page_exploration.tools import get_local_tools


def get_loop_tools() -> list:
    return list(get_local_tools())

