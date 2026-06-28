"""页面探索Agent的输入输出数据结构定义"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ==================== 输入 Schema ====================


class PageExplorationInput(BaseModel):
    """页面探索输入"""

    start_url: str = Field(..., description="探索起始URL")
    goal: str = Field(default="", description="探索目标描述")
    max_pages: int = Field(default=50, description="最大探索页面数")
    max_depth: int = Field(default=3, description="最大探索深度")
    forbidden_paths: List[str] = Field(default_factory=list, description="禁止访问的路径列表")


# ==================== 输出 Schema ====================


class PageElement(BaseModel):
    """页面元素信息"""

    element_id: str = Field(..., description="元素唯一标识")
    role: str = Field(..., description="元素角色（button/link/input等）")
    label: str = Field(..., description="元素标签/文本")
    locator: str = Field(..., description="元素定位器（Playwright格式）")
    context: str = Field(default="", description="元素上下文描述")
    visible: bool = Field(default=True, description="元素是否可见")


class PageSnapshot(BaseModel):
    """单个页面的快照信息"""

    page_id: str = Field(..., description="页面唯一标识")
    url: str = Field(..., description="页面URL")
    normalized_url: str = Field(..., description="规范化URL（路径）")
    title: str = Field(..., description="页面标题")
    description: str = Field(default="", description="页面描述")
    elements: List[PageElement] = Field(default_factory=list, description="页面元素列表")
    links: List[str] = Field(default_factory=list, description="页面中发现的链接")
    explored_at: str = Field(..., description="探索时间（ISO格式）")


class ExplorationIssue(BaseModel):
    """探索过程中的问题"""

    url: str = Field(..., description="发生问题的URL")
    error_type: str = Field(..., description="错误类型")
    error_message: str = Field(..., description="错误消息")
    timestamp: str = Field(..., description="发生时间")


class PageExplorationOutput(BaseModel):
    """页面探索输出结果"""

    success: bool = Field(..., description="探索是否成功")
    pages_explored: int = Field(..., description="实际探索的页面数")
    pages_discovered: int = Field(..., description="发现的页面总数")
    elements_found: int = Field(..., description="提取的元素总数")
    duration_seconds: float = Field(..., description="探索耗时（秒）")

    snapshots: List[PageSnapshot] = Field(default_factory=list, description="页面快照列表")
    issues: List[ExplorationIssue] = Field(default_factory=list, description="问题列表")

    artifacts: dict = Field(default_factory=dict, description="生成的产物文件路径")
    summary: str = Field(default="", description="探索结果摘要")
    recommendations: List[str] = Field(default_factory=list, description="改进建议")


# ==================== 工具输入 Schema ====================


class NavigateInput(BaseModel):
    """导航工具输入"""
    url: str = Field(..., description="目标URL")


class ClickInput(BaseModel):
    """点击工具输入"""
    locator: str = Field(..., description="元素定位器")


class FillInput(BaseModel):
    """填充工具输入"""
    locator: str = Field(..., description="元素定位器")
    value: str = Field(..., description="填充值")


class ExtractElementsInput(BaseModel):
    """提取元素工具输入"""
    element_types: List[str] = Field(
        default=["button", "link", "input"],
        description="要提取的元素类型列表"
    )


# ==================== Agent内部使用的Schema ====================


class ExplorationState(BaseModel):
    """探索状态（Agent内部使用）"""

    current_url: Optional[str] = Field(None, description="当前URL")
    explored_urls: List[str] = Field(default_factory=list, description="已探索URL列表")
    queue: List[str] = Field(default_factory=list, description="待探索URL队列")
    depth_map: dict = Field(default_factory=dict, description="URL深度映射")

    pages_explored: int = Field(default=0, description="已探索页面数")
    elements_extracted: int = Field(default=0, description="已提取元素数")

    should_terminate: bool = Field(default=False, description="是否应该终止")
    termination_reason: Optional[str] = Field(None, description="终止原因")
