from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generic, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


@dataclass(frozen=True)
class SkillReference:
    name: str
    path: Path
    content: str


@dataclass(frozen=True)
class SkillDefinition:
    path: Path
    name: str
    description: str
    instructions: str
    references: tuple[SkillReference, ...]
    fingerprint: str

    @classmethod
    def load(cls, skill_path: Path) -> SkillDefinition:
        path = skill_path.resolve()
        skill_file = path / "SKILL.md"
        if not skill_file.exists():
            raise FileNotFoundError(f"SKILL.md not found at {skill_file}")

        raw_content = skill_file.read_text(encoding="utf-8")
        metadata, instructions = _parse_skill_content(raw_content)
        missing = [field for field in ("name", "description") if not metadata.get(field)]
        if missing:
            raise ValueError(f"SKILL.md missing required metadata: {', '.join(missing)}")

        references_dir = path / "references"
        reference_paths = sorted(references_dir.glob("*.md")) if references_dir.exists() else []
        references = tuple(
            SkillReference(
                name=reference_path.name,
                path=reference_path,
                content=reference_path.read_text(encoding="utf-8"),
            )
            for reference_path in reference_paths
        )
        return cls(
            path=path,
            name=metadata["name"],
            description=metadata["description"],
            instructions=instructions,
            references=references,
            fingerprint=_fingerprint(skill_file, reference_paths),
        )

    def select_references(self, names: list[str] | None = None) -> tuple[SkillReference, ...]:
        if names is None:
            return self.references
        selected = set(names)
        return tuple(reference for reference in self.references if reference.name in selected)


@dataclass(frozen=True)
class ExecutableSkill(Generic[InputT, OutputT]):
    definition: SkillDefinition
    runner: Callable[[InputT], OutputT]

    @classmethod
    def from_path(
        cls,
        skill_path: Path,
        *,
        runner: Callable[[InputT], OutputT],
    ) -> ExecutableSkill[InputT, OutputT]:
        return cls(definition=SkillDefinition.load(skill_path), runner=runner)

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def fingerprint(self) -> str:
        return self.definition.fingerprint

    def invoke(self, input_data: InputT) -> OutputT:
        return self.runner(input_data)


def _parse_skill_content(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---"):
        return {}, content.strip()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content.strip()
    metadata = {}
    for line in parts[1].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = _strip_quotes(value.strip())
    return metadata, parts[2].strip()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _fingerprint(skill_file: Path, reference_paths: list[Path]) -> str:
    digest = hashlib.sha256()
    root = skill_file.parent
    for path in [skill_file, *reference_paths]:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


__all__ = ["ExecutableSkill", "SkillDefinition", "SkillReference"]
