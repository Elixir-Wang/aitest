from pathlib import Path


BACKEND_APP = Path(__file__).resolve().parents[1] / "app"


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_services_do_not_call_generic_agent_runtime() -> None:
    offenders: list[str] = []
    for path in _python_files(BACKEND_APP / "services"):
        text = path.read_text(encoding="utf-8")
        if "from app.agents.runtime import run_agent" in text:
            offenders.append(str(path.relative_to(BACKEND_APP.parent)))
    assert offenders == []


def test_api_does_not_call_generic_agent_runtime() -> None:
    offenders: list[str] = []
    for path in _python_files(BACKEND_APP / "api"):
        text = path.read_text(encoding="utf-8")
        if "from app.agents.runtime import run_agent" in text:
            offenders.append(str(path.relative_to(BACKEND_APP.parent)))
    assert offenders == []


def test_agent_packages_have_definition_entrypoint() -> None:
    agent_root = BACKEND_APP / "agents"
    ignored = {"__pycache__", "requirement_analysis", "site_exploration", "skills"}
    missing: list[str] = []
    for package in sorted(path for path in agent_root.iterdir() if path.is_dir()):
        if package.name.startswith("_") or package.name in ignored:
            continue
        if not (package / "agent.py").exists():
            missing.append(package.name)
    assert missing == []


def test_agent_packages_do_not_use_legacy_agent_filenames() -> None:
    legacy_files = sorted(BACKEND_APP.glob("agents/*/*_agent.py"))
    assert [str(path.relative_to(BACKEND_APP.parent)) for path in legacy_files] == []


def test_legacy_agent_service_facade_removed() -> None:
    assert not (BACKEND_APP / "services" / "agent_service.py").exists()
    assert not (BACKEND_APP / "schemas" / "agent.py").exists()

    agents_api = (BACKEND_APP / "api" / "v1" / "agents.py").read_text(encoding="utf-8")
    assert "agent_service" not in agents_api
    assert '@router.post("/{agent_id}/run"' not in agents_api
