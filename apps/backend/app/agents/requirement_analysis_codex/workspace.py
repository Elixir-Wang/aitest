import json
import shutil
from pathlib import Path

from app.agents.requirement_analysis_codex.schemas import RequirementAnalysisInput
from app.core.storage import project_requirement_dir


def prepare_workdir(input_data: RequirementAnalysisInput) -> Path:
    run_dir = input_data.run_id.strip() or "codex-latest"
    root = project_requirement_dir(input_data.project_id, input_data.document_id) / "analysis_runs" / run_dir / "codex-work"
    if root.exists():
        shutil.rmtree(root)
    (root / "input").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    return root


def write_inputs(workdir: Path, input_data: RequirementAnalysisInput, prompt: str) -> None:
    (workdir / "input" / "primary.md").write_text(input_data.primary_markdown_content, encoding="utf-8")
    (workdir / "input" / "metadata.json").write_text(
        json.dumps(input_data.model_dump(exclude={"primary_markdown_content"}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (workdir / "prompt.md").write_text(prompt, encoding="utf-8")
    copy_skill("requirement-analysis", workdir / "skills" / "requirement-analysis")


def copy_skill(skill_name: str, target: Path) -> None:
    source = Path(__file__).resolve().parent / "skills" / skill_name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
