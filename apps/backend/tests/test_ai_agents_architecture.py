from __future__ import annotations

from pathlib import Path


BACKEND_APP = Path(__file__).resolve().parents[1] / "app"
AI_AGENTS_ROOT = BACKEND_APP / "ai_agents"


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_ai_agents_root_exists() -> None:
    assert AI_AGENTS_ROOT.exists()


def test_ai_agents_do_not_use_old_prompt_or_runner_modules() -> None:
    forbidden = [
        *AI_AGENTS_ROOT.glob("**/prompts.py"),
        *AI_AGENTS_ROOT.glob("**/runner.py"),
        *AI_AGENTS_ROOT.glob("**/*_agent.py"),
    ]
    assert [str(path.relative_to(BACKEND_APP.parent)) for path in sorted(forbidden)] == []


def test_business_agent_packages_have_sdk_entrypoint_and_workflow() -> None:
    missing: list[str] = []
    for package in sorted(path for path in AI_AGENTS_ROOT.iterdir() if path.is_dir()):
        if package.name.startswith("_") or package.name == "shared":
            continue
        has_agent_entrypoint = (package / "agent.py").exists() or (package / "agents.py").exists()
        has_workflow = (package / "workflow.py").exists()
        if not has_agent_entrypoint or not has_workflow:
            missing.append(package.name)
    assert missing == []


def test_services_do_not_call_openai_runner_directly() -> None:
    offenders: list[str] = []
    for path in _python_files(BACKEND_APP / "services"):
        text = path.read_text(encoding="utf-8")
        if "Runner.run" in text or "from agents import Runner" in text:
            offenders.append(str(path.relative_to(BACKEND_APP.parent)))
    assert offenders == []


def test_api_does_not_define_sdk_agents() -> None:
    offenders: list[str] = []
    for path in _python_files(BACKEND_APP / "api"):
        text = path.read_text(encoding="utf-8")
        if "from agents import Agent" in text or "Agent(" in text:
            offenders.append(str(path.relative_to(BACKEND_APP.parent)))
    assert offenders == []
