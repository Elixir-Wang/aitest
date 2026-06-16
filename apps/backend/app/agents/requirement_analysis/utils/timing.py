"""需求分析工作流步骤耗时记录。"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def start_step_timer() -> float:
    return time.time()


def record_step_timing(
    metadata: dict[str, Any],
    *,
    run_id: str,
    step: str,
    started_at: float,
) -> int:
    elapsed_ms = int((time.time() - started_at) * 1000)
    timings = metadata.setdefault("step_timings", {})
    timings[step] = elapsed_ms
    logger.info(
        "requirement_analysis_step | run_id=%s step=%s elapsed_ms=%s",
        run_id,
        step,
        elapsed_ms,
    )
    return elapsed_ms


__all__ = ["start_step_timer", "record_step_timing"]
