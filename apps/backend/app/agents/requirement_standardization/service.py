from pathlib import Path

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.agents.requirement_standardization.agent import requirement_standardization_agent
from app.agents.requirement_standardization.schemas import RequirementConversionInput, RequirementConversionOutput
from app.services.requirement_file_conversion import convert_requirement_file_to_markdown


CAPABILITY_ID = "raw_requirement_format_converter"


async def convert_requirement_file(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    source_path = Path(input_data.source_file_path)
    if not source_path.exists():
        raise ValueError("原始需求文件不存在，无法标准化。")

    selection = resolve_model_selection(CAPABILITY_ID)
    model = build_agent_model(selection)
    agent = requirement_standardization_agent(model)
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
        raise ValueError("需求标准化智能体未返回结构化结果。")
    if not output.markdown_content.strip():
        raise ValueError("需求标准化智能体返回的 Markdown 为空。")
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
