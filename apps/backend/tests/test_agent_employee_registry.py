from app.agents.capabilities import list_ai_capabilities
from app.agents.employee_registry import list_agent_employees


def test_every_ai_capability_is_registered_as_employee() -> None:
    capability_ids = [capability.id for capability in list_ai_capabilities()]
    employees = list_agent_employees()

    assert [employee["id"] for employee in employees] == capability_ids
    assert all(employee["registered"] is True for employee in employees)
    assert all(employee["name"] for employee in employees)
    assert all(employee["department"] for employee in employees)
    assert all(employee["display_name"] for employee in employees)
    assert all(employee["role"] for employee in employees)
    assert all(employee["department_id"] for employee in employees)
    assert all(employee["department_name"] for employee in employees)
    assert all(employee["avatar_asset"] for employee in employees)
    assert all(employee["workstation_variant"] for employee in employees)
    assert all(employee["seat_code"] for employee in employees)


def test_employee_seats_are_stable_and_unique() -> None:
    employees = list_agent_employees()

    seats_by_department: dict[str, list[int]] = {}
    for employee in employees:
        seats_by_department.setdefault(employee["department_id"], []).append(employee["seat_index"])

    assert all(seat_indexes == list(range(len(seat_indexes))) for seat_indexes in seats_by_department.values())
    assert len({employee["accent_color"] for employee in employees}) >= 8
    assert len({employee["seat_code"] for employee in employees}) == len(employees)


def test_employee_visual_profiles_use_supported_assets() -> None:
    employees = list_agent_employees()

    assert {employee["workstation_variant"] for employee in employees} <= {
        "female-cream",
        "male-gray",
        "male-white",
    }
    assert all(employee["avatar_asset"].startswith(("female-", "male-")) for employee in employees)


def test_requirement_analysis_is_bound_to_zhang_jing() -> None:
    employees = {employee["id"]: employee for employee in list_agent_employees()}
    requirement_analyst = employees["requirement_analysis"]

    assert requirement_analyst["display_name"] == "张静"
    assert requirement_analyst["role"] == "需求分析师"
    assert requirement_analyst["department_id"] == "requirement"
    assert requirement_analyst["department_name"] == "需求工程组"
    assert requirement_analyst["avatar_asset"].startswith("female-")
    assert requirement_analyst["workstation_variant"] == "female-cream"
    assert requirement_analyst["task_source_types"] == [
        "requirement_analysis_run",
        "requirement_finalization_run",
    ]
