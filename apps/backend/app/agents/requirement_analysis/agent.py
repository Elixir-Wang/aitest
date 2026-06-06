from pathlib import Path

from deepagents.backends import StateBackend
from deepagents.middleware import FilesystemMiddleware, SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.schemas.requirement_analysis import RequirementAnalysisOutput


SKILLS_DIR = Path(__file__).parent / "skills"


SYSTEM_PROMPT = """
你是 AI 测试系统中的主需求锚定需求分析智能体。

你必须使用可用 skills 中的 requirement-review 和 test-scenarios 完成分析：
- requirement-review 用于识别主需求的遗漏、歧义、冲突、不可测、规则缺失和验收标准缺失。
- test-scenarios 用于从测试执行视角反推角色、前置条件、操作步骤、预期结果、边界值和异常路径缺口。

输入边界：
- primary_markdown_content 是唯一分析对象和范围边界。
- auxiliary_documents 只是证据库，只能围绕主需求问题查证据。
- 没有主需求锚点的辅助文档内容不得补入初步需求。
- 辅助文档与主需求冲突时不得补入初步需求。
- 补入 preliminary_requirement_markdown 的每一段都必须包含来源文件和证据摘录。

输出边界：
- 不得生成归并需求。
- 不得把辅助文档全量合并。
- 找不到答案、证据弱、来源冲突或无主需求锚点的问题，必须进入 clarification_questions 或 conflicts。
- 输出必须符合 RequirementAnalysisOutput。
""".strip()


def requirement_analysis_agent(model):
    backend = StateBackend()
    return create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                system_prompt="只使用文件系统读取已加载的技能说明和本次分析上下文，不要写入持久文件。",
            ),
            SkillsMiddleware(
                backend=backend,
                sources=[str(SKILLS_DIR)],
            ),
            SummarizationMiddleware(model=model, backend=backend),
        ],
        response_format=ToolStrategy(RequirementAnalysisOutput),
    )
