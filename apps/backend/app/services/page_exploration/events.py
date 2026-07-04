# apps/backend/app/services/page_exploration/events.py
"""4 种 page artifact 事件 payload model。"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class PageArtifactEvents(str, Enum):
    """Artifact 层事件枚举，供 EventBus 发布 / 订阅用。"""

    STATE_MERGE = "page_artifact_state_merge"
    LOCK_TIMEOUT = "page_artifact_lock_timeout"
    STATE_REJECTED = "page_artifact_state_rejected"
    YAML_CORRUPT = "page_artifact_yaml_corrupt"


EventType = Literal[
    "page_artifact_state_merge",
    "page_artifact_lock_timeout",
    "page_artifact_state_rejected",
    "page_artifact_yaml_corrupt",
]


class PageArtifactStateMergePayload(BaseModel):
    page_id: str
    normalized_path: str
    added_state_ids: list[str]
    updated_state_ids: list[str]
    added_element_keys: list[str]
    updated_element_keys: list[str]
    trigger: str  # "click:button-x"


class PageArtifactLockTimeoutPayload(BaseModel):
    page_id: str
    waited_seconds: float


class PageArtifactStateRejectedPayload(BaseModel):
    page_id: str
    reason: str  # enum
    rejected_state_title: str


class PageArtifactYamlCorruptPayload(BaseModel):
    page_id: str
    file_path: str
    reason: str  # yaml_parse_error / io_error / empty_file / schema_mismatch
    action: Literal["rebuild_from_scratch"]
