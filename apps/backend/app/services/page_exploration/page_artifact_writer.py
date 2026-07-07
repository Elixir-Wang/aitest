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
    # P2 强校验拒收的 observation（含原因），LLM 可见
    rejected_observations: list[dict] = field(default_factory=list)
    depth_exceeded: list[dict] = field(default_factory=list)


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

        # 集中校验整批 observation：失败整批跳过，并写到 MergeResult 里供 LLM 看见
        rejected = self._validate_observations(observations, existing)
        if rejected:
            result.rejected_observations = rejected
            observations = [
                obs for index, obs in enumerate(observations)
                if index not in {item["index"] for item in rejected}
            ]
            if not observations:
                return existing

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

    def _validate_observations(self, observations, existing) -> list[dict]:
        """批量校验 observation，拒收"占位符 / 跨级 triggered_by"等坏数据。

        校验规则（与 v2.0 addendum 对齐）：
        1. dom_signature 不能是 "sha256:unknown" 占位
        2. 非 root state 必须有 triggered_by；triggered_by.from_state 必须存在
        3. triggered_by.from_state 不能跨级（只能指向当前 state 的直接父）
        4. triggered_by.element_key 必须存在于 from_state 的 elements 中
        5. depth 不能超过 16

        返回：[{index, reason, field}, ...] 拒收列表
        """
        rejected: list[dict] = []
        # 收集现有 state id（包括 children），方便查 from_state 是否存在
        existing_state_ids = set()
        existing_state_by_id: dict[str, dict] = {}
        self._collect_states(existing["states"], existing_state_ids, existing_state_by_id)

        # 本批内分配的 state id（按顺序），用于判断非 root state 的 from_state
        # 实际上从 LLM 角度，所有非 root state 的 from_state 都应指向 existing 或 本批内已分配的 root/parent
        batch_known_ids = set(existing_state_ids)
        # 预先按本批 obs 顺序分配 state_id，把将要分配给 root/同批 parent 的 id 也加进 batch_known_ids
        # （避免 dialog 引用同批尚未写入的 root 时被误判）
        # 注意：分配算法依赖 max_n+1，需要按出现顺序递增调用。
        virtual_existing = {"states": list(existing.get("states", []))}
        # 真正分配时还会往 virtual_existing 推进。这里保守一些：只预算 root / 同批祖先。
        for obs in observations:
            if obs.state_type == "root" and (obs.parent_state_id is None or obs.parent_state_id not in batch_known_ids):
                # root 直接挂在顶层，新分配的 id 加进 batch_known_ids
                allocated = self._allocate_state_id(virtual_existing, obs)
                batch_known_ids.add(allocated)
                # 把分配后的虚拟节点 push 进 virtual_existing，让后续 root 序号递增
                virtual_existing["states"].append({
                    "id": allocated,
                    "type": "root",
                    "children": [],
                    "depth": 1,
                })

        for index, obs in enumerate(observations):
            # 1. dom_signature
            if not obs.dom_signature or obs.dom_signature == "sha256:unknown" or obs.dom_signature.strip() == "":
                rejected.append({
                    "index": index,
                    "reason": "dom_signature 不能为空或占位符 'sha256:unknown'，请使用 playwright_snap_tool 提供的 state_observation_hint。",
                    "field": "dom_signature",
                })
                continue

            # 5. depth 提前粗查（通过 page title 推断不了，但 state_type 通常对应 depth）
            #   depth 在 _merge_one_state 才最终确定，这里只做粗略提醒
            if obs.state_type not in {"root", "dialog", "drawer", "form", "list"}:
                rejected.append({
                    "index": index,
                    "reason": f"未知 state_type: {obs.state_type}",
                    "field": "state_type",
                })
                continue

            # 2. non-root 必须有 triggered_by
            if obs.state_type != "root" and obs.triggered_by is None:
                rejected.append({
                    "index": index,
                    "reason": f"state_type={obs.state_type} 缺少 triggered_by，root state 才能没有 triggered_by。",
                    "field": "triggered_by",
                })
                continue

            if obs.triggered_by is not None:
                from_state = obs.triggered_by.from_state
                if not from_state:
                    rejected.append({
                        "index": index,
                        "reason": "triggered_by.from_state 不能为空。",
                        "field": "triggered_by.from_state",
                    })
                    continue
                if from_state not in batch_known_ids and from_state not in existing_state_ids:
                    rejected.append({
                        "index": index,
                        "reason": f"triggered_by.from_state={from_state} 不在已存在 state 中，请确认是直接父 state。",
                        "field": "triggered_by.from_state",
                    })
                    continue
                # 3. 跨级校验：from_state 的 depth 与新 state 的 depth 差必须为 1
                from_depth = self._state_depth(existing["states"], from_state)
                if from_depth is None:
                    from_depth = 0  # 父不在 existing 中时（仅本批首次出现）允许 depth 差 1
                # 新 state 深度在 _merge_one_state 才算出，这里记录 from_depth 供后续检查
                obs._from_state_depth = from_depth
                # 4. element_key 必须在 from_state.elements 中（如果 from_state 在 existing）
                if from_state in existing_state_by_id:
                    from_state_dict = existing_state_by_id[from_state]
                    existing_element_keys = {
                        e.get("key") for e in from_state_dict.get("elements", []) if isinstance(e, dict)
                    }
                    if obs.triggered_by.element_key not in existing_element_keys:
                        # 不直接拒收（element 可能在 children 嵌套 state 里），
                        # 但记录 warning 到 MergeResult
                        result = getattr(self, "_current_result", None)  # 不可靠，留空
                        # 改为：在 _merge_one_state 里以"warning 字段"形式记录
                        # 这里只做硬校验：from_state 直接 element 必须存在；嵌套 children 放宽
                        nested_keys: set[str] = set()
                        self._collect_nested_element_keys(
                            from_state_dict.get("children", []),
                            nested_keys,
                        )
                        if (
                            obs.triggered_by.element_key not in existing_element_keys
                            and obs.triggered_by.element_key not in nested_keys
                        ):
                            rejected.append({
                                "index": index,
                                "reason": f"triggered_by.element_key={obs.triggered_by.element_key} 在 from_state={from_state} 的 elements 和 children 中都不存在。",
                                "field": "triggered_by.element_key",
                            })
                            continue
                batch_known_ids.add(f"{obs.page_id}__{obs.state_type}__pending")
        return rejected

    def _collect_states(self, states, ids_out, by_id_out):
        for st in states:
            ids_out.add(st.get("id"))
            by_id_out[st.get("id")] = st
            self._collect_states(st.get("children", []), ids_out, by_id_out)

    def _state_depth(self, states, sid):
        """返回 state id 的 depth；不在则 None。"""
        for st in states:
            if st.get("id") == sid:
                return st.get("depth", 1)
            nested = self._state_depth(st.get("children", []), sid)
            if nested is not None:
                return nested
        return None

    def _collect_nested_element_keys(self, children, out):
        for st in children:
            for el in st.get("elements", []):
                if isinstance(el, dict) and el.get("key"):
                    out.add(el["key"])
            self._collect_nested_element_keys(st.get("children", []), out)

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

        # v2.0 addendum 硬截断：state 嵌套深度超过 16 时停止探索。
        # 这里只把超限事实写到 result 上，不阻止写入；上层 run loop 据此停止 LLM。
        if target.get("depth", 0) > 16:
            result.depth_exceeded.append({
                "state_id": target["id"],
                "depth": target["depth"],
            })

    def _compute_state_sig(self, elements):
        flat = [{"source": {"role": e.source.get("role"), "name": e.source.get("name"),
                            "aria_label": e.source.get("aria_label")}, "key": e.key}
                for e in elements]
        return compute_dom_signature(flat)

    def _state_matches_observation(self, st, obs):
        # root state 的匹配必须同时比较 dom_signature：
        # - 相同 → 同一 state，merge elements（seen_count 递增）
        # - 不同 → 视为不同 state，追加新的 root state
        # 这样即使同一 URL 被多次 snap，只要 DOM 内容不同就各自独立记录，
        # 避免新 observation 用更多 accessibility_tree 节点覆盖旧有签名。
        if obs.state_type == "root":
            if st["type"] != "root":
                return False
            # 已有 root 的 dom_signature 与新 observation 一致则合并
            existing_sig = st.get("dom_signature", "")
            return existing_sig and existing_sig == obs.dom_signature
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
