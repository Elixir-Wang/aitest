from pathlib import Path

from app.services.requirement_file_conversion.common import ConvertedRequirementFile, decode_text
from app.services.requirement_file_conversion.pdf import convert_pdf_bytes_to_markdown
from app.services.requirement_file_conversion.text import normalize_text_markdown
from app.services.requirement_file_conversion.word import convert_docx_bytes_to_markdown


def convert_requirement_file_to_markdown(
    filename: str,
    raw_bytes: bytes,
    *,
    assets_dir: Path | None = None,
) -> tuple[str, str]:
    lowered = filename.lower()
    if lowered.endswith((".md", ".markdown", ".txt")):
        return normalize_text_markdown(filename, raw_bytes), "文本文件直接保存为 Markdown 转换稿。"
    if lowered.endswith(".pdf"):
        converted = convert_pdf_bytes_to_markdown(filename, raw_bytes)
        return converted.markdown, converted.summary
    if lowered.endswith((".doc", ".docx")):
        converted = convert_docx_bytes_to_markdown(filename, raw_bytes, assets_dir=assets_dir)
        return converted.markdown, converted.summary
    preview = decode_text(raw_bytes)[:4000]
    markdown = f"暂不支持该文件类型的完整结构解析，已保存文本预览。\n\n```\n{preview}\n```\n"
    return markdown, "文件类型暂不支持完整解析，已生成文本预览。"


__all__ = ["ConvertedRequirementFile", "convert_requirement_file_to_markdown"]
