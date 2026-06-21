"""
Plan-and-Execute 模式 - Executor（执行器）

负责按照计划执行步骤，使用智能元素定位
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.exploration.browser_session import BrowserSessionError, PlaywrightBrowserSession, resolve_navigation_url
from app.services.exploration.time_utils import exploration_now_iso
from app.services.exploration.plan_and_execute.planner import ExplorationStep, ExplorationPlan


class StepExecutionResult:
    """步骤执行结果"""

    def __init__(
        self,
        step: ExplorationStep,
        success: bool,
        message: str = "",
        page_state: dict | None = None,
        screenshot_path: str = "",
        error: str = "",
        matched_element: dict | None = None,
    ):
        self.step = step
        self.success = success
        self.message = message
        self.page_state = page_state or {}
        self.screenshot_path = screenshot_path
        self.error = error
        self.matched_element = matched_element
        self.timestamp = exploration_now_iso()

    def to_dict(self) -> dict:
        return {
            "step_id": self.step.step_id,
            "step_number": self.step.step_number,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp,
            "screenshot_path": self.screenshot_path,
            "matched_element": self.matched_element,
        }


class PlanExecutor:
    """计划执行器"""

    def __init__(
        self,
        browser_session: PlaywrightBrowserSession,
        artifact_root: Path,
        plan: ExplorationPlan,
    ):
        self.browser = browser_session
        self.artifact_root = artifact_root
        self.plan = plan
        self.execution_log: list[StepExecutionResult] = []
        self.current_step_index = 0
        self.pages_visited: dict[str, dict] = {}  # {url: page_data}
        self.elements_discovered: list[dict] = []

    def execute_plan(self, on_step_complete=None, on_step_failed=None) -> dict:
        """
        执行完整计划

        Args:
            on_step_complete: 步骤完成回调 fn(step, result)
            on_step_failed: 步骤失败回调 fn(step, result, should_continue) -> bool

        Returns:
            执行结果摘要
        """
        print(f"开始执行计划: {self.plan.plan_id}")
        print(f"总共 {len(self.plan.steps)} 个步骤")

        for step in self.plan.steps:
            self.current_step_index += 1

            print(f"\n执行步骤 {step.step_number}/{len(self.plan.steps)}: {step.description}")

            # 执行步骤
            result = self._execute_step(step)
            self.execution_log.append(result)

            if result.success:
                print(f"✓ 步骤成功: {result.message}")
                if on_step_complete:
                    on_step_complete(step, result)
            else:
                print(f"✗ 步骤失败: {result.error}")

                # 处理失败
                should_continue = True
                if on_step_failed:
                    should_continue = on_step_failed(step, result, step.is_critical)
                elif step.is_critical:
                    should_continue = False

                if not should_continue:
                    print(f"关键步骤失败，停止执行")
                    break
                else:
                    print(f"非关键步骤失败，继续执行")

        return self._build_execution_summary()

    def _execute_step(self, step: ExplorationStep) -> StepExecutionResult:
        """执行单个步骤"""
        try:
            if step.action_type == "navigate":
                return self._execute_navigate(step)
            elif step.action_type == "click":
                return self._execute_click(step)
            elif step.action_type == "fill":
                return self._execute_fill(step)
            elif step.action_type == "wait":
                return self._execute_wait(step)
            elif step.action_type == "observe":
                return self._execute_observe(step)
            elif step.action_type == "check":
                return self._execute_check(step)
            else:
                return StepExecutionResult(
                    step=step,
                    success=False,
                    error=f"未知的动作类型: {step.action_type}"
                )
        except BrowserSessionError as e:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"浏览器错误: {str(e)}"
            )
        except Exception as e:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"执行异常: {str(e)}"
            )

    def _execute_navigate(self, step: ExplorationStep) -> StepExecutionResult:
        """执行导航"""
        raw_target = step.target_selector or step.target_description
        target_url = self._navigation_target(raw_target)
        if not target_url:
            return StepExecutionResult(
                step=step,
                success=False,
                error=(
                    "导航失败: 计划步骤缺少有效URL，"
                    f"请在 navigate 步骤的 target_selector 中填写完整URL或站内路径。当前目标: {raw_target}"
                ),
            )

        result = self.browser.navigate(target_url)

        if result.get("status") == "passed":
            observation = self.browser.observe()
            self._record_page_visit(observation)

            return StepExecutionResult(
                step=step,
                success=True,
                message=f"成功导航到 {result.get('after_url', target_url)}",
                page_state=observation,
            )
        else:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"导航失败: {result.get('error', 'unknown')}"
            )

    def _navigation_target(self, raw_target: str) -> str:
        target = str(raw_target or "").strip()
        if _is_absolute_navigation_target(target):
            return target
        if target.startswith("/"):
            resolved = resolve_navigation_url(target, str(getattr(self.browser, "start_url", "") or ""))
            if resolved != target:
                return resolved
        start_url = str(getattr(self.browser, "start_url", "") or "").strip()
        if self.current_step_index <= 1 and _is_absolute_navigation_target(start_url):
            return start_url
        return ""

    def _execute_click(self, step: ExplorationStep) -> StepExecutionResult:
        """执行点击"""
        # 1. 获取当前页面观察
        observation = self.browser.observe()

        # 2. 智能定位元素
        element = self._find_element(observation, step.target_description)

        if not element:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"未找到匹配元素: {step.target_description}"
            )

        # 3. 执行点击
        result = self.browser.click(element["id"])

        # 4. 获取点击后的页面状态
        observation_after = self.browser.observe()
        self._record_page_visit(observation_after)

        if result.get("status") in {"passed", "unverified"}:
            return StepExecutionResult(
                step=step,
                success=True,
                message=f"成功点击元素: {element.get('name', element['id'])}",
                page_state=observation_after,
                matched_element=element,
            )
        else:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"点击失败: {result.get('error', 'unknown')}",
                matched_element=element,
            )

    def _execute_fill(self, step: ExplorationStep) -> StepExecutionResult:
        """执行填充"""
        observation = self.browser.observe()
        element = self._find_element(observation, step.target_description)

        if not element:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"未找到输入框: {step.target_description}"
            )

        value = step.value or "AI_TEST_DATA"
        result = self.browser.fill(element["id"], value)

        observation_after = self.browser.observe()

        if result.get("status") in {"passed", "unverified"}:
            return StepExecutionResult(
                step=step,
                success=True,
                message=f"成功填充: {element.get('name', element['id'])} = {value}",
                page_state=observation_after,
                matched_element=element,
            )
        else:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"填充失败: {result.get('error', 'unknown')}",
                matched_element=element,
            )

    def _execute_wait(self, step: ExplorationStep) -> StepExecutionResult:
        """执行等待"""
        result = self.browser.wait()

        return StepExecutionResult(
            step=step,
            success=True,
            message="等待完成",
            page_state=self.browser.observe(),
        )

    def _execute_observe(self, step: ExplorationStep) -> StepExecutionResult:
        """执行观察 - 记录当前页面状态"""
        observation = self.browser.observe()
        self._record_page_visit(observation)

        # 统计页面上的元素
        elements = observation.get("elements", [])
        element_summary = {
            "total": len(elements),
            "buttons": len([e for e in elements if e.get("role") == "button"]),
            "links": len([e for e in elements if e.get("role") == "link"]),
            "inputs": len([e for e in elements if e.get("role") in {"textbox", "combobox"}]),
        }

        return StepExecutionResult(
            step=step,
            success=True,
            message=f"观察完成: 发现 {element_summary['total']} 个元素",
            page_state=observation,
        )

    def _execute_check(self, step: ExplorationStep) -> StepExecutionResult:
        """执行检查 - 验证条件"""
        observation = self.browser.observe()

        # 检查是否存在目标元素
        element = self._find_element(observation, step.target_description)

        if element:
            return StepExecutionResult(
                step=step,
                success=True,
                message=f"检查通过: 找到元素 {element.get('name', element['id'])}",
                page_state=observation,
                matched_element=element,
            )
        else:
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"检查失败: 未找到元素 {step.target_description}",
                page_state=observation,
            )

    def _find_element(self, observation: dict, description: str) -> dict | None:
        """
        智能元素定位

        支持多种匹配策略：
        1. 精确文本匹配
        2. 包含文本匹配
        3. 角色+文本组合
        4. 语义相似度匹配（未来可扩展）
        """
        elements = observation.get("elements", [])

        if not elements:
            return None

        description_lower = description.lower()

        # 策略1: 精确匹配
        for element in elements:
            name = str(element.get("name", "")).lower()
            text = str(element.get("text", "")).lower()

            if name == description_lower or text == description_lower:
                return element

        # 策略2: 包含匹配（name或text包含描述）
        for element in elements:
            name = str(element.get("name", "")).lower()
            text = str(element.get("text", "")).lower()

            if description_lower in name or description_lower in text:
                return element

        # 策略3: 描述包含元素名（反向匹配）
        for element in elements:
            name = str(element.get("name", "")).lower()
            text = str(element.get("text", "")).lower()

            if name and name in description_lower:
                return element
            if text and text in description_lower:
                return element

        # 策略4: 角色匹配
        # 例如描述是"点击按钮"，优先返回button角色的元素
        if "按钮" in description or "button" in description_lower:
            for element in elements:
                if element.get("role") == "button":
                    return element

        if "链接" in description or "link" in description_lower:
            for element in elements:
                if element.get("role") == "link":
                    return element

        if "输入" in description or "input" in description_lower or "文本框" in description:
            for element in elements:
                if element.get("role") in {"textbox", "combobox"}:
                    return element

        # 未找到匹配元素
        return None

    def _record_page_visit(self, observation: dict):
        """记录页面访问"""
        url = observation.get("url", "")
        if not url:
            return

        if url not in self.pages_visited:
            self.pages_visited[url] = {
                "url": url,
                "title": observation.get("title", ""),
                "visit_count": 0,
                "elements": observation.get("elements", []),
                "first_visited_at": exploration_now_iso(),
            }

        self.pages_visited[url]["visit_count"] += 1
        self.pages_visited[url]["last_visited_at"] = exploration_now_iso()

        # 记录新发现的元素
        for element in observation.get("elements", []):
            if element not in self.elements_discovered:
                self.elements_discovered.append(element)

    def _build_execution_summary(self) -> dict:
        """构建执行摘要"""
        total_steps = len(self.plan.steps)
        executed_steps = len(self.execution_log)
        successful_steps = len([r for r in self.execution_log if r.success])
        failed_steps = executed_steps - successful_steps

        return {
            "plan_id": self.plan.plan_id,
            "total_steps": total_steps,
            "executed_steps": executed_steps,
            "successful_steps": successful_steps,
            "failed_steps": failed_steps,
            "success_rate": successful_steps / executed_steps if executed_steps > 0 else 0,
            "pages_visited": len(self.pages_visited),
            "elements_discovered": len(self.elements_discovered),
            "execution_log": [r.to_dict() for r in self.execution_log],
            "pages": list(self.pages_visited.values()),
            "status": "completed" if executed_steps == total_steps else "partial",
        }


def _is_valid_navigation_target(value: str) -> bool:
    if not value:
        return False
    if value.startswith("/"):
        return True
    return _is_absolute_navigation_target(value)


def _is_absolute_navigation_target(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "about"} and bool(parsed.scheme)
