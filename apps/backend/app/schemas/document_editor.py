from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DocumentEditInput(BaseModel):
    document_type: str = Field(min_length=1, max_length=80)
    document_title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1)
    instruction: str = Field(min_length=1, max_length=4000)


class DocumentEditOutput(BaseModel):
    status: Literal["edited", "unchanged"]
    edited_content: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
