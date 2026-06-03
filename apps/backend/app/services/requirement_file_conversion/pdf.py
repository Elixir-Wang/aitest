from collections import Counter
import re
from pathlib import Path

import fitz

from app.services.requirement_file_conversion.common import ConvertedRequirementFile, clean_inline_text


def convert_pdf_bytes_to_markdown(filename: str, raw_bytes: bytes) -> ConvertedRequirementFile:
    try:
        document = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:  # pragma: no cover - parser details vary by PyMuPDF version
        raise RuntimeError(f"无法转换 {filename}：PDF 文件无法解析。") from exc

    pages = []
    for page in document:
        pages.append(_extract_pdf_page_lines(page))

    repeated_noise = _detect_repeated_pdf_noise(pages)
    content_blocks = []
    for lines in pages:
        cleaned = [line for line in lines if line not in repeated_noise and not _is_page_number_line(line)]
        block = "\n".join(cleaned).strip()
        if block:
            content_blocks.append(block)

    if not content_blocks:
        raise RuntimeError(f"无法转换 {filename}：PDF 未提取到可用文本，可能是扫描件，当前不支持 OCR。")

    markdown = "\n\n".join(content_blocks) + "\n"
    return ConvertedRequirementFile(markdown=markdown, summary=f"已通过 PyMuPDF PDF 转换器提取文本，页数 {document.page_count}。")


def convert_pdf_file_to_markdown(input_path: str, *, assets_dir: str | None = None) -> tuple[str, str]:
    source_path = Path(input_path)
    converted = convert_pdf_bytes_to_markdown(source_path.name, source_path.read_bytes())
    return converted.markdown, converted.summary


def _extract_pdf_page_lines(page) -> list[str]:
    blocks = page.get_text("blocks") or []
    text_blocks = []
    for block in blocks:
        if len(block) < 5:
            continue
        x0, y0, _x1, _y1, text = block[:5]
        if not isinstance(text, str) or not text.strip():
            continue
        text_blocks.append((round(float(y0), 1), round(float(x0), 1), text))

    if text_blocks:
        ordered_text = "\n\n".join(text for _y, _x, text in sorted(text_blocks))
        return _clean_pdf_page_lines(ordered_text.splitlines())

    raw_text = page.get_text("text") or ""
    return _clean_pdf_page_lines(raw_text.splitlines())


def _clean_pdf_page_lines(lines: list[str]) -> list[str]:
    cleaned = []
    previous_blank = False
    for raw_line in lines:
        line = clean_inline_text(raw_line)
        if not line:
            previous_blank = True
            continue
        if previous_blank and cleaned and cleaned[-1] != "":
            cleaned.append("")
        cleaned.append(line)
        previous_blank = False
    while "" in cleaned[:1]:
        cleaned.pop(0)
    while "" in cleaned[-1:]:
        cleaned.pop()
    return cleaned


def _detect_repeated_pdf_noise(pages: list[list[str]]) -> set[str]:
    if len(pages) < 3:
        return set()
    candidates = []
    for lines in pages:
        meaningful = [line for line in lines if line and not _is_page_number_line(line)]
        candidates.extend(meaningful[:1])
        candidates.extend(meaningful[-1:])
    threshold = max(2, len(pages) // 2 + 1)
    return {line for line, count in Counter(candidates).items() if count >= threshold}


def _is_page_number_line(line: str) -> bool:
    normalized = line.strip()
    return bool(
        re.fullmatch(r"\d+", normalized)
        or re.fullmatch(r"-\s*\d+\s*-", normalized)
        or re.fullmatch(r"第\s*\d+\s*页", normalized)
        or re.fullmatch(r"page\s+\d+", normalized, flags=re.IGNORECASE)
        or re.fullmatch(r"\d+\s*/\s*\d+", normalized)
    )
