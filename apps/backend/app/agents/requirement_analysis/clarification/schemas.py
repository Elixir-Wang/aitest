"""澄清相关 Schemas."""

from typing import Literal
from pydantic import BaseModel, Field


class TestSurface(BaseModel):
    """测试表面（测试关注的技术层面）"""
    surface_type: Literal[
        "api",                  # API 契约层
        "state_flow",           # 状态流转层
        "data_consistency",     # 数据一致性层
        "permission",           # 权限控制层
        "security",             # 安全层
        "audit_log",            # 审计日志层
        "async_task",           # 异步任务层
        "external_dependency",  # 外部依赖层
        "ui_feedback",          # 用户反馈层
        "migration",            # 数据迁移层
        "non_functional",       # 非功能需求层
    ]
    rationale: str = Field(
        default="",
        description="为什么这个澄清项影响该测试表面"
    )


class TestCase(BaseModel):
    """测试用例草案"""
    test_id: str = Field(description="测试用例ID，如 TC-001")
    scenario: str = Field(description="测试场景描述（Given-When-Then格式）")
    test_type: Literal[
        "positive",      # 正向测试（正常路径）
        "negative",      # 负向测试（异常路径）
        "boundary",      # 边界值测试
        "concurrency",   # 并发测试
        "security",      # 安全测试
        "performance",   # 性能测试
    ] = "positive"
    expected_result: str = Field(description="预期结果（可断言的）")
    assertion_points: list[str] = Field(
        default_factory=list,
        description="具体的断言点（如：响应状态码为200、字段X包含Y）"
    )
    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        default="P1",
        description="测试优先级（P0=冒烟，P1=核心，P2=重要，P3=边缘）"
    )


class ClarificationOption(BaseModel):
    """澄清选项（供人工选择的方案）"""
    option_id: str
    label: str = Field(description="选项简称，如：按幂等处理、拒绝重复操作")
    description: str = Field(
        description="完整的规则描述，可直接写入需求文档"
    )

    # 测试视角的优劣分析
    pros: list[str] = Field(
        default_factory=list,
        description="该选项的优势（测试角度）"
    )
    cons: list[str] = Field(
        default_factory=list,
        description="该选项的劣势或风险（测试角度）"
    )

    # 如果选择该选项，需要补充的测试用例
    additional_tests: list[str] = Field(
        default_factory=list,
        description="选择该选项后需要补充的测试场景"
    )

    # 证据和来源
    confidence: Literal["high", "medium", "low"] = "medium"
    source: str = Field(
        description="选项来源：辅助文档名称、测试最佳实践、业务经验"
    )
    evidence_excerpt: str = Field(
        default="",
        description="如果来自辅助文档，引用原文片段"
    )


class ClarificationItem(BaseModel):
    """待澄清项（测试驱动视角）"""

    # ========== 基础标识 ==========
    item_id: str = Field(description="唯一标识，如 CL-001")
    title: str = Field(description="简短标题，如：订单状态流转规则待确认")

    # ========== 问题分类 ==========
    issue_category: Literal[
        "contract_unclear",        # 契约不明确（输入输出、接口定义）
        "rule_missing",            # 规则缺失（业务规则、计算规则）
        "boundary_undefined",      # 边界未定义（边界值、极端情况）
        "exception_unhandled",     # 异常未处理（错误处理、失败场景）
        "state_ambiguous",         # 状态模糊（状态流转、终态判定）
        "concurrency_unclear",     # 并发不明确（幂等性、锁策略）
        "permission_undefined",    # 权限未定义（谁能做、什么不能做）
        "dependency_unclear",      # 依赖不清楚（外部依赖、数据依赖）
        "acceptance_missing",      # 验收标准缺失
        "conflict",                # 需求冲突
    ]

    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        default="P1",
        description="优先级（P0=阻塞交付，P1=高风险，P2=中风险，P3=低风险）"
    )

    # ========== 视觉化分级标记（新增）==========
    visual_marker: str = Field(
        default="",
        description="视觉化标记：🔴(P0高风险阻塞) / 🟡(P1/P2中风险) / 🟢(P3低风险)"
    )

    risk_level: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="风险等级：high(阻塞上线) / medium(影响范围/体验) / low(可观察可优化)"
    )

    # ========== 关联信息 ==========
    module_key: str = Field(description="关联的需求模块")
    module_name: str = Field(description="模块名称")
    source_stage: Literal[
        "understanding",    # 来自需求理解阶段
        "completeness",     # 来自完整性检查
        "clarity",          # 来自清晰度检查
        "testability",      # 来自可测试性检查
        "consistency",      # 来自一致性检查
    ]

    # ========== 测试驱动核心字段 ==========

    # 1. 决策点（需要确认什么）
    decision_point: str = Field(
        description="需要人工裁决的具体业务点，如：重复提交是否幂等、失败后是否回滚"
    )

    # 2. 问题描述（为什么需要澄清）
    why_clarify: str = Field(
        description="为什么这个点必须澄清，当前有什么不确定性或风险"
    )

    # 3. 测试影响（不澄清的后果）
    test_impact: str = Field(
        description="不澄清会导致哪些测试无法设计、无法断言、无法验收"
    )

    # 4. 风险场景（Given-When-Then）
    risk_scenario: str = Field(
        description="Given-When-Then 格式的风险触发场景"
    )

    # 5. 影响的测试表面
    affected_surfaces: list[TestSurface] = Field(
        default_factory=list,
        description="该澄清项影响哪些测试层面"
    )

    # 6. 测试用例草案
    test_cases: list[TestCase] = Field(
        default_factory=list,
        description="澄清后应设计的测试用例（3-5个代表性用例）"
    )

    # ========== 澄清选项 ==========
    options: list[ClarificationOption] = Field(
        default_factory=list,
        min_length=0,
        max_length=4,
        description="供人工选择的澄清方案（2-4个互斥选项）"
    )

    recommended_option_id: str = Field(
        default="",
        description="推荐的选项ID（如果有明确推荐）"
    )

    recommendation_rationale: str = Field(
        default="",
        description="推荐理由（基于测试风险、业务通用性等）"
    )

    # ========== 原需求上下文 ==========
    source_excerpt: str = Field(
        default="",
        description="主需求中的相关原文（可追溯）"
    )

    related_requirements: list[str] = Field(
        default_factory=list,
        description="相关的需求条目ID或描述"
    )

    # ========== 解答状态 ==========
    resolution_status: Literal[
        "auto_resolved",     # 从辅助文档找到高置信度答案
        "has_options",       # 有多个选项供选择
        "needs_input",       # 需要业务方输入
        "needs_research",    # 需要进一步调研
    ] = "needs_input"

    # 如果 auto_resolved，记录自动解答的内容
    auto_resolution: str = Field(
        default="",
        description="自动解答的内容（仅当 resolution_status=auto_resolved）"
    )
    auto_resolution_source: str = Field(
        default="",
        description="自动解答的来源（辅助文档名称 + 章节）"
    )

    # ========== 元数据 ==========
    tags: list[str] = Field(
        default_factory=list,
        description="标签，如：高并发、支付核心、数据迁移"
    )

    related_items: list[str] = Field(
        default_factory=list,
        description="关联的其他澄清项ID（如：CL-002 依赖 CL-001 的答案）"
    )


class ClarificationSummary(BaseModel):
    """澄清内容汇总"""

    # 总体统计
    total: int
    by_priority: dict[str, int] = Field(
        default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    )
    by_category: dict[str, int] = Field(
        default_factory=dict,
        description="按 issue_category 分类统计"
    )
    by_resolution: dict[str, int] = Field(
        default_factory=lambda: {
            "auto_resolved": 0,
            "has_options": 0,
            "needs_input": 0,
            "needs_research": 0
        }
    )

    # 测试覆盖分析
    test_surfaces_coverage: dict[str, int] = Field(
        default_factory=dict,
        description="各测试表面被涉及的次数"
    )
    total_test_cases: int = Field(
        default=0,
        description="所有澄清项生成的测试用例总数"
    )

    # 风险评估
    blocking_count: int = Field(
        default=0,
        description="P0 阻塞项数量"
    )
    high_risk_count: int = Field(
        default=0,
        description="P1 高风险项数量"
    )

    # 推荐行动
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="建议的下一步行动（优先处理哪些项）"
    )


class ClarificationOutput(BaseModel):
    """待澄清内容输出（测试驱动版本）"""

    items: list[ClarificationItem] = Field(
        description="按优先级排序的待澄清项（P0 → P1 → P2 → P3）"
    )

    summary: ClarificationSummary

    # 整体评估
    overall_assessment: str = Field(
        description="整体评估：当前需求的可测试性和交付风险"
    )

    # 测试策略建议
    test_strategy_recommendations: list[str] = Field(
        default_factory=list,
        description="基于澄清项的测试策略建议（如：重点做并发测试、补充边界值测试）"
    )

    # 元数据
    generated_at: str = Field(description="生成时间戳")
    model_version: str = Field(default="test-driven")


__all__ = [
    "TestSurface",
    "TestCase",
    "ClarificationOption",
    "ClarificationItem",
    "ClarificationSummary",
    "ClarificationOutput",
]
