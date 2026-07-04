"""dom_signature: 基于语义定位字段的角色 + 名称 + aria-label 的 sha256; 忽略 ref / class / xpath。"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable


def _sign_payload(elements: Iterable[dict]) -> bytes:
    norm = []
    for el in elements:
        src = el.get("source", {})
        # 仅用实读字段；inferred / placeholder 全部不参与
        fingerprint = {
            "role": src.get("role"),
            "name": src.get("name"),
            "aria_label": src.get("aria_label"),
            # 子元素视为独立 root state，不影响父 signature
        }
        norm.append((fingerprint, el.get("key")))
    return json.dumps(norm, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_dom_signature(elements: Iterable[dict]) -> str:
    payload = _sign_payload(elements)
    return "sha256:" + hashlib.sha256(payload).hexdigest()
