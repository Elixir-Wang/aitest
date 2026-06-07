from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain.tools import tool

from app.schemas.requirement_analysis import RequirementAuxiliaryDocument


MAX_CHUNK_CHARS = 2400
MAX_EXCERPT_CHARS = 900
MAX_SEARCH_LIMIT = 8


@dataclass(frozen=True)
class AuxiliaryChunk:
    mapping_id: str
    filename: str
    section_hint: str
    content: str


def build_auxiliary_search_tool(auxiliary_documents: list[RequirementAuxiliaryDocument]):
    chunks = build_auxiliary_chunks(auxiliary_documents)

    @tool
    def search_auxiliary_documents(query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search auxiliary requirement documents and return cited evidence snippets."""
        return search_auxiliary_chunks(chunks, query=query, limit=limit)

    return search_auxiliary_documents


def build_auxiliary_chunks(auxiliary_documents: list[RequirementAuxiliaryDocument]) -> list[AuxiliaryChunk]:
    chunks: list[AuxiliaryChunk] = []
    for document in auxiliary_documents:
        content = document.markdown_content.strip()
        if not content:
            continue
        chunks.extend(
            AuxiliaryChunk(
                mapping_id=document.mapping_id,
                filename=document.filename,
                section_hint=section_hint,
                content=chunk_content,
            )
            for section_hint, chunk_content in _split_markdown(content)
        )
    return chunks


def search_auxiliary_chunks(chunks: list[AuxiliaryChunk], *, query: str, limit: int = 5) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    if not terms:
        return []

    safe_limit = max(1, min(int(limit or 5), MAX_SEARCH_LIMIT))
    ranked: list[tuple[float, AuxiliaryChunk]] = []
    for chunk in chunks:
        score = _score_chunk(chunk, terms)
        if score > 0:
            ranked.append((score, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "mapping_id": chunk.mapping_id,
            "filename": chunk.filename,
            "section_hint": chunk.section_hint,
            "excerpt": _best_excerpt(chunk.content, terms),
            "score": round(score, 4),
        }
        for score, chunk in ranked[:safe_limit]
    ]


def _split_markdown(markdown_content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []
    for line in markdown_content.splitlines():
        heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading_match and current_lines:
            sections.extend(_split_section(current_heading, "\n".join(current_lines).strip()))
            current_lines = []
        if heading_match:
            current_heading = heading_match.group(2).strip()
        current_lines.append(line)

    if current_lines:
        sections.extend(_split_section(current_heading, "\n".join(current_lines).strip()))
    return [(hint, content) for hint, content in sections if content]


def _split_section(section_hint: str, content: str) -> list[tuple[str, str]]:
    if len(content) <= MAX_CHUNK_CHARS:
        return [(section_hint, content)]

    chunks: list[tuple[str, str]] = []
    buffer: list[str] = []
    buffer_size = 0
    for paragraph in re.split(r"\n\s*\n", content):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        paragraph_size = len(paragraph)
        if buffer and buffer_size + paragraph_size + 2 > MAX_CHUNK_CHARS:
            chunks.append((section_hint, "\n\n".join(buffer)))
            buffer = []
            buffer_size = 0
        if paragraph_size > MAX_CHUNK_CHARS:
            chunks.extend((section_hint, part) for part in _split_long_text(paragraph, MAX_CHUNK_CHARS))
            continue
        buffer.append(paragraph)
        buffer_size += paragraph_size + 2

    if buffer:
        chunks.append((section_hint, "\n\n".join(buffer)))
    return chunks


def _split_long_text(text: str, max_chars: int) -> list[str]:
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _query_terms(query: str) -> list[str]:
    normalized = query.lower().strip()
    raw_terms = re.findall(r"[\u4e00-\u9fff]{2,}|[a-z0-9_./:-]+", normalized)
    terms: set[str] = set()
    for term in raw_terms:
        terms.add(term)
        if _is_cjk(term) and len(term) > 4:
            terms.update(term[index : index + 2] for index in range(0, len(term) - 1))
            terms.update(term[index : index + 3] for index in range(0, len(term) - 2))
    return sorted(terms, key=len, reverse=True)


def _is_cjk(value: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff]+", value))


def _score_chunk(chunk: AuxiliaryChunk, terms: list[str]) -> float:
    content = chunk.content.lower()
    heading = chunk.section_hint.lower()
    score = 0.0
    for term in terms:
        content_hits = content.count(term)
        if content_hits:
            score += content_hits * (2.0 if len(term) >= 4 else 1.0)
        if term in heading:
            score += 3.0
    return score


def _best_excerpt(content: str, terms: list[str]) -> str:
    lower_content = content.lower()
    positions = [lower_content.find(term) for term in terms if lower_content.find(term) >= 0]
    if not positions:
        return _trim_excerpt(content)
    center = min(positions)
    start = max(0, center - MAX_EXCERPT_CHARS // 3)
    end = min(len(content), start + MAX_EXCERPT_CHARS)
    if end - start < MAX_EXCERPT_CHARS:
        start = max(0, end - MAX_EXCERPT_CHARS)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{content[start:end].strip()}{suffix}"


def _trim_excerpt(content: str) -> str:
    trimmed = content.strip()
    if len(trimmed) <= MAX_EXCERPT_CHARS:
        return trimmed
    return f"{trimmed[:MAX_EXCERPT_CHARS].strip()}..."
