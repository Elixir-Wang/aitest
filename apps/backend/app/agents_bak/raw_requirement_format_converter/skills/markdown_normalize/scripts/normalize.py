from agents import function_tool

from app.services.requirement_markdown_normalizer import normalize_requirement_markdown


@function_tool
def normalize_requirement_markdown_tool(markdown: str) -> str:
    """规范化需求 Markdown，修复业务流程误包代码块和箭头链路一行化问题。"""
    return normalize_requirement_markdown(markdown)
