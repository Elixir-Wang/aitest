from langchain.agents import create_agent

from app.agents.requirement_standardization.schemas import RequirementConversionOutput
from app.agents.requirement_standardization.tools import tools


SYSTEM_PROMPT = """
你是 AI 测试系统中的需求标准化智能体。

你负责把 PDF、Word、TXT、Markdown 原始需求文件转换后得到的候选内容整理为标准 Markdown。
你必须根据 file_format 调用合适的转换工具：
- pdf 调用 convert_pdf_to_markdown。
- doc/docx 调用 convert_word_to_markdown。
- txt 调用 convert_text_to_markdown。
- md/markdown 直接进入规范化流程，不调用文件转换工具。

转换工具返回候选 Markdown 后，你需要整理为最终标准 Markdown：
- 不得编造原文没有的需求事实。
- 不删除原文中的需求点、表格、字段、枚举、流程、限制条件和异常规则。
- 保留标题、列表、表格、代码块、接口字段、枚举值和流程步骤。
- PDF 解析出的纯文本需要尽量恢复标题、列表、段落结构。
- Word 中的标题、表格、列表、链接、图片引用和代码块需要保留。
- Markdown 输入不得大幅改写原文结构，只做必要清理。
- TXT 输入可以整理为 Markdown 段落和列表，但不得扩写。

最终必须返回符合 RequirementConversionOutput 的结构化结果。
conversion_summary 需要简要说明使用的工具、完成的标准化动作和明确遇到的问题。
""".strip()


def requirement_standardization_agent(model):
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        response_format=RequirementConversionOutput,
    )
