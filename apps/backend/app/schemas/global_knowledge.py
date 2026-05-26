from __future__ import annotations

from pydantic import BaseModel


class GlobalKnowledgeUpdateIn(BaseModel):
    name: str
    knowledge_type: str
    scope: str = "全部项目"
    source_note: str = ""
    description: str = ""


class GlobalKnowledgeListQuery(BaseModel):
    keyword: str = ""
    knowledge_type: str = ""
    status: str = ""
    page: int = 1
    page_size: int = 20
