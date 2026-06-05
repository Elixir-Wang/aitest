from typing import Literal

from pydantic import BaseModel, Field


class RequirementMergeSourceBlockIndex(BaseModel):
    id: str = Field(description="来源块 ID，后续 placements.source_id 必须引用该值。")
    title: str = Field(description="来源块二级标题，只用于理解业务范围。")
    children: list[str] = Field(default_factory=list, description="来源块内的三级及更深标题文本列表。")


class RequirementMergeSourceDocumentIndex(BaseModel):
    document_name: str = Field(description="来源文档名称，只作为理解上下文，不得直接作为输出模块标题。")
    source_blocks: list[RequirementMergeSourceBlockIndex] = Field(
        min_length=1,
        description="该来源文档下待归并的二级来源块索引。",
    )


class RequirementMergeOutlineInput(BaseModel):
    requirement_name: str = Field(description="最终需求名称，只作为最终一级标题语境。")
    source_documents: list[RequirementMergeSourceDocumentIndex] = Field(
        min_length=1,
        description="按来源文档分组的待归并二级块索引。",
    )


class RequirementMergeOutlineModule(BaseModel):
    id: str = Field(description="新二级模块 ID，必须稳定且可被 placements.target_id 引用。")
    title: str = Field(description="新二级模块标题，不得使用来源文件名或摄取过程信息。")
    reason: str = Field(default="", description="生成该模块的依据或归并思路。")


class RequirementMergePlacement(BaseModel):
    source_id: str = Field(description="来源块 ID，必须来自输入 source_documents[].source_blocks[].id。")
    target_id: str = Field(description="目标新二级模块 ID，必须来自输出 outline[].id。")
    reason: str = Field(default="", description="来源块归属到该目标模块的原因。")


class RequirementMergeOutlineOutput(BaseModel):
    outline_summary: str = Field(
        default="",
        description="本次二级大纲归并摘要，说明生成了哪些模块以及主要归并依据。",
    )
    outline: list[RequirementMergeOutlineModule] = Field(
        default_factory=list,
        description="归并后的新二级模块列表，只包含二级模块，不包含三级标题和正文。",
    )
    placements: list[RequirementMergePlacement] = Field(
        default_factory=list,
        description="来源块到新二级模块的归属关系；每个输入 source_documents[].source_blocks[].id 必须且只能出现一次。",
    )


class RequirementMergeSectionSourceBlock(BaseModel):
    id: str = Field(description="来源块 ID，后续 coverage.source_id 和 conflicts.source_ids 必须引用该值。")
    title: str = Field(description="来源块标题。")
    children: list[str] = Field(default_factory=list, description="来源块内的三级及更深标题文本列表。")
    markdown: str = Field(description="来源块完整 Markdown 正文。")


class RequirementMergeSectionInput(BaseModel):
    module_id: str = Field(description="当前要归并的目标二级模块 ID。")
    module_title: str = Field(description="当前要归并的目标二级模块标题。")
    source_blocks: list[RequirementMergeSectionSourceBlock] = Field(
        min_length=1,
        description="归属到当前模块的来源块列表。",
    )


class RequirementMergeSectionContent(BaseModel):
    section_heading: str = Field(description="生成的三级标题纯文本；不得包含二级模块标题或任何结构化返回字段名。")
    markdown_blocks: list[str] = Field(
        default_factory=list,
        description="该三级标题下可直接写入最终需求文档的 Markdown 正文块、表格或代码块。",
    )


class RequirementMergeSectionCoverage(BaseModel):
    source_id: str = Field(description="来源块 ID，必须来自输入 source_blocks[].id。")
    status: Literal["merged", "duplicate", "appendix", "conflict", "pending_clarification", "discarded"] = Field(
        default="merged",
        description="来源块处理结果：合并、重复去重、放入附录、冲突、待澄清或丢弃。",
    )
    reason: str = Field(default="", description="处理原因；非 merged 状态必须说明依据。")


class RequirementMergeSectionConflict(BaseModel):
    conflict_id: str = Field(default="", description="冲突 ID；可为空，后端会补齐。")
    title: str = Field(description="冲突或待确认项标题。")
    conflict_type: str = Field(default="contradiction", description="冲突类型，例如 contradiction。")
    severity: str = Field(default="medium", description="严重程度，例如 low、medium、high。")
    source_ids: list[str] = Field(default_factory=list, description="涉及的来源块 ID 列表。")
    fragment_a: str = Field(default="", description="冲突或差异的一方描述。")
    fragment_b: str = Field(default="", description="冲突或差异的另一方描述。")
    agent_suggestion: str = Field(default="", description="建议人工确认的问题或处理建议。")


class RequirementMergeSectionOutput(BaseModel):
    module_id: str = Field(description="当前模块 ID，必须等于输入 module_id。")
    title: str = Field(default="", description="当前模块标题，通常等于输入 module_title。")
    merge_summary: str = Field(
        default="",
        description="本模块归并摘要，说明合并了哪些内容、哪些来源被去重、哪些内容待确认或丢弃。",
    )
    sections: list[RequirementMergeSectionContent] = Field(
        default_factory=list,
        description="模块内生成的三级结构和最终正文，不包含二级标题。",
    )
    coverage: list[RequirementMergeSectionCoverage] = Field(
        default_factory=list,
        description="每个输入来源块的处理结果；每个 source_blocks[].id 必须出现一次。",
    )
    conflicts: list[RequirementMergeSectionConflict] = Field(
        default_factory=list,
        description="明显冲突或必须人工确认的问题；无冲突时返回空数组。",
    )
