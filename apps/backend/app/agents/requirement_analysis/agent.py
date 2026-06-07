from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware import FilesystemMiddleware, FilesystemPermission, SkillsMiddleware, SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.agents.requirement_analysis.tools import build_auxiliary_search_tool
from app.schemas.requirement_analysis import RequirementAnalysisOutput, RequirementAuxiliaryDocument


SKILLS_DIR = Path(__file__).parent / "skills"
SKILLS_ROUTE = "/skills/"


SYSTEM_PROMPT = """
你是 AI 测试系统中的主需求锚定需求分析智能体。

你必须使用可用 skills 中的 requirement-review 和 test-scenarios 完成分析：
- requirement-review 用于识别主需求的遗漏、歧义、冲突、不可测、规则缺失和验收标准缺失。
- test-scenarios 用于从测试执行视角反推角色、前置条件、操作步骤、预期结果、边界值和异常路径缺口。

输入边界：
- primary_markdown_content 是唯一分析对象和范围边界。
- auxiliary_documents 只提供辅助文件清单，不包含全文。
- 辅助文件只是证据库，只能围绕主需求问题调用 search_auxiliary_documents 查证据。
- 需要补强、冲突判断或推荐选项时，必须先调用 search_auxiliary_documents；不能基于文件名或常识补写。
- 没有主需求锚点的辅助文档内容不得补入初步需求。
- 辅助文档与主需求冲突时不得补入初步需求。
- 补入 preliminary_requirement_markdown 的每一段都必须来自 search_auxiliary_documents 返回的 evidence，并包含来源文件和证据摘录。

输出边界：
- 不得生成归并需求。
- 不得把辅助文档全量合并。
- 找不到答案、证据弱、来源冲突或无主需求锚点的问题，必须进入 clarification_questions 或 conflicts。
- clarification_questions 或 conflicts 中的每个待确认问题，应尽量给出 recommended_options，最多 2 个。
- 每个 recommended_options 必须是可直接写入初步需求的业务答案，answer_markdown 不得是解释、问题或占位文本。
- 如果证据不足以给出可信推荐选项，可以少于 2 个，但不得编造。
- 输出必须符合 RequirementAnalysisOutput。
""".strip()


def _build_requirement_analysis_backend():
    return CompositeBackend(
        default=StateBackend(),
        routes={
            SKILLS_ROUTE: FilesystemBackend(root_dir=SKILLS_DIR, virtual_mode=True),
        },
    )


def requirement_analysis_agent(model, auxiliary_documents: list[RequirementAuxiliaryDocument] | None = None):
    backend = _build_requirement_analysis_backend()
    tools = [build_auxiliary_search_tool(auxiliary_documents)] if auxiliary_documents else []
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[
            FilesystemMiddleware(
                backend=backend,
                system_prompt="只使用文件系统读取已加载的技能说明和本次分析上下文，不要写入持久文件。",
                _permissions=[
                    FilesystemPermission(operations=["write"], paths=[f"{SKILLS_ROUTE}**"], mode="deny"),
                ],
            ),
            SkillsMiddleware(
                backend=backend,
                sources=[SKILLS_ROUTE],
            ),
            SummarizationMiddleware(
                model=model,
                backend=backend,
                trigger=("tokens", 50000),
                keep=("messages", 8),
            ),
        ],
        response_format=ToolStrategy(RequirementAnalysisOutput),
    )
