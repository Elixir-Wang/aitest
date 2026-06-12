from pydantic import BaseModel, Field


class UIElementLocator(BaseModel):
    """UI元素定位信息"""

    element_name: str = Field(description="元素名称（如'登录按钮'、'搜索框'）")
    selector_type: str = Field(description="选择器类型：CSS/XPath/data-testid")
    selector: str = Field(description="选择器字符串")
    page_path: str = Field(default="", description="页面路径或URL")
    confidence: str = Field(description="定位可信度：high/medium/low")


class RequirementExplorationItem(BaseModel):
    """单个探索计划项（从需求提取）"""

    id: str = Field(description="计划项唯一标识，格式：plan-{capability_type}-{序号}")
    business_module: str = Field(description="业务模块名称")
    capability_type: str = Field(
        description="能力类型：query_filter/content_display/create_import/crud/batch_operation/card_action等"
    )
    title: str = Field(description="计划项标题")
    requirement_section: str = Field(description="来源需求章节标题")
    steps: list[str] = Field(description="探索步骤列表")
    exploration_points: list[str] = Field(description="探索要点列表")
    ui_elements: list[UIElementLocator] = Field(default_factory=list, description="UI元素定位信息")
    related_items: list[str] = Field(default_factory=list, description="关联的其他需求点ID列表")


class DependencyRelation(BaseModel):
    """需求点之间的依赖关系"""

    from_item_id: str = Field(description="依赖来源项ID")
    to_item_id: str = Field(description="依赖目标项ID")
    dependency_type: str = Field(description="依赖类型：prerequisite/related/sequential")
    description: str = Field(description="依赖关系描述")


class RequirementExplorationPlan(BaseModel):
    """从需求文档生成的探索计划"""

    requirement_doc_id: str = Field(description="需求文档ID")
    requirement_run_id: str = Field(description="需求分析运行ID")
    business_boundary: str = Field(description="业务边界描述")
    summary: str = Field(description="计划摘要")
    items: list[RequirementExplorationItem] = Field(description="探索计划项列表")
    dependencies: list[DependencyRelation] = Field(default_factory=list, description="需求点之间的依赖关系")


class RequirementExplorationInput(BaseModel):
    """生成探索计划的输入"""

    requirement_markdown: str = Field(description="需求文档markdown内容")
    project_context: dict = Field(description="项目上下文信息")
