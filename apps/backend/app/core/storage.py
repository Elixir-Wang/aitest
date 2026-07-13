from pathlib import Path, PureWindowsPath

from app.core.settings import PROJECT_FILE_STORAGE_ROOT


def project_requirement_dir(project_id: str, document_id: str) -> Path:
    return PROJECT_FILE_STORAGE_ROOT / project_id / "requirements" / document_id


def global_knowledge_base_dir(base_id: str) -> Path:
    return PROJECT_FILE_STORAGE_ROOT.parent / "global-knowledge" / "bases" / base_id


def global_knowledge_folder_dir(base_id: str, folder_id: str) -> Path:
    return global_knowledge_base_dir(base_id) / "folders" / folder_id


def resolve_stored_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)
    if path.exists():
        return path

    normalized = path_value.replace("\\", "/")
    marker = "/data/projects/"
    if marker in normalized:
        relative = normalized.split(marker, 1)[1]
        return PROJECT_FILE_STORAGE_ROOT / relative

    windows_path = PureWindowsPath(path_value)
    parts = windows_path.parts
    if "projects" in parts:
        projects_index = parts.index("projects")
        return PROJECT_FILE_STORAGE_ROOT.joinpath(*parts[projects_index + 1 :])

    if not path.is_absolute():
        return PROJECT_FILE_STORAGE_ROOT / path

    return path


def store_path(path: Path | str | None) -> str | None:
    if path is None:
        return None

    path_obj = Path(path)
    try:
        return path_obj.resolve().relative_to(PROJECT_FILE_STORAGE_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def expose_stored_path(path_value: str | None) -> str | None:
    path = resolve_stored_path(path_value)
    return str(path) if path is not None else None
