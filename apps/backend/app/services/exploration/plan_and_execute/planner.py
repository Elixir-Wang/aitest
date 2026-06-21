"""
Plan-and-Execute 模式 - Planner（规划器）

负责分析探索目标、范围和禁止路径，生成完整的执行计划
"""

import asyncio
import json
from urllib.parse import urlparse
from typing import Literal
from pydantic import BaseModel, Field

from app.agents.model_selection import build_agent_model, resolve_model_selection


class ExplorationStep(BaseModel):
    """探索步骤"""
    step_id: str
    step_number: int
    action_type: Literal["navigate", "click", "fill", "wait", "observe", "check", "agentic_explore"]
    description: str  # 步骤描述（自然语言）
    target_description: str  # 目标元素的描述
    target_selector: str = ""  # 如果已知selector
    value: str = ""  # 填充值（用于fill）
    expected_result: str  # 预期结果
    module_name: str = ""  # 所属模块
    is_critical: bool = True  # 是否关键步骤（失败后是否继续）
    retry_on_failure: bool = True
    max_retries: int = 2
    execution_strategy: Literal["direct", "agentic"] = "direct"  # 执行策略


class ExplorationPlan(BaseModel):
    """探索计划"""
    plan_id: str
    goal_summary: str  # 目标摘要
    scope_summary: str  # 范围摘要
    strategy: str  # 探索策略
    modules: list[str] = Field(default_factory=list)  # 模块列表
    steps: list[ExplorationStep]
    estimated_duration_minutes: int = 30
    risk_assessment: str = ""
    success_criteria: list[str] = Field(default_factory=list)


class PlannerInput(BaseModel):
    """规划器输入"""
    run_id: str
    title: str
    goal: str  # 探索目标
    scope: str  # 探索范围
    forbidden_paths: str  # 禁止路径
    start_url: str
    environment_info: dict = Field(default_factory=dict)
    max_pages: int = 50
    max_actions: int = 1000
    timeout_minutes: int = 120


PLANNER_SYSTEM_PROMPT = """
你是一个站点探索规划专家。你的任务是分析探索需求，制定详细的探索计划。

## 输入信息

你会收到以下信息：
- **探索目标 (goal)**: 用户希望达成的探索目的
- **探索范围 (scope)**: 允许探索的范围
- **禁止路径 (forbidden_paths)**: 禁止访问的路径或关键词
- **起始URL (start_url)**: 探索起点

## 你的任务

**第一步：理解和分析**
1. 分析探索目标，识别关键意图
2. 如果目标已包含结构化步骤（如"模块一：xxx"），提取这些步骤
3. 如果目标是自然语言描述，推断需要执行的操作序列
4. 分析探索范围，确定边界
5. 识别禁止路径，规划规避策略

**第二步：制定计划**

生成一个完整的探索计划，包括：

1. **模块划分**：将探索任务分解为逻辑模块
   - 如果目标已指定模块，使用用户的模块划分
   - 否则根据功能区域自行划分（如：首页、导航、列表、详情、操作等）

2. **步骤生成**：为每个模块生成详细步骤
   每个步骤必须包含：
   - `action_type`: 动作类型（navigate/click/fill/wait/observe/check）
   - `description`: 清晰的步骤描述
   - `target_description`: 目标元素的自然语言描述（如"包含'登录'文字的按钮"）
   - `target_selector`:
     * **对于navigate动作**：必须填写实际的完整URL（如"http://localhost:3000/workspace"或相对路径"/workspace"）
     * **对于其他动作**：如已知CSS选择器可填写，否则留空
   - `expected_result`: 预期结果
   - `module_name`: 所属模块
   - `is_critical`: 是否关键步骤

3. **策略说明**：
   - 如何处理动态内容
   - 如何处理列表和分页
   - 如何验证探索完整性

4. **成功标准**：
   - 定义探索成功的标准
   - 定义需要验证的关键点

## 步骤类型说明

- **navigate**: 导航到指定URL（起始步骤或页面跳转）
- **click**: 点击元素（按钮、链接、卡片等）
- **fill**: 填充表单字段（输入框、下拉选择等）
- **wait**: 等待页面加载或动画完成
- **observe**: 观察并记录当前页面状态（用于记录关键页面）
- **check**: 验证条件（如"检查是否存在XX元素"）
- **agentic_explore**: 使用Agent自主探索（用于不明确的探索任务）

## 执行策略说明

每个步骤支持两种执行策略：

1. **direct（直接执行）**：目标明确，直接定位和操作
   - 示例："点击'登录'按钮" → 直接找到并点击
   - 适用：明确的操作步骤

2. **agentic（Agent自主执行）**：目标模糊，需要Agent探索决策
   - 示例："探索页面上所有可交互元素" → Agent自主发现和测试
   - 适用：探索、发现类任务

**如何选择执行策略：**
- 明确的动作（点击XX、填写YY） → direct
- 探索性任务（发现所有按钮、测试所有链接） → agentic
- 不确定目标元素的位置或名称 → agentic

## 规划原则

1. **目标导向**：所有步骤必须服务于探索目标
2. **范围约束**：步骤不能超出探索范围
3. **安全第一**：避免触及禁止路径，避免破坏性操作
4. **可执行性**：步骤描述必须清晰，执行器能理解
5. **容错性**：关键步骤失败要有应对方案
6. **完整性**：覆盖目标要求的所有功能点

## 示例

### 输入示例 1：结构化目标

```
goal: |
  模块一：进入智能体与切换对话模型
  1. 进入工作台。
  2. 点击"测试_自主规划智能体"卡片的空白处。
  3. 点击对话模型的下拉栏。
  4. 在下拉选项中选择一个模型。

  模块二：首次会话的发送、发布与历史记录操作
  1. 点击右上角历史记录。
  2. 点击"新建回话"。
  ...
scope: "/workspace"
forbidden_paths: "删除, 发布, 支付"
```

**输出计划**（简化版）：
```json
{
  "goal_summary": "测试智能体工作台的对话模型切换和会话管理功能",
  "strategy": "按照用户提供的模块顺序执行，每个步骤都进行验证",
  "modules": ["进入智能体与切换对话模型", "首次会话的发送、发布与历史记录操作"],
  "steps": [
    {
      "step_id": "step-001",
      "step_number": 1,
      "action_type": "navigate",
      "description": "导航到工作台页面",
      "target_description": "工作台首页，显示智能体卡片列表",
      "target_selector": "/workspace",
      "expected_result": "成功进入工作台，看到智能体卡片列表",
      "module_name": "进入智能体与切换对话模型",
      "is_critical": true
    },
    {
      "step_id": "step-002",
      "step_number": 2,
      "action_type": "click",
      "description": "点击'测试_自主规划智能体'卡片",
      "target_description": "包含文本'测试_自主规划智能体'的可点击卡片或按钮",
      "expected_result": "进入智能体详情页或对话页",
      "module_name": "进入智能体与切换对话模型",
      "is_critical": true
    },
    {
      "step_id": "step-003",
      "step_number": 3,
      "action_type": "click",
      "description": "点击对话模型下拉栏",
      "target_description": "对话模型选择器或下拉菜单",
      "expected_result": "显示模型选项列表",
      "module_name": "进入智能体与切换对话模型",
      "is_critical": true
    }
  ],
  "success_criteria": [
    "成功切换对话模型",
    "成功创建和管理会话",
    "所有交互元素可正常操作"
  ]
}
```

### 输入示例 2：自然语言目标（混合策略）

```
goal: "全面探索工作台功能，包括智能体的创建、使用、编辑和删除流程"
scope: "/workspace"
forbidden_paths: "真实删除, 支付"
```

**输出计划**（简化版）：
```json
{
  "goal_summary": "全面探索工作台的智能体CRUD功能",
  "strategy": "混合策略：明确步骤使用直接执行，探索任务使用Agent自主执行",
  "modules": ["工作台首页", "智能体创建", "智能体使用", "智能体编辑", "智能体管理"],
  "steps": [
    {
      "step_id": "step-001",
      "action_type": "navigate",
      "description": "进入工作台首页",
      "target_description": "/workspace",
      "expected_result": "显示工作台页面",
      "execution_strategy": "direct",
      "is_critical": true
    },
    {
      "step_id": "step-002",
      "action_type": "agentic_explore",
      "description": "探索工作台页面上所有可交互元素",
      "target_description": "发现并记录所有按钮、链接、卡片等元素",
      "expected_result": "记录完整的页面元素清单",
      "execution_strategy": "agentic",
      "is_critical": false
    },
    {
      "step_id": "step-003",
      "action_type": "click",
      "description": "点击创建智能体按钮",
      "target_description": "包含'创建'、'新建'或'+'的按钮",
      "expected_result": "进入智能体创建表单",
      "execution_strategy": "direct",
      "is_critical": true
    }
  ],
  "success_criteria": [
    "记录所有主要页面的结构",
    "验证CRUD流程可正常执行",
    "识别所有关键交互元素"
  ]
}
```

## 输出格式

你必须返回一个符合 `ExplorationPlan` schema 的JSON对象。

## 注意事项

1. **不要猜测具体的selector**：target_description 用自然语言描述即可
2. **步骤要具体**：避免"探索页面"这种模糊描述，要明确说"点击XX按钮"
3. **考虑失败场景**：非关键步骤失败时，后续步骤应该能继续
4. **避免破坏性操作**：遇到删除、支付等敏感操作，只探索入口，不实际执行
5. **适应性强**：页面结构可能与预期不同，步骤描述要支持模糊匹配
"""


class ExplorationPlanner:
    """探索规划器"""

    def __init__(self):
        self.capability_id = "site_exploration"

    async def create_plan(self, planner_input: PlannerInput) -> ExplorationPlan:
        """
        创建探索计划

        Args:
            planner_input: 规划器输入

        Returns:
            探索计划
        """
        # 构建规划提示词
        prompt = self._build_planning_prompt(planner_input)

        # 调用LLM生成计划
        plan_data = await self._call_planner_llm(prompt)

        # 解析并验证计划
        plan = self._parse_and_validate_plan(plan_data, planner_input)

        return plan

    def _build_planning_prompt(self, input_data: PlannerInput) -> str:
        """构建规划提示词"""
        return f"""
请为以下探索任务制定详细计划：

## 任务信息

**探索目标**：
{input_data.goal or "进行全面的站点探索"}

**探索范围**：
{input_data.scope or "无特定限制"}

**禁止路径**：
{input_data.forbidden_paths or "无"}

**起始URL**：
{input_data.start_url}

**约束条件**：
- 最大页面数：{input_data.max_pages}
- 最大动作数：{input_data.max_actions}
- 超时时间：{input_data.timeout_minutes}分钟

## 请输出探索计划

按照 ExplorationPlan schema 格式输出完整计划，包括：
1. 目标摘要和探索策略
2. 模块划分
3. 详细步骤列表
4. 成功标准

请确保计划：
- 符合探索目标
- 遵守范围约束
- 避开禁止路径
- 步骤清晰可执行
- 包含验证点
"""

    async def _call_planner_llm(self, prompt: str) -> dict:
        """调用LLM生成计划"""
        from langchain.agents import create_agent
        from langchain.agents.structured_output import ToolStrategy

        # 使用高质量模型进行规划
        selection = resolve_model_selection(self.capability_id)
        model = build_agent_model(selection)

        agent = create_agent(
            model=model,
            tools=[],
            system_prompt=PLANNER_SYSTEM_PROMPT,
            response_format=ToolStrategy(ExplorationPlan),
        )

        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": prompt}]
        })

        plan_data = result.get("structured_response")
        if plan_data is None:
            raise ValueError("规划器未返回有效计划")

        return plan_data.model_dump() if hasattr(plan_data, 'model_dump') else plan_data

    def _parse_and_validate_plan(self, plan_data: dict, input_data: PlannerInput) -> ExplorationPlan:
        """解析并验证计划"""
        # 确保plan_id
        if "plan_id" not in plan_data:
            plan_data["plan_id"] = f"plan-{input_data.run_id}"

        # 确保每个步骤有step_id
        for idx, step in enumerate(plan_data.get("steps", []), start=1):
            if "step_id" not in step:
                step["step_id"] = f"step-{idx:03d}"
            if "step_number" not in step:
                step["step_number"] = idx

        self._normalize_navigate_steps(plan_data.get("steps", []), input_data.start_url)

        # 验证步骤的范围约束
        scope_path = self._extract_scope_path(input_data.scope)
        forbidden_keywords = self._extract_forbidden_keywords(input_data.forbidden_paths)

        for step in plan_data.get("steps", []):
            # 验证范围
            if scope_path and step.get("action_type") == "navigate":
                target = step.get("target_description", "").lower()
                if scope_path.lower() not in target:
                    step["description"] += f" [范围约束: 必须在{scope_path}内]"

            # 验证禁止路径
            description = step.get("description", "").lower()
            for keyword in forbidden_keywords:
                if keyword in description:
                    step["is_critical"] = False
                    step["description"] += f" [警告: 涉及禁止关键词'{keyword}']"

        return ExplorationPlan(**plan_data)

    def _normalize_navigate_steps(self, steps: list[dict], start_url: str) -> None:
        """确保导航步骤使用真实 URL 或路径，不把自然语言描述传给浏览器。"""
        navigate_index = 0
        for step in steps:
            if step.get("action_type") != "navigate":
                continue

            navigate_index += 1
            target_selector = str(step.get("target_selector") or "").strip()
            target_description = str(step.get("target_description") or "").strip()

            if self._is_valid_navigation_target(target_selector):
                step["target_selector"] = target_selector
                continue

            if self._is_valid_navigation_target(target_description):
                step["target_selector"] = target_description
                continue

            if self._should_use_start_url_for_navigate(navigate_index, step) and self._is_valid_navigation_target(start_url):
                step["target_selector"] = start_url

    @staticmethod
    def _is_valid_navigation_target(value: str) -> bool:
        if not value:
            return False
        if value.startswith("/"):
            return True
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https", "about"} and bool(parsed.scheme)

    @staticmethod
    def _should_use_start_url_for_navigate(navigate_index: int, step: dict) -> bool:
        if navigate_index == 1:
            return True
        text = f"{step.get('description') or ''} {step.get('target_description') or ''}".lower()
        return any(keyword in text for keyword in ("起始", "首页", "工作台", "home", "start_url", "start url"))

    def _extract_scope_path(self, scope: str) -> str:
        """从scope中提取路径"""
        if not scope:
            return ""
        # 简单提取，可以更复杂
        import re
        path_match = re.search(r'/[a-zA-Z0-9/_-]+', scope)
        return path_match.group(0) if path_match else ""

    def _extract_forbidden_keywords(self, forbidden_paths: str) -> list[str]:
        """提取禁止关键词"""
        if not forbidden_paths:
            return []
        import re
        keywords = re.split(r'[,，;；\n]+', forbidden_paths)
        return [k.strip().lower() for k in keywords if k.strip()]


# 便捷函数
async def create_exploration_plan(
    run_id: str,
    title: str,
    goal: str,
    scope: str,
    forbidden_paths: str,
    start_url: str,
    **kwargs
) -> ExplorationPlan:
    """创建探索计划"""
    planner = ExplorationPlanner()
    planner_input = PlannerInput(
        run_id=run_id,
        title=title,
        goal=goal,
        scope=scope,
        forbidden_paths=forbidden_paths,
        start_url=start_url,
        **kwargs
    )
    return await planner.create_plan(planner_input)
