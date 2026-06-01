from pydantic import BaseModel


class RequirementConversionInput(BaseModel):
    filename: str
    file_format: str
    source_file_path: str
    assets_dir_path: str | None = None


class RequirementConversionOutput(BaseModel):
    markdown_content: str
    conversion_summary: str = ""
