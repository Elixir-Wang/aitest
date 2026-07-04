# apps/backend/tests/agents/page_exploration/test_page_artifact_writer.py
import pytest
from pathlib import Path

from app.services.page_exploration.page_artifact_writer import (
    PageArtifactWriter,
    NewStateObservation,
    NewElementObservation,
    MergeResult,
)
from app.agents.page_exploration.schemas import TriggeredBy


def _obs(*, sid_short, state_type, triggered_by=None, parent_state_id=None, elements=None, observed_url="/x"):
    return NewStateObservation(
        page_id="page-x", page_title="X", normalized_path="/x",
        observed_url=observed_url, run_id="run-1",
        observed_at="2026-07-04T10:00:00Z",
        state_type=state_type,
        title=sid_short,
        dom_signature="sha256:temp",  # 写入会被重算
        triggered_by=triggered_by,
        parent_state_id=parent_state_id,
        elements=elements or [],
    )


def _tb(from_state, ek="button-a", action="click", url_changed=False):
    return TriggeredBy(
        from_state=from_state, element_key=ek,
        action=action, url_changed=url_changed, observed_url="/x"
    )


def test_initial_create(tmp_path: Path):
    page_dir = tmp_path / "pages"
    writer = PageArtifactWriter(tmp_path)
    obs = _obs(sid_short="root", state_type="root", triggered_by=None)
    result = writer.merge_states([obs])
    assert isinstance(result, MergeResult)
    # root state 应分配一个 seq=1 的 id
    assert any(s.endswith("__root__001") for s in result.added_state_ids)
    out = tmp_path / "pages" / "page-x.yaml"
    assert out.exists()


def test_idempotent_repeat(tmp_path: Path):
    writer = PageArtifactWriter(tmp_path)
    obs = _obs(sid_short="root", state_type="root")
    writer.merge_states([obs])
    # 第二次同输入 - state 总数不应该增
    result2 = writer.merge_states([obs])
    assert result2.added_state_ids == []
    # 但 state 应被更新 (last_observed_at 等)
    # 通过读 yaml 验证 state 总数 = 1
    import yaml
    data = yaml.safe_load((tmp_path / "pages" / "page-x.yaml").read_text(encoding="utf-8"))
    assert len(data["states"]) == 1


def test_first_to_wins_for_conflict(tmp_path: Path):
    writer = PageArtifactWriter(tmp_path)
    el_a = NewElementObservation(
        key="button-a", source={"role": "button", "name": "Alpha"},
        inferred=False
    )
    obs1 = _obs(sid_short="root", state_type="root",
                elements=[NewElementObservation(
                    key="button-x", source={"role":"button","name":"X"},
                    inferred=False
                )])
    obs2 = _obs(sid_short="root", state_type="root",
                elements=[NewElementObservation(
                    key="button-x", source={"role":"button","name":"X-different"},
                    inferred=True
                )])
    # 第一次: name="X"；第二次故意改 name
    writer.merge_states([obs1])
    result2 = writer.merge_states([obs2])
    import yaml
    data = yaml.safe_load((tmp_path / "pages" / "page-x.yaml").read_text(encoding="utf-8"))
    el = data["states"][0]["elements"][0]
    assert el["source"]["name"] == "X"   # 先到为强
    assert "conflicts" in el  # 冲突被记录


def test_lock_timeout_returns_flag(tmp_path: Path, monkeypatch):
    writer = PageArtifactWriter(tmp_path)
    obs = _obs(sid_short="root", state_type="root")
    # 模拟 acquire 阶段抛 LockTimeout
    from app.services.page_exploration import page_artifact_writer as mod
    class _RaisingLock:
        def __enter__(self): raise mod.LockTimeout("x")
        def __exit__(self,*a): pass
    monkeypatch.setattr(mod, "FileLock", lambda *a, **k: _RaisingLock())
    result = writer.merge_states([obs])
    assert result.skipped_due_to_lock is True
