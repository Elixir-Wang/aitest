import hashlib
import re
from pathlib import Path

from app.schemas.requirement_merge import RequirementMergeSourceFile, RequirementSourceFragment


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def build_source_fragments(source_files: list[RequirementMergeSourceFile]) -> list[RequirementSourceFragment]:
    fragments: list[RequirementSourceFragment] = []
    for source_file in source_files:
        fragments.extend(split_source_file(source_file))
    return fragments


def split_source_file(source_file: RequirementMergeSourceFile) -> list[RequirementSourceFragment]:
    blocks = _markdown_blocks(source_file.markdown_content)
    heading_path: list[str] = []
    fragments: list[RequirementSourceFragment] = []
    sequence = 1
    for block in blocks:
        heading = _heading_match(block)
        if heading:
            level, title = heading
            heading_path = heading_path[: level - 1]
            heading_path.append(title)
            continue
        normalized = block.strip()
        if not normalized or _is_ignorable_block(normalized):
            continue
        fragments.append(
            RequirementSourceFragment(
                fragment_id=_fragment_id(source_file.mapping_id, sequence),
                mapping_id=source_file.mapping_id,
                source_filename=source_file.original_filename,
                heading_path=heading_path.copy(),
                fragment_type=_classify_fragment(normalized, heading_path),
                content_hash=_content_hash(normalized),
                text=_plain_text(normalized),
                markdown_block=normalized,
            )
        )
        sequence += 1
    return fragments


def _markdown_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    paragraph: list[str] = []
    table: list[str] = []
    fence: list[str] = []
    in_fence = False

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("\n".join(paragraph).strip())
            paragraph.clear()

    def flush_table() -> None:
        if table:
            blocks.append("\n".join(table).strip())
            table.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if in_fence:
            fence.append(line)
            if stripped.startswith("```"):
                blocks.append("\n".join(fence).strip())
                fence.clear()
                in_fence = False
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_table()
            fence = [line]
            in_fence = True
            continue

        if _is_table_line(stripped):
            flush_paragraph()
            table.append(line)
            continue
        flush_table()

        if not stripped:
            flush_paragraph()
            continue

        if HEADING_PATTERN.match(stripped):
            flush_paragraph()
            blocks.append(stripped)
            continue

        if _is_list_item(stripped):
            flush_paragraph()
            blocks.append(line.strip())
            continue

        paragraph.append(line)

    if in_fence and fence:
        blocks.append("\n".join(fence).strip())
    flush_table()
    flush_paragraph()
    return [block for block in blocks if block.strip()]


def _heading_match(block: str) -> tuple[int, str] | None:
    match = HEADING_PATTERN.match(block.strip())
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def _is_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^([-*+]|\d+[.)])\s+", line))


def _is_ignorable_block(block: str) -> bool:
    return bool(re.fullmatch(r"[-*_]{3,}", block.strip()))


def _fragment_id(mapping_id: str, sequence: int) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "", mapping_id.removeprefix("docmap-")) or "source"
    return f"frag-{normalized}-{sequence:05d}"


def _content_hash(markdown_block: str) -> str:
    digest = hashlib.sha256(markdown_block.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _plain_text(markdown_block: str) -> str:
    text = re.sub(r"```[a-zA-Z0-9_-]*\n?", "", markdown_block)
    text = text.replace("```", "")
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[#>*\-\d.)+\s]+", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", text).strip()


def _classify_fragment(markdown_block: str, heading_path: list[str]) -> str:
    lowered = f"{' '.join(heading_path)} {markdown_block}".lower()
    if markdown_block.startswith("```mermaid"):
        return "state_flow"
    if markdown_block.startswith("```"):
        return "interface"
    if markdown_block.startswith("|"):
        if any(token in lowered for token in ("字段", "接口", "错误码", "request", "response", "api")):
            return "interface"
        if "验收" in lowered:
            return "acceptance"
        return "requirement"
    if any(token in lowered for token in ("验收", "acceptance")):
        return "acceptance"
    if any(token in lowered for token in ("约束", "安全", "权限", "必须", "不得", "不能")):
        return "constraint"
    if any(token in lowered for token in ("附件", "图片", "链接")):
        return "attachment"
    if any(token in lowered for token in ("目录", "阅读", "说明")) and len(_plain_text(markdown_block)) < 80:
        return "non_requirement"
    if any(token in lowered for token in ("背景", "概述")):
        return "background"
    return "requirement"
