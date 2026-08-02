import json
import os
from pathlib import Path

import pytest

from support.scenario import run_scenario


pytestmark = pytest.mark.skipif(
    not os.environ.get("API_SCENARIO_FILE", "").strip(),
    reason="API_SCENARIO_FILE is not set",
)


def test_scenario(api_client):
    suite_root = Path(__file__).resolve().parents[2]
    scenario_file = os.environ.get("API_SCENARIO_FILE", "").strip()
    scenario_path = (suite_root / scenario_file).resolve()
    try:
        scenario_path.relative_to(suite_root)
    except ValueError as exc:
        raise RuntimeError("API_SCENARIO_FILE must be inside the pytest suite") from exc
    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    run_scenario(api_client, scenario)
