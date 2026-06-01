from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeSourceDocumentInput(BaseModel):
    document_id: str
    document_name: str
    version_id: str
    version_no: int
    markdown_content: str


class KnowledgeExplorationInput(BaseModel):
    exploration_run_id: str
    title: str
    status: str
    result_summary: str = ""
    modules: list[dict] = Field(default_factory=list)


class KnowledgeBuildInput(BaseModel):
    project_id: str
    project_name: str
    build_no: str
    source_documents: list[KnowledgeSourceDocumentInput] = Field(default_factory=list)
    explorations: list[KnowledgeExplorationInput] = Field(default_factory=list)


class KnowledgeSourceRef(BaseModel):
    source_type: Literal["requirement", "exploration", "manual"]
    source_id: str
    source_title: str
    location: str = ""
    excerpt: str = ""


class WikiPageOutput(BaseModel):
    page_id: str
    title: str
    relative_path: str
    page_type: Literal["index", "overview", "module", "map", "quality", "testing", "build", "log"]
    module_key: str = ""
    summary: str = ""
    markdown_content: str
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)


class KnowledgeItemOutput(BaseModel):
    module_key: str
    module_name: str
    knowledge_type: Literal["requirement_fact", "page_fact", "merged_fact", "test_focus"]
    content: str
    source_refs: list[KnowledgeSourceRef] = Field(default_factory=list)


class WikiLintIssueOutput(BaseModel):
    severity: Literal["info", "warning", "error"]
    title: str
    detail: str
    page_id: str = ""


class KnowledgeBuildOutput(BaseModel):
    status: Literal["blocked", "draft"]
    summary: str
    change_summary: str
    affected_modules: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    pages: list[WikiPageOutput] = Field(default_factory=list)
    knowledge_items: list[KnowledgeItemOutput] = Field(default_factory=list)
    lint_issues: list[WikiLintIssueOutput] = Field(default_factory=list)
