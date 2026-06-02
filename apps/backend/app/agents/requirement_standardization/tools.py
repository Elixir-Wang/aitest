from langchain_core.tools import tool

from app.services.requirement_file_conversion.pdf import convert_pdf_file_to_markdown
from app.services.requirement_file_conversion.text import convert_text_file_to_markdown
from app.services.requirement_file_conversion.word import convert_word_file_to_markdown
from app.services.requirement_markdown_normalizer import normalize_requirement_markdown


@tool
def convert_pdf_to_markdown(input_path: str, assets_dir_path: str | None = None) -> dict:
    """Convert a local PDF requirement file into candidate Markdown."""
    markdown, summary = convert_pdf_file_to_markdown(input_path, assets_dir=assets_dir_path)
    return {"markdown": markdown, "summary": summary}


@tool
def convert_word_to_markdown(input_path: str, assets_dir_path: str | None = None) -> dict:
    """Convert a local Word requirement file into candidate Markdown."""
    markdown, summary = convert_word_file_to_markdown(input_path, assets_dir=assets_dir_path)
    return {"markdown": markdown, "summary": summary}


@tool
def convert_text_to_markdown(input_path: str) -> dict:
    """Convert a local TXT or Markdown requirement file into candidate Markdown."""
    markdown, summary = convert_text_file_to_markdown(input_path)
    return {"markdown": markdown, "summary": summary}


@tool
def normalize_markdown_content(markdown: str) -> str:
    """Normalize candidate requirement Markdown without changing business meaning."""
    return normalize_requirement_markdown(markdown)


tools = [
    convert_pdf_to_markdown,
    convert_word_to_markdown,
    convert_text_to_markdown,
    normalize_markdown_content,
]


__all__ = [
    "convert_pdf_to_markdown",
    "convert_word_to_markdown",
    "convert_text_to_markdown",
    "normalize_markdown_content",
    "tools",
]
