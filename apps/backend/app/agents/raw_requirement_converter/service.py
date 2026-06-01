from pathlib import Path

from app.agents.model_factory import build_agent_model
from app.agents.model_selection import resolve_model_selection
from app.agents.raw_requirement_converter.agent import raw_requirement_converter_agent
from app.agents.raw_requirement_converter.converters import convert_requirement_file_to_markdown
from app.agents.raw_requirement_converter.schemas import RequirementConversionInput, RequirementConversionOutput


async def convert_requirement_file(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    source_path = Path(input_data.source_file_path)
    if not source_path.exists():
        raise ValueError("原始需求文件不存在，无法转换。")

    selection = resolve_model_selection("raw_requirement_format_converter")
    model = build_agent_model(selection)
    agent = raw_requirement_converter_agent(model)
    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": _build_conversion_input(input_data),
                }
            ]
        }
    )
    output = result.get("structured_response")
    if output is None:
        raise ValueError("原始需求格式转换智能体未返回结构化结果。")
    if not output.markdown_content.strip():
        raise ValueError("原始需求格式转换智能体返回的 Markdown 为空。")
    return output


def _build_conversion_input(input_data: RequirementConversionInput) -> str:
    lines = [
        f"filename: {input_data.filename}",
        f"file_format: {input_data.file_format}",
        f"source_file_path: {input_data.source_file_path}",
    ]
    if input_data.assets_dir_path:
        lines.append(f"assets_dir_path: {input_data.assets_dir_path}")
    return "\n".join(lines)


def fallback_convert_requirement_file(input_data: RequirementConversionInput) -> tuple[str, str]:
    source_path = Path(input_data.source_file_path)
    return convert_requirement_file_to_markdown(
        input_data.filename,
        source_path.read_bytes(),
        assets_dir=Path(input_data.assets_dir_path) if input_data.assets_dir_path else None,
    )
