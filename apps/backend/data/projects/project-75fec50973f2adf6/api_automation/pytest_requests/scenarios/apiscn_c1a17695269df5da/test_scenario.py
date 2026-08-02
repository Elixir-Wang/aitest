import json
from pathlib import Path

from scenario import run_scenario


def test_scenario(api_client):
    scenario = json.loads((Path(__file__).parent / "scenario.json").read_text(encoding="utf-8"))
    run_scenario(api_client, scenario)
