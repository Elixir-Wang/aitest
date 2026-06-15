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


class GlobalKnowledgeBaseCreateIn(BaseModel):
    name: str
    description: str = ""


class GlobalKnowledgeBaseUpdateIn(BaseModel):
    name: str
    description: str = ""


class GlobalKnowledgeFolderCreateIn(BaseModel):
    parent_id: str
    name: str
