"""Fix company knowledge vault markdown: heading bold markers and internal doc links."""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import connect
from app.core.storage import resolve_stored_path
from app.repositories import global_knowledge_repo

BASE_ID = "gkb-df74f65ec2ab4935"
API_TREE_URL = "https://saibotan-pre.100credit.cn/agent-document-content/api/v1/tree"

DOC_LINK_RE = re.compile(r"\]\(/docCenter/(manual|oapi)/(\d+)/?\)")
HEADING_RE = re.compile(r"^(#+\s+)(.*)$")

FOLDER_FALLBACK_DOC_ID: dict[int, int] = {
    15: 34,  # 智能体项目开发 -> 智能体管理
    22: 30,  # 高级配置 -> 对话流配置
    35: 36,  # 订阅和使用智能体 -> 企业用户订阅使用智能体
}


def _normalize_title(value: str) -> str:
    return (
        value.removesuffix(".md")
        .replace("——", "--")
        .replace("&", "-")
        .replace(" ", "")
        .strip()
        .lower()
    )


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def _flatten_tree(items: list[dict] | None, docs: list[dict] | None = None, folders: list[dict] | None = None) -> None:
    docs = [] if docs is None else docs
    folders = [] if folders is None else folders
    for item in items or []:
        if item.get("type") == "doc":
            docs.append(item)
        elif item.get("type") == "folder":
            folders.append(item)
        _flatten_tree(item.get("items"), docs, folders)


def _first_doc_id(node: dict) -> int | None:
    for child in node.get("items") or []:
        if child.get("type") == "doc":
            return int(child["id"])
        doc_id = _first_doc_id(child)
        if doc_id is not None:
            return doc_id
    return None


def _build_doc_id_map(project_items: list[dict]) -> dict[int, int]:
    docs: list[dict] = []
    folders: list[dict] = []
    _flatten_tree(project_items, docs, folders)

    mapping: dict[int, int] = {int(doc["id"]): int(doc["id"]) for doc in docs}
    for folder in folders:
        folder_id = int(folder["id"])
        fallback = FOLDER_FALLBACK_DOC_ID.get(folder_id) or _first_doc_id(folder)
        if fallback is not None:
            mapping[folder_id] = fallback
    return mapping


def _build_title_to_gkfile(db) -> dict[str, str]:
    rows = db.execute(
        "SELECT id, display_name FROM global_knowledge_vault_files WHERE knowledge_base_id = ?",
        (BASE_ID,),
    ).fetchall()
    title_map: dict[str, str] = {}
    for row in rows:
        title_map[_normalize_title(row["display_name"])] = row["id"]
    return title_map


def _build_doc_id_to_gkfile(db, project_items: list[dict]) -> dict[int, str]:
    title_to_gkfile = _build_title_to_gkfile(db)
    docs: list[dict] = []
    folders: list[dict] = []
    _flatten_tree(project_items, docs, folders)

    doc_titles = {int(doc["id"]): str(doc["title"]) for doc in docs}
    doc_id_map = _build_doc_id_map(project_items)
    doc_id_to_gkfile: dict[int, str] = {}

    for source_id, target_doc_id in doc_id_map.items():
        title = doc_titles.get(target_doc_id, "")
        gkfile_id = title_to_gkfile.get(_normalize_title(title))
        if gkfile_id:
            doc_id_to_gkfile[source_id] = gkfile_id
    return doc_id_to_gkfile


def _resolve_gkfile_id(link_text: str, doc_id: int, doc_id_to_gkfile: dict[int, str], title_to_gkfile: dict[str, str]) -> str | None:
    normalized_text = _normalize_title(link_text)
    if normalized_text in title_to_gkfile:
        return title_to_gkfile[normalized_text]
    return doc_id_to_gkfile.get(doc_id)


def _replace_doc_links(content: str, doc_id_to_gkfile: dict[int, str], title_to_gkfile: dict[str, str]) -> str:
    def replacer(match: re.Match[str]) -> str:
        doc_id = int(match.group(2))
        before = content[: match.start()]
        link_text_match = re.search(r"\[([^\]]+)\]$", before)
        link_text = link_text_match.group(1) if link_text_match else ""
        gkfile_id = _resolve_gkfile_id(link_text, doc_id, doc_id_to_gkfile, title_to_gkfile)
        if gkfile_id:
            return f"]({gkfile_id})"
        return match.group(0)

    return DOC_LINK_RE.sub(replacer, content)


def _strip_heading_bold(content: str) -> str:
    lines: list[str] = []
    for line in content.splitlines():
        heading = HEADING_RE.match(line)
        if heading is None:
            lines.append(line)
            continue
        prefix, body = heading.groups()
        lines.append(prefix + body.replace("**", "").strip())
    return "\n".join(lines) + ("\n" if content.endswith("\n") else "")


def _transform_markdown(content: str, doc_id_to_gkfile: dict[int, str], title_to_gkfile: dict[str, str]) -> str:
    updated = _replace_doc_links(content, doc_id_to_gkfile, title_to_gkfile)
    updated = _strip_heading_bold(updated)
    updated = re.sub(r"[ \t]{2,}", " ", updated)
    updated = re.sub(r"^(#+\s+\d+\.)\s+", r"\1 ", updated, flags=re.MULTILINE)
    return updated


def _iter_markdown_files(base_dir: Path) -> list[Path]:
    return sorted(base_dir.glob("bases/*/folders/*/markdown/*.md"))


def main() -> None:
    tree_payload = _fetch_json(API_TREE_URL)
    projects = tree_payload.get("data") or []
    manual_project = next((item for item in projects if item.get("project_title") == "产品手册"), None)
    if manual_project is None:
        raise SystemExit("产品手册 project not found in API tree.")

    knowledge_root = ROOT / "data" / "global-knowledge"
    markdown_files = _iter_markdown_files(knowledge_root)
    if not markdown_files:
        raise SystemExit(f"No markdown files found under {knowledge_root}")

    with connect() as db:
        title_to_gkfile = _build_title_to_gkfile(db)
        doc_id_to_gkfile = _build_doc_id_to_gkfile(db, manual_project.get("items") or [])
        print(f"Resolved {len(doc_id_to_gkfile)} docCenter IDs to vault files.")

        updated_files = 0
        for markdown_path in markdown_files:
            original = markdown_path.read_text(encoding="utf-8")
            transformed = _transform_markdown(original, doc_id_to_gkfile, title_to_gkfile)
            if transformed == original:
                continue

            markdown_path.write_text(transformed, encoding="utf-8")
            updated_files += 1

            raw_dir = markdown_path.parent.parent / "raw"
            if raw_dir.is_dir():
                for raw_path in raw_dir.glob("*.md"):
                    if raw_path.stem.startswith(markdown_path.stem):
                        raw_path.write_text(transformed, encoding="utf-8")
                        break

            row = db.execute(
                "SELECT id FROM global_knowledge_vault_files WHERE id = ?",
                (markdown_path.stem,),
            ).fetchone()
            if row is not None:
                db.execute(
                    """
                    UPDATE global_knowledge_vault_files
                    SET markdown_content = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (transformed, row["id"]),
                )
                stored_markdown = resolve_stored_path(
                    db.execute(
                        "SELECT markdown_path FROM global_knowledge_vault_files WHERE id = ?",
                        (row["id"],),
                    ).fetchone()["markdown_path"],
                )
                if stored_markdown is not None:
                    stored_markdown.write_text(transformed, encoding="utf-8")

            print(f"  updated {markdown_path.name}")

        global_knowledge_repo.touch_base(db, BASE_ID)
        print(f"Done. Updated {updated_files} markdown file(s).")


if __name__ == "__main__":
    main()
