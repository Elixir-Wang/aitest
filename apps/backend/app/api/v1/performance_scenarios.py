from fastapi import APIRouter, Depends

from app.dependencies.auth import current_user, require_admin
from app.schemas.performance_scenario import PerformanceScenarioCreateIn, PerformanceScenarioUpdateIn
from app.services.performance_testing import scenario_service


router = APIRouter(prefix="/projects/{project_id}/performance-scenarios", tags=["performance-scenarios"])
run_router = APIRouter(prefix="/projects/{project_id}/performance-runs", tags=["performance-runs"])


@router.post("")
def create(project_id: str, payload: PerformanceScenarioCreateIn, actor=Depends(require_admin)) -> dict:
    return scenario_service.create_scenario(project_id, payload, actor)


@router.get("")
def list_all(project_id: str, actor=Depends(current_user)) -> list[dict]:
    return scenario_service.list_scenarios(project_id, actor)


@router.get("/{scenario_id}")
def get_one(project_id: str, scenario_id: str, actor=Depends(current_user)) -> dict:
    return scenario_service.get_scenario(project_id, scenario_id, actor)


@router.patch("/{scenario_id}")
def update(project_id: str, scenario_id: str, payload: PerformanceScenarioUpdateIn, actor=Depends(require_admin)) -> dict:
    return scenario_service.update_scenario(project_id, scenario_id, payload, actor)


@router.delete("/{scenario_id}", status_code=204)
def delete(project_id: str, scenario_id: str, actor=Depends(require_admin)) -> None:
    scenario_service.delete_scenario(project_id, scenario_id, actor)


@router.post("/{scenario_id}/runs")
def create_run(project_id: str, scenario_id: str, actor=Depends(require_admin)) -> dict:
    return scenario_service.create_run(project_id, scenario_id, actor)


@run_router.get("/{run_id}")
def get_run(project_id: str, run_id: str, actor=Depends(current_user)) -> dict:
    return scenario_service.get_run(project_id, run_id, actor)
