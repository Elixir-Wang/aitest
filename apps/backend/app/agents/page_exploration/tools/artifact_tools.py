"""read_page_artifact_tool, merge_page_artifact_tool。v2.0 工具集。"""
from __future__ import annotations

from pathlib import Path

import yaml

from app.services.page_exploration.page_artifact_writer import (
    PageArtifactWriter, NewStateObservation, NewElementObservation,
)
from app.agents.page_exploration.schemas import PageArtifact, TriggeredBy


def _obs_from_dict(d: dict) -> NewStateObservation:
    def _element_from_dict(el: dict) -> NewElementObservation:
        return NewElementObservation(
            key=el.get("key"),
            source=el.get("source", {}),
            inferred=bool(el.get("inferred", False)),
            children=[_element_from_dict(child) for child in el.get("children", [])],
        )

    triggered_by = d.get("triggered_by")
    if isinstance(triggered_by, dict):
        triggered_by = TriggeredBy(**triggered_by)

    elements = [_element_from_dict(el) for el in d.get("elements", [])]
    return NewStateObservation(
        page_id=d["page_id"],
        page_title=d["page_title"],
        normalized_path=d["normalized_path"],
        observed_url=d["observed_url"],
        run_id=d["run_id"],
        observed_at=d["observed_at"],
        state_type=d["state_type"],
        title=d["title"],
        dom_signature=d.get("dom_signature") or "sha256:unknown",
        triggered_by=triggered_by,
        parent_state_id=d.get("parent_state_id"),
        elements=elements,
    )


def read_page_artifact(page_id: str, project_id: str, base_dir: Path) -> dict:
    writer = PageArtifactWriter(base_dir=Path(base_dir) / project_id / "page_exploration")
    artifact = writer.read_existing(page_id)
    if artifact is None:
        return {"exists": False, "schema_version": None, "page": None}
    return {
        "exists": True,
        "schema_version": artifact.schema_version,
        "page": artifact.page.model_dump(mode="json"),
    }


def merge_page_artifact(
    page_id: str,
    project_id: str,
    run_id: str,
    base_dir: Path,
    observed_states: list[dict],
) -> dict:
    writer = PageArtifactWriter(base_dir=Path(base_dir) / project_id / "page_exploration")
    obs = [_obs_from_dict({**d, "run_id": run_id}) for d in observed_states]
    result = writer.merge_states(obs)
    return {
        "added_state_ids": result.added_state_ids,
        "updated_state_ids": result.updated_state_ids,
        "added_element_keys": result.added_element_keys,
        "updated_element_keys": result.updated_element_keys,
        "skipped_due_to_lock": result.skipped_due_to_lock,
    }


def make_artifact_tools(base_dir: Path):
    from langchain_core.tools import tool

    @tool
    def read_page_artifact_tool(
        page_id: str,
        project_id: str,
    ) -> dict:
        """Read the full v2.0 page artifact yaml.
        Args: page_id (stable id), project_id
        Returns: {exists: bool, schema_version: str|None, page: dict|None}"""
        return read_page_artifact(page_id=page_id, project_id=project_id, base_dir=base_dir)

    @tool
    def merge_page_artifact_tool(
        page_id: str,
        observed_states: list[dict],
        project_id: str,
        run_id: str,
    ) -> dict:
        """Merge observed states into a page artifact (idempotent, append-only).

        observed_states: list of dicts with keys:
          page_id, page_title, normalized_path, observed_url,
          run_id, observed_at, state_type, title,
          dom_signature, triggered_by (dict|None),
          parent_state_id (str|None), elements (list)
        Returns: same as MergeResult."""
        return merge_page_artifact(
            page_id=page_id, project_id=project_id, run_id=run_id,
            base_dir=base_dir, observed_states=observed_states,
        )

    return [read_page_artifact_tool, merge_page_artifact_tool]
