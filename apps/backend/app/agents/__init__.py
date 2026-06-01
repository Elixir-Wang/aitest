from pathlib import Path


_backup_agents_root = Path(__file__).resolve().parent.parent / "agents_bak"
if _backup_agents_root.exists():
    __path__.append(str(_backup_agents_root))
