from pydantic import BaseModel, ConfigDict, Field


class RequirementPlanImportIn(BaseModel):
    """从需求导入探索计划的输入"""

    model_config = ConfigDict(extra="forbid")

    requirement_doc_id: str = Field(description="需求文档ID")
    requirement_run_id: str = Field(description="需求分析运行ID")
