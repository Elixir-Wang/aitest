from app.agents.capabilities import list_ai_capabilities
from app.agents.employee_registry import list_agent_employees


def test_every_ai_capability_is_registered_as_employee() -> None:
    capability_ids = [capability.id for capability in list_ai_capabilities()]
    employees = list_agent_employees()

    assert [employee["id"] for employee in employees] == capability_ids
    assert all(employee["registered"] is True for employee in employees)
    assert all(employee["name"] for employee in employees)
    assert all(employee["department"] for employee in employees)


def test_employee_seats_are_stable_and_unique() -> None:
    employees = list_agent_employees()

    assert [employee["seat_index"] for employee in employees] == list(range(len(employees)))
    assert len({employee["accent_color"] for employee in employees}) >= 8
