# apps/backend/app/services/page_exploration/output_registry.py

import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.agents.page_exploration.utils.page_id import make_page_id
from app.agents.page_exploration.utils.element_key import build_element_key, slugify
from app.core import settings
from app.core.db import connect as default_connect
from app.repositories import exploration_run_repo as default_exploration_run_repo
from app.services.page_exploration.artifact_normalizer import normalize_snapshot_artifact
from app.services.page_exploration.report_writer import (
    _artifact_quality_warnings,
    _exploration_completion_status,
    _read_timeline_events_from_run_dir,
    _write_exploration_report,
)

logger = logging.getLogger(__name__)


def _service_attr(name: str, default):
    service_module = sys.modules.get("app.services.page_exploration.service")
    return getattr(service_module, name, default)


def _connect():
    return _service_attr("connect", default_connect)()


def _exploration_run_repo():
    return _service_attr("exploration_run_repo", default_exploration_run_repo)


def _project_file_storage_root() -> Path:
    service_settings = _service_attr("settings", settings)
    return getattr(service_settings, "PROJECT_FILE_STORAGE_ROOT", settings.PROJECT_FILE_STORAGE_ROOT)


def _string(value) -> str:
    if value is None:
        return ""
    return str(value)


def _read_yaml_file(path: Path) -> dict:
    import yaml

    if not path.exists():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("failed to read page exploration yaml: path=%s error=%s", path, exc)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _register_exploration_outputs(
    *,
    project_id: str,
    run_id: str,
    start_url: str,
    scope: str,
    exploration_mode: str,
    max_pages: int,
    result_status: str = "completed",
    goal: str = "",
) -> str:
    """Register file artifacts produced by the new page exploration agent."""
    run_dir = _project_file_storage_root() / project_id / "page_exploration" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    page_artifacts = _collect_project_page_artifacts_for_run(project_id=project_id, run_id=run_id)
    timeline_events = _read_timeline_events_from_run_dir(run_dir)
    completion_status = result_status if result_status in {"failed", "partial", "blocked"} else _exploration_completion_status(timeline_events)
    report_path = _write_exploration_report(
        run_dir=run_dir,
        run_id=run_id,
        start_url=start_url,
        exploration_mode=exploration_mode,
        page_artifacts=page_artifacts,
        goal=goal,
        timeline_events=timeline_events,
        artifact_quality_warnings=_artifact_quality_warnings(page_artifacts),
    )
    with _connect() as db:
        _exploration_run_repo().update_artifact_root(db, run_id, str(run_dir))
        for path, artifact in page_artifacts:
            _register_page_artifact_file(
                db,
                project_id=project_id,
                run_dir=run_dir,
                run_id=run_id,
                path=path,
                artifact=artifact,
                scope=scope,
            )

        _upsert_exploration_artifact(
            db,
            artifact_id=f"{run_id}-report",
            run_id=run_id,
            artifact_type="report",
            file_path=str(report_path),
            title="探索报告",
            summary=f"本次探索记录 {len(page_artifacts)} 个页面。",
        )

    if completion_status == "failed":
        return f"已保留本次失败前生成的 {len(page_artifacts)} 个页面产物。"
    if completion_status == "blocked":
        return f"探索被阻塞，已登记 {len(page_artifacts)} 个页面产物。"
    return f"探索完成，已登记 {len(page_artifacts)} 个页面产物。"


def _collect_page_artifact_files(*directories: Path) -> list[tuple[Path, dict]]:
    artifacts: list[tuple[Path, dict]] = []
    seen: set[Path] = set()
    for directory in directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.yaml")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            artifact = _read_yaml_file(path)
            if artifact.get("page"):
                artifacts.append((path, artifact))
    return artifacts


def _collect_project_page_artifacts_for_run(*, project_id: str, run_id: str) -> list[tuple[Path, dict]]:
    pages_dir = _project_file_storage_root() / project_id / "page_exploration" / "pages"
    artifacts: list[tuple[Path, dict]] = []
    index_entries = _read_project_pages_index(project_id)
    for path, artifact in _collect_page_artifact_files(pages_dir):
        page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
        index_info = index_entries.get(path.name, {})
        last_explored = page.get("last_explored") if isinstance(page.get("last_explored"), dict) else {}
        artifact_run_id = _string(index_info.get("run_id") or last_explored.get("run_id"))
        if artifact_run_id == run_id:
            artifacts.append((path, artifact))
    return artifacts


def _append_project_page_edge(
    *,
    project_id: str,
    run_id: str,
    from_page_id: str,
    to_page_id: str,
    action: str = "click",
    element_name: str = "",
    locator: str = "",
    from_url: str = "",
    to_url: str = "",
    edge_type: str = "business_drilldown",
    navigation_group: str = "",
    source_region_type: str = "content",
) -> dict | None:
    if not project_id or not run_id or not from_page_id or not to_page_id or from_page_id == to_page_id:
        return None

    path = _project_page_edges_path(project_id)
    payload = _read_yaml_file(path)
    edges = payload.get("edges") if isinstance(payload.get("edges"), list) else []
    edge = {
        "id": _page_edge_id(
            run_id=run_id,
            from_page_id=from_page_id,
            to_page_id=to_page_id,
            action=action,
            element_name=element_name,
            locator=locator,
        ),
        "run_id": run_id,
        "from_page_id": from_page_id,
        "to_page_id": to_page_id,
        "action": action or "click",
        "element_name": element_name,
        "locator": locator,
        "from_url": _normalize_snapshot_url_path(from_url) if from_url else "",
        "to_url": _normalize_snapshot_url_path(to_url) if to_url else "",
        "edge_type": edge_type or "unknown",
        "source_region_type": source_region_type or "content",
        "navigation_group": navigation_group,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }
    edge = {key: value for key, value in edge.items() if value not in ("", None)}

    existing_index = next((index for index, item in enumerate(edges) if isinstance(item, dict) and item.get("id") == edge["id"]), -1)
    if existing_index >= 0:
        edges[existing_index] = {**edges[existing_index], **edge}
    else:
        edges.append(edge)
    _write_yaml_file(path, {"edges": edges})
    return edge


def _list_project_page_edges(project_id: str, *, run_id: str = "") -> list[dict]:
    payload = _read_yaml_file(_project_page_edges_path(project_id))
    raw_edges = payload.get("edges") if isinstance(payload.get("edges"), list) else []
    edges = [edge for edge in raw_edges if isinstance(edge, dict)]
    if run_id:
        edges = [edge for edge in edges if _string(edge.get("run_id")) == run_id]
    return edges


def _project_page_edges_path(project_id: str) -> Path:
    return _project_file_storage_root() / project_id / "page_exploration" / "page_edges.yaml"


def _page_edge_id(
    *,
    run_id: str,
    from_page_id: str,
    to_page_id: str,
    action: str,
    element_name: str,
    locator: str,
) -> str:
    raw = "|".join([run_id, from_page_id, to_page_id, action or "click", element_name, locator])
    return f"edge-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def _page_identity_from_url(url: str) -> tuple[str, str]:
    normalized_path = _normalize_snapshot_url_path(url)
    return make_page_id(normalized_path), normalized_path


def _element_name_from_locator(locator: str) -> str:
    import re

    patterns = [
        r"name\s*:\s*['\"]([^'\"]+)['\"]",
        r"getByText\(['\"]([^'\"]+)['\"]",
        r"getByLabel\(['\"]([^'\"]+)['\"]",
        r"getByPlaceholder\(['\"]([^'\"]+)['\"]",
        r"hasText\s*:\s*['\"]([^'\"]+)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, locator or "")
        if match:
            return match.group(1)
    return ""




def _write_yaml_file(path: Path, payload: dict) -> None:
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _checkpoint_snapshot_artifact_from_event(event: dict, *, project_id: str, run_id: str) -> Path | None:
    """Persist a minimal page artifact whenever the browser snapshot tool succeeds."""
    if not project_id or not run_id or not isinstance(event, dict):
        return None
    if event.get("event") != "on_tool_end" or event.get("name") != "playwright_snap_tool":
        return None

    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    snapshot = _coerce_tool_output_dict(data.get("output"))
    if not snapshot or snapshot.get("error"):
        return None

    url = _string(snapshot.get("url")).strip()
    title = _string(snapshot.get("title")).strip() or url or "探索页面"
    if not url:
        return None

    normalized_path = _normalize_snapshot_url_path(url)
    page_id = make_page_id(normalized_path)
    run_dir = _project_file_storage_root() / project_id / "page_exploration" / "runs" / run_id
    existing_path = _project_file_storage_root() / project_id / "page_exploration" / "pages" / f"{page_id}.yaml"
    existing_artifact: dict | None = None
    if existing_path.exists():
        import yaml
        existing = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
        if isinstance(existing, dict) and existing.get("schema_version") == "4.0":
            existing_artifact = existing
    artifact = normalize_snapshot_artifact(snapshot, existing=existing_artifact)

    saved_path = Path(
        _save_project_page_artifact(
            project_id=project_id,
            run_id=run_id,
            artifact=artifact,
            source_path=Path(f"pages/{page_id}.yaml"),
            scope="主探索模块",
        )
    )
    try:
        with _connect() as db:
            _register_page_artifact_file(
                db,
                project_id=project_id,
                run_dir=run_dir,
                run_id=run_id,
                path=Path(f"pages/{page_id}.yaml"),
                artifact=artifact,
                scope="主探索模块",
                project_page_path=saved_path,
            )
    except Exception as exc:
        # Snapshot checkpoints are best-effort. The final exploration output
        # registration re-indexes all run-scoped page artifacts.
        logger.warning(
            "failed to register snapshot checkpoint artifact: project_id=%s run_id=%s page_id=%s path=%s error=%s",
            project_id,
            run_id,
            page_id,
            saved_path,
            exc,
        )
    return saved_path


def _checkpoint_page_identity(
    *,
    project_id: str,
    run_id: str,
    url: str,
    title: str = "",
) -> Path | None:
    """Ensure a page node exists as soon as navigation identifies a URL."""
    normalized_path = _normalize_snapshot_url_path(url)
    page_id = make_page_id(normalized_path)
    existing_path = _project_file_storage_root() / project_id / "page_exploration" / "pages" / f"{page_id}.yaml"
    artifact = _read_yaml_file(existing_path)
    if not artifact.get("page"):
        artifact = normalize_snapshot_artifact(
            {
                "url": url,
                "title": title or normalized_path,
                "interaction_scope": "page",
                "elements": [],
            }
        )
    run_dir = _project_file_storage_root() / project_id / "page_exploration" / "runs" / run_id
    saved_path = Path(
        _save_project_page_artifact(
            project_id=project_id,
            run_id=run_id,
            artifact=artifact,
            source_path=Path(f"pages/{page_id}.yaml"),
            scope="主探索模块",
        )
    )
    try:
        with _connect() as db:
            _register_page_artifact_file(
                db,
                project_id=project_id,
                run_dir=run_dir,
                run_id=run_id,
                path=Path(f"pages/{page_id}.yaml"),
                artifact=artifact,
                scope="主探索模块",
                project_page_path=saved_path,
            )
    except Exception as exc:
        logger.warning(
            "failed to register page identity checkpoint: project_id=%s run_id=%s page_id=%s error=%s",
            project_id,
            run_id,
            page_id,
            exc,
        )
    return saved_path


def _register_page_artifact_file(
    db,
    *,
    project_id: str,
    run_dir: Path,
    run_id: str,
    path: Path,
    artifact: dict,
    scope: str,
    project_page_path: Path | None = None,
) -> Path:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    env_urls = page.get("env_urls") if isinstance(page.get("env_urls"), dict) else {}
    page_id = _string(page.get("id") or path.stem)
    title = _string(page.get("semantic_title") or page.get("title") or path.stem)
    url = _string(page.get("url") or page.get("env_url") or env_urls.get("test") or next(iter(env_urls.values()), "") or "")
    entry_path = _string(page.get("normalized_url") or page.get("normalized_path") or page.get("entry_path") or "")
    module_key = _string(page.get("module_key") or page.get("module") or metadata.get("module") or scope or "主探索模块")
    structure_summary = _string(page.get("structure_summary") or _page_structure_summary(artifact))

    _exploration_run_repo().update_artifact_root(db, run_id, str(run_dir))
    if project_page_path is None:
        project_page_path = Path(
            _save_project_page_artifact(
                project_id=project_id,
                run_id=run_id,
                artifact=artifact,
                source_path=path,
                scope=scope,
            )
        )

    _upsert_exploration_page(
        db,
        page_id=page_id,
        run_id=run_id,
        title=title,
        url=url,
        entry_path=entry_path,
        module_key=module_key,
        structure_summary=structure_summary,
        snapshot_path=str(project_page_path),
    )
    _upsert_exploration_artifact(
        db,
        artifact_id=f"{run_id}-{path.stem}-yaml",
        run_id=run_id,
        artifact_type="page_yaml",
        file_path=str(project_page_path),
        title=title,
        summary=structure_summary,
    )
    return project_page_path


# --- Inlined from ProjectPagesService ---
_HOME_DISPLAY_NAME = "首页"


def _inline_save_page(
    *,
    project_id: str,
    page_id: str,
    page_data: dict,
    run_id: str,
    normalized_path: str,
    env: str = "test",
) -> bool:
    """Inlined from ProjectPagesService.save_page.

    The persisted YAML is optimized for UI automation consumption. Index-only
    fields used by the product UI stay in the DB or are derived while listing
    pages instead of being written into the automation artifact.
    """
    import yaml

    base_dir = _project_file_storage_root() / project_id / "page_exploration"
    pages_dir = base_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_file = pages_dir / f"{page_id}.yaml"

    page_payload = {
        "id": page_id,
        "title": page_data.get("title", ""),
        "normalized_path": normalized_path,
    }
    full_page_data = {
        "schema_version": "4.0",
        "page": page_payload,
    }
    for key in ("objects", "states", "elements", "collections", "transitions", "quality"):
        value = page_data.get(key)
        if value not in (None, [], {}):
            full_page_data[key] = value
    _update_project_pages_index(
        project_id=project_id,
        file_name=page_file.name,
        index_payload={
            "display_name": page_data.get("display_name") or _inline_display_name_from_path(normalized_path),
            "breadcrumb": page_data.get("breadcrumb") or _inline_breadcrumb_from_path(normalized_path),
            "structure_summary": page_data.get("structure_summary", ""),
            "run_id": run_id,
            "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
    )
    with open(page_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(full_page_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return True


def _inline_list_pages(project_id: str):
    """Inlined from ProjectPagesService.list_pages."""
    import yaml

    base_dir = _project_file_storage_root() / project_id / "page_exploration"
    pages_dir = base_dir / "pages"
    index_entries = _read_project_pages_index(project_id)
    pages = []
    if not pages_dir.exists():
        return pages
    for page_file in pages_dir.glob("*.yaml"):
        if page_file.name == "pages-index.yaml":
            continue
        try:
            page_data = yaml.safe_load(open(page_file, encoding="utf-8"))
            page_info = page_data.get("page", {})
            index_info = index_entries.get(page_file.name, {})
            pages.append(
                {
                    "page_id": page_info.get("id"),
                    "title": page_info.get("title"),
                    "display_name": index_info.get("display_name")
                    or page_info.get("display_name")
                    or _inline_display_name_from_path(page_info.get("normalized_path") or ""),
                    "breadcrumb": index_info.get("breadcrumb")
                    or page_info.get("breadcrumb")
                    or _inline_breadcrumb_from_path(page_info.get("normalized_path") or ""),
                    "normalized_path": page_info.get("normalized_path"),
                    "structure_summary": index_info.get("structure_summary") or page_info.get("structure_summary"),
                    "last_explored": {
                        "run_id": index_info.get("run_id"),
                        "timestamp": index_info.get("captured_at"),
                    } if index_info else page_info.get("last_explored"),
                    "file": page_file.name,
                }
            )
        except Exception as exc:
            logger.warning("failed to read project page yaml: project_id=%s path=%s error=%s", project_id, page_file, exc)
    return pages


def _read_project_pages_index(project_id: str) -> dict[str, dict]:
    payload = _read_yaml_file(_project_pages_index_path(project_id))
    entries = payload.get("pages") if isinstance(payload.get("pages"), dict) else {}
    return {str(name): data for name, data in entries.items() if isinstance(data, dict)}


def _update_project_pages_index(*, project_id: str, file_name: str, index_payload: dict) -> None:
    path = _project_pages_index_path(project_id)
    payload = _read_yaml_file(path)
    entries = payload.get("pages") if isinstance(payload.get("pages"), dict) else {}
    entries[file_name] = index_payload
    _write_yaml_file(path, {"pages": entries})


def _project_pages_index_path(project_id: str) -> Path:
    return _project_file_storage_root() / project_id / "page_exploration" / "pages" / "pages-index.yaml"


def _inline_breadcrumb_from_path(normalized_path: str) -> list:
    segments = [s for s in normalized_path.strip("/").split("/") if s]
    return segments or [_HOME_DISPLAY_NAME]


def _inline_display_name_from_path(normalized_path: str) -> str:
    breadcrumb = _inline_breadcrumb_from_path(normalized_path)
    return breadcrumb[-1] if breadcrumb else _HOME_DISPLAY_NAME


# --- End inlined helpers ---


def _save_project_page_artifact(
    *,
    project_id: str,
    run_id: str,
    artifact: dict,
    source_path: Path,
    scope: str,
) -> str:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    page_id = _string(page.get("id") or source_path.stem)
    title = _string(page.get("semantic_title") or page.get("title") or source_path.stem)
    url = _string(page.get("url") or page.get("env_url") or "")
    normalized_path = _string(page.get("normalized_url") or page.get("normalized_path") or page.get("entry_path") or "")
    structure_summary = _string(page.get("structure_summary") or _page_structure_summary(artifact))
    if not normalized_path and url:
        normalized_path = _normalize_snapshot_url_path(url)
    if normalized_path:
        normalized_path = _normalize_snapshot_url_path(normalized_path)
        page_id = make_page_id(normalized_path)

    _inline_save_page(
        project_id=project_id,
        page_id=page_id,
        page_data={
            "title": title,
            "structure_summary": structure_summary,
            "objects": artifact.get("objects", []),
            "states": artifact.get("states", []),
            "elements": artifact.get("elements", []),
            "collections": artifact.get("collections", []),
            "transitions": artifact.get("transitions", []),
            "quality": artifact.get("quality", {}),
            "metadata": {
                **(artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}),
                "module": _string(page.get("module_key") or page.get("module") or scope),
            },
        },
        run_id=run_id,
        normalized_path=normalized_path,
    )
    base_dir = _project_file_storage_root() / project_id / "page_exploration"
    return str(base_dir / "pages" / f"{page_id}.yaml")


def _coerce_tool_output_dict(output) -> dict:
    if isinstance(output, dict):
        return output
    content = getattr(output, "content", None)
    if content is None and isinstance(output, str):
        content = output
    if not isinstance(content, str):
        return {}
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _normalize_snapshot_url_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or "/"


def _normalize_action_type(role: str, action_type: str) -> str:
    action = _string(action_type).strip().lower()
    if action:
        return action
    role = _string(role).strip().lower()
    if role in {"textbox", "searchbox", "combobox", "spinbutton"}:
        return "fill"
    if role in {"button", "link", "checkbox", "radio", "tab", "menuitem", "option", "treeitem", "switch"}:
        return "click"
    return "assert"


def _best_container(ancestor_chain: list) -> tuple[str, str]:
    overlay_roles = {"dialog", "alertdialog", "popover", "menu", "listbox", "drawer"}
    for item in ancestor_chain:
        if not isinstance(item, dict):
            continue
        role = _string(item.get("role")).strip()
        if role in overlay_roles:
            return role, _string(item.get("name")).strip()
    for item in reversed(ancestor_chain):
        if not isinstance(item, dict):
            continue
        name = _string(item.get("name")).strip()
        if name:
            return _string(item.get("role")).strip(), name[:120]
    return "", ""


def _automation_context(element: dict, *, ordinal: int, sibling_count: int) -> dict:
    ancestor_chain = element.get("ancestor_chain") if isinstance(element.get("ancestor_chain"), list) else []
    container_role, container_name = _best_container(ancestor_chain)
    context: dict = {}
    if sibling_count > 1:
        context["ordinal"] = ordinal
    if container_role:
        context["role"] = container_role
    if container_name:
        context["name"] = container_name
    return context


def _element_group_counts(elements: list) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for element in elements:
        if not isinstance(element, dict):
            continue
        key = (_string(element.get("role") or "element"), _string(element.get("name") or element.get("text") or ""))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _snapshot_elements_for_artifact(elements: list, _accessibility_tree: list) -> list[dict]:
    """Project verified DOM elements into the compact automation artifact.

    Accessibility-only and unverified candidates remain in raw run events. They
    are intentionally excluded because a permanent POM entry must be executable.
    """
    result: list[dict] = []
    counts = _element_group_counts(elements)
    ordinals: dict[tuple[str, str], int] = {}
    used_element_keys: dict[str, int] = {}
    for element in elements:
        if not isinstance(element, dict):
            continue
        name = _string(element.get("name") or element.get("text") or f"element-{len(result) + 1}")
        role = _string(element.get("role") or "element")
        key = (role, name)
        ordinals[key] = ordinals.get(key, 0) + 1
        locators = _verified_locators(element)
        if not locators:
            continue
        action = _normalize_action_type(role, _string(element.get("action_type") or ""))
        context = _automation_context(
            element,
            ordinal=ordinals[key],
            sibling_count=counts.get(key, 1),
        )
        base_key = build_element_key({"role": role, "name": name})
        container_name = _string(context.get("name")).strip()
        scoped_key = base_key
        if counts.get(key, 1) > 1 and container_name:
            container_slug = slugify(container_name) or container_name[:40]
            scoped_key = f"{base_key}--in--{container_slug}"
        occurrence = used_element_keys.get(scoped_key, 0) + 1
        used_element_keys[scoped_key] = occurrence
        element_key = scoped_key if occurrence == 1 else f"{scoped_key}-{occurrence}"
        artifact_element: dict = {
            "key": element_key,
            "role": role,
            "name": name,
            "action": action,
            "locators": locators,
        }
        if context:
            artifact_element["context"] = context
        result.append(artifact_element)
    return result


def _is_verified_selector(selector: object) -> bool:
    if not isinstance(selector, dict) or not selector.get("code"):
        return False
    verification = selector.get("verification")
    return bool(
        isinstance(verification, dict)
        and verification.get("checked") is True
        and verification.get("unique") is True
        and verification.get("visible") is True
    )


def _verified_locators(element: dict) -> list[dict]:
    locators: list[dict] = []
    for field in ("primary_selector", "fallback_selector"):
        selector = element.get(field)
        if not _is_verified_selector(selector):
            continue
        code = _normalize_locator_code(selector["code"])
        if code and all(item["code"] != code for item in locators):
            locators.append({"code": code})
    return locators


def _normalize_locator_code(code: str) -> str:
    value = _string(code).strip()
    return value.removeprefix("page.")


def _upsert_exploration_page(db, **kwargs) -> None:
    db.execute(
        """
        INSERT INTO exploration_pages (
            id, exploration_run_id, module_key, title, url,
            entry_path, structure_summary, screenshot_path,
            snapshot_path, trace_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            module_key = excluded.module_key,
            title = excluded.title,
            url = excluded.url,
            entry_path = excluded.entry_path,
            structure_summary = excluded.structure_summary,
            snapshot_path = excluded.snapshot_path
        """,
        (
            kwargs["page_id"],
            kwargs["run_id"],
            kwargs["module_key"],
            kwargs["title"],
            kwargs["url"],
            kwargs["entry_path"],
            kwargs["structure_summary"],
            "",
            kwargs["snapshot_path"],
            "",
        ),
    )


def _upsert_exploration_artifact(db, **kwargs) -> None:
    db.execute(
        """
        INSERT INTO exploration_artifacts (
            id, exploration_run_id, artifact_type, file_path, title, summary
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            artifact_type = excluded.artifact_type,
            file_path = excluded.file_path,
            title = excluded.title,
            summary = excluded.summary
        """,
        (
            kwargs["artifact_id"],
            kwargs["run_id"],
            kwargs["artifact_type"],
            kwargs["file_path"],
            kwargs["title"],
            kwargs["summary"],
        ),
    )


def _page_structure_summary(artifact: dict) -> str:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    elements = page.get("elements")
    if not isinstance(elements, list):
        states = artifact.get("states")
        elements = []
        if isinstance(states, list):
            for state in states:
                if isinstance(state, dict) and isinstance(state.get("elements"), list):
                    elements.extend(state["elements"])
    return f"发现 {len(elements)} 个元素"
