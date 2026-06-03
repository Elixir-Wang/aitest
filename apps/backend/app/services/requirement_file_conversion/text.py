from pathlib import Path

from app.services.requirement_file_conversion.common import decode_text


def normalize_text_markdown(filename: str, raw_bytes: bytes) -> str:
    text = decode_text(raw_bytes).strip()
    if filename.lower().endswith((".md", ".markdown")):
        return text + "\n"
    return text + "\n"


def convert_text_file_to_markdown(input_path: str) -> tuple[str, str]:
    source_path = Path(input_path)
    markdown = normalize_text_markdown(source_path.name, source_path.read_bytes())
    return markdown, "文本文件直接保存为 Markdown 转换稿。"
