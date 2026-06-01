from pathlib import Path

from app.agents.raw_requirement_converter.converters import convert_requirement_file_to_markdown


def convert_markdown_file_to_markdown(input_path: str) -> tuple[str, str]:
    source_path = Path(input_path)
    return convert_requirement_file_to_markdown(source_path.name, source_path.read_bytes())
