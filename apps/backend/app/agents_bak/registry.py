import importlib
from pathlib import Path

from app.agents.definitions import AgentDefinition


class AgentRegistry:
    def __init__(self, agents: list[AgentDefinition]) -> None:
        self._agents = {agent.id: agent for agent in agents}

    def list(self) -> list[AgentDefinition]:
        return list(self._agents.values())

    def get(self, agent_id: str) -> AgentDefinition:
        return self._agents[agent_id]


def discover_agent_definitions(agents_dir: Path | None = None) -> list[AgentDefinition]:
    root = agents_dir or Path(__file__).parent
    definitions: list[AgentDefinition] = []
    for package_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if not _is_agent_package(package_dir):
            continue
        agent_file = package_dir / "agent.py"
        if not agent_file.exists():
            continue
        module = importlib.import_module(f"app.agents.{package_dir.name}.{agent_file.stem}")
        definition = getattr(module, "agent_definition", None)
        if isinstance(definition, AgentDefinition):
            definitions.append(definition)
    return sorted(definitions, key=lambda item: (item.sort_order, item.id))


def _is_agent_package(path: Path) -> bool:
    return path.is_dir() and not path.name.startswith("_") and path.name != "skills" and (path / "__init__.py").exists()


agent_registry = AgentRegistry(discover_agent_definitions())
