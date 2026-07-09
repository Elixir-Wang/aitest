from app.agents.shared.skill_middleware import SkillMiddleware


def test_skill_middleware_loads_skill_and_references(tmp_path):
    skill_dir = tmp_path / "skills" / "demo-skill"
    references_dir = skill_dir / "references"
    references_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\n---\n\n# Demo Skill\n\nUse the skill.",
        encoding="utf-8",
    )
    (references_dir / "b.md").write_text("second reference", encoding="utf-8")
    (references_dir / "a.md").write_text("first reference", encoding="utf-8")

    middleware = SkillMiddleware(skill_path=skill_dir)

    assert middleware.name == "SkillMiddleware"
    assert middleware._load_skill_md() == "# Demo Skill\n\nUse the skill."
    assert middleware._load_references() == (
        "## 📄 a\n\nfirst reference\n\n---\n\n## 📄 b\n\nsecond reference"
    )
