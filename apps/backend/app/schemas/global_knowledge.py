from pydantic import BaseModel


class GlobalKnowledgeBaseCreateIn(BaseModel):
    name: str
    description: str = ""


class GlobalKnowledgeBaseUpdateIn(BaseModel):
    name: str
    description: str = ""


class GlobalKnowledgeFolderCreateIn(BaseModel):
    parent_id: str
    name: str
