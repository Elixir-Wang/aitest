from app.agents.raw_requirement_converter.service import convert_requirement_file
from app.schemas.requirement_conversion import RequirementConversionInput, RequirementConversionOutput


async def convert_raw_requirement_format(input_data: RequirementConversionInput) -> RequirementConversionOutput:
    return await convert_requirement_file(input_data)
