"""element.key slug + 同 state 内 -2 / -3 后缀冲突处理。"""
from __future__ import annotations

import re
from typing import Iterable, Iterator


_MAX_LEN = 40
_NON_ALNUM = re.compile(r"[^a-z0-9]+")  # 仅 ASCII 字母数字（中文字符全部被替换）
_DASH_RUN = re.compile(r"-{2,}")


def slugify(value: str) -> str:
    """lowercase + non-[a-z0-9一-鿿]→- + 折叠连续 - + 去首尾 + 长度截断 40。"""
    if not value:
        return ""
    s = value.strip().lower()
    s = _NON_ALNUM.sub("-", s)
    s = _DASH_RUN.sub("-", s)
    s = s.strip("-")
    return s[:_MAX_LEN]


def build_element_key(source: dict) -> str:
    """按 role+name > role+aria_label > role+label > role+placeholder > role+text_id > role+text 顺序。"""
    role = source.get("role")
    if not role:
        return slugify(source.get("aria_label") or source.get("text") or "unknown")

    name = source.get("name")
    if name:
        key = slugify(name) if name.isascii() else name
        return f"{role}-{key}"
    aria = source.get("aria_label")
    if aria:
        key = slugify(aria) if aria.isascii() else aria
        return f"{role}-{key}"
    label = source.get("label")
    if label:
        key = slugify(label) if label.isascii() else label
        return f"{role}-{key}"
    placeholder = source.get("placeholder")
    if placeholder:
        key = slugify(placeholder) if placeholder.isascii() else placeholder
        return f"{role}-{key}"
    test_id = source.get("test_id")
    if test_id:
        key = slugify(test_id) if test_id.isascii() else test_id
        return f"{role}-{key}"
    text = source.get("text")
    if text:
        key = slugify(text) if text.isascii() else text
        return f"{role}-{key}"
    return role


def ensure_unique_within_state(keys: Iterable[str]) -> Iterator[str]:
    """同 state 内 element.key 冲突用 -2 / -3 后缀递增。"""
    seen: dict[str, int] = {}
    for k in keys:
        n = seen.get(k, 0)
        if n == 0:
            seen[k] = 1
            yield k
        else:
            new_k = f"{k}-{n + 1}"
            seen[k] = n + 1
            # 后续再撞到 new_k 也不影响（不递归）
            yield new_k
