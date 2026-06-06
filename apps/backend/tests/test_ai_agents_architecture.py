from pathlib import Path


BACKEND_APP = Path(__file__).resolve().parents[1] / "app"
OLD_AI_AGENTS_ROOT = BACKEND_APP / "ai_agents"
OLD_LLM_TASKS_ROOT = BACKEND_APP / "llm_tasks"
LEGACY_AGENTS_ROOT = BACKEND_APP / "agents_bak"
NEW_AGENTS_ROOT = BACKEND_APP / "agents"


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_old_ai_agents_root_removed() -> None:
    assert not OLD_AI_AGENTS_ROOT.exists()


def test_old_llm_tasks_root_removed() -> None:
    assert not OLD_LLM_TASKS_ROOT.exists()


def test_new_agents_do_not_use_old_prompt_or_runner_modules() -> None:
    forbidden = [
        *NEW_AGENTS_ROOT.glob("**/prompts.py"),
        *NEW_AGENTS_ROOT.glob("**/runner.py"),
        *NEW_AGENTS_ROOT.glob("**/*_agent.py"),
    ]
    assert [str(path.relative_to(BACKEND_APP.parent)) for path in sorted(forbidden)] == []


def test_business_agent_packages_have_agent_entrypoint() -> None:
    missing: list[str] = []
    for package in sorted(path for path in NEW_AGENTS_ROOT.iterdir() if path.is_dir()):
        if package.name.startswith("_") or package.name == "shared":
            continue
        has_agent_entrypoint = (package / "agent.py").exists()
        if not has_agent_entrypoint:
            missing.append(package.name)
    assert missing == []


def test_document_editor_is_not_a_legacy_agent_package() -> None:
    assert not (LEGACY_AGENTS_ROOT / "document_editor").exists()


def test_document_editor_exists_in_new_agents_directory() -> None:
    assert (NEW_AGENTS_ROOT / "document_editor" / "agent.py").exists()


def test_raw_requirement_converter_legacy_package_removed() -> None:
    assert not (NEW_AGENTS_ROOT / "raw_requirement_converter").exists()
    assert not (LEGACY_AGENTS_ROOT / "raw_requirement_format_converter").exists()


def test_requirement_standardization_agent_exists_as_canonical_package() -> None:
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "agent.py").exists()
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "service.py").exists()
    assert (NEW_AGENTS_ROOT / "requirement_standardization" / "schemas.py").exists()
    assert not (NEW_AGENTS_ROOT / "requirement_standardization" / "tools.py").exists()


def test_site_exploration_agent_exists_as_langchain_package() -> None:
    package = NEW_AGENTS_ROOT / "site_exploration"
    assert (package / "agent.py").exists()
    assert (package / "service.py").exists()
    assert (package / "schemas.py").exists()
    assert (package / "tools.py").exists()
    assert (package / "__init__.py").exists()


def test_deterministic_requirement_file_conversion_lives_outside_agent_package() -> None:
    conversion_root = BACKEND_APP / "services" / "requirement_file_conversion"
    for filename in ("__init__.py", "common.py", "dispatcher.py", "pdf.py", "word.py", "text.py"):
        assert (conversion_root / filename).exists()
    assert not (BACKEND_APP / "services" / "requirement_file_converter.py").exists()
    assert not (NEW_AGENTS_ROOT / "requirement_standardization" / "converters").exists()


def test_raw_requirement_format_converter_capability_is_displayed_as_requirement_standardization() -> None:
    from app.agents.capabilities import get_ai_capability

    capability = get_ai_capability("raw_requirement_format_converter")

    assert capability.name == "需求标准化智能体"
    assert "标准 Markdown" in capability.description
    assert "解析为 Markdown 工作稿" not in capability.description


def test_document_editor_no_longer_uses_llm_task_module() -> None:
    assert not (OLD_LLM_TASKS_ROOT / "document_editor.py").exists()


def test_raw_requirement_converter_legacy_service_removed() -> None:
    service_path = BACKEND_APP / "services" / "raw_requirement_format_converter_service.py"
    assert not service_path.exists()


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


def test_v1_api_package_imports_after_agents_rebuild() -> None:
    from app.api.v1 import v1_router

    assert v1_router.routes
