from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from app.core.db import connect
from app.core.exceptions import api_error
from app.core.settings import PROJECT_FILE_STORAGE_ROOT
from app.core.storage import resolve_stored_path, store_path
from app.repositories import document_repo, exploration_repo, knowledge_repo, project_repo
from app.schemas.knowledge import (
    KnowledgeBuildInput,
    KnowledgeBuildOutput,
    KnowledgeExplorationInput,
    KnowledgeItemOutput,
    KnowledgeSourceDocumentInput,
    KnowledgeSourceRef,
    WikiLintIssueOutput,
    WikiPageOutput,
)
from app.services import knowledge_builder_service, operation_log_service

READY_EXPLORATION_STATUSES = {"completed", "partial"}


def list_builds(project_id: str, actor) -> list[dict]:
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")
        rows = knowledge_repo.list_builds(db, project_id)
        return [_serialize_build(row, actor["role"]) for row in rows]


async def generate_build(project_id: str, actor) -> dict:
    input_data, source_version_ids, exploration_run_ids, blockers = _collect_build_input(project_id)
    with connect() as db:
        build_no = knowledge_repo.next_build_no(db, project_id)

    build_id = f"kb-{secrets.token_hex(8)}"
    if blockers:
        output = _blocked_output(input_data, blockers)
    else:
        try:
            output = await knowledge_builder_service.run_knowledge_builder(input_data.model_copy(update={"build_no": build_no}))
        except Exception:
            output = _fallback_output(input_data.model_copy(update={"build_no": build_no}))

    status = "blocked" if output.status == "blocked" else "draft"
    output_dir = PROJECT_FILE_STORAGE_ROOT / project_id / "knowledge" / build_no
    _write_wiki_files(output_dir, output)

    with connect() as db:
        knowledge_repo.create_build(
            db,
            build_id=build_id,
            project_id=project_id,
            build_no=build_no,
            status=status,
            build_type="initial",
            source_document_version_ids=source_version_ids,
            exploration_run_ids=exploration_run_ids,
            output_dir=store_path(output_dir) or str(output_dir),
            summary=output.summary,
            change_summary=output.change_summary,
            blockers=output.blockers,
            affected_modules=output.affected_modules,
            created_by=actor["id"],
        )
        _persist_output(db, build_id, output, output_dir)
        row = knowledge_repo.find_build(db, project_id, build_id)

    operation_log_service.record_success(
        module="knowledge",
        action="generate",
        object_type="knowledge_build",
        object_id=build_id,
        object_name=build_no,
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"生成项目知识库 {build_no}，状态：{_status_label(status)}。",
        after={"build_id": build_id, "status": status, "source_versions": source_version_ids},
        artifact_path=[store_path(output_dir) or str(output_dir)],
    )
    return _build_detail(project_id, build_id, actor, row=row)


def get_build(project_id: str, build_id: str, actor) -> dict:
    return _build_detail(project_id, build_id, actor)


def publish_build(project_id: str, build_id: str, actor) -> dict:
    with connect() as db:
        build = knowledge_repo.find_build(db, project_id, build_id)
        if not build:
            raise api_error(404, "KNOWLEDGE_BUILD_NOT_FOUND", "知识库构建不存在。")
        if build["status"] == "blocked":
            raise api_error(409, "KNOWLEDGE_BUILD_BLOCKED", "知识库存在阻塞项，不能发布。")
        knowledge_repo.publish_build(db, project_id, build_id)

    operation_log_service.record_success(
        module="knowledge",
        action="publish",
        object_type="knowledge_build",
        object_id=build_id,
        object_name=build["build_no"],
        project_id=project_id,
        actor_id=actor["id"],
        actor_name=operation_log_service.actor_display_name(actor),
        source="web",
        summary=f"发布项目知识库 {build['build_no']}。",
    )
    return get_build(project_id, build_id, actor)


def get_page(project_id: str, build_id: str, page_id: str, actor) -> dict:
    _ = actor
    with connect() as db:
        build = knowledge_repo.find_build(db, project_id, build_id)
        if not build:
            raise api_error(404, "KNOWLEDGE_BUILD_NOT_FOUND", "知识库构建不存在。")
        page = knowledge_repo.find_page(db, build_id, page_id)
        if not page:
            raise api_error(404, "WIKI_PAGE_NOT_FOUND", "Wiki 页面不存在。")
        path = resolve_stored_path(page["file_path"])
        content = path.read_text(encoding="utf-8") if path and path.exists() else ""
        return {
            **_serialize_page(page),
            "markdown_content": content,
        }


def _collect_build_input(project_id: str) -> tuple[KnowledgeBuildInput, list[str], list[str], list[str]]:
    with connect() as db:
        project = project_repo.find_by_id(db, project_id)
        if not project:
            raise api_error(404, "PROJECT_NOT_FOUND", "项目不存在。")

        source_documents: list[KnowledgeSourceDocumentInput] = []
        source_version_ids: list[str] = []
        blockers: list[str] = []
        for doc in document_repo.list_by_project(db, project_id):
            if not doc["current_version_id"]:
                continue
            open_conflicts = document_repo.list_conflicts(db, doc["id"], status="open")
            if open_conflicts:
                blockers.append(f"需求文档「{doc['name']}」存在未解决归并冲突。")
                continue
            version = document_repo.find_version(db, doc["current_version_id"])
            if not version:
                continue
            markdown_path = resolve_stored_path(version["file_path"]) or Path(version["file_path"])
            if not markdown_path.exists():
                blockers.append(f"需求文档「{doc['name']}」当前版本文件不存在。")
                continue
            source_version_ids.append(version["id"])
            source_documents.append(
                KnowledgeSourceDocumentInput(
                    document_id=doc["id"],
                    document_name=doc["name"],
                    version_id=version["id"],
                    version_no=version["version_no"],
                    markdown_content=markdown_path.read_text(encoding="utf-8"),
                )
            )

        explorations: list[KnowledgeExplorationInput] = []
        exploration_run_ids: list[str] = []
        for run in exploration_repo.list_by_project(db, project_id):
            if run["status"] not in READY_EXPLORATION_STATUSES:
                continue
            exploration_run_ids.append(run["id"])
            modules = [
                {
                    **dict(module),
                    "pages": [dict(page) for page in exploration_repo.list_pages(db, run["id"]) if page["module_key"] == module["module_key"]],
                    "elements": [
                        dict(element)
                        for element in exploration_repo.list_elements(db, run["id"])
                        if element["module_key"] == module["module_key"]
                    ],
                    "blockers": [
                        dict(blocker)
                        for blocker in exploration_repo.list_blockers(db, run["id"])
                        if blocker["module_key"] == module["module_key"]
                    ],
                }
                for module in exploration_repo.list_module_coverages(db, run["id"])
            ]
            explorations.append(
                KnowledgeExplorationInput(
                    exploration_run_id=run["id"],
                    title=run["title"],
                    status=run["status"],
                    result_summary=run["result_summary"],
                    modules=modules,
                )
            )

    if not source_documents:
        blockers.append("当前项目没有可用于知识库构建的需求文档版本。")
    return (
        KnowledgeBuildInput(
            project_id=project_id,
            project_name=project["name"],
            build_no="",
            source_documents=source_documents,
            explorations=explorations,
        ),
        source_version_ids,
        exploration_run_ids,
        blockers,
    )


def _fallback_output(input_data: KnowledgeBuildInput) -> KnowledgeBuildOutput:
    modules: dict[str, dict[str, object]] = {}
    for doc in input_data.source_documents:
        headings = _extract_headings(doc.markdown_content)
        for index, heading in enumerate(headings or [doc.document_name], start=1):
            key = _slugify(heading) or f"module-{index}"
            modules.setdefault(
                key,
                {
                    "name": heading,
                    "facts": [],
                    "refs": [
                        KnowledgeSourceRef(
                            source_type="requirement",
                            source_id=doc.version_id,
                            source_title=f"{doc.document_name} v{doc.version_no}",
                            location=heading,
                            excerpt=_first_non_empty_line(doc.markdown_content),
                        )
                    ],
                },
            )
            cast_facts = modules[key]["facts"]
            if isinstance(cast_facts, list):
                cast_facts.append(f"需求文档确认存在「{heading}」相关业务内容。")

    for exploration in input_data.explorations:
        for module in exploration.modules:
            key = str(module.get("module_key") or _slugify(str(module.get("module_name") or exploration.title)))
            item = modules.setdefault(key, {"name": module.get("module_name") or exploration.title, "facts": [], "refs": []})
            facts = item["facts"]
            if isinstance(facts, list):
                facts.append(str(module.get("completion_summary") or "站点探索已覆盖该模块页面事实。"))
            refs = item["refs"]
            if isinstance(refs, list):
                refs.append(
                    KnowledgeSourceRef(
                        source_type="exploration",
                        source_id=exploration.exploration_run_id,
                        source_title=exploration.title,
                        location=str(module.get("entry_path") or ""),
                        excerpt=str(module.get("completion_summary") or exploration.result_summary),
                    )
                )

    pages = _base_pages(input_data, modules)
    items = [
        KnowledgeItemOutput(
            module_key=key,
            module_name=str(value["name"]),
            knowledge_type="merged_fact",
            content=fact,
            source_refs=list(value["refs"]) if isinstance(value["refs"], list) else [],
        )
        for key, value in modules.items()
        for fact in (value["facts"] if isinstance(value["facts"], list) else [])
    ]
    return KnowledgeBuildOutput(
        status="draft",
        summary=f"基于 {len(input_data.source_documents)} 个需求版本和 {len(input_data.explorations)} 个探索结果生成项目知识库。",
        change_summary="首次生成项目知识库。",
        affected_modules=[str(value["name"]) for value in modules.values()],
        pages=pages,
        knowledge_items=items,
        lint_issues=[
            WikiLintIssueOutput(severity="info", title="确定性构建", detail="模型不可用时使用后端确定性 llm-wiki fallback 生成。")
        ],
    )


def _blocked_output(input_data: KnowledgeBuildInput, blockers: list[str]) -> KnowledgeBuildOutput:
    pages = _base_pages(input_data, {})
    pages.append(
        WikiPageOutput(
            page_id="build-blockers",
            title="构建阻塞",
            relative_path="build/build-blockers.md",
            page_type="build",
            summary="知识库构建阻塞项。",
            markdown_content="# 构建阻塞\n\n" + "\n".join(f"- {item}" for item in blockers),
        )
    )
    return KnowledgeBuildOutput(
        status="blocked",
        summary="知识库构建存在阻塞项，不能发布。",
        change_summary="未生成正式知识条目。",
        blockers=blockers,
        pages=pages,
        lint_issues=[WikiLintIssueOutput(severity="error", title="构建阻塞", detail=item) for item in blockers],
    )


def _base_pages(input_data: KnowledgeBuildInput, modules: dict[str, dict[str, object]]) -> list[WikiPageOutput]:
    module_lines = [f"- [{value['name']}](modules/{value['name']}.md)" for value in modules.values()]
    pages = [
        WikiPageOutput(
            page_id="schema",
            title="AGENTS",
            relative_path="AGENTS.md",
            page_type="index",
            summary="项目知识库维护规则。",
            markdown_content="# 项目知识库规则\n\n- 只记录已确认来源。\n- 未确认冲突和阻塞项不得进入正式知识。\n- 查询时先读 index，再进入模块页，必要时回查来源。",
        ),
        WikiPageOutput(
            page_id="index",
            title="知识库索引",
            relative_path="index.md",
            page_type="index",
            summary="项目知识库页面索引。",
            markdown_content="# 知识库索引\n\n## 模块\n\n" + ("\n".join(module_lines) if module_lines else "- 暂无可发布模块。"),
        ),
        WikiPageOutput(
            page_id="log",
            title="构建日志",
            relative_path="log.md",
            page_type="log",
            summary="知识库生成日志。",
            markdown_content=f"# 构建日志\n\n- {input_data.build_no or 'KB'}：生成项目知识库。",
        ),
        WikiPageOutput(
            page_id="overview",
            title="项目总览",
            relative_path="00-项目总览.md",
            page_type="overview",
            summary=input_data.project_name,
            markdown_content=f"# {input_data.project_name}\n\n## 来源\n\n- 需求版本：{len(input_data.source_documents)}\n- 探索结果：{len(input_data.explorations)}",
        ),
        WikiPageOutput(
            page_id="module-index",
            title="模块索引",
            relative_path="01-模块索引.md",
            page_type="overview",
            summary="模块清单。",
            markdown_content="# 模块索引\n\n" + ("\n".join(module_lines) if module_lines else "- 暂无模块。"),
        ),
        WikiPageOutput(
            page_id="source-reference-matrix",
            title="来源引用矩阵",
            relative_path="maps/source-reference-matrix.md",
            page_type="map",
            summary="知识条目来源映射。",
            markdown_content="# 来源引用矩阵\n\n| 来源 | 说明 |\n| --- | --- |\n"
            + "\n".join(f"| {doc.document_name} v{doc.version_no} | 需求来源 |" for doc in input_data.source_documents),
        ),
        WikiPageOutput(
            page_id="lint-report",
            title="Lint 报告",
            relative_path="quality/lint-report.md",
            page_type="quality",
            summary="知识库健康检查。",
            markdown_content="# Lint 报告\n\n- 已检查基础目录、模块页和来源引用。",
        ),
        WikiPageOutput(
            page_id="test-focus",
            title="测试关注点",
            relative_path="testing/test-focus.md",
            page_type="testing",
            summary="测试设计关注点。",
            markdown_content="# 测试关注点\n\n" + "\n".join(f"- {value['name']}" for value in modules.values()),
        ),
        WikiPageOutput(
            page_id="build-summary",
            title="构建摘要",
            relative_path="build/build-summary.md",
            page_type="build",
            summary="构建输入和输出摘要。",
            markdown_content=f"# 构建摘要\n\n- 项目：{input_data.project_name}\n- 需求版本：{len(input_data.source_documents)}\n- 探索结果：{len(input_data.explorations)}",
        ),
    ]
    for key, value in modules.items():
        refs = list(value["refs"]) if isinstance(value["refs"], list) else []
        facts = value["facts"] if isinstance(value["facts"], list) else []
        name = str(value["name"])
        pages.append(
            WikiPageOutput(
                page_id=f"module-{key}",
                title=name,
                relative_path=f"modules/{name}.md",
                page_type="module",
                module_key=key,
                summary=f"{name} 模块知识。",
                source_refs=refs,
                markdown_content=(
                    f"---\nmodule_key: {key}\nmodule_name: {name}\nstatus: confirmed\nsource_count: {len(refs)}\n---\n\n"
                    f"# {name}\n\n## 已确认知识\n\n"
                    + "\n".join(f"- {fact}" for fact in facts)
                    + "\n\n## 测试关注点\n\n- 覆盖正常路径、异常路径、权限和状态变化。\n"
                ),
            )
        )
    for page_id, relative_path, title in [
        ("module-source-map", "maps/module-source-map.md", "模块来源映射"),
        ("page-requirement-map", "maps/page-requirement-map.md", "页面需求映射"),
        ("stale-claims", "quality/stale-claims.md", "过期声明"),
        ("risk-paths", "testing/risk-paths.md", "风险路径"),
        ("state-flows", "testing/state-flows.md", "状态流转"),
        ("update-plan", "build/update-plan.md", "更新计划"),
        ("conflict-check", "build/conflict-check.md", "冲突检查"),
        ("changelog", "build/changelog.md", "变更记录"),
    ]:
        pages.append(
            WikiPageOutput(
                page_id=page_id,
                title=title,
                relative_path=relative_path,
                page_type="build" if relative_path.startswith("build/") else "map" if relative_path.startswith("maps/") else "testing" if relative_path.startswith("testing/") else "quality",
                summary=title,
                markdown_content=f"# {title}\n\n- 本次构建自动生成。",
            )
        )
    return pages


def _write_wiki_files(output_dir: Path, output: KnowledgeBuildOutput) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for folder in ("modules", "maps", "quality", "testing", "build"):
        (output_dir / folder).mkdir(exist_ok=True)
    for page in output.pages:
        target = output_dir / page.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page.markdown_content, encoding="utf-8")


def _persist_output(db, build_id: str, output: KnowledgeBuildOutput, output_dir: Path) -> None:
    seen_refs: set[tuple[str, str, str]] = set()
    for index, page in enumerate(output.pages):
        knowledge_repo.create_page(
            db,
            page_id=page.page_id,
            build_id=build_id,
            title=page.title,
            relative_path=page.relative_path,
            page_type=page.page_type,
            module_key=page.module_key,
            summary=page.summary,
            file_path=store_path(output_dir / page.relative_path) or str(output_dir / page.relative_path),
            source_refs=[ref.model_dump() for ref in page.source_refs],
            sort_order=index,
        )
        for ref in page.source_refs:
            _create_unique_ref(db, build_id, ref, seen_refs)
    for item in output.knowledge_items:
        knowledge_repo.create_item(
            db,
            item_id=f"kitem-{secrets.token_hex(8)}",
            build_id=build_id,
            module_key=item.module_key,
            module_name=item.module_name,
            knowledge_type=item.knowledge_type,
            content=item.content,
            source_refs=[ref.model_dump() for ref in item.source_refs],
        )
        for ref in item.source_refs:
            _create_unique_ref(db, build_id, ref, seen_refs)
    for issue in output.lint_issues:
        knowledge_repo.create_lint_issue(
            db,
            issue_id=f"klint-{secrets.token_hex(8)}",
            build_id=build_id,
            severity=issue.severity,
            title=issue.title,
            detail=issue.detail,
            page_id=issue.page_id,
        )


def _create_unique_ref(db, build_id: str, ref: KnowledgeSourceRef, seen_refs: set[tuple[str, str, str]]) -> None:
    key = (ref.source_type, ref.source_id, ref.location)
    if key in seen_refs:
        return
    seen_refs.add(key)
    knowledge_repo.create_source_reference(
        db,
        ref_id=f"kref-{secrets.token_hex(8)}",
        build_id=build_id,
        source_type=ref.source_type,
        source_id=ref.source_id,
        source_title=ref.source_title,
        location=ref.location,
        excerpt=ref.excerpt,
    )


def _build_detail(project_id: str, build_id: str, actor, row=None) -> dict:
    with connect() as db:
        build = row or knowledge_repo.find_build(db, project_id, build_id)
        if not build:
            raise api_error(404, "KNOWLEDGE_BUILD_NOT_FOUND", "知识库构建不存在。")
        return {
            "build": _serialize_build(build, actor["role"]),
            "pages": [_serialize_page(page) for page in knowledge_repo.list_pages(db, build_id)],
            "lint_issues": [dict(issue) for issue in knowledge_repo.list_lint_issues(db, build_id)],
            "source_refs": [dict(ref) for ref in knowledge_repo.list_source_references(db, build_id)],
        }


def _serialize_build(row, role: str) -> dict:
    status = row["status"]
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "build_no": row["build_no"],
        "status": status,
        "status_label": _status_label(status),
        "build_type": row["build_type"],
        "summary": row["summary"],
        "change_summary": row["change_summary"],
        "source_document_version_ids": _json_list(row["source_document_version_ids"]),
        "exploration_run_ids": _json_list(row["exploration_run_ids"]),
        "blockers": _json_list(row["blockers_json"]),
        "affected_modules": _json_list(row["affected_modules_json"]),
        "output_dir": row["output_dir"],
        "page_count": row["page_count"] if "page_count" in row.keys() else 0,
        "item_count": row["item_count"] if "item_count" in row.keys() else 0,
        "lint_count": row["lint_count"] if "lint_count" in row.keys() else 0,
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "published_at": row["published_at"],
        "available_actions": _available_actions(status, role),
    }


def _serialize_page(row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "relative_path": row["relative_path"],
        "page_type": row["page_type"],
        "module_key": row["module_key"],
        "summary": row["summary"],
        "source_refs": _json_list(row["source_refs_json"]),
        "created_at": row["created_at"],
    }


def _available_actions(status: str, role: str) -> list[dict]:
    can_write = role in {"admin", "tester"}
    return [
        {
            "key": "publish_knowledge",
            "label": "发布知识库",
            "enabled": can_write and status == "draft",
            "disabled_reason": "" if can_write and status == "draft" else "仅草稿知识库可发布。",
            "risk_level": "warning",
            "confirm_required": True,
        }
    ]


def _json_list(raw: str) -> list:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def _status_label(status: str) -> str:
    return {"building": "构建中", "blocked": "阻塞", "draft": "草稿", "published": "已发布"}.get(status, status)


def _extract_headings(markdown: str) -> list[str]:
    headings = []
    for line in markdown.splitlines():
        match = re.match(r"^#{1,3}\s+(.+)$", line.strip())
        if match:
            title = match.group(1).strip()
            if title and title not in headings:
                headings.append(title)
    return headings[:12]


def _slugify(value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff_-]+", "", normalized)
    return normalized[:60]


def _first_non_empty_line(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip().strip("#").strip()
        if stripped:
            return stripped[:160]
    return ""
