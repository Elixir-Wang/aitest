from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

import yaml

from app.core.storage import store_path


def write_exploration_artifacts(
    artifact_root: Path,
    *,
    run: dict,
    summary: dict,
    pages: list[dict],
    elements: list[dict],
    blockers: list[dict],
    log_content: str,
) -> dict[str, str]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    pages_dir = artifact_root / "pages"
    logs_dir = artifact_root / "logs"
    pages_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    run_path = artifact_root / "run.yaml"
    summary_path = artifact_root / "summary.yaml"
    graph_path = artifact_root / "graph.yaml"
    blockers_path = artifact_root / "blockers.yaml"
    log_path = logs_dir / "run.log"
    log_path.write_text(log_content.rstrip() + "\n", encoding="utf-8")

    page_payloads = _build_page_payloads(run, pages, elements, blockers)
    for payload in page_payloads:
        payload["file_path"] = f"pages/{payload['file_name']}"
        (pages_dir / payload["file_name"]).write_text(
            yaml.safe_dump(payload["content"], allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    run_yaml = {
        "run": _run_section(run, summary, page_payloads, blockers),
        "summary": summary,
        "pages": [
            {
                "file_path": page["file_path"],
                "page_url": page["content"]["page"]["url"],
                "title": page["content"]["page"]["title"],
            }
            for page in page_payloads
        ],
        "graph_path": "graph.yaml",
        "blockers_path": "blockers.yaml",
        "log_path": "logs/run.log",
    }
    run_path.write_text(yaml.safe_dump(run_yaml, allow_unicode=True, sort_keys=False, default_flow_style=False), encoding="utf-8")

    summary_path.write_text(
        yaml.safe_dump(_summary_yaml(summary, run, page_payloads, blockers), allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    graph_path.write_text(
        yaml.safe_dump(_graph_yaml(run, page_payloads, elements, blockers), allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    blockers_path.write_text(
        yaml.safe_dump({"blockers": blockers}, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    return {
        "run_path": store_path(run_path) or "",
        "summary_path": store_path(summary_path) or "",
        "graph_path": store_path(graph_path) or "",
        "blockers_path": store_path(blockers_path) or "",
        "log_path": store_path(log_path) or "",
    }


def read_yaml_artifact(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def read_text_artifact(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_exploration_run_artifacts(artifact_root: Path) -> dict:
    run = read_yaml_artifact(artifact_root / "run.yaml")
    summary = read_yaml_artifact(artifact_root / "summary.yaml")
    graph = read_yaml_artifact(artifact_root / "graph.yaml")
    blockers = read_yaml_artifact(artifact_root / "blockers.yaml")
    page_items = []
    pages_dir = artifact_root / "pages"
    if pages_dir.exists():
        for path in sorted(pages_dir.glob("page-*.yaml")):
            page_items.append(
                {
                    "file_path": store_path(path) or "",
                    "content": read_yaml_artifact(path),
                }
            )
    return {
        "run": run,
        "summary": summary,
        "graph": graph,
        "blockers": blockers,
        "pages": page_items,
        "log_content": read_text_artifact(artifact_root / "logs" / "run.log"),
    }


def _build_page_payloads(run: dict, pages: list[dict], elements: list[dict], blockers: list[dict]) -> list[dict]:
    elements_by_page = defaultdict(list)
    for element in elements:
        elements_by_page[element.get("page_url", "")].append(element)

    blockers_by_page = defaultdict(list)
    for blocker in blockers:
        blockers_by_page[blocker.get("page_ref", "")].append(blocker)

    payloads = []
    for index, page in enumerate(pages, start=1):
        slug = _slugify(page.get("title") or page.get("url") or f"page-{index}")
        file_name = f"page-{index:03d}-{slug}.yaml"
        page_elements = elements_by_page.get(page["url"], [])
        payloads.append(
            {
                "file_name": file_name,
                "content": {
                    "page": {
                        "title": page["title"],
                        "url": page["url"],
                        "entry_path": page["entry_path"],
                        "structure_summary": page["structure_summary"],
                    },
                    "accessibility_tree": {
                        "headings": [],
                        "elements": [
                            {
                                "name": element.get("name") or element.get("locator") or "未命名元素",
                                "type": element.get("type") or "element",
                                "locator": element.get("locator") or "",
                                "href": element.get("href") or "",
                            }
                            for element in page_elements
                        ],
                    },
                    "actions": [
                        {
                            "name": element.get("name") or element.get("locator") or "未命名元素",
                            "type": element.get("type") or "element",
                            "locator": element.get("locator") or "",
                        }
                        for element in page_elements
                        if element.get("href") or (element.get("type") in {"button", "input", "textarea", "select"})
                    ],
                    "relations": [
                        {
                            "type": "blocked_by",
                            "reason_type": blocker.get("reason_type") or "exploration_gap",
                            "reason": blocker.get("reason") or "",
                        }
                        for blocker in blockers_by_page.get(page["url"], [])
                    ],
                    "quality": {
                        "element_count": len(page_elements),
                        "blocked_count": len(blockers_by_page.get(page["url"], [])),
                    },
                },
            }
        )
    return payloads


def _run_section(run: dict, summary: dict, pages: list[dict], blockers: list[dict]) -> dict:
    return {
        "id": run["id"],
        "project_id": run["project_id"],
        "project_name": run["project_name"],
        "environment_id": run["environment_id"],
        "environment_name": run["environment_name"],
        "title": run["title"],
        "status": summary["status"],
        "summary": summary["summary"],
        "page_count": len(pages),
        "blocker_count": len(blockers),
        "log_path": "logs/run.log",
    }


def _summary_yaml(summary: dict, run: dict, pages: list[dict], blockers: list[dict]) -> dict:
    return {
        "run_id": run["id"],
        "title": f"探索报告 v1",
        "status": summary["status"],
        "summary": summary["summary"],
        "markdown_content": summary["markdown_content"],
        "page_count": len(pages),
        "blocker_count": len(blockers),
    }


def _graph_yaml(run: dict, pages: list[dict], elements: list[dict], blockers: list[dict]) -> dict:
    page_by_url = {page["content"]["page"]["url"]: page for page in pages}
    edges = []
    for element in elements:
        source = element.get("page_url") or ""
        target = element.get("href") or ""
        if source and target:
            edges.append(
                {
                    "source": source,
                    "target": target,
                    "type": "link",
                    "label": element.get("name") or element.get("locator") or "未命名元素",
                }
            )
    for blocker in blockers:
        edges.append(
            {
                "source": blocker.get("page_ref") or "",
                "target": run["id"],
                "type": "blocker",
                "label": blocker.get("reason_type") or "blocker",
            }
        )
    return {"edges": edges, "pages": list(page_by_url.keys())}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
    return slug[:40] or "page"
