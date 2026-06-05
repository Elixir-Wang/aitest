from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_merge.schemas import RequirementMergeOutlineOutput, RequirementMergeSectionOutput


OUTLINE_SYSTEM_PROMPT = """
你是需求文档二级大纲归并智能体。

输入是一组来源文档。每个来源文档包含文档名称和若干来源块：
- 来源块 id 是唯一编号，例如 A-01、B-03。
- 来源块 title 是原文二级标题。
- 来源块 children 是该二级标题下的三级及更深标题，只帮助你判断内容范围。

你的工作：
1. 参考 requirement_name、来源文档名称、来源块 title 和 children，归并出最终需求文档的二级模块。
2. 把所有来源块分配到新二级模块，形成 placements。
3. 相似、重叠或互补的来源块可以分到同一个模块。

归并原则：
- 按业务能力、规则和对象组织二级模块。
- 大纲顺序应先建立上下文，再进入方案设计、业务流程、接口数据、安全约束和验收交付，让读者能从背景逐步理解到实现细节。
- 常见顺序可参考：背景/目标/范围/边界 -> 用户/角色/业务对象/接入模式 -> 总体架构/核心能力/模块职责 -> 核心业务流程/状态流转/交互链路 -> 功能需求/接口/数据模型/权限/安全/异常处理 -> 非功能要求/兼容性/约束 -> 联调/验收/交付/运营要求。
- 不要机械生成上述所有模块；只有来源块中确实有依据的内容才生成对应模块。
- 如果某类内容是当前需求的主业务核心，可以适当前置，但仍要保持从上下文到细节的阅读顺序。
- 不要按来源文档分组生成目录。
- 不要直接把来源文档名、文件名或上传过程词汇作为模块标题。
- 只生成二级模块，不生成三级标题，不输出正文。

输出要求：
- outline_summary：简要说明归并结果和主要依据。
- outline：新二级模块列表。
- placements：每个来源块 id 必须且只能出现一次；source_id 只能填来源块 id，不能填 children 文本；target_id 必须来自 outline[].id。
""".strip()


SECTION_SYSTEM_PROMPT = """
你是需求文档模块正文归并智能体。请把多个来源需求块整理成可直接放进正式需求文档的正文。

整理要求：
- 需要延续当前二级标题的编号层级组织三级标题；例如当前二级标题是 `2.`，三级标题应使用 `2.1`、`2.2` 这类编号。
- 根据来源内容组织合适的三级标题，不必照搬原文标题；每个标题下都要写完整需求内容，不要只做摘要。
- 章节内必须按读者理解顺序拆分连续三级小节：先说明背景、现状、问题或建设必要性，再说明建设目标、建设范围、职责边界、非建设范围，最后进入流程、接口、数据、安全、验收等细节；不要把首期能力、非建设范围、产品职责、接口细节混在“项目背景”小节里。
- 接口、字段、状态、权限、约束、异常、验收点、示例等信息都要保留。
- 多个来源里重复的内容要合并；互补的细节要补全，不能随便丢掉。
- Markdown 表格、Mermaid、JSON、SQL、HTTP、curl、代码块、字段表、错误码表、状态流转表等内容，如果来源里有且对需求有用，要尽量原样保留。
- 正文里不要出现来源文件名、mapping_id、原始文件、标准文件等处理过程信息。
- 背景说明、目录、附件提示、转换说明、纯解释性文字，只有能转成可测试需求时才写进正文。
- 阅读建议、附件链接、参考资料这类内容如果还需要保留，不要写进正文主流程，放到 appendix 处理。

冲突处理：
- 只有数字阈值不一致、权限规则互斥、启停方向相反、流程/状态不兼容，或同一行为同时出现“必须”和“不得”时，才算冲突。
- 只是写得更详细、说法不同、缺少验收标准、表达不够明确，不算冲突；这类需要人工确认时，标记为 pending_clarification。
- 没解决的冲突不要擅自选一方写进正文，要放到 conflicts。

输出：
按 RequirementMergeSectionOutput 返回结果；不要输出完整文档，只输出当前模块内容。正文里只能放最终需求文档内容，不要出现返回格式、字段名、半截 JSON、数组语法或你的思考过程。
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
