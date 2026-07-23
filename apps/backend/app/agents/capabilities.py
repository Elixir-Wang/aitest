from dataclasses import dataclass


@dataclass(frozen=True)
class AiCapability:
    id: str
    name: str
    description: str


AI_CAPABILITIES: tuple[AiCapability, ...] = (
    AiCapability(
        id="document_editor",
        name="文档修改",
        description="根据用户指令修改 Markdown 文档，返回修改后的文档、修改摘要和风险提示。",
    ),
    AiCapability(
        id="requirement_standardization",
        name="需求标准化",
        description="负责将上传的 PDF、Word、TXT 和 Markdown 需求文件标准化为结构稳定的标准 Markdown。",
    ),
    AiCapability(
        id="requirement_analysis",
        name="需求分析",
        description="基于当前主需求 Markdown 工作稿，生成模块分析、澄清问题、可测试性检查和质量门禁结果。",
    ),
    AiCapability(
        id="knowledge_query",
        name="项目知识库查询",
        description="基于最终需求文档执行 agentic 检索，返回带来源引用的项目知识库答案。",
    ),
    AiCapability(
        id="test_case_generation",
        name="测试用例生成",
        description="根据最终需求文档生成完整、系统、可执行的测试用例集。",
    ),
    AiCapability(
        id="test_point_generation",
        name="测试点生成",
        description="根据指定最终需求版本生成结构化、可追溯、可评审的业务测试点。",
    ),
    AiCapability(
        id="api_test_generation",
        name="接口自动化用例生成",
        description="根据 OpenAPI 接口定义、接口环境摘要和测试重点生成结构化接口自动化用例。",
    ),
    AiCapability(
        id="api_scenario_orchestration",
        name="接口自动化场景编排",
        description="根据业务目标和当前项目接口资产生成可审阅的接口自动化场景计划。",
    ),
    AiCapability(
        id="ui_test_generation",
        name="UI 自动化代码生成",
        description="根据已采纳测试用例和站点探索证据生成受控 pytest + Playwright UI 自动化代码。",
    ),
    AiCapability(
        id="page_exploration",
        name="站点探索",
        description="负责自动化探索 Web 应用，包括页面分析、元素识别、登录表单分析和验证码识别等多模态任务。",
    ),
    AiCapability(
        id="performance_script_generation",
        name="性能测试脚本计划生成",
        description="根据脱敏后的单接口配置生成受控 LocustScriptPlan。",
    ),
    AiCapability(
        id="performance_report_analysis",
        name="性能测试报告分析",
        description="根据脱敏后的 Locust 统计事实生成性能问题、证据和优化建议。",
    ),
)


def list_ai_capabilities() -> list[AiCapability]:
    return list(AI_CAPABILITIES)


def get_ai_capability(capability_id: str) -> AiCapability:
    for capability in AI_CAPABILITIES:
        if capability.id == capability_id:
            return capability
    raise KeyError(capability_id)
