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
    ignored = {
        "__pycache__",
        "api_automation",
        "performance_testing",
        "requirement_analysis",
        "shared",
        "site_exploration",
        "skills",
    }
    missing: list[str] = []
    for package in sorted(path for path in agent_root.iterdir() if path.is_dir()):
        if package.name.startswith("_") or package.name in ignored:
            continue
        if not (package / "agent.py").exists():
            missing.append(package.name)
    assert missing == []


def test_agent_packages_do_not_use_legacy_agent_filenames() -> None:
    legacy_files = sorted(BACKEND_APP.glob("agents/*/*_agent.py"))
    assert [str(path.relative_to(BACKEND_APP.parent)) for path in legacy_files] == [
        "app/agents/test_point_generation/obligation_agent.py"
    ]


def test_legacy_agent_service_facade_removed() -> None:
    assert not (BACKEND_APP / "services" / "agent_service.py").exists()
    assert not (BACKEND_APP / "schemas" / "agent.py").exists()

    agents_api = (BACKEND_APP / "api" / "v1" / "agents.py").read_text(encoding="utf-8")
    assert "agent_service" not in agents_api
    assert '@router.post("/{agent_id}/run"' not in agents_api


def test_api_automation_uses_explicit_child_capabilities() -> None:
    package = BACKEND_APP / "agents" / "api_automation"

    assert not (package / "agent.py").exists()
    assert not (package / "schemas.py").exists()
    assert not (package / "service.py").exists()
    assert (package / "case_generation" / "agent.py").exists()
    assert (package / "case_generation" / "schemas.py").exists()
    assert (package / "case_generation" / "service.py").exists()

    pytest_package = package / "pytest_requests"
    assert (pytest_package / "skill.py").exists()
    assert (pytest_package / "agent.py").exists()
    assert not (pytest_package / "generator.py").exists()
    assert not (pytest_package / "schemas.py").exists()
    assert not (pytest_package / "service.py").exists()

    pytest_source = "\n".join(
        path.read_text(encoding="utf-8") for path in _python_files(pytest_package)
    )
    assert "PROJECT_FILE_STORAGE_ROOT" not in pytest_source
    assert "api_automation_repo" not in pytest_source


def test_performance_testing_uses_explicit_child_capabilities() -> None:
    package = BACKEND_APP / "agents" / "performance_testing"

    assert not (package / "agent.py").exists()
    assert not (package / "schemas.py").exists()
    assert not (package / "service.py").exists()

    child_package = package / "script_generation"
    assert (child_package / "agent.py").exists()
    assert (child_package / "schemas.py").exists()
    assert (child_package / "service.py").exists()

    script_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in _python_files(package / "script_generation")
    )
    assert "from app.services.performance_testing" not in script_source
