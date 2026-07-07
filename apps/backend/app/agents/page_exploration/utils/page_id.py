"""Page identity utilities shared between agent tools and service layer.

所有页面 ID 和 DOM 签名计算必须走这里，确保 agent 和 service
对同一 normalized_path 产生完全一致的 page_id。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable


# ---------------------------------------------------------------------------
# page_id 生成
# ---------------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MAX_LEN = 80


def _slugify_for_page_id(value: str) -> str:
    """lowercase + non-alphanumeric → - + collapse consecutive - + strip edges."""
    if not value:
        return ""
    s = value.strip().lower()
    s = _NON_ALNUM.sub("-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def make_page_id(normalized_path: str) -> str:
    """把 URL 路径（去除协议/host 的 path+query）转换为稳定的 page_id。

    规则：
    - 去除首尾斜杠，空路径 → "home"
    - ?, &, =, #, %, : → -
    - / → -
    - 合并连续 -
    - 过滤空段
    - 前缀 "page-"

    例：
        /agentRelease?agentId=19174&access_type=0&agent_type=1
        → page-agentrelease-agentid-19174-access-type-0-agent-type-1
    """
    value = (normalized_path or "").strip("/") or "home"
    for char in ("?", "&", "=", "#", "%", ":"):
        value = value.replace(char, "-")
    value = value.replace("/", "-")
    value = "-".join(part for part in value.split("-") if part)
    return f"page-{value or 'home'}"


# ---------------------------------------------------------------------------
# dom_signature 计算（与 dom_signature.py 保持一致，供 service 层直接调用）
# ---------------------------------------------------------------------------

def compute_dom_signature_from_elements(elements: Iterable[dict]) -> str:
    """基于语义定位字段的 role + name + aria_label 计算 sha256 指纹。

    仅用实读字段；inferred / placeholder 不参与签名。
    子元素不参与父级的 signature（各自独立 root state）。
    """
    norm = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        src = el.get("source", {}) if isinstance(el.get("source"), dict) else {}
        fingerprint = {
            "role": src.get("role"),
            "name": src.get("name"),
            "aria_label": src.get("aria_label"),
        }
        key = el.get("key") if isinstance(el.get("key"), str) else None
        norm.append((fingerprint, key))
    payload = json.dumps(norm, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()
