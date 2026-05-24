from __future__ import annotations

import re


_CODE_FENCE_RE = re.compile(r"```[^\n]*\n(?P<body>.*?)\n```", re.DOTALL)
_FLOW_MARKER_RE = re.compile(r"\s*[↓→]\s*")


def normalize_requirement_markdown(markdown: str) -> str:
    normalized = _unwrap_business_flow_code_fences(markdown)
    normalized = _normalize_business_flow_lines(normalized)
    return normalized.strip() + "\n" if normalized.strip() else ""


def _unwrap_business_flow_code_fences(markdown: str) -> str:
    def replace(match: re.Match[str]) -> str:
        body = match.group("body").strip()
        if _looks_like_business_flow(body):
            return _flow_text_to_mermaid(body)
        return match.group(0)

    return _CODE_FENCE_RE.sub(replace, markdown)


def _normalize_business_flow_lines(markdown: str) -> str:
    blocks = re.split(r"(\n{2,})", markdown)
    normalized_blocks: list[str] = []
    for block in blocks:
        if block.startswith("\n"):
            normalized_blocks.append(block)
            continue
        stripped = block.strip()
        if _looks_like_business_flow(stripped) and not _is_markdown_table(stripped):
            normalized_blocks.append(_flow_text_to_mermaid(stripped))
        else:
            normalized_blocks.append(block)
    return "".join(normalized_blocks)


def _looks_like_business_flow(text: str) -> bool:
    if not text:
        return False
    if text.count("↓") + text.count("→") < 2:
        return False
    lowered = text.lower()
    code_signals = ("function ", "class ", "const ", "let ", "var ", "import ", "export ", "};")
    if any(signal in lowered for signal in code_signals):
        return False
    return any(keyword in text for keyword in ("用户", "官网", "产品", "认证", "调用", "返回", "进入", "跳转"))


def _flow_text_to_ordered_list(text: str) -> str:
    raw_parts = [part.strip() for part in _FLOW_MARKER_RE.split(_collapse_flow_whitespace(text)) if part.strip()]
    if len(raw_parts) < 2:
        return text
    return "\n".join(f"{index}. {part}" for index, part in enumerate(raw_parts, start=1))


def _flow_text_to_mermaid(text: str) -> str:
    steps = [part.strip() for part in _FLOW_MARKER_RE.split(_collapse_flow_whitespace(text)) if part.strip()]
    if len(steps) < 2:
        return text
    lines = ["```mermaid", "flowchart TD"]
    for index, step in enumerate(steps, start=1):
        node_id = f"S{index}"
        lines.append(f'  {node_id}["{_escape_mermaid_label(step)}"]')
    for index in range(1, len(steps)):
        lines.append(f"  S{index} --> S{index + 1}")
    lines.append("```")
    return "\n".join(lines)


def _escape_mermaid_label(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', "'")


def _collapse_flow_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines)


def _is_markdown_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return len(lines) >= 2 and all(line.startswith("|") and line.endswith("|") for line in lines[:2])
