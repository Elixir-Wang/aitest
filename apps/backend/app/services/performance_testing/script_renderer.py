from pprint import pformat
from typing import Any

from app.agents.performance_testing.script_generation.schemas import LocustScriptPlan


def _runtime_plan(plan: LocustScriptPlan) -> dict[str, Any]:
    """Serialize only fields consumed by the selected runtime user."""
    raw = plan.model_dump(mode="json")
    if plan.target_type == "scenario":
        payload = {
            "target_type": "scenario",
            "scenario_name": plan.scenario_name,
            "steps": raw.get("steps") or [],
        }
        if raw.get("scenario_variables"):
            payload["scenario_variables"] = raw["scenario_variables"]
    else:
        payload = {
            "target_type": "endpoint",
            "request": raw.get("request"),
            "success_rules": raw.get("success_rules") or [],
        }
    if raw.get("data", {}).get("json_rows"):
        payload["data"] = raw["data"]
    if raw.get("random_seed") is not None:
        payload["random_seed"] = raw["random_seed"]
    if plan.load.mode != "fixed":
        payload["load"] = {"stages": raw.get("load", {}).get("stages") or []}
        payload["circuit_breaker"] = raw.get("circuit_breaker") or {}
    return payload


def render_locust_script(plan: LocustScriptPlan) -> str:
    plan_source = pformat(_runtime_plan(plan), sort_dicts=True, width=100)
    wait_min = plan.load.wait_time_min_seconds
    wait_max = plan.load.wait_time_max_seconds
    base = "ScenarioUser" if plan.target_type == "scenario" else "EndpointUser"
    shape = "\nfrom scenario_runtime import PerformanceLoadShape as RuntimeLoadShape\n" if plan.load.mode != "fixed" else ""
    shape_class = "\n\nclass PerformanceLoadShape(RuntimeLoadShape):\n    plan = PLAN\n" if plan.load.mode != "fixed" else ""
    return f'''from locust import between, task

from scenario_runtime import {base}
{shape}

PLAN = {plan_source}


class PerformanceUser({base}):
    plan = PLAN
    wait_time = between({wait_min!r}, {wait_max!r})

    @task
    def execute_target(self):
        self.run_plan()
{shape_class}
'''


def runtime_module_source() -> str:
    """Return the source copied beside generated_locustfile.py for each run."""
    from pathlib import Path

    return Path(__file__).with_name("scenario_runtime.py").read_text(encoding="utf-8")
