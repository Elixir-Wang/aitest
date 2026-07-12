from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.login_form_analysis.schemas import LoginFormAnalysisOutput


SYSTEM_PROMPT = """
你是 Web 登录页分析助手。
根据页面截图和元素列表，识别登录表单关键控件。

要求：
1. 只输出结构化结果，不要输出解释、JSON 代码块或额外文本。
2. 所有 element_id 必须来自输入 elements 列表。
3. 找不到时对应字段返回空字符串；agreement_element_id 可以返回 null。
4. 不要猜测不存在的元素。
""".strip()


def login_form_analysis_agent(model):
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        response_format=ToolStrategy(LoginFormAnalysisOutput),
    )
