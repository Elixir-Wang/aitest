from pathlib import Path

from app.services.requirement_file_conversion import convert_requirement_file_to_markdown


def convert_word_file_to_markdown(input_path: str, *, assets_dir: str | None = None) -> tuple[str, str]:
    source_path = Path(input_path)
    return convert_requirement_file_to_markdown(
        source_path.name,
        source_path.read_bytes(),
        assets_dir=Path(assets_dir) if assets_dir else None,
    )
