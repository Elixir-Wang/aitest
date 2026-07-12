"""Atomic persistence for project-level replay operations."""

from pathlib import Path
from datetime import datetime, timezone

import yaml

from app.core.settings import PROJECT_FILE_STORAGE_ROOT
from app.services.page_exploration.locking import FileLock

from .models import OperationsArtifact, ReplayOperation
from .models import EnvironmentValidation


class OperationsStore:
    def __init__(self, storage_root: Path | None = None) -> None:
        self._storage_root = Path(storage_root or PROJECT_FILE_STORAGE_ROOT)

    def upsert(self, project_id: str, operation: ReplayOperation) -> OperationsArtifact:
        path = self.path_for(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(path, timeout_seconds=5):
            artifact = self.read(project_id)
            operations = [item for item in artifact.operations if item.key != operation.key]
            operations.append(operation)
            operations.sort(key=lambda item: item.key)
            updated = artifact.model_copy(update={"operations": operations})
            temp_path = path.with_suffix(".yaml.tmp")
            temp_path.write_text(
                yaml.safe_dump(updated.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            temp_path.replace(path)
            return updated

    def read(self, project_id: str) -> OperationsArtifact:
        path = self.path_for(project_id)
        if not path.exists():
            return OperationsArtifact()
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return OperationsArtifact.model_validate(payload)

    def record_validation(
        self,
        project_id: str,
        operation: ReplayOperation,
        *,
        environment_id: str,
        success: bool,
        error: str = "",
    ) -> ReplayOperation:
        validations = [item for item in operation.validations if item.environment_id != environment_id]
        validations.append(EnvironmentValidation(
            environment_id=environment_id,
            status="passed" if success else "failed",
            validated_at=datetime.now(timezone.utc).isoformat(),
            error=error,
        ))
        status = operation.status
        if success and status == "draft":
            status = "validated"
        elif not success and status in {"validated", "published"}:
            status = "degraded"
        updated = operation.model_copy(update={"validations": validations, "status": status})
        self.upsert(project_id, updated)
        return updated

    def path_for(self, project_id: str) -> Path:
        return self._storage_root / project_id / "page_exploration" / "operations.yaml"
