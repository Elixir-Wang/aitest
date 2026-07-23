from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import AssertionPlan, AutomationPlan, LocatorPlan, PageObjectPlan, StepPlan
from .suite import ensure_suite_root, resolve_suite_file


SUITE_FILES = {
    "AGENTS.md": """# Pytest Playwright Suite Instructions

- Keep one shared suite for the whole platform.
- Keep each business project's pages, tests, and data inside its backend-provided project namespace.
- Preserve files not selected by the current generation request.
- Only edit backend-provided artifact paths.
- Derived case data may be normalized, but secrets must remain environment references.
- Never invent locators; every locator requires exploration evidence.
- Run pytest collection after code changes and never execute real tests during generation.
""",
    "pyproject.toml": """[project]
name = "generated-pytest-playwright"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pytest>=9.0.1",
    "pytest-playwright>=0.7.0",
    "pyyaml>=6.0.2",
]
""",
    "pytest.ini": """[pytest]
testpaths = testcases
python_files = test_*.py
addopts = -q
""",
    "conftest.py": """from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    args = dict(browser_context_args)
    args["ignore_https_errors"] = True
    args["locale"] = os.getenv("UI_LOCALE", "zh-CN")
    storage_state = os.getenv("UI_STORAGE_STATE", "").strip()
    if storage_state:
        args["storage_state"] = storage_state
    return args


@pytest.fixture(autouse=True)
def configure_page(page):
    timeout = int(os.getenv("UI_TIMEOUT_MS", "30000"))
    page.set_default_timeout(timeout)
    page.set_default_navigation_timeout(timeout)
""",
    "config/__init__.py": "",
    "config/settings.py": """from __future__ import annotations

import os


BASE_URL = os.getenv("UI_BASE_URL", "").rstrip("/")
""",
    "pages/__init__.py": "",
    "pages/generated/__init__.py": "",
    "pages/base_page.py": """from __future__ import annotations

from playwright.sync_api import Page

from config.settings import BASE_URL


class BasePage:
    route = ""

    def __init__(self, page: Page):
        self.page = page

    def open(self) -> None:
        if not BASE_URL:
            raise RuntimeError("UI_BASE_URL 未配置。")
        self.page.goto(f"{BASE_URL}{self.route}")
""",
    "testcases/__init__.py": "",
    "testcases/conftest.py": "",
    "testcases/generated/__init__.py": "",
    "data/__init__.py": "",
    "data/projects/.gitkeep": "",
    "utils/__init__.py": "",
    "utils/data_loader.py": """from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_case_data(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return _resolve_environment_values(payload)


def _resolve_environment_values(value):
    if isinstance(value, dict):
        if value.get("source") == "environment" and value.get("key"):
            return os.getenv(str(value["key"]), value.get("default", ""))
        return {key: _resolve_environment_values(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_environment_values(item) for item in value]
    return value
""",
    "utils/waiters.py": """from __future__ import annotations

from playwright.sync_api import Locator


def wait_visible(locator: Locator, timeout: int | None = None) -> None:
    locator.wait_for(state="visible", timeout=timeout)
""",
    "utils/assertions.py": """from playwright.sync_api import expect

__all__ = ["expect"]
""",
    "utils/artifacts.py": """from __future__ import annotations

import json
import os
from pathlib import Path


def write_result(payload: dict) -> None:
    target = os.getenv("UI_RESULT_PATH", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
""",
    ".deepagents/skills/pytest-playwright-ui-generation/SKILL.md": """---
name: pytest-playwright-ui-generation
description: Generate one project-namespaced pytest Playwright case inside the platform-shared suite.
---

# Rules

- Inspect the existing suite before changing files.
- Use only backend-provided artifact paths.
- Derived data may be normalized; source test cases are never updated.
- Never invent locators or remove assertions to make validation pass.
- Use the deterministic render tool for POM and test source changes.
- Run collection only; real UI execution is a separate user action.
""",
}


def initialize_suite(suite_path: Path) -> list[Path]:
    root = ensure_suite_root(suite_path)
    changed: list[Path] = []
    for relative_path, content in SUITE_FILES.items():
        target = resolve_suite_file(root, relative_path)
        if target.exists():
            continue
        _write_atomic(target, content)
        changed.append(target)
    return changed


def render_automation_plan(suite_path: Path, plan: AutomationPlan) -> dict:
    root = ensure_suite_root(suite_path)
    page_files: list[Path] = []
    for page_plan in plan.page_objects:
        target = resolve_suite_file(root, page_plan.file_path)
        _ensure_package(target.parent)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        _write_atomic(target, _render_page(page_plan, existing))
        page_files.append(target)

    test_file = resolve_suite_file(root, plan.artifacts.test_file)
    plan_file = resolve_suite_file(root, plan.artifacts.plan_file)
    resolve_suite_file(root, plan.artifacts.data_file)
    _ensure_package(test_file.parent)
    _write_atomic(test_file, _render_test(plan))
    _write_atomic(plan_file, json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n")
    return {"page_files": page_files, "test_file": test_file, "plan_file": plan_file}


def _render_page(page_plan: PageObjectPlan, existing: str) -> str:
    element_blocks = _existing_element_blocks(existing)
    for element in page_plan.elements:
        element_blocks[element.key] = _render_element_block(element.key, element.locator)
    imports_and_class = (
        "from __future__ import annotations\n\n"
        "from pages.base_page import BasePage\n\n\n"
        f"class {page_plan.class_name}(BasePage):\n"
        f"    route = {json.dumps(page_plan.route, ensure_ascii=False)}\n"
    )
    blocks = "\n".join(element_blocks[key] for key in sorted(element_blocks))
    return f"{imports_and_class}\n{blocks}".rstrip() + "\n"


def _existing_element_blocks(source: str) -> dict[str, str]:
    pattern = re.compile(
        r"    # <ui-element (?P<key>[A-Za-z0-9_]+)>\n.*?    # </ui-element>\n?",
        re.DOTALL,
    )
    return {match.group("key"): match.group(0).rstrip() for match in pattern.finditer(source)}


def _render_element_block(key: str, locator: LocatorPlan) -> str:
    expression = _locator_expression(locator)
    evidence = ", ".join(locator.evidence_refs)
    return (
        f"    # <ui-element {key}>\n"
        "    @property\n"
        f"    def {key}(self):\n"
        f"        # evidence: {evidence}\n"
        f"        return {expression}\n"
        "    # </ui-element>"
    )


def _locator_expression(locator: LocatorPlan) -> str:
    name = locator.name or locator.value
    if locator.strategy == "role":
        return f"self.page.get_by_role({json.dumps(locator.role)}, name={json.dumps(name, ensure_ascii=False)})"
    method = {
        "label": "get_by_label",
        "placeholder": "get_by_placeholder",
        "test_id": "get_by_test_id",
        "text": "get_by_text",
    }.get(locator.strategy)
    if method:
        return f"self.page.{method}({json.dumps(name, ensure_ascii=False)})"
    if locator.strategy == "xpath":
        return f"self.page.locator({json.dumps('xpath=' + name, ensure_ascii=False)})"
    return f"self.page.locator({json.dumps(name, ensure_ascii=False)})"


def _render_test(plan: AutomationPlan) -> str:
    page_map = {page.page_key: page for page in plan.page_objects}
    imports = [
        "from pathlib import Path",
        "",
        "from playwright.sync_api import expect",
        "",
        "from utils.data_loader import load_case_data",
    ]
    for page in sorted(plan.page_objects, key=lambda item: item.file_path):
        module = page.file_path.removesuffix(".py").replace("/", ".")
        imports.append(f"from {module} import {page.class_name}")
    suite_parent_index = len(Path(plan.artifacts.test_file).parts) - 1
    body = [
        "",
        "",
        f"def test_{_python_identifier(plan.automation_case_id)}(page):",
        f"    case_data = load_case_data(Path(__file__).resolve().parents[{suite_parent_index}] / {json.dumps(plan.artifacts.data_file)})",
    ]
    for page in plan.page_objects:
        body.append(f"    {page.page_key}_page = {page.class_name}(page)")
    for step in plan.steps:
        body.extend(_render_step(step))
    for assertion in plan.assertions:
        body.extend(_render_assertion(assertion))
    if not plan.steps and not plan.assertions:
        body.append("    assert case_data is not None")
    return "\n".join([*imports, *body]) + "\n"


def _render_step(step: StepPlan) -> list[str]:
    page_var = f"{step.page_key}_page"
    if step.kind == "navigate":
        return [f"    {page_var}.open()"]
    target = f"{page_var}.{step.element_key}"
    value = f"case_data[{json.dumps(step.value_ref)}]" if step.value_ref else json.dumps(step.value, ensure_ascii=False)
    actions = {
        "click": f"{target}.click()",
        "fill": f"{target}.fill(str({value}))",
        "select_option": f"{target}.select_option(str({value}))",
        "check": f"{target}.check()",
        "uncheck": f"{target}.uncheck()",
        "press": f"{target}.press(str({value}))",
        "upload": f"{target}.set_input_files(str({value}))",
        "wait_visible": f"{target}.wait_for(state=\"visible\")",
    }
    return [f"    {actions[step.kind]}"]


def _render_assertion(assertion: AssertionPlan) -> list[str]:
    expected = (
        f"case_data[{json.dumps(assertion.expected_ref)}]"
        if assertion.expected_ref
        else json.dumps(assertion.expected, ensure_ascii=False)
    )
    if assertion.kind == "url":
        return [f"    expect(page).to_have_url(str({expected}))"]
    target = f"{assertion.page_key}_page.{assertion.element_key}"
    statement = {
        "visible": f"expect({target}).to_be_visible()",
        "hidden": f"expect({target}).to_be_hidden()",
        "text": f"expect({target}).to_have_text(str({expected}))",
        "value": f"expect({target}).to_have_value(str({expected}))",
    }[assertion.kind]
    return [f"    {statement}"]


def _python_identifier(value: str) -> str:
    identifier = re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower()
    if not identifier:
        return "generated_case"
    if identifier[0].isdigit():
        return f"case_{identifier}"
    return identifier


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def _ensure_package(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    init_file = directory / "__init__.py"
    if not init_file.exists():
        _write_atomic(init_file, "")


__all__ = ["initialize_suite", "render_automation_plan"]
