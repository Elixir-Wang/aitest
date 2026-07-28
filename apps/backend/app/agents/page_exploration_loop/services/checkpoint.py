from __future__ import annotations

import json
from pathlib import Path

from app.agents.page_exploration_loop.state.models import LoopExplorationState


def checkpoint_path(run_dir: Path) -> Path:
    return run_dir / "loop_state.json"


def save_checkpoint(run_dir: Path, state: LoopExplorationState) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    target = checkpoint_path(run_dir)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def load_checkpoint(run_dir: Path) -> LoopExplorationState | None:
    path = checkpoint_path(run_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return LoopExplorationState.from_dict(payload) if isinstance(payload, dict) else None

