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
