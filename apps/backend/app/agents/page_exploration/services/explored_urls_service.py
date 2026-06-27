"""Service for managing explored_urls.yaml"""

from pathlib import Path
from datetime import datetime, UTC
from typing import Optional
import yaml

from app.agents.page_exploration.utils.url_normalizer import normalize_url


class ExploredUrlsService:
    """Manages explored URLs tracking at project level"""

    def __init__(self, project_id: str, base_dir: Optional[Path] = None):
        self.project_id = project_id
        self.base_dir = Path(base_dir) if base_dir else Path("data/projects")
        self.yaml_path = self.base_dir / project_id / "page_exploration" / "explored_urls.yaml"

    def check(self, normalized_path: str) -> dict:
        """Check if a normalized path has been explored"""
        if not self.yaml_path.exists():
            return {"explored": False}

        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for url_record in data.get("urls", []):
            if url_record["normalized_path"] == normalized_path:
                return {
                    "explored": True,
                    "page_id": url_record["page_id"],
                    "page_file": url_record["page_file"],
                    "last_explored_at": url_record["last_explored_at"],
                    "last_run_id": url_record["last_run_id"]
                }

        return {"explored": False}

    def update(self, normalized_path: str, page_id: str, run_id: str) -> None:
        """Update or add an explored URL record"""
        self.yaml_path.parent.mkdir(parents=True, exist_ok=True)

        if self.yaml_path.exists():
            with open(self.yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            data = {
                "version": "1.0",
                "project_id": self.project_id,
                "urls": []
            }

        timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

        # Find existing record or add new
        found = False
        for url_record in data["urls"]:
            if url_record["normalized_path"] == normalized_path:
                url_record["page_id"] = page_id
                url_record["page_file"] = f"pages/{page_id}.yaml"
                url_record["last_explored_at"] = timestamp
                url_record["last_run_id"] = run_id
                found = True
                break

        if not found:
            data["urls"].append({
                "normalized_path": normalized_path,
                "page_id": page_id,
                "page_file": f"pages/{page_id}.yaml",
                "last_explored_at": timestamp,
                "last_run_id": run_id
            })

        with open(self.yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
