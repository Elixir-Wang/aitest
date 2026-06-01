import hashlib
import re

from app.schemas.requirement_merge import RequirementMergeSourceFile, SourceOutlineDocument, SourceOutlineNode


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_PATTERN = re.compile(r"(?ms)^```([A-Za-z0-9_-]*)\n.*?^```")
API_PATH_PATTERN = re.compile(r"\b(?:GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_./{}-]+)", re.IGNORECASE)


def build_source_outline(source_files: list[RequirementMergeSourceFile]) -> list[SourceOutlineDocument]:
    documents: list[SourceOutlineDocument] = []
    for source_index, source_file in enumerate(source_files):
        document_code = _source_code(source_index)
        flat_nodes = _outline_nodes_for_file(source_file, document_code)
        nodes = _nest_nodes(flat_nodes)
        _classify_nodes(nodes)
        documents.append(
            SourceOutlineDocument(
                document_code=document_code,
                mapping_id=source_file.mapping_id,
                source_file=source_file.original_filename,
                source_file_hash=_content_hash(source_file.markdown_content),
                nodes=nodes,
            )
        )
    return documents


def flatten_source_outline(documents: list[SourceOutlineDocument]) -> list[SourceOutlineNode]:
    nodes: list[SourceOutlineNode] = []

    def visit(node: SourceOutlineNode) -> None:
        nodes.append(node)
        for child in node.children:
            visit(child)

    for document in documents:
        for node in document.nodes:
            visit(node)
    return nodes


def _outline_nodes_for_file(source_file: RequirementMergeSourceFile, document_code: str) -> list[SourceOutlineNode]:
    units = _heading_units(source_file.markdown_content)
    if not units:
        fallback = _fallback_unit(source_file.markdown_content)
        units = [fallback] if fallback else []

    counters: list[int] = []
    nodes: list[SourceOutlineNode] = []
    for unit in units:
        level = unit["level"]
        counters = counters[:level]
        while len(counters) < level:
            counters.append(0)
        counters[level - 1] += 1
        for index in range(level, len(counters)):
            counters[index] = 0
        node_id = _node_id(document_code, [value for value in counters if value])
        markdown = unit["markdown"].strip()
        content_types = _content_types(markdown)
        own_body_markdown = _own_body_markdown(markdown, unit["title"])
        own_body_plain_text = _plain_text(own_body_markdown)
        nodes.append(
            SourceOutlineNode(
                node_id=node_id,
                document_code=document_code,
                mapping_id=source_file.mapping_id,
                source_file=source_file.original_filename,
                level=level,
                title=unit["title"],
                heading_path=unit["heading_path"],
                content_markdown=markdown,
                plain_text=_plain_text(markdown),
                own_body_markdown=own_body_markdown,
                own_body_plain_text=own_body_plain_text,
                sub_headings=_sub_headings(markdown, min_level=level + 1),
                content_types=content_types,
                anchors=_anchors(markdown),
                preserve_original=any(
                    item in content_types
                    for item in ("interface", "table", "code", "state_flow", "error_code")
                ),
                content_hash=_content_hash(markdown),
            )
        )
    return [node for node in nodes if node.plain_text or node.content_markdown]


def _heading_units(markdown: str) -> list[dict]:
    lines = markdown.splitlines()
    units: list[dict] = []
    current: dict | None = None
    title_stack: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
        heading = _heading_match(line) if not in_fence else None
        if heading:
            level, title = heading
            if level <= 3:
                if current and current["body"]:
                    current["markdown"] = "\n".join(current["body"]).strip()
                    units.append(current)
                title_stack = title_stack[: level - 1]
                title_stack.append(title)
                current = {
                    "level": level,
                    "title": title,
                    "heading_path": title_stack.copy(),
                    "body": [line],
                }
                continue
        if current is not None:
            current["body"].append(line)

    if current and current["body"]:
        current["markdown"] = "\n".join(current["body"]).strip()
        units.append(current)
    return [unit for unit in units if not _is_non_requirement(unit.get("markdown", ""))]


def _fallback_unit(markdown: str) -> dict | None:
    body = markdown.strip()
    if not body:
        return None
    return {
        "level": 2,
        "title": "全文",
        "heading_path": ["全文"],
        "body": body.splitlines(),
        "markdown": body,
    }


def _nest_nodes(flat_nodes: list[SourceOutlineNode]) -> list[SourceOutlineNode]:
    roots: list[SourceOutlineNode] = []
    stack: list[SourceOutlineNode] = []
    for node in flat_nodes:
        node.children = []
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


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


def _node_id(document_code: str, counters: list[int]) -> str:
    suffix = "-".join(f"{value:02d}" for value in counters)
    return f"{document_code}-{suffix}" if suffix else document_code


def _content_hash(content: str) -> str:
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _plain_text(markdown: str) -> str:
    text = re.sub(r"(?ms)^```.*?^```", "", markdown)
    text = re.sub(r"!\[[^\]]*]\([^)]+\)", "", text)
    text = re.sub(r"\[([^\]]+)]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^[>*\-\d.)+\s]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _sub_headings(markdown: str, *, min_level: int) -> list[str]:
    headings: list[str] = []
    for line in markdown.splitlines():
        heading = _heading_match(line)
        if heading and heading[0] >= min_level:
            headings.append(heading[1])
    return headings


def _content_types(markdown: str) -> list[str]:
    types: list[str] = []
    lowered = markdown.lower()
    if re.search(r"(?m)^\|.*\|$", markdown):
        types.append("table")
    fence_languages = [match.group(1).lower() for match in FENCE_PATTERN.finditer(markdown)]
    if "mermaid" in fence_languages:
        types.append("state_flow")
    if fence_languages:
        types.append("code")
    if API_PATH_PATTERN.search(markdown) or any(token in lowered for token in ("接口", "request", "response")):
        types.append("interface")
    if any(token in lowered for token in ("错误码", "error code", "状态码")):
        types.append("error_code")
    if any(token in lowered for token in ("验收", "acceptance")):
        types.append("acceptance")
    if any(token in lowered for token in ("安全", "鉴权", "权限", "token")):
        types.append("security")
    if any(token in lowered for token in ("背景", "目标", "概述")):
        types.append("background")
    return types or ["requirement"]


def _anchors(markdown: str) -> list[str]:
    anchors: list[str] = []
    for match in API_PATH_PATTERN.finditer(markdown):
        anchors.append(match.group(1))
    for match in re.finditer(r"`([A-Za-z_][A-Za-z0-9_]{2,})`", markdown):
        anchors.append(match.group(1))
    return list(dict.fromkeys(anchors))


def _is_non_requirement(markdown: str) -> bool:
    plain = _plain_text(markdown)
    if not plain:
        return True
    return bool(re.fullmatch(r"[-*_]{3,}", plain))


def _own_body_markdown(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    body_started = False
    body_lines: list[str] = []
    for line in lines:
        heading = _heading_match(line)
        if not body_started and heading and heading[1].strip() == title.strip():
            body_started = True
            continue
        if body_started:
            body_lines.append(line)
    return "\n".join(body_lines).strip()


def _node_role(level: int, children: list, own_body_plain_text: str) -> str:
    if level not in {2, 3}:
        return "structural"
    if children and not own_body_plain_text:
        return "structural"
    return "content"


def _classify_nodes(nodes: list[SourceOutlineNode]) -> None:
    for node in nodes:
        _classify_nodes(node.children)
        node.node_role = _node_role(node.level, node.children, node.own_body_plain_text)
        node.must_assign = node.node_role == "content"
