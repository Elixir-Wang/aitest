from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from app.agents.manual_test_case_generation.schemas import (
    ExplorationContext,
    ExplorationElementContext,
    ExplorationOperationContext,
    ExplorationOperationStepContext,
    ExplorationPageContext,
)
from app.core import settings
from app.services.page_exploration import page_exploration_service


MAX_PAGES = 100
MAX_FULL_PAGES = 20
MAX_ELEMENTS_PER_FULL_PAGE = 80
MAX_OPERATIONS = 100
MAX_FULL_OPERATIONS = 30
MAX_CONTEXT_CHARS = 80_000


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _keywords(description: str) -> list[str]:
    return [item for item in re.findall(r"[\w\u4e00-\u9fff]+", description.lower()) if len(item) > 1]


def _score(value: str, keywords: list[str]) -> int:
    normalized = value.lower()
    return sum(1 for keyword in keywords if keyword in normalized)


def _redact(value: str, hint: str = "") -> str:
    if not value:
        return value
    combined = f"{hint} {value}"
    if re.search(r"password|passwd|pwd|密码", combined, re.IGNORECASE):
        return "<redacted-password>"
    if re.search(r"token|authorization|cookie|secret|密钥", combined, re.IGNORECASE):
        return "<redacted-secret>"
    return value


def _extract_elements(payload: Any) -> list[ExplorationElementContext]:
    elements: list[ExplorationElementContext] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            name = _text(value.get("name") or value.get("element_name") or value.get("label"))
            text = _text(value.get("text") or value.get("inner_text"))
            role = _text(value.get("role"))
            action_type = _text(value.get("action_type") or value.get("action"))
            element_key = _text(value.get("element_key") or value.get("key"))
            if name or text or element_key:
                elements.append(
                    ExplorationElementContext(
                        element_key=element_key,
                        name=name,
                        text=text,
                        role=role,
                        action_type=action_type,
                        context_hint=_redact(_text(value.get("context_hint"))),
                    )
                )
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    seen: set[tuple[str, str, str, str]] = set()
    result = []
    for element in elements:
        key = (element.element_key, element.name, element.role, element.action_type)
        if key in seen:
            continue
        seen.add(key)
        result.append(element)
    return result


def _read_page(page: dict, actor, project_id: str) -> ExplorationPageContext:
    page_id = _text(page.get("id"))
    content = page_exploration_service.get_project_page_yaml_content(actor, project_id, page_id)["content"]
    payload = yaml.safe_load(content) or {}
    return ExplorationPageContext(
        page_id=page_id,
        title=_text(page.get("title")),
        display_name=_text(page.get("display_name")),
        breadcrumb=[_text(item) for item in page.get("breadcrumb", []) if _text(item)],
        entry_path=_text(page.get("entry_path")),
        structure_summary=_text(page.get("structure_summary")),
        elements=_extract_elements(payload),
    )


def _operations_path(project_id: str) -> Path:
    root = (settings.PROJECT_FILE_STORAGE_ROOT / project_id / "page_exploration").resolve()
    storage_root = settings.PROJECT_FILE_STORAGE_ROOT.resolve()
    root.relative_to(storage_root)
    return root / "operations.yaml"


def _read_operations(project_id: str) -> list[ExplorationOperationContext]:
    path = _operations_path(project_id)
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    operations = payload.get("operations", []) if isinstance(payload, dict) else []
    result = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        steps = []
        for raw_step in operation.get("steps", []) or []:
            if not isinstance(raw_step, dict):
                continue
            expected = raw_step.get("expected", []) or []
            if isinstance(expected, str):
                expected = [expected]
            element_key = _text(raw_step.get("element_key"))
            element_name = _text(raw_step.get("element_name"))
            steps.append(
                ExplorationOperationStepContext(
                    action=_text(raw_step.get("action")),
                    element_key=element_key,
                    element_name=element_name,
                    value=_redact(
                        _text(raw_step.get("value") or raw_step.get("value_ref")),
                        hint=f"{element_key} {element_name}",
                    ),
                    expected=[_redact(_text(item)) for item in expected if _text(item)],
                )
            )
        result.append(
            ExplorationOperationContext(
                operation_key=_text(operation.get("key")),
                page_path=_text(operation.get("page_path")),
                steps=steps,
            )
        )
    return result


def build_exploration_context(
    actor,
    project_id: str,
    description: str,
    include_exploration_artifacts: bool,
) -> ExplorationContext | None:
    if not include_exploration_artifacts:
        return None

    warnings: list[str] = []
    pages: list[ExplorationPageContext] = []
    page_rows = page_exploration_service.list_project_pages(actor, project_id)
    keywords = _keywords(description)
    for page in page_rows[:MAX_PAGES]:
        try:
            normalized = _read_page(page, actor, project_id)
        except Exception as exc:
            warnings.append(f"探索页面 {page.get('id', '')} 无法解析，已跳过。")
            continue
        page_score = _score(
            " ".join(
                [normalized.title, normalized.display_name, normalized.entry_path, normalized.structure_summary]
            ),
            keywords,
        )
        for element in normalized.elements:
            element_score = _score(" ".join([element.name, element.text, element.context_hint]), keywords)
            if page_score <= 0 and element_score <= 0:
                element.action_type = ""
        normalized.elements.sort(
            key=lambda item: _score(" ".join([item.name, item.text, item.context_hint]), keywords), reverse=True
        )
        if page_score <= 0:
            normalized.elements = normalized.elements[:10]
        else:
            normalized.elements = normalized.elements[:MAX_ELEMENTS_PER_FULL_PAGE]
        pages.append(normalized)

    pages.sort(
        key=lambda page: _score(
            " ".join([page.title, page.display_name, page.entry_path, page.structure_summary]), keywords
        ),
        reverse=True,
    )
    for index, page in enumerate(pages):
        if index >= MAX_FULL_PAGES:
            page.elements = page.elements[:10]
    operations: list[ExplorationOperationContext] = []
    try:
        operations = _read_operations(project_id)
    except Exception:
        warnings.append("项目操作探索产物无法解析，已跳过。")
    operations.sort(
        key=lambda operation: _score(
            " ".join(
                [operation.operation_key, operation.page_path]
                + [step.action + step.element_name for step in operation.steps]
            ),
            keywords,
        ),
        reverse=True,
    )
    operations = operations[:MAX_OPERATIONS]
    for index, operation in enumerate(operations):
        if index >= MAX_FULL_OPERATIONS:
            operation.steps = operation.steps[:3]

    context = ExplorationContext(
        pages=pages,
        operations=operations,
        source_count=len(pages) + len(operations),
        warnings=warnings,
    )
    serialized_size = len(context.model_dump_json())
    if serialized_size > MAX_CONTEXT_CHARS:
        context.truncated = True
        for page in context.pages[MAX_FULL_PAGES:]:
            page.elements = page.elements[:3]
        for operation in context.operations[MAX_FULL_OPERATIONS:]:
            operation.steps = operation.steps[:1]
    return context
