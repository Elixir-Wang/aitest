from pathlib import Path

from app.services.page_exploration.report_writer import (
    _artifact_quality_warnings,
    _render_page_section,
    _write_exploration_report,
)


def _schema4_artifact() -> dict:
    return {
        "schema_version": "4.0",
        "page": {
            "id": "page-agentStore",
            "title": "Agent Store",
            "normalized_path": "/agentStore",
        },
        "states": [{"id": "state-root", "type": "root"}],
        "elements": [
            {"key": "button-search", "source": {"role": "button", "name": "搜索"}},
            {"key": "combobox-language", "source": {"role": "combobox", "name": "选择语言"}},
        ],
        "quality": {"status": "complete", "warnings": [], "issues": []},
    }


def test_schema4_page_section_uses_top_level_elements_and_normalized_path(tmp_path: Path) -> None:
    path = tmp_path / "page-agentStore.yaml"

    lines = _render_page_section((path, _schema4_artifact()), {}, {})
    rendered = "\n".join(lines)

    assert "| 路径 | `/agentStore` |" in rendered
    assert "| 元素 | 2 个 |" in rendered
    assert "搜索" in rendered
    assert "选择语言" in rendered


def test_schema4_quality_warning_accepts_top_level_elements(tmp_path: Path) -> None:
    path = tmp_path / "page-agentStore.yaml"

    warnings = _artifact_quality_warnings([(path, _schema4_artifact())])

    assert warnings == []


def test_report_with_page_artifact_does_not_claim_no_page_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    path = tmp_path / "page-agentStore.yaml"

    report_path = _write_exploration_report(
        run_dir=run_dir,
        run_id="run-1",
        start_url="https://example.test/agentStore",
        exploration_mode="loop",
        page_artifacts=[(path, _schema4_artifact())],
        db_path=tmp_path / "missing.db",
    )

    report = report_path.read_text(encoding="utf-8")
    assert "共采集 **1** 个页面" in report
    assert "本次探索未产生页面产物" not in report
