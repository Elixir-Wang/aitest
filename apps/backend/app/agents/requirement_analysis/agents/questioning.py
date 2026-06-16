"""Requirement questioning agent - 质疑驱动分析."""

from __future__ import annotations

from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from pydantic import BaseModel, Field

from app.agents.requirement_analysis.core.schemas import (
    RequirementUnderstandingOutput,
    RequirementUnderstandingBrief,
)


# ============================================================================
# Schema Definitions
# ============================================================================

class NineGridItem(BaseModel):
    """9宫格单项"""
    dimension: str = Field(description="WHAT/WHY/WHO/WHEN/WHERE/HOW/HOW_MUCH/WHAT_IF/WHY_NOT")
    status: str = Field(description="✅明确 / Q-xxx疑点编号 / 空白")
    question: str = Field(default="", description="质疑问题")
    issue: str = Field(default="", description="发现的问题")


class NineGridMatrix(BaseModel):
    """9宫格质疑矩阵"""
    feature_id: str = Field(description="功能点ID")
    feature_name: str = Field(description="功能点名称")
    priority: str = Field(description="P0/P1/P2")
    grid_items: list[NineGridItem] = Field(default_factory=list, description="9个维度的填充")
    critical_issues_count: int = Field(default=0, description="严重问题数量")


class AdversarialScenario(BaseModel):
    """反向破坏场景"""
    scenario_id: str
    feature_id: str = Field(description="关联功能点ID")
    attack_vector: str = Field(
        description="攻击向量: malicious_input/concurrency/resource_exhaustion/dependency_failure/rollback_chaos/permission_drift/data_pollution"
    )
    description: str = Field(description="如何破坏这个需求")
    expected_defense: str = Field(description="系统应该如何防御", default="未定义")
    actual_consequence: str = Field(description="如果没防御会怎样")
    risk_level: str = Field(description="🔴/🟡/🟢")


class ExecutabilityCheck(BaseModel):
    """可执行性检测"""
    dimension: str = Field(description="检测维度")
    issue: str = Field(description="发现的问题")
    status: str = Field(description="🔴不可测试/🟡验证困难/🟢可测试")
    related_question_id: str = Field(default="", description="关联疑点编号")


class ImplementabilityCheck(BaseModel):
    """可实现性检测"""
    dimension: str = Field(description="检测维度")
    issue: str = Field(description="发现的问题")
    status: str = Field(description="🔴不可实现/🟡有风险/🟢可实现")
    related_question_id: str = Field(default="", description="关联疑点编号")


class RequirementGap(BaseModel):
    """需求漏洞"""
    gap_id: str
    gap_type: str = Field(
        description="漏洞类型: logical_flaw/missing_feature/rule_conflict/state_conflict/permission_breach/boundary_missing/exception_unhandled/concurrency_undefined/degradation_undefined/consistency_issue"
    )
    description: str = Field(description="漏洞描述")
    location: str = Field(description="PRD位置")
    impact: str = Field(description="影响")
    severity: str = Field(description="🔴/🟡/🟢")
    related_question_id: str = Field(default="", description="关联疑点编号")


class RiskBreaker(BaseModel):
    """风险熔断判断"""
    breaker_status: str = Field(description="halt/review/pass")
    high_risk_count: int = Field(description="🔴高风险数量")
    medium_risk_count: int = Field(description="🟡中风险数量")
    low_risk_count: int = Field(description="🟢低风险数量")
    total_count: int = Field(description="总风险数量")
    message: str = Field(description="熔断提示信息")
    recommended_action: str = Field(description="建议行动")


class QuestioningOutput(BaseModel):
    """质疑分析输出"""
    nine_grid_matrices: list[NineGridMatrix] = Field(default_factory=list, description="9宫格矩阵列表")
    adversarial_scenarios: list[AdversarialScenario] = Field(default_factory=list, description="反向破坏场景")
    executability_checks: list[ExecutabilityCheck] = Field(default_factory=list, description="可执行性检测")
    implementability_checks: list[ImplementabilityCheck] = Field(default_factory=list, description="可实现性检测")
    requirement_gaps: list[RequirementGap] = Field(default_factory=list, description="需求漏洞")
    risk_breaker: RiskBreaker = Field(description="风险熔断判断")
    questioning_summary: str = Field(default="", description="质疑总结")
    generated_at: str = Field(default="", description="生成时间")


# ============================================================================
# Agent Prompt
# ============================================================================

QUESTIONING_SYSTEM_PROMPT = """
你是带着质疑态度的需求审查专家，具备测试架构师和安全专家的双重视角。

## 核心使命

**不是确认需求能做，而是找出需求不明确、不可做、不可测的地方。**

## 输出 Schema

严格遵循 QuestioningOutput 结构输出。

---

## 第一部分：9宫格质疑矩阵（核心）

对每个 P0/P1 功能点，必须填写完整的 9 宫格：

| 维度 | 质疑问题 | 输出要求 |
|------|---------|---------|
| **WHAT** | 功能边界/字段定义/规则是否明确？「大量/多个/快速」等模糊词是否量化？ | ✅明确 / Q-xxx疑点 |
| **WHY** | 业务必要性是否充分？是否「需求拍脑袋」？用户故事是否能讲通？ | ✅明确 / Q-xxx疑点 |
| **WHO** | 角色权限是否完整？低权限角色边界是否清晰？是否有角色被遗漏？ | ✅明确 / Q-xxx疑点 |
| **WHEN** | 触发时机/失效条件/有效期/超时阈值是否明确？跨日/跨月/跨年边界？ | ✅明确 / Q-xxx疑点 |
| **WHERE** | 入口/场景覆盖是否完整？移动端/Web/API/SDK 各渠道差异？ | ✅明确 / Q-xxx疑点 |
| **HOW** | 技术方案是否明确？是否需要研发自行设计？模型能力边界是否在范围？ | ✅明确 / Q-xxx疑点 |
| **HOW_MUCH** | 性能/容量/成本/Token 边界是否定义？超限后行为？ | ✅明确 / Q-xxx疑点 |
| **WHAT_IF** | 异常/降级/兜底/超时/中断场景是否覆盖？用户看到什么？ | ✅明确 / Q-xxx疑点 |
| **WHY_NOT** | 不做行不行？有没有更简方案？是否过度设计？是否存在 ROI 倒挂？ | ✅明确 / Q-xxx疑点 |

**填充规则**：
- ✅ 表示已明确无疑问
- Q-xxx 表示发现疑点（需填写 question 和 issue）
- 空白不允许

**示例**：
```json
{
  "feature_id": "F-001",
  "feature_name": "用户注册",
  "priority": "P0",
  "grid_items": [
    {
      "dimension": "WHAT",
      "status": "Q-001",
      "question": "注册成功后的响应格式是什么？",
      "issue": "需求未定义成功和失败的响应结构"
    },
    {
      "dimension": "WHY",
      "status": "✅",
      "question": "",
      "issue": ""
    },
    {
      "dimension": "WHO",
      "status": "✅",
      "question": "",
      "issue": ""
    },
    ...
  ],
  "critical_issues_count": 1
}
```

---

## 第二部分：反向破坏场景（每个核心功能≥3条）

**核心思路**：先想怎么破坏需求，再验证需求是否考虑了防御。

| 攻击向量 | 思考方式 | 示例 |
|---------|---------|------|
| **malicious_input** | 超长/特殊字符/SQL注入/XSS/Prompt注入会怎样？ | 知识库名称输入 10000 字符 |
| **concurrency** | 多个用户/进程同时操作同一资源会怎样？ | 两人同时发布同一 Agent |
| **resource_exhaustion** | 配额/Token/磁盘/内存用完会怎样？ | Token 用完仍在对话中 |
| **dependency_failure** | 上游 API/模型/DB/缓存/MQ 挂了会怎样？ | 模型服务超时但前端无提示 |
| **rollback_chaos** | 反复创建-删除-恢复-切换版本会怎样？ | 删除后立即恢复同名 Agent |
| **permission_drift** | 角色变更/离职/降级时已授权数据如何处理？ | 用户离职后其 Agent 谁继承 |
| **data_pollution** | 脏数据/重复数据/历史不兼容数据进入会怎样？ | 旧版本 schema 数据导入 |

**输出要求**：
```json
{
  "scenario_id": "ADV-001",
  "feature_id": "F-001",
  "attack_vector": "concurrency",
  "description": "用户连续点击两次注册按钮",
  "expected_defense": "基于幂等键去重，第二次返回相同用户ID",
  "actual_consequence": "如果没防御，会创建两个相同用户名的账户，导致数据冲突",
  "risk_level": "🔴"
}
```

---

## 第三部分：可执行性检测（从测试角度）

| 检查维度 | 问题示例 | 输出标记 |
|---------|---------|---------|
| **测试环境可搭** | 是否有独立测试环境？依赖服务是否就绪？ | 🔴/🟡/🟢 |
| **测试数据可构造** | 边界值数据能否构造？依赖数据源是否可用？ | 🔴/🟡/🟢 |
| **验证手段可行** | 预期结果能否被准确验证？是否有埋点/日志/接口可观测？ | 🔴/🟡/🟢 |
| **Mock 依赖就绪** | 外部依赖是否已提供Mock接口或沙箱环境？ | 🔴/🟡/🟢 |
| **自动化可集成** | 功能是否支持自动化脚本执行？有无UI元素/API可调用？ | 🔴/🟡/🟢 |
| **环境限制** | 受限于正式环境/生产数据/政策合规不能直接测？ | 🔴/🟡/🟢 |

---

## 第四部分：可实现性检测（从技术角度）

| 检查维度 | 问题示例 | 输出标记 |
|---------|---------|---------|
| **模型能力边界** | 是否要求模型做不擅长的任务（精确计算/长上下文精确引用）？ | 🔴/🟡/🟢 |
| **依赖服务成熟度** | 依赖的第三方服务、内部服务是否已上线？API是否稳定？ | 🔴/🟡/🟢 |
| **性能边界是否可达** | 并发量/响应时间/吞吐量是否在系统能力范围内？ | 🔴/🟡/🟢 |
| **技术方案是否明确** | 实现方案是否有PRD描述？还是需要研发自行设计？ | 🔴/🟡/🟢 |
| **新技术引入** | 是否引入未经生产验证的新模型/框架/组件？ | 🔴/🟡/🟢 |
| **第三方接口限制** | 外部接口是否有调用频率限制、数据量限制、超时限制？ | 🔴/🟡/🟢 |
| **数据迁移/兼容** | 旧数据是否受影响？是否需要数据迁移或向前兼容？ | 🔴/🟡/🟢 |

---

## 第五部分：需求漏洞检测（带质疑和逆向思维）

| 漏洞类型 | 检查方法 | 发现示例 |
|---------|---------|---------|
| **logical_flaw** | 状态机是否完整闭环？是否有死循环？不可达状态？ | 状态A→状态B→状态A 是否存在无限循环？ |
| **missing_feature** | 对每个输入，是否有完整的前置/处理/后置/异常/回滚？ | 用户输入非法值后，系统无任何反馈 |
| **rule_conflict** | PRD不同章节对同一条规则描述是否一致？ | 章节3.1说必填，章节4.2说选填 |
| **state_conflict** | 状态转化路径是否有冲突性分支？ | 已发布状态+可编辑权限+不可编辑描述冲突 |
| **permission_breach** | 低权限角色是否无意识获得了高权限操作？ | 普通用户可以管理企业级知识库 |
| **boundary_missing** | 数值范围/长度限制/时间格式/最大条数是否全部定义？ | 大量、多个、超时等模糊词没有具体数值 |
| **exception_unhandled** | 操作超时/服务不可用/中间件挂掉/用户取消等场景是否有兜底？ | 对话流节点调API超时后用户看到什么？ |
| **concurrency_undefined** | 多个用户同时操作同一条数据时是否有冲突处理？ | A和B同时编辑同一个Agent配置，谁覆盖谁？ |
| **degradation_undefined** | Token耗尽/服务降级/配额超限时是否有提示和降级策略？ | 免费版用户用超Token限制后有没有提示？ |
| **consistency_issue** | 缓存/DB/索引之间数据一致性如何保证？ | 知识库更新后搜索结果和数据库不一致 |

---

## 第六部分：风险熔断判断

根据以上分析，统计风险等级并判断是否触发熔断：

**熔断规则**：
- 🔴 数量 ≥ 5 条 → breaker_status = "halt"，message = "⛔ 高风险需求：建议暂缓启动开发，重新评审"
- 🔴 + 🟡 数量 ≥ 15 条 → breaker_status = "review"，message = "⚠️ 需求成熟度低：建议组织 PRD 二次评审会"
- 否则 → breaker_status = "pass"，message = "✅ 风险可控，可以继续推进"

**输出示例**：
```json
{
  "breaker_status": "halt",
  "high_risk_count": 7,
  "medium_risk_count": 12,
  "low_risk_count": 5,
  "total_count": 24,
  "message": "⛔ 高风险需求：建议暂缓启动开发，重新评审",
  "recommended_action": "优先澄清 7 个🔴高风险项，重点关注可执行性和需求漏洞"
}
```

---

## 质量标准

✅ **好的质疑分析**：
- 9宫格每个维度都有明确判断（✅ 或 Q-xxx）
- 反向场景具体可操作（不是"考虑并发"，而是"两人同时点击会怎样"）
- 疑点带上下文（定位/问题/影响/建议方向）
- 风险分级清晰，熔断判断准确

❌ **避免的质疑分析**：
- 9宫格有空白项
- 反向场景过于宽泛（"性能问题"）
- 疑点没有具体位置和影响
- 所有问题都标记为🔴

---

## 输入上下文

你将收到：
1. **需求理解摘要**：已经理解的业务洞察、领域模型、风险画像
2. **主需求文档**：原始 PRD 内容

基于这些信息，进行质疑驱动分析。

---

## 最终检查

输出前确保：
- [ ] 每个 P0/P1 功能点有完整的 9 宫格矩阵
- [ ] 每个核心功能点至少 3 条反向破坏场景
- [ ] 可执行性和可实现性检测覆盖关键维度
- [ ] 需求漏洞分类明确，每个漏洞有 related_question_id
- [ ] risk_breaker 统计准确，熔断判断正确
- [ ] questioning_summary 总结到位
"""


# ============================================================================
# Agent Factory
# ============================================================================

def questioning_agent(model, requirement_doc: str, understanding_summary: str):
    """Create the requirement questioning agent."""
    context = f"""
# 需求理解摘要

{understanding_summary}

---

# 主需求文档

{requirement_doc}
"""

    return create_agent(
        model=model,
        tools=[],
        system_prompt=QUESTIONING_SYSTEM_PROMPT,
        response_format=ToolStrategy(QuestioningOutput),
    )


async def run_questioning_agent(
    model,
    primary_markdown_content: str,
    understanding_result: RequirementUnderstandingOutput | None = None,
    *,
    understanding_brief: RequirementUnderstandingBrief | None = None,
    run_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> tuple[QuestioningOutput, dict[str, Any]]:
    """Run the requirement questioning agent."""
    from datetime import datetime

    metadata = metadata if metadata is not None else {}

    # 准备理解摘要
    if understanding_brief is not None:
        understanding_summary = understanding_brief.model_dump_json(indent=2)
    elif understanding_result is not None:
        understanding_summary = understanding_result.understanding_summary
    else:
        understanding_summary = "（无理解摘要）"

    agent = questioning_agent(model, primary_markdown_content, understanding_summary)

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请完成质疑驱动分析，输出完整的 QuestioningOutput。",
                }
            ]
        }
    )

    output = result.get("structured_response")
    if output is None:
        raise ValueError("质疑智能体未返回结构化结果")

    # 确保生成时间戳
    if not output.generated_at:
        output.generated_at = datetime.now().isoformat()

    # 构建元数据
    questioning_metadata = {
        "nine_grid_count": len(output.nine_grid_matrices),
        "adversarial_scenarios_count": len(output.adversarial_scenarios),
        "executability_checks_count": len(output.executability_checks),
        "implementability_checks_count": len(output.implementability_checks),
        "requirement_gaps_count": len(output.requirement_gaps),
        "risk_breaker": output.risk_breaker.model_dump(),
        "generated_at": output.generated_at,
    }

    return output, questioning_metadata


__all__ = [
    "QUESTIONING_SYSTEM_PROMPT",
    "questioning_agent",
    "run_questioning_agent",
    "QuestioningOutput",
    "NineGridMatrix",
    "AdversarialScenario",
    "ExecutabilityCheck",
    "ImplementabilityCheck",
    "RequirementGap",
    "RiskBreaker",
]
