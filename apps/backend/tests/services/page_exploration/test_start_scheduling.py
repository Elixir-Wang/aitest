from app.services.page_exploration import service


class _Db:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Repo:
    def __init__(self):
        self.run = {"id": "run-queued", "project_id": "project-1", "status": "queued"}

    def find_by_id(self, _db, _run_id):
        return self.run

    def reset_completion_state(self, _db, _run_id):
        return None

    def update_status(self, _db, _run_id, status):
        self.run = {**self.run, "status": status}


def test_orphaned_queued_run_is_actually_scheduled(monkeypatch):
    repo = _Repo()
    started = []

    class _Thread:
        def __init__(self, *, target, args, daemon):
            started.append((target, args, daemon))

        def start(self):
            started.append("started")

    monkeypatch.setattr(service, "connect", lambda: _Db())
    monkeypatch.setattr(service, "exploration_run_repo", repo)
    monkeypatch.setattr(service, "_clear_previous_exploration_outputs", lambda _run: None)
    monkeypatch.setattr(service.event_bus, "clear", lambda _run_id: None)
    monkeypatch.setattr(service.event_bus, "publish", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.threading, "Thread", _Thread)
    service._running_explorations.pop("run-queued", None)

    result = service.start_exploration_async({"id": "user-1"}, "run-queued")

    assert result["status"] == "queued"
    assert started[-1] == "started"


def test_in_process_queued_run_is_not_scheduled_twice(monkeypatch):
    repo = _Repo()
    monkeypatch.setattr(service, "connect", lambda: _Db())
    monkeypatch.setattr(service, "exploration_run_repo", repo)
    service._running_explorations["run-queued"] = {"should_stop": False}

    try:
        result = service.start_exploration_async({"id": "user-1"}, "run-queued")
    finally:
        service._running_explorations.pop("run-queued", None)

    assert result["status"] == "queued"


def test_resume_exploration_schedules_without_clearing_outputs(monkeypatch):
    repo = _Repo()
    started = []
    cleared = []

    class _Thread:
        def __init__(self, *, target, args, daemon):
            started.append((target, args, daemon))

        def start(self):
            started.append("started")

    monkeypatch.setattr(service, "connect", lambda: _Db())
    monkeypatch.setattr(service, "exploration_run_repo", repo)
    monkeypatch.setattr(service, "_clear_previous_exploration_outputs", lambda run: cleared.append(run))
    monkeypatch.setattr(service.event_bus, "clear", lambda _run_id: None)
    monkeypatch.setattr(service.event_bus, "publish", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.threading, "Thread", _Thread)
    service._running_explorations.pop("run-queued", None)

    result = service.resume_exploration_async({"id": "user-1"}, "run-queued")

    assert result["status"] == "queued"
    assert cleared == []
    assert started[0][1] == ("run-queued", True)
    assert started[-1] == "started"
