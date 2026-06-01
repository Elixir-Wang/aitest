import importlib.util
import inspect
import sys
from pathlib import Path

from agents import FunctionTool

from app.agents.definitions import SkillDefinition


def load_skill(skill_dir: Path) -> SkillDefinition:
    skill_dir = skill_dir.resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise FileNotFoundError(f"缺少 SKILL.md: {skill_dir}")

    metadata, instructions = _parse_skill_md(skill_md.read_text(encoding="utf-8"))
    skill_id = str(metadata.get("name") or skill_dir.name)
    return SkillDefinition(
        id=skill_id,
        name=str(metadata.get("display_name") or metadata.get("title") or skill_id),
        description=str(metadata.get("description") or ""),
        instructions=instructions,
        tools=tuple(_load_script_tools(skill_dir / "scripts", skill_id)),
        path=str(skill_dir),
        enabled=_metadata_bool(metadata.get("enabled", True)),
    )


def load_skills(skills_dir: Path) -> list[SkillDefinition]:
    if not skills_dir.exists():
        return []
    return [
        load_skill(skill_dir)
        for skill_dir in sorted(path for path in skills_dir.iterdir() if path.is_dir() and not path.name.startswith("_"))
        if (skill_dir / "SKILL.md").exists()
    ]


def _parse_skill_md(raw: str) -> tuple[dict[str, object], str]:
    if not raw.startswith("---"):
        return {}, raw.strip()

    lines = raw.splitlines()
    end_index = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), -1)
    if end_index == -1:
        return {}, raw.strip()

    metadata = _parse_simple_yaml(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :]).strip()
    return metadata, body


def _parse_simple_yaml(lines: list[str]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        metadata[key.strip()] = _parse_scalar(value.strip())
    return metadata


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _metadata_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in {"false", "0", "no", "off"}
    return bool(value)


def _load_script_tools(scripts_dir: Path, skill_id: str) -> list[FunctionTool]:
    if not scripts_dir.exists():
        return []

    tools: list[FunctionTool] = []
    for py_file in sorted(scripts_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"app.agents.loaded_skills.{skill_id}.{py_file.stem}"
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        for _name, obj in inspect.getmembers(module):
            if isinstance(obj, FunctionTool):
                tools.append(obj)
    return tools
