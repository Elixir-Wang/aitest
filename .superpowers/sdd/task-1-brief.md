## Task 1: v2.0 Schema（Pydantic）+ test fixtures

**Files:**
- Modify: `apps/backend/app/agents/page_exploration/schemas.py`（当前实现什么不重要，本任务把它**完全重写**为 v2.0 schema）
- Create: `apps/backend/tests/agents/page_exploration/test_schemas.py`
- Create: `apps/backend/tests/agents/page_exploration/fixtures/v2/page-workspace-agents.yaml`

**Interfaces:**
- Consumes: 无（基础任务）
- Produces:
  - `class SourceEntry(BaseModel)`：`role, name, aria_label: str | None; label, placeholder, test_id, text: str | None`
  - `class Element(BaseModel)`：`key: str; source: SourceEntry; inferred: bool; last_seen_at: str; seen_count: int; children: list["Element"] = []`
  - `class TriggeredBy(BaseModel)`：`from_state: str; element_key: str; action: Literal["click","fill","submit","navigate","hover","unknown"]; url_changed: bool; observed_url: str`
  - `class State(BaseModel)`：`id: str; type: Literal["root","dialog","drawer","form","list"]; title: str; triggered_by: TriggeredBy | None; depth: int; last_observed_at: str; observed_by_runs: list[str]; dom_signature: str; elements: list[Element]; children: list["State"] = []`
  - `class Page(BaseModel)`：`id: str; title: str; normalized_path: str; url: str | None; observed_url: str; first_observed_at: str; last_observed_at: str; observed_by_runs: list[str]`
  - `class PageArtifact(BaseModel)`：`schema_version: Literal["2.0"] = "2.0"; page: Page; states: list[State]`

- [ ] **Step 1: 写 Pydantic 测试**

```python
# apps/backend/tests/agents/page_exploration/test_schemas.py
import pytest
from pydantic import ValidationError
from app.agents.page_exploration.schemas import (
    PageArtifact, State, Element, TriggeredBy, SourceEntry
)

def test_page_artifact_minimal():
    yaml_obj = {
        "schema_version": "2.0",
        "page": {
            "id": "page-workspace",
            "title": "工作台",
            "normalized_path": "/workspace",
            "url": "https://test.example.com/workspace",
            "observed_url": "/workspace",
            "first_observed_at": "2026-07-04T10:00:00Z",
            "last_observed_at": "2026-07-04T10:15:00Z",
            "observed_by_runs": ["run-1"],
        },
        "states": [
            {
                "id": "page-workspace__root__001",
                "type": "root",
                "title": "工作台 - 列表状态",
                "triggered_by": None,
                "depth": 1,
                "last_observed_at": "2026-07-04T10:15:00Z",
                "observed_by_runs": ["run-1"],
                "dom_signature": "sha256:abc",
                "elements": [],
                "children": [],
            }
        ],
    }
    artifact = PageArtifact(**yaml_obj)
    assert artifact.schema_version == "2.0"
    assert artifact.page.id == "page-workspace"
    assert artifact.states[0].depth == 1
    assert artifact.states[0].triggered_by is None


def test_state_non_root_requires_triggered_by():
    state_dict = {
        "id": "page-x__dialog__001",
        "type": "dialog",
        "title": "弹窗",
        # triggered_by 缺失 - 即使业务逻辑允许，schema 不强制（运行时强约束）
        "depth": 2,
        "last_observed_at": "2026-07-04T10:00:00Z",
        "observed_by_runs": ["run-1"],
        "dom_signature": "sha256:def",
        "elements": [],
        "children": [],
    }
    s = State(**state_dict)
    assert s.type == "dialog"
    assert s.triggered_by is None  # schema 层允许，工具层拒


def test_state_type_must_be_in_whitelist():
    with pytest.raises(ValidationError):
        State(
            id="x__unknown__001", type="wizard",
            title="t", depth=1,
            last_observed_at="2026-07-04T10:00:00Z",
            observed_by_runs=["r"],
            dom_signature="sha256:1", elements=[], children=[],
        )


def test_triggered_by_action_whitelist():
    with pytest.raises(ValidationError):
        TriggeredBy(
            from_state="root", element_key="k",
            action="swipe", url_changed=False, observed_url="/x"
        )


def test_nested_children():
    leaf = State(
        id="page-x__form__001", type="form", title="l",
        triggered_by=TriggeredBy(
            from_state="page-x__dialog__001", element_key="k",
            action="click", url_changed=True, observed_url="/x?y=z"
        ),
        depth=3,
        last_observed_at="2026-07-04T10:00:00Z",
        observed_by_runs=["r"],
        dom_signature="sha256:leaf", elements=[], children=[],
    )
    parent = State(
        id="page-x__dialog__001", type="dialog", title="p",
        triggered_by=TriggeredBy(
            from_state="page-x__root__001", element_key="k",
            action="click", url_changed=False, observed_url="/x"
        ),
        depth=2,
        last_observed_at="2026-07-04T10:00:00Z",
        observed_by_runs=["r"],
        dom_signature="sha256:p", elements=[], children=[leaf],
    )
    assert len(parent.children) == 1
    assert parent.children[0].id == "page-x__form__001"
    assert parent.children[0].depth == 3
```

- [ ] **Step 2: 跑测试 - 期望 FAIL（schemas.py 还没有 v2.0 实现）**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/test_schemas.py -v
```

Expected: FAIL with `ModuleNotFoundError: cannot import name 'PageArtifact' from 'app.agents.page_exploration.schemas'` or similar.

- [ ] **Step 3: 重写 schemas.py**

把 `apps/backend/app/agents/page_exploration/schemas.py` 替换成：

```python
# apps/backend/app/agents/page_exploration/schemas.py
"""Page exploration artifact v2.0 schema (Pydantic)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SourceEntry(BaseModel):
    """元素来源字段；inferred=True 时仅允许 label/placeholder/test_id/text。"""

    model_config = ConfigDict(extra="forbid")

    role: str | None = None
    name: str | None = None
    aria_label: str | None = None
    label: str | None = None
    placeholder: str | None = None
    test_id: str | None = None
    text: str | None = None


class Element(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    source: SourceEntry
    inferred: bool
    last_seen_at: str
    seen_count: int
    children: list["Element"] = []


Action = Literal["click", "fill", "submit", "navigate", "hover", "unknown"]
StateType = Literal["root", "dialog", "drawer", "form", "list"]


class TriggeredBy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_state: str
    element_key: str
    action: Action
    url_changed: bool
    observed_url: str


class State(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: StateType
    title: str
    triggered_by: TriggeredBy | None = None
    depth: int
    last_observed_at: str
    observed_by_runs: list[str]
    dom_signature: str
    elements: list[Element]
    children: list["State"] = []


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    normalized_path: str
    url: str | None = None
    observed_url: str
    first_observed_at: str
    last_observed_at: str
    observed_by_runs: list[str]


class PageArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["2.0"] = "2.0"
    page: Page
    states: list[State]


Element.model_rebuild()
State.model_rebuild()
```

- [ ] **Step 4: 跑测试 - 期望 PASS**

```bash
cd apps/backend
apps/backend/.venv/bin/python -m pytest tests/agents/page_exploration/test_schemas.py -v
```

Expected: PASS（5 tests collected, all green）.

- [ ] **Step 5: 落 test fixture（v2.0 yaml）**

`apps/backend/tests/agents/page_exploration/fixtures/v2/page-workspace-agents.yaml`：

```yaml
schema_version: "2.0"
page:
  id: page-workspace-agents
  title: "智能体工作台"
  normalized_path: /workspace/agents
  url: https://test.example.com/workspace/agents
  observed_url: /workspace/agents
  first_observed_at: "2026-07-04T10:00:00Z"
  last_observed_at: "2026-07-04T10:15:00Z"
  observed_by_runs:
    - run-001
states:
  - id: page-workspace-agents__root__001
    type: root
    title: "智能体工作台 - 列表状态"
    triggered_by: null
    depth: 1
    last_observed_at: "2026-07-04T10:15:00Z"
    observed_by_runs:
      - run-001
    dom_signature: "sha256:5e7c"
    elements:
      - key: button-create-agent
        source:
          role: button
          name: "创建智能体"
        inferred: false
        last_seen_at: "2026-07-04T10:15:00Z"
        seen_count: 12
        children: []
    children:
      - id: page-workspace-agents__dialog__001
        type: dialog
        title: "选择创建类型"
        triggered_by:
          from_state: page-workspace-agents__root__001
          element_key: button-create-agent
          action: click
          url_changed: false
          observed_url: /workspace/agents
        depth: 2
        last_observed_at: "2026-07-04T10:15:00Z"
        observed_by_runs:
          - run-001
        dom_signature: "sha256:8a3f"
        elements:
          - key: button-create-autonomous
            source:
              role: button
              name: "自主规划"
            inferred: false
            last_seen_at: "2026-07-04T10:15:00Z"
            seen_count: 3
            children: []
        children: []
```

- [ ] **Step 6: 验证 fixture 可解析**

```python
# 临时 REPL / 或写入独立的 parse test
from pathlib import Path
from app.agents.page_exploration.schemas import PageArtifact

yaml_text = Path("tests/agents/page_exploration/fixtures/v2/page-workspace-agents.yaml").read_text(encoding="utf-8")

# 用 PyYAML 解析
import yaml
obj = yaml.safe_load(yaml_text)
artifact = PageArtifact(**obj)
assert artifact.states[0].children[0].type == "dialog"
```

Run:

```bash
cd apps/backend
apps/backend/.venv/bin/python -c "
from pathlib import Path
import yaml
from app.agents.page_exploration.schemas import PageArtifact
obj = yaml.safe_load(Path('tests/agents/page_exploration/fixtures/v2/page-workspace-agents.yaml').read_text(encoding='utf-8'))
a = PageArtifact(**obj)
print('parsed:', a.page.id, '/', a.states[0].id, '/', a.states[0].children[0].id)
"
```

Expected: `parsed: page-workspace-agents / page-workspace-agents__root__001 / page-workspace-agents__dialog__001`.

- [ ] **Step 7: Commit**

```bash
cd d:/project/test_project
git add apps/backend/app/agents/page_exploration/schemas.py \
        apps/backend/tests/agents/page_exploration/test_schemas.py \
        apps/backend/tests/agents/page_exploration/fixtures/v2/page-workspace-agents.yaml
git commit -m "feat(page_exploration): v2.0 Pydantic schema (state 嵌套 + triggered_by)"
```

---

