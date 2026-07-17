from app.agents.page_exploration.state.coverage_state import CoverageState


def test_coverage_state_requires_every_discovered_element_to_finish() -> None:
    state = CoverageState()
    state.discover_elements([
        {"role": "button", "name": "创建"},
        {"role": "button", "name": "删除"},
    ])

    assert state.pending_count == 2
    assert state.complete is False

    first = state.next_pending()
    assert first is not None
    state.mark_executing(first["stable_key"])
    state.mark_verified(first["stable_key"], {"status": "success"})

    assert state.pending_count == 1
    assert state.complete is False

    second = state.next_pending()
    assert second is not None
    state.mark_verified(second["stable_key"], {"status": "success"})
    assert state.complete is True


def test_coverage_state_tracks_created_data_and_cleanup() -> None:
    state = CoverageState()
    state.discover_elements([{"stable_key": "button:create", "role": "button", "name": "创建"}])
    state.record_test_data({"kind": "agent", "id": "test-1"})
    state.mark_verified("button:create", {"status": "success"})
    assert state.complete is False

    state.record_cleanup({"kind": "agent", "id": "test-1", "status": "deleted"})
    assert state.complete is True
