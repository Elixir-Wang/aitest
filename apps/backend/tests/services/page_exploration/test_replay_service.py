from pathlib import Path
import time
from types import SimpleNamespace

import yaml

from app.services.page_exploration.replay.models import ReplayOperation
from app.services.page_exploration.replay.service import ReplayService
from app.services.page_exploration.replay.store import OperationsStore
from app.services.page_exploration.output_registry import _write_draft_operation
from app.services.page_exploration.replay.run_service import ReplayRunService


class FakeSession:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def click(self, locator):
        self.calls.append(("click", locator))
        return {"success": True}

    def fill(self, locator, value):
        self.calls.append(("fill", locator, value))
        return {"success": True}

    def press(self, locator, key):
        self.calls.append(("press", locator, key))
        return {"success": True}

    def navigate(self, path):
        self.calls.append(("navigate", path))
        return {"status": "passed"}

    def wait(self, milliseconds):
        self.calls.append(("wait", milliseconds))
        return {"status": "passed"}

    def go_back(self):
        self.calls.append(("go_back",))
        return {"status": "passed"}


class FallbackSession(FakeSession):
    def click(self, locator):
        self.calls.append(("click", locator))
        return {"success": locator == "getByText('创建', { exact: true })"}


def _write_project_artifacts(root: Path, project_id: str) -> None:
    project_root = root / project_id / "page_exploration"
    pages = project_root / "pages"
    pages.mkdir(parents=True)
    (pages / "page-workspace.yaml").write_text(yaml.safe_dump({
        "schema_version": "3.0",
        "page": {
            "id": "page-workspace",
            "normalized_path": "/workspace",
            "elements": [{
                "key": "textbox-智能体名称",
                "locators": [{
                    "code": "getByPlaceholder('请输入智能体名称', { exact: true })",
                }],
            }],
        },
        "states": [],
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    OperationsStore(root).upsert(project_id, ReplayOperation.model_validate({
        "key": "agent.create",
        "page_path": "/workspace",
        "parameters": {"agent_name": {"type": "string", "required": True}},
        "steps": [{
            "action": "fill",
            "element_key": "textbox-智能体名称",
            "value_ref": "agent_name",
        }],
    }))


def test_same_project_operation_uses_selected_environment_at_runtime(tmp_path, monkeypatch):
    project_id = "project-1"
    _write_project_artifacts(tmp_path, project_id)
    FakeSession.instances.clear()
    service = ReplayService(storage_root=tmp_path, session_factory=FakeSession)
    monkeypatch.setattr(service, "_load_environment", lambda project, environment: {
        "id": environment,
        "project_id": project,
        "site_url": "https://selected.example/base/",
        "login_strategy": "skip_login",
        "reuse_auth_state": False,
    })
    monkeypatch.setattr(service, "_storage_state", lambda _environment: None)

    result = service.execute(
        project_id=project_id,
        environment_id="env-any-name",
        operation_key="agent.create",
        parameters={"agent_name": "哈哈"},
    )

    assert result.success is True
    assert result.environment_id == "env-any-name"
    session = FakeSession.instances[0]
    assert session.kwargs["start_url"] == "https://selected.example/workspace"
    assert session.kwargs["browser_channel"] == "chrome"
    assert session.calls == [("fill", "getByPlaceholder('请输入智能体名称', { exact: true })", "哈哈")]
    operation = OperationsStore(tmp_path).read(project_id).operations[0]
    assert operation.status == "validated"
    assert operation.validations[0].environment_id == "env-any-name"
    assert operation.validations[0].status == "passed"


def test_operations_store_replaces_same_key_without_environment_fields(tmp_path):
    store = OperationsStore(tmp_path)
    first = ReplayOperation(key="agent.create", page_path="/old", steps=[])
    second = ReplayOperation(key="agent.create", page_path="/workspace", steps=[])

    store.upsert("project-1", first)
    artifact = store.upsert("project-1", second)

    assert artifact.base_url_source == "environment"
    assert artifact.browser == "chrome"
    assert len(artifact.operations) == 1
    assert artifact.operations[0].page_path == "/workspace"
    payload = yaml.safe_load(store.path_for("project-1").read_text(encoding="utf-8"))
    assert "pre" not in payload
    assert "pre4" not in payload


def test_replay_tries_project_locator_candidates_across_environments(tmp_path, monkeypatch):
    project_id = "project-1"
    project_root = tmp_path / project_id / "page_exploration"
    pages = project_root / "pages"
    pages.mkdir(parents=True)
    (pages / "page-workspace.yaml").write_text(yaml.safe_dump({
        "schema_version": "3.0",
        "page": {"elements": [{
            "key": "button-创建",
            "locators": [
                {"code": "getByRole('button', { name: '创建' })"},
                {"code": "getByText('创建', { exact: true })"},
            ],
        }]},
        "states": [],
    }, allow_unicode=True), encoding="utf-8")
    OperationsStore(tmp_path).upsert(project_id, ReplayOperation.model_validate({
        "key": "create",
        "steps": [{"action": "click", "element_key": "button-创建"}],
    }))
    FallbackSession.instances.clear()
    service = ReplayService(storage_root=tmp_path, session_factory=FallbackSession)
    monkeypatch.setattr(service, "_load_environment", lambda project, environment: {
        "id": environment, "project_id": project, "site_url": "https://any.example",
        "login_strategy": "skip_login", "reuse_auth_state": False,
    })
    monkeypatch.setattr(service, "_storage_state", lambda _environment: None)

    result = service.execute(
        project_id=project_id,
        environment_id="env-random",
        operation_key="create",
    )

    assert result.success is True
    assert FallbackSession.instances[0].calls == [
        ("click", "getByRole('button', { name: '创建' })"),
        ("click", "getByText('创建', { exact: true })"),
    ]


def test_successful_exploration_actions_generate_project_draft(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.page_exploration.output_registry._project_file_storage_root",
        lambda: tmp_path,
    )
    page_artifacts = [(Path("page-workspace.yaml"), {
        "page": {"elements": [{
            "key": "button-创建智能体",
            "locators": [{"code": "getByRole('button', { name: '创建智能体' })"}],
        }]},
        "states": [],
    })]
    events = [{
        "type": "agent_tool_completed",
        "payload": {
            "tool_name": "playwright_click_tool",
            "locator": "page.getByRole('button', { name: '创建智能体' })",
        },
    }]

    _write_draft_operation(
        project_id="project-1",
        run_id="run-1",
        start_url="https://any.example/workspace",
        timeline_events=events,
        page_artifacts=page_artifacts,
    )

    operation = OperationsStore(tmp_path).read("project-1").operations[0]
    assert operation.key == "exploration.run-1"
    assert operation.status == "draft"
    assert operation.page_path == "/workspace"
    assert operation.steps[0].element_key == "button-创建智能体"


def test_async_replay_run_persists_status_and_can_retry(tmp_path, monkeypatch):
    class FakeReplayService:
        def __init__(self, **_kwargs):
            pass

        def execute(self, **kwargs):
            kwargs["on_step"](SimpleNamespace(model_dump=lambda **_kwargs: {
                "index": 1, "action": "click", "element_key": "button-创建", "success": True, "detail": {},
            }))
            return SimpleNamespace(success=True)

    monkeypatch.setattr("app.services.page_exploration.replay.run_service.ReplayService", FakeReplayService)
    service = ReplayRunService(tmp_path)
    created = service.start(
        project_id="project-1",
        environment_id="env-any",
        operation_key="create",
    )
    deadline = time.time() + 2
    current = created
    while current["status"] not in {"passed", "failed", "cancelled"} and time.time() < deadline:
        time.sleep(0.01)
        current = service.get("project-1", created["id"])

    assert current["status"] == "passed"
    assert current["steps"][0]["element_key"] == "button-创建"
    retried = service.retry("project-1", created["id"])
    assert retried["id"] != created["id"]
    assert retried["environment_id"] == "env-any"
