from __future__ import annotations

from pathlib import Path

from langchain_core.tools import StructuredTool

from app.services.api_automation.runner import collect_script_suite


def build_collection_tool(*, suite_path: Path, timeout: int = 120) -> StructuredTool:
    resolved_suite_path = suite_path.resolve()

    def run_pytest_collection(test_paths: list[str] | None = None) -> dict:
        return collect_script_suite(
            suite_path=resolved_suite_path,
            timeout=timeout,
            test_paths=test_paths,
        )

    return StructuredTool.from_function(
        func=run_pytest_collection,
        name="run_pytest_collection",
        description=(
            "Run pytest collection in the current project suite without sending real API requests. "
            "Pass relative test paths when validating selected files; omit them to validate the whole suite."
        ),
    )

