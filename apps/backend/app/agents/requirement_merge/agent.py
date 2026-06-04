from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_merge.schemas import RequirementMergeOutlineOutput, RequirementMergeSectionOutput


OUTLINE_SYSTEM_PROMPT = """
你是需求文档二级大纲归并智能体。

你的任务：
1. 根据多个来源需求块的二级标题和块内子标题列表，生成新的初始需求二级大纲。
2. 给出每个来源块归属到哪个新二级模块。

输入说明：
- document_name：最终需求文档名称，只作为一级标题语境。
- source_blocks[].id：来源块 ID，placements.source_id 必须引用它。
- source_blocks[].title：来源块二级标题。
- source_blocks[].children：该来源块内部的三级及更深标题文本列表，只用于理解内容范围，不能被 placements.source_id 引用。

严格约束：
- 只生成二级模块，不生成三级标题。
- 不输出正文。
- 不创造输入中没有依据的业务模块。
- 每个 source_blocks[].id 必须且只能出现在 placements 中一次。
- placements[].target_id 必须来自 outline[].id。
- children 里的文本没有 ID，不能出现在 placements.source_id 中。
- 相似、重叠或互补的来源块可以归属到同一个新二级模块。
""".strip()


SECTION_SYSTEM_PROMPT = """
你是需求文档模块正文归并智能体。

你的任务：
基于当前二级模块下归属的来源块 Markdown，生成该模块内部的三级结构和正文。

严格约束：
- 只处理当前 module_id/module_title 对应的来源块。
- 可以基于真实正文自动生成三级标题。
- 不要求沿用来源块的三级标题。
- 重复内容要合并。
- 明显冲突、口径不清、缺少决策依据的内容进入 conflicts，不得写成确定结论。
- 每个输入 source_blocks[].id 必须出现在 coverage 中。
- 不要输出完整文档，只输出当前模块内容。
""".strip()


def requirement_merge_outline_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=OUTLINE_SYSTEM_PROMPT,
        response_format=ToolStrategy(RequirementMergeOutlineOutput),
    )


def requirement_merge_section_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SECTION_SYSTEM_PROMPT,
        response_format=ToolStrategy(RequirementMergeSectionOutput),
    )
