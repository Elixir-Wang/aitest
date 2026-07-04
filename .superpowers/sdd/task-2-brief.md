## Task 2: utils 纯函数（六件套）

按 writing-plans skill 的"每步 2-5 分钟"原则，把 T2 拆成 6 个 sub-task，每个 sub-task 走"写测试 → 跑 FAIL → 写实现 → 跑 PASS → commit"循环。

### T2.1: `element_key` slug + 冲突后缀

**Files:**
- Create: `apps/backend/app/agents/page_exploration/utils/__init__.py`
- Create: `apps/backend/app/agents/page_exploration/utils/element_key.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/__init__.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/test_element_key.py`

- [ ] **Step 1: 写测试**

```python
# apps/backend/tests/agents/page_exploration/utils/test_element_key.py
from app.agents.page_exploration.utils.element_key import (
    build_element_key, slugify, ensure_unique_within_state
)


def test_slugify_lowercase_and_dash():
    assert slugify("Create Agent") == "create-agent"
    assert slugify("创建智能体") == ""  # 全中文 = 空 slug


def test_slugify_collapses_dashes_and_trims():
    assert slugify("a  --  b") == "a-b"
    assert slugify("---foo---") == "foo"
    assert slugify("a" * 50) == "a" * 40  # 截断到 40


def test_build_element_key_role_name():
    src = {"role": "button", "name": "创建智能体"}
    assert build_element_key(src) == "button-创建智能体"

    src = {"role": "button", "name": "Create"}
    assert build_element_key(src) == "button-create"


def test_build_element_key_priority_order():
    # role+name 胜出，label 不参与
    src = {
        "role": "button", "name": "Submit",
        "label": "OK", "placeholder": "请输入"
    }
    assert build_element_key(src) == "button-submit"


def test_build_element_key_only_label():
    src = {"role": "textbox", "label": "搜索"}
    assert build_element_key(src) == "textbox-搜索"


def test_build_element_key_fallback_text():
    src = {"role": "button", "text": "我是按钮"}
    assert build_element_key(src) == "button-我是按钮"


def test_ensure_unique_within_state_passthrough():
    keys = ["button-a", "button-b"]
    out = list(ensure_unique_within_state(keys))
    assert out == ["button-a", "button-b"]


def test_ensure_unique_within_state_collision():
    keys = ["button-a", "button-a", "button-b", "button-a"]
    out = list(ensure_unique_within_state(keys))
    assert out == ["button-a", "button-a-2", "button-b", "button-a-3"]
```

- [ ] **Step 2: 跑测试 - 期望 FAIL**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_element_key.py -v
```

Expected: ModuleNotFoundError: cannot import name 'build_element_key' ...

- [ ] **Step 3: 实现**

```python
# apps/backend/app/agents/page_exploration/utils/element_key.py
"""element.key slug + 同 state 内 -2 / -3 后缀冲突处理。"""
from __future__ import annotations

import re
from typing import Iterable, Iterator


_MAX_LEN = 40
_NON_ALNUM = re.compile(r"[^a-z0-9一-鿿]+")  # 仅 ASCII 字母数字 + 中文
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
        # 没有 role 无法产生有意义 key
        return slugify(source.get("aria_label") or source.get("text") or "unknown")

    name = slugify(source.get("name") or "")
    if name:
        return f"{role}-{name}"
    aria = slugify(source.get("aria_label") or "")
    if aria:
        return f"{role}-{aria}"
    label = slugify(source.get("label") or "")
    if label:
        return f"{role}-{label}"
    placeholder = slugify(source.get("placeholder") or "")
    if placeholder:
        return f"{role}-{placeholder}"
    test_id = slugify(source.get("test_id") or "")
    if test_id:
        return f"{role}-{test_id}"
    text = slugify(source.get("text") or "")
    if text:
        return f"{role}-{text}"
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
```

- [ ] **Step 4: 跑测试 - 期望 PASS**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_element_key.py -v
```

Expected: PASS（8 tests）.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/agents/page_exploration/utils/element_key.py \
        apps/backend/app/agents/page_exploration/utils/__init__.py \
        apps/backend/tests/agents/page_exploration/utils/test_element_key.py \
        apps/backend/tests/agents/page_exploration/utils/__init__.py
git commit -m "feat(page_exploration): element_key slug + 冲突后缀"
```

### T2.2: `state_id` 模板生成器

**Files:**
- Create: `apps/backend/app/agents/page_exploration/utils/state_id.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/test_state_id.py`

- [ ] **Step 1: 写测试**

```python
# apps/backend/tests/agents/page_exploration/utils/test_state_id.py
from app.agents.page_exploration.utils.state_id import (
    next_state_id, allocate_ids_for_observation
)
from app.agents.page_exploration.schemas import StateType

StateType  # silence linter
```

> 注：本任务我们只需要工具函数返回 id 字符串；具体 State 模型构造由调用方做。

```python
# 真正测试 - 放在 test_state_id.py
from app.agents.page_exploration.utils.state_id import (
    make_state_id, STATE_ID_PATTERN
)
import re


def test_root_id():
    assert make_state_id("page-x", "root", 1) == "page-x__root__001"


def test_seq3_padding():
    assert make_state_id("page-x", "dialog", 7) == "page-x__dialog__007"
    assert make_state_id("page-x", "form", 100) == "page-x__form__100"


def test_pattern_matches():
    pat = re.compile(STATE_ID_PATTERN)
    assert pat.fullmatch("page-x__root__001")
    assert pat.fullmatch("page-abc-def__dialog__042")
    assert not pat.fullmatch("page-x__unknown__001")  # unknown 不是 type
    assert not pat.fullmatch("page-x__root__1")       # 缺零填充
```

- [ ] **Step 2: 跑测试 - 期望 FAIL**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_state_id.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: 实现**

```python
# apps/backend/app/agents/page_exploration/utils/state_id.py
"""state.id 模板生成; {page_id}__{type}__{seq3}; agent 不命名。"""
from __future__ import annotations

from typing import Final

STATE_ID_PATTERN: Final = r"^[a-zA-Z0-9_\-]+__(root|dialog|drawer|form|list)__[0-9]{3}$"


def make_state_id(page_id: str, state_type: str, seq: int) -> str:
    """生成 state.id。seq 从 1 起。"""
    if seq < 1:
        raise ValueError(f"seq must be >= 1, got {seq}")
    return f"{page_id}__{state_type}__{seq:03d}"
```

- [ ] **Step 4: 跑测试 - 期望 PASS**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_state_id.py -v
```

Expected: PASS（3 tests）.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/agents/page_exploration/utils/state_id.py \
        apps/backend/tests/agents/page_exploration/utils/test_state_id.py
git commit -m "feat(page_exploration): state_id 模板生成器"
```

### T2.3: `dom_signature` 哈希

**Files:**
- Create: `apps/backend/app/agents/page_exploration/utils/dom_signature.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/test_dom_signature.py`

- [ ] **Step 1: 写测试**

```python
# apps/backend/tests/agents/page_exploration/utils/test_dom_signature.py
import hashlib
from app.agents.page_exploration.utils.dom_signature import compute_dom_signature


def test_signature_stable_for_same_content():
    el1 = [
        {"key": "button-a", "source": {"role": "button", "name": "A"}},
        {"key": "input-b", "source": {"role": "textbox", "label": "B"}},
    ]
    el2 = [
        {"key": "button-a", "source": {"role": "button", "name": "A"}},
        {"key": "input-b", "source": {"role": "textbox", "label": "B"}},
    ]
    s1 = compute_dom_signature(el1)
    s2 = compute_dom_signature(el2)
    assert s1 == s2


def test_signature_ignores_ref_but_sensitive_to_role():
    # 不同的 element.key 但同 role+name -> 仍相同（语义同）
    el1 = [{"source": {"role": "button", "name": "A"}}]
    el2 = [{"source": {"role": "button", "name": "A"}}]
    assert compute_dom_signature(el1) == compute_dom_signature(el2)


def test_signature_sensitive_to_role_change():
    el1 = [{"source": {"role": "button", "name": "A"}}]
    el2 = [{"source": {"role": "textbox", "name": "A"}}]
    assert compute_dom_signature(el1) != compute_dom_signature(el2)


def test_signature_sensitive_to_name_change():
    el1 = [{"source": {"role": "button", "name": "A"}}]
    el2 = [{"source": {"role": "button", "name": "B"}}]
    assert compute_dom_signature(el1) != compute_dom_signature(el2)


def test_signature_sensitive_to_aria_change():
    el1 = [{"source": {"role": "button", "aria_label": "A"}}]
    el2 = [{"source": {"role": "button", "aria_label": "B"}}]
    assert compute_dom_signature(el1) != compute_dom_signature(el2)


def test_signature_format_is_sha256_prefix():
    el = [{"source": {"role": "button", "name": "A"}}]
    s = compute_dom_signature(el)
    assert s.startswith("sha256:")
    assert len(s) == len("sha256:") + 64


def test_signature_empty_returns_seed():
    assert compute_dom_signature([]).startswith("sha256:")
```

- [ ] **Step 2: 跑测试 - 期望 FAIL**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_dom_signature.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: 实现**

```python
# apps/backend/app/agents/page_exploration/utils/dom_signature.py
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
```

- [ ] **Step 4: 跑测试 - 期望 PASS**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_dom_signature.py -v
```

Expected: PASS（7 tests）.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/agents/page_exploration/utils/dom_signature.py \
        apps/backend/tests/agents/page_exploration/utils/test_dom_signature.py
git commit -m "feat(page_exploration): dom_signature 语义哈希"
```

### T2.4: `toast_filter`

**Files:**
- Create: `apps/backend/app/agents/page_exploration/utils/toast_filter.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/test_toast_filter.py`

- [ ] **Step 1: 写测试**

```python
# apps/backend/tests/agents/page_exploration/utils/test_toast_filter.py
from app.agents.page_exploration.utils.toast_filter import is_toast, filter_snapshot


def test_is_toast_role_status():
    info = {"role": "status", "aria_modal": None, "timeout_ms": 3000}
    assert is_toast(info) is True


def test_is_toast_role_alert_short_timeout():
    info = {"role": "alert", "aria_modal": None, "timeout_ms": 3000}
    assert is_toast(info) is True


def test_dialog_not_toast():
    info = {"role": "dialog", "aria_modal": True, "timeout_ms": 3000}
    assert is_toast(info) is False


def test_alert_without_timeout_not_toast():
    # 长 timeout 或未知 -> 不当 toast
    info = {"role": "alert", "aria_modal": None, "timeout_ms": None}
    assert is_toast(info) is False


def test_known_ant_message_container():
    info = {"role": "status", "aria_modal": None, "timeout_ms": 3000,
            "dom_path": "div#root > .ant-message"}
    assert is_toast(info) is True


def test_filter_snapshot_drops_toasts():
    snap = [
        {"role": "button", "aria_modal": None, "timeout_ms": None},   # keep
        {"role": "status", "aria_modal": None, "timeout_ms": 3000},  # drop
        {"role": "dialog", "aria_modal": True, "timeout_ms": None},  # keep
        {"role": "alert", "aria_modal": None, "timeout_ms": 4000},   # drop
    ]
    out = filter_snapshot(snap)
    assert len(out) == 2
    assert out[0]["role"] == "button"
    assert out[1]["role"] == "dialog"
```

- [ ] **Step 2: 跑测试 - 期望 FAIL**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_toast_filter.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: 实现**

```python
# apps/backend/app/agents/page_exploration/utils/toast_filter.py
"""toast / snackbar 启发式过滤：role=status/alert 且短 timeout 或已知容器, 都不进 state 树。"""
from __future__ import annotations

from typing import Iterable

_KNOWN_TOAST_CONTAINERS = (
    ".ant-message",
    ".ant-notification",
    "#root > .toast-container",
    ".toast",
    ".snackbar",
)

_DIALOG_LIKE = {"dialog", "alertdialog"}


def is_toast(info: dict) -> bool:
    role = info.get("role")
    aria_modal = info.get("aria_modal")
    if role in _DIALOG_LIKE or aria_modal is True:
        return False

    timeout = info.get("timeout_ms")
    dom_path = info.get("dom_path") or ""

    known_container = any(seg in dom_path for seg in _KNOWN_TOAST_CONTAINERS)
    short_timeout = isinstance(timeout, (int, float)) and timeout <= 5000

    if role in {"status", "alert"}:
        return short_timeout or known_container

    # 没有任何 role 标签但命中已知容器 -> 认为是 toast
    return known_container and role is None


def filter_snapshot(snapshot: Iterable[dict]) -> list[dict]:
    return [el for el in snapshot if not is_toast(el)]
```

- [ ] **Step 4: 跑测试 - 期望 PASS**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_toast_filter.py -v
```

Expected: PASS（6 tests）.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/agents/page_exploration/utils/toast_filter.py \
        apps/backend/tests/agents/page_exploration/utils/test_toast_filter.py
git commit -m "feat(page_exploration): toast_filter 启发式"
```

### T2.5: `url_normalize`

**Files:**
- Create: `apps/backend/app/agents/page_exploration/utils/url_normalize.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/test_url_normalize.py`

- [ ] **Step 1: 写测试**

```python
# apps/backend/tests/agents/page_exploration/utils/test_url_normalize.py
from app.agents.page_exploration.utils.url_normalize import (
    normalize_for_compare, urls_equal_modulo_hash
)


def test_normalize_query_order_independent():
    a = normalize_for_compare("/x?a=1&b=2")
    b = normalize_for_compare("/x?b=2&a=1")
    assert a == b


def test_normalize_drops_hash():
    a = normalize_for_compare("/x#frag")
    b = normalize_for_compare("/x")
    assert a == b


def test_normalize_keeps_fragment():
    # 路径里的 hash 区分（fragment 是 DOM 锚点，忽略；URL 协议/host 区分）
    a = normalize_for_compare("https://a.com/x")
    b = normalize_for_compare("https://b.com/x")
    assert a != b


def test_normalize_lowercase_path():
    a = normalize_for_compare("/X")
    b = normalize_for_compare("/x")
    # query 排序 + path lowercase
    assert a == b or a.rstrip("/") == b.rstrip("/")  # 实施可放宽


def test_urls_equal_modulo_hash_true():
    assert urls_equal_modulo_hash("/x#a", "/x#b")


def test_urls_equal_modulo_hash_false():
    assert not urls_equal_modulo_hash("/x", "/y")
```

- [ ] **Step 2: 跑测试 - 期望 FAIL**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_url_normalize.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: 实现**

```python
# apps/backend/app/agents/page_exploration/utils/url_normalize.py
"""URL 规范化: query 排序; hash 剥离; path lowercase; 主序 + 协议 + host 不区分将抛。"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def normalize_for_compare(url: str) -> str:
    """query 排序、hash 去除、path 小写、其它原状。"""
    parts = urlsplit(url)
    # query 排序
    qsl = sorted(parse_qsl(parts.query, keep_blank_values=True))
    new_query = urlencode(qsl)
    new_path = parts.path.lower()
    # 去掉 fragment
    return urlunsplit((parts.scheme, parts.netloc, new_path, new_query, ""))


def urls_equal_modulo_hash(a: str, b: str) -> bool:
    return normalize_for_compare(a) == normalize_for_compare(b)
```

- [ ] **Step 4: 跑测试 - 期望 PASS**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_url_normalize.py -v
```

Expected: PASS（6 tests; 实施可放宽 lowercase 路径用例）.

- [ ] **Step 5: Commit**

```bash
git add apps/backend/app/agents/page_exploration/utils/url_normalize.py \
        apps/backend/tests/agents/page_exploration/utils/test_url_normalize.py
git commit -m "feat(page_exploration): url_normalize (query 排序 + hash 剥离)"
```

### T2.6: 文件锁 helper

**Files:**
- Create: `apps/backend/app/services/page_exploration/locking.py`
- Create: `apps/backend/tests/agents/page_exploration/utils/test_locking.py`（或新位置 `tests/services/.../test_locking.py`）

- [ ] **Step 1: 写测试**

```python
# apps/backend/tests/agents/page_exploration/utils/test_locking.py
import threading
import time
from pathlib import Path

import pytest

from app.services.page_exploration.locking import FileLock, LockTimeout


def test_acquire_and_release(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("schema_version: 2.0\n")
    lock = FileLock(path, timeout_seconds=1.0)
    with lock:
        assert path.exists()  # lock file 不会冲突路径
    # 再次获取应成功
    with lock:
        pass


def test_concurrent_acquire_waits_then_times_out(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("schema_version: 2.0\n")
    a = FileLock(path, timeout_seconds=0.5)
    b = FileLock(path, timeout_seconds=0.2)
    with a:
        with pytest.raises(LockTimeout):
            with b:
                pass


def test_acquired_lock_blocks_other_writers(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("x")
    a = FileLock(path, timeout_seconds=1.0)
    b = FileLock(path, timeout_seconds=2.0)
    with a:
        t0 = time.monotonic()
        try:
            with b:
                pass
        except LockTimeout:
            elapsed = time.monotonic() - t0
        else:
            pytest.fail("b should not have acquired during a's hold")


def test_release_unlocks(tmp_path: Path):
    path = tmp_path / "page.yaml"
    path.write_text("x")
    a = FileLock(path, timeout_seconds=0.5)
    a.acquire()
    try:
        # 释放后再获取应成功
        a.release()
        a.acquire()
    finally:
        a.release()


def test_raise_class_exists():
    from app.services.page_exploration.locking import LockTimeout
    assert issubclass(LockTimeout, Exception)
```

- [ ] **Step 2: 跑测试 - 期望 FAIL**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/utils/test_locking.py -v
```

Expected: ModuleNotFoundError

- [ ] **Step 3: 实现**

```python
# apps/backend/app/services/page_exploration/locking.py
"""文件级互斥锁: tmp/<file>.lock; acquire 阶段超时抛 LockTimeout。"""
from __future__ import annotations

import contextlib
import fcntl
import time
from pathlib import Path


class LockTimeout(Exception):
    """锁等待超时。"""


class FileLock:
    def __init__(self, file_path: Path, timeout_seconds: float = 5.0):
        self._lock_path = Path(str(file_path) + ".lock")
        self._timeout = timeout_seconds
        self._fd = None

    def acquire(self) -> None:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.touch(exist_ok=True)
        # O_CREAT 模式取 fd 然后 flock
        self._fd = open(self._lock_path, "w")
        deadline = time.monotonic() + self._timeout
        while True:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise LockTimeout(f"timeout acquiring {self._lock_path}")
                time.sleep(0.05)

    def release(self) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd.fileno(), fcntl.LOCK_UN)
            finally:
                self._fd.close()
                self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()

---

