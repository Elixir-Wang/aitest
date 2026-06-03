from pydantic import BaseModel, Field


class RequirementConversionInput(BaseModel):
    filename: str = Field(min_length=1)
    markdown_content: str = Field(min_length=1)


class RequirementConversionOutput(BaseModel):
    markdown_content: str = Field(
        min_length=1,
        description="标准化后的完整 Markdown。必须保留原文需求事实、表格、字段、枚举、流程、限制条件和异常规则。",
    )
    conversion_summary: str = Field(
        min_length=1,
        description="简要说明完成的标准化动作，并明确说明遇到的问题、保留的不确定内容或无法修复的转换缺陷。",
    )
