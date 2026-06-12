from app.agents.requirement_analysis_codex.runner import run_requirement_analysis_with_codex
from app.agents.requirement_analysis_codex.schemas import RequirementAnalysisInput, RequirementAnalysisOutput


CAPABILITY_ID = "requirement_analysis"


async def analyze_requirement(input_data: RequirementAnalysisInput) -> RequirementAnalysisOutput:
    output = await run_requirement_analysis_with_codex(input_data)
    primary_markdown = input_data.primary_markdown_content.strip()
    if not primary_markdown:
        raise ValueError("主需求标准文件为空，无法生成初步需求。")
    if not output.preliminary_requirement_markdown.strip():
        output.preliminary_requirement_markdown = primary_markdown
    return output
