from app.api.v1.api_automation import router


def test_api_repair_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/projects/{project_id}/api-runs/{run_id}/repair-session" in paths
    assert "/projects/{project_id}/api-repair-sessions/{session_id}" in paths
    assert "/projects/{project_id}/api-repair-sessions/{session_id}/attempts" not in paths
    assert "/projects/{project_id}/api-repair-attempts/{attempt_id}" in paths
    assert "/projects/{project_id}/api-repair-attempts/{attempt_id}/approve" in paths
    assert "/projects/{project_id}/api-repair-attempts/{attempt_id}/apply" in paths
    assert "/projects/{project_id}/api-repair-attempts/{attempt_id}/discard" in paths
    assert "/projects/{project_id}/api-repair-attempts/{attempt_id}/reject" in paths
    assert "/projects/{project_id}/api-repair-sessions/{session_id}/rollback" in paths
