# apps/backend/app/services/page_exploration/output_registry.py

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.agents.page_exploration.utils.page_id import make_page_id
from app.core import settings
from app.core.db import connect as default_connect
from app.repositories import exploration_run_repo as default_exploration_run_repo
from app.services.page_exploration.report_writer import (
    _artifact_quality_warnings,
    _exploration_completion_status,
    _read_timeline_events_from_run_dir,
    _write_exploration_report,
    _write_exploration_summary,
)


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

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
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
    pages_dir = run_dir / "pages"
    run_dir.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_artifacts = _collect_page_artifact_files(pages_dir)
    timeline_events = _read_timeline_events_from_run_dir(run_dir)
    completion_status = (
        result_status
        if result_status == "failed"
        else _exploration_completion_status(timeline_events)
    )
    _write_exploration_summary(
        run_dir=run_dir,
        run_id=run_id,
        start_url=start_url,
        scope=scope,
        exploration_mode=exploration_mode,
        max_pages=max_pages,
        page_artifacts=page_artifacts,
        completion_status=completion_status,
    )

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
    pages_dir = run_dir / "pages"
    elements = snapshot.get("elements") if isinstance(snapshot.get("elements"), list) else []
    accessibility_tree = snapshot.get("accessibility_tree") if isinstance(snapshot.get("accessibility_tree"), list) else []
    artifact_elements = _snapshot_elements_for_artifact(elements, accessibility_tree)
    visible_text_blocks = snapshot.get("visible_text_blocks") if isinstance(snapshot.get("visible_text_blocks"), list) else []
    captured_at = datetime.now(timezone.utc).isoformat()
    artifact = {
        "page": {
            "id": page_id,
            "title": title,
            "url": url,
            "normalized_url": normalized_path,
            "normalized_path": normalized_path,
            "module": "主探索模块",
            "status": "explored",
            "structure_summary": f"自动保存页面快照，发现 {len(artifact_elements)} 个元素。",
            "elements": artifact_elements,
            "accessibility_tree": accessibility_tree,
            "visible_text_blocks": visible_text_blocks,
            "last_explored": {
                "run_id": run_id,
                "timestamp": captured_at,
            },
        },
        "states": [
            {
                "id": "snapshot-current",
                "title": title,
                "url": url,
                "elements": artifact_elements,
                "accessibility_tree": accessibility_tree,
                "visible_text_blocks": visible_text_blocks,
            }
        ],
        "actions": [
            {
                "id": "snapshot-captured",
                "type": "snapshot",
                "target": title,
                "result": "浏览器快照已自动保存为页面产物。",
                "status": "completed",
                "occurred_at": captured_at,
                "source": "playwright_snap_tool",
            }
        ],
        "metadata": {
            "captured_at": captured_at,
            "source": "snapshot_checkpoint",
        },
    }

    path = pages_dir / f"{page_id}.yaml"
    _write_yaml_file(path, artifact)
    try:
        with _connect() as db:
            _register_page_artifact_file(
                db,
                project_id=project_id,
                run_dir=run_dir,
                run_id=run_id,
                path=path,
                artifact=artifact,
                scope="主探索模块",
            )
    except Exception:
        # Snapshot checkpoints are best-effort. The final exploration output
        # registration re-indexes all run-scoped page artifacts.
        pass
    return path


def _register_page_artifact_file(
    db,
    *,
    project_id: str,
    run_dir: Path,
    run_id: str,
    path: Path,
    artifact: dict,
    scope: str,
) -> None:
    page = artifact.get("page") if isinstance(artifact.get("page"), dict) else {}
    page_id = _string(page.get("id") or path.stem)
    title = _string(page.get("semantic_title") or page.get("title") or path.stem)
    url = _string(page.get("url") or page.get("env_url") or "")
    entry_path = _string(page.get("normalized_url") or page.get("normalized_path") or page.get("entry_path") or "")
    module_key = _string(page.get("module_key") or page.get("module") or scope or "主探索模块")
    structure_summary = _string(page.get("structure_summary") or _page_structure_summary(artifact))

    _exploration_run_repo().update_artifact_root(db, run_id, str(run_dir))
    _upsert_exploration_page(
        db,
        page_id=page_id,
        run_id=run_id,
        title=title,
        url=url,
        entry_path=entry_path,
        module_key=module_key,
        structure_summary=structure_summary,
        snapshot_path=str(path),
    )
    _upsert_exploration_artifact(
        db,
        artifact_id=f"{run_id}-{path.stem}-yaml",
        run_id=run_id,
        artifact_type="page_yaml",
        file_path=_save_project_page_artifact(
            project_id=project_id,
            run_id=run_id,
            artifact=artifact,
            source_path=path,
            scope=scope,
        ),
        title=title,
        summary=structure_summary,
    )


# --- Inlined from ProjectPagesService ---
_HOME_DISPLAY_NAME = "首页"


def _inline_save_page(
    *,
    project_id: str,
    page_id: str,
    page_data: dict,
    run_id: str,
    url: str,
    normalized_path: str,
    env: str = "test",
) -> bool:
    """Inlined from ProjectPagesService.save_page."""
    import yaml

    base_dir = _project_file_storage_root() / project_id / "page_exploration"
    pages_dir = base_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    page_file = pages_dir / f"{page_id}.yaml"

    env_urls = {env: url}
    if page_file.exists():
        try:
            existing = yaml.safe_load(open(page_file, encoding="utf-8"))
            if existing:
                env_urls = existing.get("page", {}).get("env_urls", {})
                env_urls[env] = url
        except Exception:
            pass

    full_page_data = {
        "page": {
            "id": page_id,
            "title": page_data.get("title", ""),
            "display_name": page_data.get("display_name") or _inline_display_name_from_path(normalized_path),
            "breadcrumb": page_data.get("breadcrumb") or _inline_breadcrumb_from_path(normalized_path),
            "normalized_path": normalized_path,
            "structure_summary": page_data.get("structure_summary", ""),
            "path_hash": _inline_path_hash(normalized_path),
            "env_urls": env_urls,
            "last_explored": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "run_id": run_id,
            },
            "elements": page_data.get("elements", []),
        },
        "states": page_data.get("states", []),
        "quality": page_data.get("quality", {}),
        "metadata": page_data.get("metadata", {}),
    }

    with open(page_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(full_page_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return True


def _inline_list_pages(project_id: str):
    """Inlined from ProjectPagesService.list_pages."""
    import yaml

    base_dir = _project_file_storage_root() / project_id / "page_exploration"
    pages_dir = base_dir / "pages"
    pages = []
    if not pages_dir.exists():
        return pages
    for page_file in pages_dir.glob("*.yaml"):
        if page_file.name == "pages-index.yaml":
            continue
        try:
            page_data = yaml.safe_load(open(page_file, encoding="utf-8"))
            page_info = page_data.get("page", {})
            pages.append(
                {
                    "page_id": page_info.get("id"),
                    "title": page_info.get("title"),
                    "display_name": page_info.get("display_name")
                    or _inline_display_name_from_path(page_info.get("normalized_path") or ""),
                    "breadcrumb": page_info.get("breadcrumb")
                    or _inline_breadcrumb_from_path(page_info.get("normalized_path") or ""),
                    "normalized_path": page_info.get("normalized_path"),
                    "structure_summary": page_info.get("structure_summary"),
                    "last_explored": page_info.get("last_explored"),
                    "file": page_file.name,
                }
            )
        except Exception:
            pass
    return pages


def _inline_breadcrumb_from_path(normalized_path: str) -> list:
    segments = [s for s in normalized_path.strip("/").split("/") if s]
    return segments or [_HOME_DISPLAY_NAME]


def _inline_display_name_from_path(normalized_path: str) -> str:
    breadcrumb = _inline_breadcrumb_from_path(normalized_path)
    return breadcrumb[-1] if breadcrumb else _HOME_DISPLAY_NAME


def _inline_path_hash(normalized_path: str) -> str:
    import hashlib
    h = hashlib.sha256(normalized_path.encode("utf-8"))
    return f"sha256-{h.hexdigest()[:16]}"


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
            "states": artifact.get("states", []),
            "quality": artifact.get("quality", {}),
            "metadata": {
                **(artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}),
                "source": "page_exploration_run",
                "source_run_id": run_id,
                "source_artifact_path": str(source_path),
                "module": _string(page.get("module_key") or page.get("module") or scope),
            },
        },
        run_id=run_id,
        url=url,
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


def _snapshot_elements_for_artifact(elements: list, accessibility_tree: list) -> list[dict]:
    """合并 DOM 采集元素与 accessibility_tree 可见节点，去重后写入 yaml。

    背景：DOM 采集（collectDomFacts）只覆盖主页面 DOM，不含 popover / dropdown 浮层内容。
    accessibility_tree（accessibility.snapshot({ interestingOnly: false })）包含浮层节点，
    两者合并才能产出完整的 yaml elements 列表。

    合并策略：
    - DOM 元素（elements）完整保留，不去重（列表中多个同名按钮需要全部出现）
    - accessibility_tree 节点只补充 DOM 中没有的（用 "ax-{role}:{name}" key 去重，
      避免纯文本节点造成重复；去重粒度宽松，避免误吞同名不同行的元素）

    复用契约（外部 Playwright 自动化测试依赖此契约）：
    - 透传 observePage 标定的 element.ancestor_chain（元素 DOM 祖先链）
    - 把 primary_selector / fallback_selector 携带的 verification 元数据
      （{checked, unique, visible, match_count}）按 code 匹配到对应 locator 上，
      让外部脚本读 yaml 即可知道这个 selector 是否 verified
    """
    result: list[dict] = []
    # DOM 元素全部保留（不去重，保持列表完整性）
    for element in elements:
        if not isinstance(element, dict):
            continue
        name = _string(element.get("name") or element.get("text") or f"element-{len(result) + 1}")
        role = _string(element.get("role") or "element")
        role_source = _string(element.get("role_source") or "")
        artifact_element: dict = {
            "id": _string(element.get("ref") or f"el-{len(result) + 1}"),
            "name": name,
            "role": role,
            "text": element.get("text"),
            "visible": bool(element.get("visible", True)),
            "locators": _attach_verification_metadata(
                _semantic_locator_candidates(role, name, role_source),
                element,
            ),
        }
        ancestor_chain = element.get("ancestor_chain")
        if isinstance(ancestor_chain, list) and ancestor_chain:
            artifact_element["ancestor_chain"] = ancestor_chain
        result.append(artifact_element)

    # accessibility_tree 只补充 DOM 中没有的节点（用宽松 key 避免吞掉同名不同行元素）
    _TEXT_ROLES = frozenset({"text", "img", "graphic"})
    seen: set[str] = set()
    for node in accessibility_tree:
        if not isinstance(node, dict):
            continue
        role = _string(node.get("role") or "")
        name = _string(node.get("name") or "")
        if not role or not name:
            continue
        if role in _TEXT_ROLES:
            continue
        # 宽松 key：role + name 前 30 字符，避免 "自主规划 Agent 能..." 和 "自主规划 Agent" 被误判为重复
        key = f"{role}:{name[:30]}"
        if key in seen:
            continue
        seen.add(key)
        result.append({
            "id": f"ax-{len(result) + 1}",
            "name": name,
            "role": role,
            "text": node.get("name"),
            "visible": True,
            "locators": _semantic_locator_candidates(role, name, "accessibility_tree"),
        })

    return result


def _attach_verification_metadata(
    candidates: list[dict], observed_element: dict
) -> list[dict]:
    """把 observePage 验证过的 primary_selector / fallback_selector 的 verification
    元数据按 code 精确匹配附加到对应 candidate，让 yaml 对外暴露 verified=true/false。

    匹配规则：
    - candidate.code == selector.code → 复制 selector.verification 到 candidate.verification
    - 没匹配上的 candidate 保留空 verification 字段（schema 占位，让 schema 知道位置）

    这样外部脚本能直接读 yaml 决定复不复制这个 selector：
        locator = page.locator(element["locators"][0]["code"])
        if element["locators"][0].get("verification", {}).get("unique") is True:
            ...
    """
    selector_index: dict[str, dict] = {}
    for key in ("primary_selector", "fallback_selector"):
        sel = observed_element.get(key)
        if isinstance(sel, dict) and sel.get("code"):
            selector_index[sel["code"]] = sel

    attached: list[dict] = []
    for candidate in candidates:
        code = candidate.get("code", "")
        matched_selector = selector_index.get(code)
        if matched_selector and isinstance(matched_selector.get("verification"), dict):
            new_candidate = dict(candidate)
            new_candidate["verification"] = dict(matched_selector["verification"])
            attached.append(new_candidate)
        else:
            new_candidate = dict(candidate)
            new_candidate["verification"] = {"checked": False, "unique": None, "visible": None, "match_count": 0}
            attached.append(new_candidate)
    return attached


_REAL_ARIA_ROLES = frozenset({
    "button", "link", "textbox", "combobox", "checkbox", "radio",
    "tab", "menuitem", "option", "treeitem", "searchbox", "switch", "spinbutton",
    "heading", "listitem", "row", "cell", "columnheader", "rowheader",
    "gridcell", "dialog", "alertdialog",
})


def _semantic_locator_candidates(role: str, name: str, role_source: str = "") -> list[dict]:
    """为元素生成稳定可用的 locator，写入 yaml 供后续探索使用。

    规则：
    - role 是真实 ARIA role 且非 inferred → 输出 getByRole
    - 其他情况（inferred / clickable / div / span / 占位 element）一律不输出 getByRole，
      只输出 getByText（popover / 卡片场景最稳的兜底）

    注：本函数是纯生成器，不带 verification 元数据。verification 由
    _attach_verification_metadata 在 _snapshot_elements_for_artifact 整合观察数据时附加。
    """
    if not name or not role or role == "element":
        return []
    escaped_name = name.replace("\\", "\\\\").replace("'", "\\'")
    candidates: list[dict] = []
    if role in _REAL_ARIA_ROLES and role_source != "inferred":
        candidates.append({
            "kind": "role",
            "code": f"getByRole('{role}', {{ name: '{escaped_name}' }})",
            "priority": 1,
        })
    candidates.append({
        "kind": "text",
        "code": f"getByText('{escaped_name}', {{ exact: true }})",
        "priority": 2 if candidates else 1,
    })
    return candidates


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




