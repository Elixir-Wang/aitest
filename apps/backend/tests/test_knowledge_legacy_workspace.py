from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_knowledge_codex_workspace_is_not_referenced() -> None:
    assert not (BACKEND_ROOT / "app/services/knowledge/codex_query.py").exists()

    production_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (BACKEND_ROOT / "app").rglob("*.py")
    )

    assert "agentic-search" not in production_source
    assert "knowledge-query-input.json" not in production_source
    assert "output/query.json" not in production_source


def test_legacy_knowledge_codex_workspace_is_ignored() -> None:
    gitignore = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "apps/backend/data/projects/**/knowledge/agentic-search/" in gitignore
