from __future__ import annotations

import os
from pathlib import Path

from app.core.db import DATA_DIR

PROJECT_FILE_STORAGE_ROOT = Path(os.getenv("AI_TESTING_PROJECT_FILE_STORAGE_DIR", DATA_DIR / "projects")).resolve()


def project_requirement_dir(project_id: str, document_id: str) -> Path:
    return PROJECT_FILE_STORAGE_ROOT / project_id / "requirements" / document_id
