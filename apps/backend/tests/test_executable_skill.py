from pathlib import Path

import pytest

import app.agents.shared as shared_package
from app.agents.shared.skill_runtime import ExecutableSkill, SkillDefinition


def _write_skill(root: Path, *, instructions: str = "Run deterministically.") -> Path:
    skill_dir = root / "demo-skill"
    references_dir = skill_dir / "references"
    references_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo-skill\n"
        "description: Demonstrates executable skills\n"
        "---\n\n"
        f"# Demo\n\n{instructions}",
        encoding="utf-8",
    )
    (references_dir / "b.md").write_text("second", encoding="utf-8")
    (references_dir / "a.md").write_text("first", encoding="utf-8")
    return skill_dir


def test_skill_definition_loads_metadata_body_and_sorted_references(tmp_path: Path) -> None:
    definition = SkillDefinition.load(_write_skill(tmp_path))

    assert definition.name == "demo-skill"
    assert definition.description == "Demonstrates executable skills"
    assert definition.instructions == "# Demo\n\nRun deterministically."
    assert [reference.name for reference in definition.references] == ["a.md", "b.md"]
    assert [reference.content for reference in definition.references] == ["first", "second"]


def test_skill_definition_fingerprint_changes_with_skill_content(tmp_path: Path) -> None:
    skill_dir = _write_skill(tmp_path)
    first = SkillDefinition.load(skill_dir).fingerprint

    (skill_dir / "references" / "a.md").write_text("changed", encoding="utf-8")
    second = SkillDefinition.load(skill_dir).fingerprint

    assert first != second


def test_skill_definition_rejects_missing_required_metadata(tmp_path: Path) -> None:
    skill_dir = tmp_path / "invalid-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Missing frontmatter", encoding="utf-8")

    with pytest.raises(ValueError, match="name.*description"):
        SkillDefinition.load(skill_dir)


def test_executable_skill_invokes_registered_runner(tmp_path: Path) -> None:
    skill = ExecutableSkill.from_path(
        _write_skill(tmp_path),
        runner=lambda value: value.upper(),
    )

    assert skill.name == "demo-skill"
    assert skill.invoke("input") == "INPUT"


def test_shared_package_does_not_eagerly_import_langchain_middleware() -> None:
    assert not hasattr(shared_package, "SkillMiddleware")
