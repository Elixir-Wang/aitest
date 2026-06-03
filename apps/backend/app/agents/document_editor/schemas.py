from pydantic import BaseModel, Field


class DocumentEditInput(BaseModel):
    content: str = Field(min_length=1)
    instruction: str = Field(min_length=1)


class DocumentEditOutput(BaseModel):
    edited_content: str = Field(
        default="",
        description="修改后的完整 Markdown。只有实际修改文档时返回完整内容；未修改时必须返回空字符串。",
    )
    change_summary: str = Field(
        min_length=1,
        description="本次处理摘要。实际修改时说明改了什么；未修改、依据不足、指令歧义、无法定位或只完成部分修改时，也必须在这里说明。",
    )
