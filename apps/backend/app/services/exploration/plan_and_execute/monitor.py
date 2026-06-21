"""
Plan-and-Execute 模式 - Monitor & Re-planner（监控器和重新规划器）

负责监控执行过程，在遇到问题时触发重新规划
"""

from typing import Callable
from app.services.exploration.plan_and_execute.planner import ExplorationPlan, ExplorationStep, PlannerInput, ExplorationPlanner
from app.services.exploration.plan_and_execute.executor import StepExecutionResult


class ExecutionMonitor:
    """执行监控器"""

    def __init__(self, plan: ExplorationPlan, planner_input: PlannerInput):
        self.plan = plan
        self.planner_input = planner_input
        self.execution_history: list[StepExecutionResult] = []
        self.consecutive_failures = 0
        self.re_plan_count = 0
        self.max_re_plans = 3  # 最多重新规划3次

    def should_re_plan(self, result: StepExecutionResult, step: ExplorationStep) -> bool:
        """
        判断是否需要重新规划

        触发重新规划的条件：
        1. 连续3个步骤失败
        2. 关键步骤失败且无法继续
        3. 发现页面结构与预期不符
        """
        self.execution_history.append(result)

        if result.success:
            self.consecutive_failures = 0
            return False

        self.consecutive_failures += 1

        # 条件1: 连续失败
        if self.consecutive_failures >= 3:
            print(f"⚠️  连续 {self.consecutive_failures} 个步骤失败，触发重新规划")
            return True

        # 条件2: 关键步骤失败
        if step.is_critical and not result.success:
            print(f"⚠️  关键步骤失败: {step.description}，触发重新规划")
            return True

        return False

    async def re_plan(self, current_step_index: int, failure_context: str) -> ExplorationPlan | None:
        """
        重新规划

        Args:
            current_step_index: 当前步骤索引
            failure_context: 失败上下文

        Returns:
            新的计划，如果无法重新规划则返回None
        """
        if self.re_plan_count >= self.max_re_plans:
            print(f"❌ 已达到最大重新规划次数 ({self.max_re_plans})，停止规划")
            return None

        self.re_plan_count += 1
        print(f"\n🔄 开始第 {self.re_plan_count} 次重新规划...")

        # 构建重新规划的上下文
        executed_steps = self.plan.steps[:current_step_index]
        remaining_steps = self.plan.steps[current_step_index:]

        re_plan_goal = f"""
原始目标：
{self.planner_input.goal}

已完成的步骤：
{self._format_executed_steps(executed_steps)}

失败的步骤：
{remaining_steps[0].description if remaining_steps else "无"}

失败原因：
{failure_context}

请重新规划剩余步骤，考虑：
1. 实际页面结构可能与预期不同
2. 调整策略以绕过失败点
3. 保持目标不变，但可以改变路径
"""

        # 使用Planner生成新计划
        planner = ExplorationPlanner()
        new_planner_input = PlannerInput(
            run_id=self.planner_input.run_id,
            title=f"{self.planner_input.title} (Re-plan {self.re_plan_count})",
            goal=re_plan_goal,
            scope=self.planner_input.scope,
            forbidden_paths=self.planner_input.forbidden_paths,
            start_url=self.planner_input.start_url,
            max_pages=self.planner_input.max_pages,
            max_actions=self.planner_input.max_actions,
            timeout_minutes=self.planner_input.timeout_minutes,
        )

        try:
            new_plan = await planner.create_plan(new_planner_input)
            print(f"✓ 重新规划成功，生成 {len(new_plan.steps)} 个新步骤")
            return new_plan
        except Exception as e:
            print(f"✗ 重新规划失败: {str(e)}")
            return None

    def _format_executed_steps(self, steps: list[ExplorationStep]) -> str:
        """格式化已执行的步骤"""
        lines = []
        for idx, step in enumerate(steps, start=1):
            result = next((r for r in self.execution_history if r.step.step_id == step.step_id), None)
            status = "✓" if result and result.success else "✗"
            lines.append(f"{idx}. {status} {step.description}")
        return "\n".join(lines) if lines else "无"

    def get_execution_summary(self) -> dict:
        """获取执行摘要"""
        total = len(self.execution_history)
        successful = len([r for r in self.execution_history if r.success])
        failed = total - successful

        return {
            "total_steps_executed": total,
            "successful_steps": successful,
            "failed_steps": failed,
            "re_plan_count": self.re_plan_count,
            "consecutive_failures": self.consecutive_failures,
        }


class AdaptiveExecutionStrategy:
    """自适应执行策略"""

    @staticmethod
    def should_retry_step(result: StepExecutionResult, step: ExplorationStep, retry_count: int) -> bool:
        """判断是否应该重试步骤"""
        if retry_count >= step.max_retries:
            return False

        if not step.retry_on_failure:
            return False

        # 某些错误不值得重试
        error = result.error.lower()
        non_retryable_errors = [
            "未找到匹配元素",
            "元素不存在",
            "not found",
        ]

        for non_retryable in non_retryable_errors:
            if non_retryable in error:
                return False

        return True

    @staticmethod
    def should_skip_step(result: StepExecutionResult, step: ExplorationStep) -> bool:
        """判断是否应该跳过步骤"""
        # 非关键步骤失败可以跳过
        if not step.is_critical:
            return True

        return False

    @staticmethod
    def adjust_step_for_retry(step: ExplorationStep, previous_result: StepExecutionResult) -> ExplorationStep:
        """调整步骤以便重试"""
        # 可以在这里实现一些智能调整
        # 例如：放宽匹配条件、增加等待时间等
        adjusted = step.model_copy()

        # 如果是元素定位失败，可以尝试更宽松的描述
        if "未找到" in previous_result.error:
            # 提取关键词进行更模糊的匹配
            adjusted.target_description = adjusted.target_description.split("的")[0] if "的" in adjusted.target_description else adjusted.target_description

        return adjusted
