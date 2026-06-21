from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


GenerationScopeType = Literal["all", "specified"]


class TestCaseGenerationRequest(BaseModel):
    """测试用例生成请求"""
    requirement_doc_id: str = Field(min_length=1, description="需求文档ID")
    generation_scope: str = Field(default="", description="生成范围")
    include_company_knowledge: bool = Field(default=False, description="是否包含公司知识库")

    @field_validator("requirement_doc_id", "generation_scope", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TestCaseItem(BaseModel):
    """单个测试用例"""
    id: str
    module: str
    title: str
    priority: str
    type: str
    precondition: str
    steps: list[str]
    expected_result: str
    test_data: str
    notes: str


class TestCaseGenerationResponse(BaseModel):
    """测试用例生成响应"""
    summary: str
    total_count: int
    modules: list[dict[str, Any]]
    markdown: str


class TestCaseSetCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    requirement_doc_id: str = Field(min_length=1)
    exploration_run_id: str = ""
    include_company_knowledge: bool = True
    generation_scope_type: GenerationScopeType = "all"
    generation_scope_text: str = ""
    notes: str = ""

    @field_validator("name", "requirement_doc_id", "exploration_run_id", "generation_scope_text", "notes", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("generation_scope_text")
    @classmethod
    def _validate_scope_text(cls, value: str, info) -> str:
        if info.data.get("generation_scope_type") == "specified" and not value:
            raise ValueError("指定范围模式下必须填写生成范围。")
        return value


class TestCaseGenerationRunOut(BaseModel):
    id: str
    test_case_set_id: str
    task_id: str
    status: str
    input_snapshot: dict[str, Any]
    error_message: str
    created_at: str
    finished_at: str | None = None


class TestCaseSetOut(BaseModel):
    id: str
    project_id: str
    project_name: str = ""
    name: str
    requirement_doc_id: str
    requirement_doc_title: str = ""
    exploration_run_id: str = ""
    exploration_run_title: str = ""
    include_company_knowledge: bool
    generation_scope_type: GenerationScopeType
    generation_scope_text: str
    notes: str
    status: str
    status_label: str
    case_count: int
    created_by: str
    created_at: str
    updated_at: str
    generation_run: TestCaseGenerationRunOut | None = None
