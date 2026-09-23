"""Public facade for deterministic standalone Locust compilation."""

from pathlib import Path

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan
from app.services.performance_testing.compiler.compiler import compile_locustfile


def render_locust_script(plan: LocustScriptPlan) -> str:
    return compile_locustfile(plan)


def runtime_module_source() -> str:
    """Compatibility helper for runtime unit tests; generated files do not use it."""
    return Path(__file__).with_name("scenario_runtime.py").read_text(encoding="utf-8")
