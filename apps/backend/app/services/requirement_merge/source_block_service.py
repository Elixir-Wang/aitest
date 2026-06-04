import re

from app.schemas.requirement_merge import RequirementMergeSourceFile, RequirementSourceBlock


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def build_source_blocks(
    source_files: list[RequirementMergeSourceFile],
    *,
    max_chars: int = 10000,
) -> list[RequirementSourceBlock]:
    blocks: list[RequirementSourceBlock] = []
    for source_index, source_file in enumerate(source_files):
        source_code = _source_code(source_index)
        sections = _second_level_sections(source_file.markdown_content)
        sequence = 1
        for section in sections:
            markdown = "\n".join(section["body"]).strip()
            blocks.append(_source_block(source_file, source_code, sequence, {**section, "markdown": markdown}))
            sequence += 1
    return blocks


def _second_level_sections(markdown: str) -> list[dict]:
    lines = markdown.splitlines()
    current: dict | None = None
    sections: list[dict] = []
    title_stack: list[str] = []

    for line in lines:
        heading = _heading_match(line)
        if heading:
            level, title = heading
            if level == 1:
                title_stack = []
                continue
            title_stack = title_stack[: level - 2]
            title_stack.append(title)
            if level == 2:
                if current and current["body"]:
                    sections.append(current)
                current = {
                    "heading_level": level,
                    "original_heading": title,
                    "heading_path": title_stack.copy(),
                    "body": [line],
                }
                continue
        if current is not None:
            current["body"].append(line)

    if current and current["body"]:
        sections.append(current)
    if not sections:
        fallback = _fallback_document_section(markdown)
        if fallback:
            sections.append(fallback)
    return [section for section in sections if not _is_non_requirement("\n".join(section["body"]))]


def _fallback_document_section(markdown: str) -> dict | None:
    body = markdown.strip()
    if not body:
        return None
    title = "全文"
    for line in markdown.splitlines():
        heading = _heading_match(line)
        if heading:
            title = heading[1]
            break
    return {
        "heading_level": 1,
        "original_heading": title,
        "heading_path": [title],
        "body": body.splitlines(),
        "markdown": body,
    }


def _source_block(
    source_file: RequirementMergeSourceFile,
    source_code: str,
    sequence: int,
    unit: dict,
) -> RequirementSourceBlock:
    markdown = unit.get("markdown") or "\n".join(unit["body"]).strip()
    return RequirementSourceBlock(
        block_id=f"{source_code}-{sequence:02d}" if sequence < 100 else f"{source_code}-{sequence}",
        source_code=source_code,
        mapping_id=source_file.mapping_id,
        source_file=source_file.original_filename,
        original_heading=unit["original_heading"],
        heading_path=list(unit["heading_path"]),
        markdown=markdown,
        sub_headings=_sub_headings(markdown),
    )


def _heading_match(line: str) -> tuple[int, str] | None:
    match = HEADING_PATTERN.match(line.strip())
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def _source_code(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    code = ""
    value = index
    while True:
        code = alphabet[value % 26] + code
        value = value // 26 - 1
        if value < 0:
            return code


def _plain_text(markdown: str) -> str:
    text = re.sub(r"(?ms)^```.*?^```", "", markdown)
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^[>*\-\d.)+\s]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _sub_headings(markdown: str) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        heading = _heading_match(line)
        if heading and heading[0] >= 3:
            headings.append(heading[1])
    return headings


def _is_non_requirement(markdown: str) -> bool:
    plain = _plain_text(markdown)
    if not plain:
        return True
    return bool(re.fullmatch(r"[-*_]{3,}", plain))
