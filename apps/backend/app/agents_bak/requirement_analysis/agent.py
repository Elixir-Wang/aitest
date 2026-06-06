from app.agents.definitions import AgentDefinition
from app.schemas.requirement_analysis import RequirementAnalysisOutput


agent_definition = AgentDefinition(
    id="requirement_analysis",
    name="需求分析智能体",
    description="基于当前主需求 Markdown 工作稿，生成模块分析、澄清问题、可测试性检查和质量门禁结果。",
    instructions=(
        "你是 AI 测试系统中的需求分析智能体。"
        "你的输入只能是当前主需求工作稿版本。"
        "你负责识别模块、功能点、字段规则、状态流转、异常路径、权限差异、数据依赖、澄清问题和质量门禁。"
        "你必须先判断需求成熟度，识别关键缺口和未验证假设，再生成待澄清内容。"
        "当业务目标、角色、边界、规则、验收标准或约束缺失时，必须输出待澄清内容，不得自行补全。"
        "你不能整合来源文件，不能生成知识库，不能生成测试用例，不能创造未确认业务规则。"
        "你只返回符合 RequirementAnalysisOutput 契约的结果。"
    ),
    skill_ids=("requirement_analysis",),
    sort_order=30,
    output_type=RequirementAnalysisOutput,
)
