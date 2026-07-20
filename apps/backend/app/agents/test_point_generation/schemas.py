from typing import Literal

from pydantic import BaseModel, Field, field_validator


TestPointCategory = Literal["功能", "异常", "边界", "权限", "数据", "状态", "性能", "安全", "兼容性"]
TestPointPriority = Literal["P0", "P1", "P2", "P3"]


class TestPointGenerationInput(BaseModel):
    requirement_name: str = Field(min_length=1)
    requirement_content: str = Field(min_length=1)
    requirement_version_id: str = Field(min_length=1)

    @field_validator("requirement_name", "requirement_content", "requirement_version_id", mode="before")
    @classmethod
    def strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class GeneratedTestPoint(BaseModel):
    point_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=240)
    module: str = Field(default="", max_length=120)
    category: TestPointCategory
    priority: TestPointPriority
    description: str = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    verification_points: list[str] = Field(min_length=1)
    source_refs: list[str] = Field(default_factory=list)
    notes: str = ""


class TestPointGenerationResult(BaseModel):
    summary: str = ""
    points: list[GeneratedTestPoint]


__all__ = ["GeneratedTestPoint", "TestPointGenerationInput", "TestPointGenerationResult", "TestPointCategory", "TestPointPriority"]
