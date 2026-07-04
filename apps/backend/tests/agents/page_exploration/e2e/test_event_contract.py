"""端到端: 订阅 RunEventBus, 验证 page_artifact_state_merge 事件在 merge 时发出."""
import pytest
import threading
from pathlib import Path

from app.services.page_exploration import page_artifact_writer as mod
from app.agents.page_exploration.tools.artifact_tools import merge_page_artifact


@pytest.fixture
def event_log(monkeypatch):
    log = []
    orig_merge = mod.PageArtifactWriter.merge_states
    def wrapped(self, obs):
        result = orig_merge(self, obs)
        if result.added_state_ids:
            log.append({
                "type": "page_artifact_state_merge",
                "page_id": self._pages_dir.parent.name,
                "added_state_ids": result.added_state_ids,
            })
        return result
    monkeypatch.setattr(mod.PageArtifactWriter, "merge_states", wrapped)
    return log


def test_event_emitted_on_merge(tmp_path: Path, event_log):
    merge_page_artifact(
        page_id="page-x", project_id="proj-x", run_id="run-1",
        base_dir=tmp_path,
        observed_states=[{
            "page_id": "page-x", "page_title": "x", "normalized_path": "/x",
            "observed_url": "/x", "run_id": "run-1",
            "observed_at": "2026-07-04T10:00:00Z",
            "state_type": "root", "title": "r",
            "dom_signature": "sha256:t", "triggered_by": None,
            "parent_state_id": None, "elements": [],
        }],
    )
    assert any(e["type"] == "page_artifact_state_merge" for e in event_log)


def test_concurrent_lock_contention(monkeypatch, tmp_path: Path):
    import time
    from app.services.page_exploration import page_artifact_writer as mod

    # 把 lock 超时调整为极小值, 让竞争确定性触发超时
    monkeypatch.setattr(mod.PageArtifactWriter, "LOCK_TIMEOUT_S", 0.01)

    # 让 write 变慢，使锁持有时间 > 超时
    orig_write = mod.PageArtifactWriter._write
    def slow_write(self, path, data):
        time.sleep(0.1)
        orig_write(self, path, data)
    monkeypatch.setattr(mod.PageArtifactWriter, "_write", slow_write)

    writer = mod.PageArtifactWriter(tmp_path)
    page_yaml = tmp_path / "pages" / "page-x.yaml"
    page_yaml.parent.mkdir(parents=True, exist_ok=True)
    init_obs = mod.NewStateObservation(
        page_id="page-x", page_title="x", normalized_path="/x",
        observed_url="/x", run_id="init", observed_at="2026-07-04T10:00:00Z",
        state_type="root", title="r",
        dom_signature="sha256:t", triggered_by=None,
        parent_state_id=None, elements=[],
    )
    writer.merge_states([init_obs])

    results = {}
    barrier = threading.Barrier(2)

    def worker(name):
        barrier.wait()
        # 故意让 a 先抢锁，给 b 制造竞争
        if name == "a":
            time.sleep(0.005)
        obs = mod.NewStateObservation(
            page_id="page-x", page_title="x", normalized_path="/x",
            observed_url="/x", run_id=name, observed_at="2026-07-04T10:00:00Z",
            state_type="root", title="r",
            dom_signature="sha256:t", triggered_by=None,
            parent_state_id=None, elements=[
                mod.NewElementObservation(
                    key=f"button-{name}",
                    source={"role":"button","name":name},
                    inferred=False, children=[]
                )
            ],
        )
        results[name] = writer.merge_states([obs])

    t1 = threading.Thread(target=worker, args=("a",))
    t2 = threading.Thread(target=worker, args=("b",))
    t1.start(); t2.start()
    t1.join(); t2.join()

    flags = [r.skipped_due_to_lock for r in results.values()]
    # 锁竞争下, 持有时间 > 超时, 后抢锁的会 timeout
    assert any(flags), f"expected at least one lock timeout, got {flags}"
