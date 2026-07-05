# apps/backend/app/services/page_exploration/page_artifact_writer.py
"""PageArtifactWriter - 单一写入口; 幂等合并; 先到为强。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from app.agents.page_exploration.schemas import (
    PageArtifact, Page, State, Element, TriggeredBy, SourceEntry,
)
from app.agents.page_exploration.utils.element_key import (
    build_element_key, ensure_unique_within_state,
)
from app.agents.page_exploration.utils.state_id import make_state_id
from app.agents.page_exploration.utils.dom_signature import compute_dom_signature
from app.services.page_exploration.locking import FileLock, LockTimeout


StateType = Literal["root","dialog","drawer","form","list"]


@dataclass
class NewElementObservation:
    key: str
    source: dict
    inferred: bool
    children: list["NewElementObservation"] = field(default_factory=list)


@dataclass
class NewStateObservation:
    page_id: str
    page_title: str
    normalized_path: str
    observed_url: str
    run_id: str
    observed_at: str
    state_type: StateType
    title: str
    dom_signature: str
    triggered_by: TriggeredBy | None
    parent_state_id: str | None
    elements: list[NewElementObservation]


@dataclass
class MergeResult:
    added_state_ids: list[str] = field(default_factory=list)
    updated_state_ids: list[str] = field(default_factory=list)
    added_element_keys: list[str] = field(default_factory=list)
    updated_element_keys: list[str] = field(default_factory=list)
    skipped_due_to_lock: bool = False


class PageArtifactWriter:
    LOCK_TIMEOUT_S = 5.0
    SCHEMA_VERSION = "2.0"

    def __init__(self, base_dir: Path):
        self._base = Path(base_dir)
        self._pages_dir = self._base / "pages"
        self._pages_dir.mkdir(parents=True, exist_ok=True)

    def _page_path(self, page_id: str) -> Path:
        return self._pages_dir / f"{page_id}.yaml"

    def merge_states(self, observations: list[NewStateObservation]) -> MergeResult:
        if not observations:
            return MergeResult()
        page_id = observations[0].page_id
        path = self._page_path(page_id)
        result = MergeResult()
        try:
            with FileLock(path, timeout_seconds=self.LOCK_TIMEOUT_S):
                existing = self.read_existing(page_id)
                existing = existing.model_dump(mode="python") if existing else None
                merged = self._apply_observations(existing, observations, result)
                self._write(path, merged)
        except LockTimeout:
            result.skipped_due_to_lock = True
        return result

    def read_existing(self, page_id: str) -> PageArtifact | None:
        path = self._page_path(page_id)
        if not path.exists():
            return None
        try:
            obj = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not obj or obj.get("schema_version") != self.SCHEMA_VERSION:
            return None
        return PageArtifact(**obj)

    def _apply_observations(self, existing, observations, result):
        if existing is None:
            existing = {
                "schema_version": self.SCHEMA_VERSION,
                "page": {
                    "id": observations[0].page_id,
                    "title": observations[0].page_title,
                    "normalized_path": observations[0].normalized_path,
                    "url": None,
                    "observed_url": observations[0].observed_url,
                    "first_observed_at": observations[0].observed_at,
                    "last_observed_at": observations[0].observed_at,
                    "observed_by_runs": [],
                },
                "states": [],
            }
        existing.setdefault("states", [])

        for obs in observations:
            new_id = self._allocate_state_id(existing, obs)
            self._merge_one_state(existing, obs, new_id, result)

        existing["page"]["last_observed_at"] = max(
            existing["page"]["last_observed_at"],
            *(o.observed_at for o in observations),
        )
        if observations[0].run_id not in existing["page"]["observed_by_runs"]:
            existing["page"]["observed_by_runs"].append(observations[0].run_id)
        existing["page"]["observed_url"] = observations[-1].observed_url
        existing["page"]["title"] = observations[0].page_title
        return existing

    def _allocate_state_id(self, existing, obs):
        prefix = f"{obs.page_id}__{obs.state_type}__"
        max_n = 0
        for st in existing["states"]:
            sid = st["id"]
            if sid.startswith(prefix):
                try:
                    n = int(sid.rsplit("__", 1)[1])
                    if n > max_n:
                        max_n = n
                except ValueError:
                    pass
        def _walk(states):
            nonlocal max_n
            for st in states:
                sid = st["id"]
                if sid.startswith(prefix):
                    try:
                        n = int(sid.rsplit("__", 1)[1])
                        if n > max_n:
                            max_n = n
                        return
                    except ValueError:
                        pass
                _walk(st.get("children", []))
        _walk(existing["states"])
        return make_state_id(obs.page_id, obs.state_type, max_n + 1)

    def _merge_one_state(self, existing, obs, new_id, result):
        target = None
        for st in existing["states"]:
            if self._state_matches_observation(st, obs):
                target = st
                break
            found = self._find_match_in_children(st.get("children", []), obs)
            if found is not None:
                target = found
                break

        if target is None:
            parent_id = obs.parent_state_id
            if parent_id is None:
                target = self._new_state_dict(obs, new_id, depth=1)
                existing["states"].append(target)
            else:
                parent = self._find_state_by_id(existing["states"], parent_id)
                if parent is None:
                    target = self._new_state_dict(obs, new_id, depth=1)
                    existing["states"].append(target)
                else:
                    target = self._new_state_dict(
                        obs,
                        new_id,
                        depth=parent.get("depth", 0) + 1,
                    )
                    parent.setdefault("children", []).append(target)
            result.added_state_ids.append(new_id)
        else:
            result.updated_state_ids.append(target["id"])

        self._merge_elements(target, obs.elements, result, obs.observed_at)
        target["last_observed_at"] = max(target["last_observed_at"], obs.observed_at)
        if obs.run_id not in target["observed_by_runs"]:
            target["observed_by_runs"].append(obs.run_id)
        target["dom_signature"] = self._compute_state_sig(obs.elements)

    def _compute_state_sig(self, elements):
        flat = [{"source": {"role": e.source.get("role"), "name": e.source.get("name"),
                            "aria_label": e.source.get("aria_label")}, "key": e.key}
                for e in elements]
        return compute_dom_signature(flat)

    def _state_matches_observation(self, st, obs):
        if obs.state_type == "root":
            return st["type"] == "root"
        if st["type"] != obs.state_type:
            return False
        if not obs.triggered_by:
            return False
        tb = st.get("triggered_by")
        if tb is None:
            return False
        return (
            tb.get("from_state") == obs.triggered_by.from_state
            and tb.get("element_key") == obs.triggered_by.element_key
        )

    def _find_match_in_children(self, children, obs):
        for st in children:
            if self._state_matches_observation(st, obs):
                return st
            nested = self._find_match_in_children(st.get("children", []), obs)
            if nested is not None:
                return nested
        return None

    def _find_state_by_id(self, states, sid):
        for st in states:
            if st["id"] == sid:
                return st
            nested = self._find_state_by_id(st.get("children", []), sid)
            if nested is not None:
                return nested
        return None

    def _new_state_dict(self, obs, new_id, depth: int):
        return {
            "id": new_id,
            "type": obs.state_type,
            "title": obs.title,
            "triggered_by": (
                {
                    "from_state": obs.triggered_by.from_state,
                    "element_key": obs.triggered_by.element_key,
                    "action": obs.triggered_by.action,
                    "url_changed": obs.triggered_by.url_changed,
                    "observed_url": obs.triggered_by.observed_url,
                }
                if obs.triggered_by is not None else None
            ),
            "depth": depth,
            "last_observed_at": obs.observed_at,
            "observed_by_runs": [obs.run_id],
            "dom_signature": self._compute_state_sig(obs.elements),
            "elements": [],
            "children": [],
        }

    def _merge_elements(self, target, observations, result, observed_at: str):
        existing = target.setdefault("elements", [])
        obs_keys = [self._slot_key(o) for o in observations]

        # 先按原始 key 匹配（先到为强）
        for obs_el in observations:
            orig_key = obs_el.key
            match = next((e for e in existing if e["key"] == orig_key), None)
            if match is None:
                # 新增（slot key 后续统一去重）
                new_dict = self._new_element_dict(obs_el, orig_key, observed_at)
                existing.append(new_dict)
                result.added_element_keys.append(orig_key)
            else:
                # 更新已有
                self._update_element(match, obs_el, result, observed_at)
                result.updated_element_keys.append(orig_key)

        # 统一去重（处理同一 key 出现多次的情况）
        all_keys = [e["key"] for e in existing]
        final_keys = list(ensure_unique_within_state(all_keys))
        for i, e in enumerate(existing):
            e["key"] = final_keys[i]

        target["elements"] = existing

    def _slot_key(self, obs_el):
        return obs_el.key

    def _new_element_dict(self, obs_el, key, observed_at: str):
        return {
            "key": key,
            "source": dict(obs_el.source),
            "inferred": obs_el.inferred,
            "last_seen_at": observed_at,
            "seen_count": 1,
            "children": [
                self._new_element_dict(child, child.key, observed_at)
                for child in obs_el.children
            ],
        }

    def _update_element(self, target, obs_el, result, observed_at: str):
        for k, v in obs_el.source.items():
            existing_v = target["source"].get(k)
            if existing_v is None:
                target["source"][k] = v
            elif existing_v != v:
                target.setdefault("conflicts", []).append({
                    "field": k, "attempted_value": v
                })
        target["seen_count"] = target.get("seen_count", 0) + 1
        target["last_seen_at"] = observed_at

    def _write(self, path, data):
        path.write_text(
            yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
            encoding="utf-8"
        )
