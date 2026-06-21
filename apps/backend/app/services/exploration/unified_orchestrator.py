"""
统一探索编排器 - Unified Exploration Orchestrator

整合 Plan-and-Execute 和 Agentic Loop，提供统一的探索接口
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Literal

import yaml

from app.core.db import connect
from app.core.storage import store_path
from app.repositories import exploration_repo
from app.services.exploration import event_bus
from app.services.exploration.time_utils import exploration_now_iso
from app.services.exploration.browser_session import PlaywrightBrowserSession, BrowserSessionError
from app.services.exploration.plan_and_execute.planner import (
    ExplorationPlanner,
    ExplorationPlan,
    ExplorationStep,
    PlannerInput,
)
from app.services.exploration.plan_and_execute.executor import PlanExecutor, StepExecutionResult
from app.services.exploration.plan_and_execute.monitor import ExecutionMonitor


PLANNING_TIMEOUT_MAX_SECONDS = 180
AGENTIC_DECISION_TIMEOUT_SECONDS = 90


class UnifiedExplorationOrchestrator:
    """
    统一探索编排器

    策略：
    1. 所有探索都先进行 Planning
    2. 根据计划类型选择执行策略：
       - 明确步骤 → Direct Execution（直接执行）
       - 探索类步骤 → Agentic Execution（Agent自主执行）
    3. 统一的监控和重新规划机制
    """

    def __init__(
        self,
        run_id: str,
        artifact_root: Path,
        start_url: str,
        forbidden_paths: str = "",
        storage_state_path: str = "",
    ):
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.start_url = start_url
        self.forbidden_paths = forbidden_paths
        self.storage_state_path = storage_state_path

        self.plan: ExplorationPlan | None = None
        self.monitor: ExecutionMonitor | None = None
        self.executor: PlanExecutor | None = None

        self.log_lines: list[str] = []
        self.pages_discovered: list[dict] = []
        self.elements_discovered: list[dict] = []
        self.run_context: dict = {}
        self.live_progress: dict = {
            "modules": {},
            "plan": {},
            "events": [],
        }

    async def run(self) -> dict:
        """运行统一探索流程"""
        try:
            # 立即发布开始事件，确保前端能收到
            self._publish("orchestrator_initialized", {
                "message": "统一探索编排器已初始化",
                "start_url": self.start_url,
            })

            run = self._load_run()
            if not run:
                error_msg = "探索任务不存在"
                self._publish("error", {"message": error_msg})
                return self._error_result(error_msg)

            self._log("run_started", message=f"开始统一探索: {run['title']}")
            self._publish("run_started", {"status": "running", "mode": "unified"})
            self.run_context = self._build_run_context(run)
        except Exception as e:
            error_msg = f"初始化阶段异常: {str(e)}"
            self._publish("error", {"message": error_msg})
            return self._error_result(error_msg)

        try:
            # Phase 1: Planning - 所有探索都先规划
            self._log("planning_started", message="分析目标并生成探索计划...")
            self._publish("planning_started", {"message": "正在智能分析探索目标..."})
            self._record_lifecycle_progress("正在智能分析探索目标并生成探索计划。")

            initial_module = self._initial_module_key(run)
            self._publish_lifecycle_step(
                step_id="planning-started",
                step_type="planning",
                title="生成探索计划",
                detail="正在分析探索目标并生成执行步骤。",
                status="running",
                module_key=initial_module,
            )

            planner_input = self._build_planner_input(run)
            self.plan = await self._create_smart_plan(planner_input)
            self._write_plan_artifact(self.plan)
            self._persist_plan_progress(self.plan)

            self._log(
                "planning_completed",
                plan_id=self.plan.plan_id,
                total_steps=len(self.plan.steps),
                modules=self.plan.modules,
                strategy=self.plan.strategy,
            )
            self._publish("planning_completed", {
                "plan_id": self.plan.plan_id,
                "goal_summary": self.plan.goal_summary,
                "scope_summary": self.plan.scope_summary,
                "total_steps": len(self.plan.steps),
                "modules": self.plan.modules,
                "strategy": self.plan.strategy,
                "estimated_duration_minutes": self.plan.estimated_duration_minutes,
                "risk_assessment": self.plan.risk_assessment,
                "success_criteria": self.plan.success_criteria,
                "steps": [self._step_plan_payload(step) for step in self.plan.steps],
            })
            self._record_lifecycle_progress(
                f"探索计划已生成：{len(self.plan.steps)} 个执行步骤，{len(self.plan.modules)} 个模块，准备执行。"
            )
            self._publish_lifecycle_step(
                step_id="planning-completed",
                step_type="planning",
                title="探索计划已生成",
                detail=f"已生成 {len(self.plan.steps)} 个执行步骤，包含 {len(self.plan.modules)} 个模块。",
                status="completed",
                module_key=initial_module,
            )

            # Phase 2: Execution - 智能执行
            self._log("execution_started", message="开始执行探索计划...")
            self._publish("execution_started", {"plan_id": self.plan.plan_id, "total_steps": len(self.plan.steps)})
            self._record_lifecycle_progress(f"开始执行探索计划，共 {len(self.plan.steps)} 个步骤。")
            self._publish_lifecycle_step(
                step_id="execution-started",
                step_type="execution",
                title="开始执行探索",
                detail=f"即将执行 {len(self.plan.steps)} 个步骤。",
                status="running",
                module_key=initial_module,
            )

            self.monitor = ExecutionMonitor(self.plan, planner_input)

            with PlaywrightBrowserSession(
                start_url=self.start_url,
                storage_state_path=self.storage_state_path,
                timeout_seconds=45,
                run_id=self.run_id,
            ) as browser_session:

                self.executor = PlanExecutor(
                    browser_session=browser_session,
                    artifact_root=self.artifact_root,
                    plan=self.plan,
                )

                result = await self._execute_unified(browser_session, planner_input)

            # Phase 3: Result
            self._publish_lifecycle_step(
                step_id="execution-completed",
                step_type="execution",
                title="探索执行完成",
                detail=f"已完成所有步骤，状态：{result.get('status', 'completed')}。",
                status="completed",
                module_key=initial_module,
            )

            return self._build_final_result(result)

        except Exception as e:
            error_message = self._exception_message(e)
            self._log("error", message=error_message)
            self._publish("error", {"message": error_message})
            self._record_live_failure(error_message)
            return self._error_result(error_message)

    async def _create_smart_plan(self, planner_input: PlannerInput) -> ExplorationPlan:
        """
        智能规划：根据目标类型生成合适的计划

        策略：
        - 明确的步骤目标 → 生成精确步骤计划
        - 模糊的探索目标 → 生成探索式计划（包含 agentic 步骤）
        """
        planner = ExplorationPlanner()
        try:
            plan = await asyncio.wait_for(
                planner.create_plan(planner_input),
                timeout=min(max(planner_input.timeout_minutes * 60, 60), PLANNING_TIMEOUT_MAX_SECONDS),
            )
        except asyncio.TimeoutError:
            timeout_message = self._exception_message(asyncio.TimeoutError())
            self._log("planning_fallback", message=timeout_message)
            self._publish("planning_fallback", {"message": timeout_message})
            plan = self._fallback_plan(planner_input, timeout_message)

        # 分析计划并标记执行策略
        plan = self._annotate_execution_strategy(plan)

        return plan

    def _fallback_plan(self, planner_input: PlannerInput, reason: str) -> ExplorationPlan:
        module_name = (planner_input.scope or planner_input.title or "站点入口").splitlines()[0][:80]
        return ExplorationPlan(
            plan_id=f"fallback-{planner_input.run_id}",
            goal_summary=planner_input.goal or planner_input.title or "站点探索",
            scope_summary=planner_input.scope or "未限定探索范围",
            strategy=f"模型规划超时后使用本地兜底计划。{reason}",
            modules=[module_name],
            steps=[
                ExplorationStep(
                    step_id="fallback-step-001",
                    step_number=1,
                    action_type="navigate",
                    description="进入探索起始页面",
                    target_description=planner_input.start_url,
                    target_selector=planner_input.start_url,
                    expected_result="页面加载完成，可以观察页面结构。",
                    module_name=module_name,
                    is_critical=True,
                    retry_on_failure=True,
                    max_retries=1,
                    execution_strategy="direct",
                ),
                ExplorationStep(
                    step_id="fallback-step-002",
                    step_number=2,
                    action_type="observe",
                    description="记录起始页面结构",
                    target_description="当前页面",
                    expected_result="记录当前页面的主要元素和页面事实。",
                    module_name=module_name,
                    is_critical=True,
                    retry_on_failure=True,
                    max_retries=1,
                    execution_strategy="direct",
                ),
                ExplorationStep(
                    step_id="fallback-step-003",
                    step_number=3,
                    action_type="agentic_explore",
                    description="基于当前页面和探索目标继续自主探索",
                    target_description=planner_input.goal or planner_input.scope or "当前页面可交互元素",
                    expected_result="根据探索目标记录关键页面、元素和阻塞项。",
                    module_name=module_name,
                    is_critical=False,
                    retry_on_failure=False,
                    max_retries=0,
                    execution_strategy="agentic",
                ),
            ],
            estimated_duration_minutes=min(max(planner_input.timeout_minutes, 1), 30),
            risk_assessment="兜底计划未经过模型完整规划，只执行起始页观察和受保护的自主探索。",
            success_criteria=["成功进入起始页面", "记录页面结构和关键可交互元素"],
        )

    def _annotate_execution_strategy(self, plan: ExplorationPlan) -> ExplorationPlan:
        """
        为每个步骤标注执行策略

        策略类型：
        - direct: 直接执行（目标明确）
        - agentic: Agent自主执行（需要探索）
        """
        for step in plan.steps:
            # 判断步骤类型
            if step.action_type == "agentic_explore":
                step.execution_strategy = "agentic"
            elif step.action_type in {"navigate", "wait", "observe"}:
                # 导航、等待、观察 → 直接执行
                step.execution_strategy = "direct"
            elif step.action_type in {"click", "fill"} and step.target_description:
                # 有明确目标描述 → 直接执行
                step.execution_strategy = "direct"
            elif step.action_type == "check":
                # 检查验证 → 直接执行
                step.execution_strategy = "direct"
            elif "探索" in step.description or "发现" in step.description:
                # 包含探索关键词 → Agent执行
                step.execution_strategy = "agentic"
            else:
                # 默认直接执行
                step.execution_strategy = "direct"

        return plan

    async def _execute_unified(
        self,
        browser_session: PlaywrightBrowserSession,
        planner_input: PlannerInput,
    ) -> dict:
        """
        统一执行：根据步骤策略选择执行方式
        """
        retry_counts = {}

        for step_index, step in enumerate(self.plan.steps):
            if self._cancel_requested():
                self._publish("exploration_cancelled", {"reason": "用户取消探索"})
                return {"status": "cancelled", "message": "用户取消探索"}

            started_at = exploration_now_iso()
            started_perf = time.perf_counter()
            attempt = retry_counts.get(step.step_id, 0) + 1

            # 发布步骤开始事件
            self._publish(
                "step_started",
                {
                    **self._step_plan_payload(step),
                    "total_steps": len(self.plan.steps),
                    "attempt": attempt,
                    "started_at": started_at,
                },
            )

            # 发布步骤记录事件（状态：运行中）
            self._publish_step_recorded(step, None, status="running")

            # 根据执行策略选择执行方式
            execution_strategy = getattr(step, "execution_strategy", "direct")

            if execution_strategy == "agentic":
                # Agentic 执行：使用 Agent 自主探索
                self._log("agentic_step_started", step_id=step.step_id, description=step.description)
                result = await self._execute_agentic_step(step, browser_session)
            else:
                # Direct 执行：直接执行
                self._log("direct_step_started", step_id=step.step_id, description=step.description)
                result = self.executor._execute_step(step)

            self.executor.execution_log.append(result)

            self._log_step_result(step, result)

            # 发布步骤完成事件
            final_status = "completed" if result.success else "failed"
            self._publish_step_recorded(step, result, status=final_status)
            result_payload = self._step_result_payload(
                step,
                result,
                total_steps=len(self.plan.steps),
                attempt=attempt,
                started_at=started_at,
                duration_ms=int((time.perf_counter() - started_perf) * 1000),
            )

            if result.success:
                self._publish("step_completed", result_payload)
            else:
                self._publish("step_failed", result_payload)

            # 处理执行结果（失败处理、重试、重新规划等）
            should_continue = await self._handle_step_result(
                step, result, step_index, planner_input, retry_counts
            )

            if not should_continue:
                break

        self._publish("execution_completed", {"total_steps": len(self.plan.steps)})
        return {"status": "completed", "message": "探索完成"}

    async def _execute_agentic_step(
        self,
        step: ExplorationStep,
        browser_session: PlaywrightBrowserSession,
    ) -> StepExecutionResult:
        """
        Agentic 步骤执行：使用 Agent 自主决策并执行

        适用场景：
        - "探索页面上的所有按钮"
        - "发现所有可点击元素"
        - "测试所有表单字段"
        """
        from app.agents.site_exploration.execution_decision import service as agentic_service
        from app.agents.site_exploration.execution_decision.schemas import AgenticExplorationInput

        observation = browser_session.observe()

        # 构建 Agent 输入
        agent_input = AgenticExplorationInput(
            run={
                "id": self.run_id,
                "title": self.run_context.get("title", ""),
                "goal": self.run_context.get("goal", ""),
                "scope": self.run_context.get("scope", ""),
                "forbidden_paths": self.run_context.get("forbidden_paths", ""),
                "current_step": step.description,
                "current_step_target": step.target_description or "",
                "crud_test_data_name": f"AI_EXPLORE_{self.run_id[:8]}",
            },
            budget={
                "remaining_turns": 5,  # 限制Agent的探索深度
                "remaining_pages": 10,
                "remaining_actions": 20,
            },
            history_summary="",
            current_observation={
                "url": observation.get("url", ""),
                "title": observation.get("title", ""),
                "elements": observation.get("elements", [])[:50],  # 限制元素数量
            },
        )

        try:
            # 调用 Agent 决策
            decision = await asyncio.wait_for(
                agentic_service.decide_next_action(agent_input),
                timeout=AGENTIC_DECISION_TIMEOUT_SECONDS,
            )

            # 执行 Agent 决策的动作
            if decision.action and decision.decision_type == "act":
                result = self._execute_agentic_action(decision.action, browser_session)
                success = result.get("status") in {"passed", "unverified"}
                page_state = browser_session.observe()
                self.executor._record_page_visit(page_state)
                return StepExecutionResult(
                    step=step,
                    success=success,
                    message=f"Agent决策并执行: {decision.reason}",
                    error="" if success else str(result.get("error") or result.get("reason") or "Agent动作执行失败"),
                    page_state=page_state,
                )
            if decision.decision_type == "block":
                return StepExecutionResult(
                    step=step,
                    success=False,
                    error=f"Agent阻塞: {decision.reason}",
                    page_state=observation,
                )
            else:
                # Agent 决定跳过或完成
                return StepExecutionResult(
                    step=step,
                    success=True,
                    message=f"Agent决策: {decision.reason}",
                    page_state=observation,
                )

        except asyncio.TimeoutError:
            return StepExecutionResult(
                step=step,
                success=False,
                error="Agent 决策超时：大模型在 90 秒内未返回下一步动作，请检查站点探索模型配置或稍后重试。",
                page_state=observation,
            )
        except Exception as e:
            error_detail = str(e).strip() or type(e).__name__
            return StepExecutionResult(
                step=step,
                success=False,
                error=f"Agent执行失败: {error_detail}",
                page_state=observation,
            )

    def _execute_agentic_action(self, action, browser_session: PlaywrightBrowserSession) -> dict:
        if action.type == "click":
            return browser_session.click(action.target_element_id)
        if action.type == "fill":
            return browser_session.fill(action.target_element_id, action.value or "AI_TEST_DATA")
        if action.type == "navigate":
            return browser_session.navigate(action.url)
        if action.type == "go_back":
            return browser_session.go_back()
        if action.type == "close_modal":
            return browser_session.close_modal()
        if action.type == "wait":
            return browser_session.wait()
        if action.type == "record_state":
            return {"status": "passed"}
        return {"status": "skipped", "reason": f"Unsupported action: {action.type}"}

    async def _handle_step_result(
        self,
        step: ExplorationStep,
        result: StepExecutionResult,
        step_index: int,
        planner_input: PlannerInput,
        retry_counts: dict,
    ) -> bool:
        """
        处理步骤执行结果

        Returns:
            bool: 是否应该继续执行
        """
        if result.success:
            retry_counts[step.step_id] = 0
            return True

        # 步骤失败处理
        self._log("step_failed", step_id=step.step_id, error=result.error)

        # 策略1: 重试
        from app.services.exploration.plan_and_execute.monitor import AdaptiveExecutionStrategy

        retry_count = retry_counts.get(step.step_id, 0)
        if AdaptiveExecutionStrategy.should_retry_step(result, step, retry_count):
            retry_counts[step.step_id] = retry_count + 1
            self._publish("step_retrying", {
                **self._step_plan_payload(step),
                "attempt": retry_counts[step.step_id] + 1,
                "previous_error": result.error,
            })
            adjusted_step = AdaptiveExecutionStrategy.adjust_step_for_retry(step, result)
            retry_result = self.executor._execute_step(adjusted_step)

            if retry_result.success:
                self._publish("step_completed", self._step_result_payload(step, retry_result, attempt=retry_counts[step.step_id] + 1))
                return True

        # 策略2: 跳过非关键步骤
        if AdaptiveExecutionStrategy.should_skip_step(result, step):
            self._publish("step_skipped", {
                **self._step_plan_payload(step),
                "step_number": step.step_number,
                "description": step.description,
                "reason": result.error,
            })
            return True

        # 策略3: 重新规划
        if self.monitor.should_re_plan(result, step):
            self._publish("re_planning_started", {
                "reason": "遇到阻塞，正在重新规划...",
            })

            new_plan = await self.monitor.re_plan(step_index, result.error)

            if new_plan:
                new_plan = self._annotate_execution_strategy(new_plan)
                self.plan = new_plan
                self.executor.plan = new_plan

                self._publish("re_planning_completed", {
                    "new_steps": len(new_plan.steps),
                    "message": "已生成新计划，继续执行",
                })

                self.monitor.consecutive_failures = 0
                return True
            else:
                return False

        # 策略4: 关键步骤失败，终止
        if step.is_critical:
            return False

        return True

    def _build_planner_input(self, run) -> PlannerInput:
        """构建规划器输入"""
        return PlannerInput(
            run_id=self.run_id,
            title=run["title"],
            goal=self._run_value(run, "goal", ""),
            scope=self._run_value(run, "scope", ""),
            forbidden_paths=self.forbidden_paths or self._run_value(run, "forbidden_paths", ""),
            start_url=self.start_url,
            max_pages=self._run_value(run, "max_pages", 50),
            max_actions=self._run_value(run, "max_actions", 1000),
            timeout_minutes=self._run_value(run, "timeout_minutes", 120),
        )

    def _build_run_context(self, run) -> dict:
        return {
            "title": self._run_value(run, "title", ""),
            "goal": self._run_value(run, "goal", ""),
            "scope": self._run_value(run, "scope", ""),
            "forbidden_paths": self.forbidden_paths or self._run_value(run, "forbidden_paths", ""),
        }

    def _build_final_result(self, execution_result: dict) -> dict:
        """构建最终结果"""
        if not self.executor:
            return execution_result

        summary = self.executor._build_execution_summary()

        page_artifacts = self._build_structured_pages(summary)
        log_content, log_path = self._write_log()

        return {
            "status": execution_result.get("status", "completed"),
            "summary": execution_result.get("message", "探索完成"),
            "plan_id": self.plan.plan_id if self.plan else "",
            "execution_summary": summary,
            "monitor_summary": self.monitor.get_execution_summary() if self.monitor else {},
            "pages_visited": summary.get("pages_visited", 0),
            "elements_discovered": summary.get("elements_discovered", 0),
            "structured_pages": page_artifacts,
            "graph": self._build_graph(page_artifacts),
            "action_count": summary.get("executed_steps", 0),
            "field_count": self._count_fields(summary.get("pages", [])),
            "state_transition_count": summary.get("successful_steps", 0),
            "discovery": {
                "discovered_link_count": self._count_role(summary.get("pages", []), "link"),
                "same_origin_link_count": self._count_role(summary.get("pages", []), "link"),
            },
            "modules": self.plan.modules if self.plan else [],
            "pages": summary.get("pages", []),
            "log_path": store_path(log_path) or "",
            "log": log_content + ("\n" if log_content else ""),
        }

    def _error_result(self, message: str) -> dict:
        """错误结果"""
        log_content, log_path = self._write_log()
        return {
            "status": "blocked",
            "summary": message,
            "reason_type": "unified_orchestrator_failed",
            "suggested_action": "检查统一探索编排器日志、浏览器会话和模型调用配置后重试。",
            "log_path": store_path(log_path) or "",
            "log": log_content,
        }

    def _exception_message(self, error: Exception) -> str:
        if isinstance(error, asyncio.TimeoutError):
            return (
                f"探索计划生成超时：大模型在 {PLANNING_TIMEOUT_MAX_SECONDS} 秒内未返回可执行探索计划，"
                "请检查模型服务可用性、模型配置或缩小探索目标后重试。"
            )
        detail = str(error).strip()
        if detail:
            return f"探索执行异常: {type(error).__name__}: {detail}"
        return f"探索执行异常: {type(error).__name__}"

    def _write_log(self) -> tuple[str, Path]:
        log_content = "\n".join(self.log_lines)
        if log_content:
            log_content += "\n"
        log_path = self.artifact_root / "logs" / "run.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(log_content, encoding="utf-8")
        return log_content, log_path

    def _write_plan_artifact(self, plan: ExplorationPlan) -> None:
        plan_path = self.artifact_root / "exploration-plan.yaml"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            yaml.safe_dump(plan.model_dump(), allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )

    def _build_structured_pages(self, summary: dict) -> list[dict]:
        pages = summary.get("pages", [])
        if not isinstance(pages, list):
            return []
        structured_pages = []
        for index, page_data in enumerate(pages, start=1):
            if not isinstance(page_data, dict):
                continue
            url = str(page_data.get("url") or "")
            elements = page_data.get("elements") if isinstance(page_data.get("elements"), list) else []
            page_id = f"page-{index:03d}"
            structured_pages.append(
                {
                    "page": {
                        "id": page_id,
                        "url": url,
                        "title": str(page_data.get("title") or url or f"页面 {index}"),
                        "normalized_url": url,
                        "module": self._module_for_page(index),
                        "depth": 0,
                        "status": "explored",
                        "structure_summary": f"统一探索采集到 {len(elements)} 个可观察元素。",
                    },
                    "accessibility_tree": [self._accessibility_node(element) for element in elements],
                    "actions": self._actions_from_execution_log(page_id),
                    "forms": [],
                    "tables": [],
                    "relations": {"incoming_edges": [], "outgoing_edges": []},
                    "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
                }
            )
        return structured_pages

    def _module_for_page(self, index: int) -> str:
        if self.plan and self.plan.modules:
            return self.plan.modules[min(index - 1, len(self.plan.modules) - 1)]
        return "统一探索"

    def _accessibility_node(self, element: dict) -> dict:
        name = str(element.get("name") or element.get("text") or element.get("id") or "")
        return {
            "role": str(element.get("role") or element.get("tag") or "element"),
            "name": name,
            "locator_hint": str(element.get("id") or element.get("selector") or ""),
            "fallback_locator": str(element.get("selector") or element.get("id") or ""),
        }

    def _actions_from_execution_log(self, page_id: str) -> list[dict]:
        if not self.executor:
            return []
        actions = []
        for result in self.executor.execution_log:
            action_type = result.step.action_type
            if action_type not in {"click", "fill", "navigate", "check", "observe"}:
                continue
            actions.append(
                {
                    "id": f"{page_id}-action-{len(actions) + 1:03d}",
                    "type": action_type,
                    "target": result.step.target_description or result.step.description,
                    "status": "passed" if result.success else "failed",
                    "result": result.message if result.success else result.error,
                }
            )
        return actions

    def _build_graph(self, page_artifacts: list[dict]) -> dict:
        nodes = []
        for page_artifact in page_artifacts:
            page = page_artifact["page"]
            nodes.append({"id": page["id"], "title": page["title"], "url": page["url"]})
        return {"nodes": nodes, "edges": [], "paths": []}

    def _count_fields(self, pages: list[dict]) -> int:
        return sum(
            1
            for page in pages
            if isinstance(page, dict)
            for element in page.get("elements", [])
            if isinstance(element, dict) and element.get("role") in {"textbox", "combobox", "checkbox", "radio"}
        )

    def _count_role(self, pages: list[dict], role: str) -> int:
        return sum(
            1
            for page in pages
            if isinstance(page, dict)
            for element in page.get("elements", [])
            if isinstance(element, dict) and element.get("role") == role
        )

    def _load_run(self):
        """加载探索任务"""
        with connect() as db:
            return exploration_repo.find_by_id(db, self.run_id)

    def _cancel_requested(self) -> bool:
        """检查是否请求取消"""
        with connect() as db:
            run = exploration_repo.find_by_id(db, self.run_id)
            return bool(run and run["status"] == "stopping")

    def _log(self, event: str, **payload):
        """记录日志"""
        log_entry = json.dumps({
            "ts": exploration_now_iso(),
            "event": event,
            **payload
        }, ensure_ascii=False)
        self.log_lines.append(log_entry)

    def _log_step_result(self, step, result: StepExecutionResult):
        """记录步骤结果"""
        self._log(
            "step_executed",
            step_id=step.step_id,
            step_number=step.step_number,
            description=step.description,
            success=result.success,
            message=result.message if result.success else result.error,
        )

    def _step_plan_payload(self, step: ExplorationStep) -> dict:
        """构建可直接推给前端监控视图的步骤计划字段。"""
        return {
            "step_id": step.step_id,
            "step_number": step.step_number,
            "module_name": step.module_name,
            "action_type": step.action_type,
            "description": step.description,
            "target_description": step.target_description,
            "target_selector": step.target_selector,
            "value": self._safe_step_value(step),
            "expected_result": step.expected_result,
            "execution_strategy": getattr(step, "execution_strategy", "direct"),
            "is_critical": step.is_critical,
            "retry_on_failure": step.retry_on_failure,
            "max_retries": step.max_retries,
        }

    def _step_result_payload(
        self,
        step: ExplorationStep,
        result: StepExecutionResult,
        *,
        total_steps: int | None = None,
        attempt: int | None = None,
        started_at: str | None = None,
        duration_ms: int | None = None,
    ) -> dict:
        payload = {
            **self._step_plan_payload(step),
            "success": result.success,
            "message": result.message,
            "error": result.error,
            "failure_type": self._failure_type(result.error),
            "retryable": bool(step.retry_on_failure and not result.success),
            "matched_element": self._safe_matched_element(result.matched_element),
            "page_state": self._page_state_summary(result.page_state),
            "screenshot_path": result.screenshot_path,
            "completed_at": result.timestamp,
        }
        if total_steps is not None:
            payload["total_steps"] = total_steps
        if attempt is not None:
            payload["attempt"] = attempt
        if started_at is not None:
            payload["started_at"] = started_at
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        return payload

    def _safe_step_value(self, step: ExplorationStep) -> str:
        if step.action_type != "fill" or not step.value:
            return step.value
        return "******"

    def _safe_matched_element(self, element: dict | None) -> dict:
        if not isinstance(element, dict):
            return {}
        return {
            "id": str(element.get("id") or ""),
            "role": str(element.get("role") or element.get("tag") or ""),
            "name": str(element.get("name") or element.get("text") or ""),
            "selector": str(element.get("selector") or ""),
        }

    def _page_state_summary(self, page_state: dict | None) -> dict:
        if not isinstance(page_state, dict):
            return {}
        elements = page_state.get("elements")
        element_count = len(elements) if isinstance(elements, list) else 0
        return {
            "url": str(page_state.get("url") or ""),
            "title": str(page_state.get("title") or ""),
            "element_count": element_count,
        }

    def _failure_type(self, error: str) -> str:
        if not error:
            return ""
        if "未找到" in error:
            return "element_not_found"
        if "导航失败" in error:
            return "navigation_failed"
        if "浏览器错误" in error:
            return "browser_error"
        return "execution_error"

    def _publish_step_recorded(self, step: ExplorationStep, result: StepExecutionResult | None, *, status: str) -> None:
        page_state = result.page_state if result and isinstance(result.page_state, dict) else {}
        page_id = self._page_id_for_state(page_state)
        module_key = self._module_key_for_step(step)

        # 构建步骤消息
        if result:
            detail = result.message if result.success else (result.error or "")
        else:
            detail = f"正在执行：{step.description}"

        step_payload = {
            "id": step.step_id,
            "type": step.action_type or "event",
            "title": step.description or step.target_description or "探索步骤",
            "detail": detail,
            "status": status,
            "occurred_at": exploration_now_iso(),
            "artifact_path": "",
            "source": "unified_orchestrator",
        }
        self._record_live_step(module_key=module_key, page_id=page_id, step=step_payload, page_state=page_state)
        self._publish(
            "step_recorded",
            {
                "module_key": module_key,
                "page_id": page_id,
                "step": step_payload,
            },
        )

    def _publish_lifecycle_step(
        self,
        *,
        step_id: str,
        step_type: str,
        title: str,
        detail: str,
        status: str,
        module_key: str,
    ) -> None:
        step_payload = {
            "id": step_id,
            "type": step_type,
            "title": title,
            "detail": detail,
            "status": status,
            "occurred_at": exploration_now_iso(),
            "artifact_path": "",
            "source": "unified_orchestrator",
        }
        self._record_live_step(module_key=module_key, page_id="lifecycle", step=step_payload, page_state={})
        self._publish(
            "step_recorded",
            {
                "module_key": module_key,
                "page_id": "lifecycle",
                "step": step_payload,
            },
        )

    def _module_key_for_step(self, step: ExplorationStep) -> str:
        module_name = str(step.module_name or self._module_for_page(1) or "")
        with connect() as db:
            modules = exploration_repo.list_module_coverages(db, self.run_id)
        for module in modules:
            if str(module["module_name"]) == module_name:
                return str(module["module_key"])
        for module in modules:
            persisted_name = str(module["module_name"] or "")
            if persisted_name and (persisted_name in module_name or module_name in persisted_name):
                return str(module["module_key"])
        return module_name or "site-entry"

    def _record_lifecycle_progress(self, summary: str) -> None:
        with connect() as db:
            run = exploration_repo.find_by_id(db, self.run_id)
            if not run:
                return
            exploration_repo.update_run_state(
                db,
                self.run_id,
                status=run["status"],
                result_summary=summary,
            )

            # 发布运行状态更新事件，通知前端进度变化
            self._publish("run_status_updated", {
                "status": run["status"],
                "result_summary": summary,
            })

            modules = exploration_repo.list_module_coverages(db, self.run_id)
            if not modules:
                return
            module = modules[0]
            exploration_repo.update_module_coverage(
                db,
                exploration_run_id=self.run_id,
                module_key=module["module_key"],
                module_name=module["module_name"],
                entry_path=module["entry_path"],
                planned_page_count=module["planned_page_count"],
                explored_page_count=module["explored_page_count"],
                blocked_page_count=module["blocked_page_count"],
                action_count=module["action_count"],
                field_count=module["field_count"],
                state_transition_count=module["state_transition_count"],
                completion_status=run["status"],
                completion_summary=summary,
            )

            # 发布模块更新事件，通知前端模块进度变化
            self._publish("module_updated", {
                "module_id": module["id"],
                "module_key": module["module_key"],
                "module_name": module["module_name"],
                "entry_path": module["entry_path"],
                "planned_page_count": module["planned_page_count"],
                "explored_page_count": module["explored_page_count"],
                "blocked_page_count": module["blocked_page_count"],
                "action_count": module["action_count"],
                "field_count": module["field_count"],
                "state_transition_count": module["state_transition_count"],
                "completion_status": run["status"],
                "completion_summary": summary,
            })

    def _persist_plan_progress(self, plan: ExplorationPlan) -> None:
        self.live_progress["plan"] = plan.model_dump()
        with connect() as db:
            modules = exploration_repo.list_module_coverages(db, self.run_id)
        module_key_by_name = {str(module["module_name"]): str(module["module_key"]) for module in modules}
        fallback_key = str(modules[0]["module_key"]) if modules else "site-entry"
        grouped_steps: dict[str, list[dict]] = {}
        for index, step in enumerate(plan.steps, start=1):
            module_key = module_key_by_name.get(str(step.module_name or ""), fallback_key)
            grouped_steps.setdefault(module_key, []).append(
                {
                    "id": step.step_id or f"step-{index:03d}",
                    "type": step.action_type or "planned_step",
                    "title": step.description or step.target_description or f"探索步骤 {index}",
                    "detail": step.expected_result or step.description or "",
                    "status": "pending",
                    "occurred_at": "",
                    "artifact_path": "exploration-plan.yaml",
                    "source": "exploration_plan",
                }
            )
        for module in modules:
            module_key = str(module["module_key"])
            self._ensure_live_page(module_key, f"plan-{module_key}", title="探索计划步骤", page_status="running")[
                "steps"
            ] = grouped_steps.get(module_key, [])
        self._write_live_progress()

    def _record_live_step(self, *, module_key: str, page_id: str, step: dict, page_state: dict) -> None:
        page = self._ensure_live_page(
            module_key,
            page_id,
            title=str(page_state.get("title") or ("当前运行阶段" if page_id == "lifecycle" else page_id)),
            url=str(page_state.get("url") or ""),
            page_status=str(step.get("status") or "running"),
        )
        existing_index = next((index for index, item in enumerate(page["steps"]) if item.get("id") == step.get("id")), -1)
        if existing_index >= 0:
            page["steps"][existing_index] = step
        else:
            page["steps"].append(step)
        page["recent_event"] = str(step.get("detail") or step.get("title") or "")
        page["status"] = str(step.get("status") or page.get("status") or "running")
        self.live_progress.setdefault("events", []).append(
            {
                "type": "step_recorded",
                "module_key": module_key,
                "page_id": page_id,
                "step": step,
            }
        )
        self.live_progress["events"] = self.live_progress["events"][-100:]
        self._write_live_progress()

    def _record_live_failure(self, message: str) -> None:
        modules = self.live_progress.get("modules") if isinstance(self.live_progress.get("modules"), dict) else {}
        for module in modules.values():
            if not isinstance(module, dict):
                continue
            pages = module.get("pages") if isinstance(module.get("pages"), dict) else {}
            for page in pages.values():
                if not isinstance(page, dict):
                    continue
                if page.get("status") == "running":
                    page["status"] = "failed"
                    page["recent_event"] = message
                steps = page.get("steps") if isinstance(page.get("steps"), list) else []
                for step in steps:
                    if isinstance(step, dict) and step.get("status") == "running":
                        step["status"] = "failed"
                        step["detail"] = message
                        step["occurred_at"] = exploration_now_iso()
        self._write_live_progress()

    def _ensure_live_page(
        self,
        module_key: str,
        page_id: str,
        *,
        title: str,
        url: str = "",
        page_status: str = "running",
    ) -> dict:
        modules = self.live_progress.setdefault("modules", {})
        module = modules.setdefault(module_key, {"pages": {}})
        pages = module.setdefault("pages", {})
        page = pages.setdefault(
            page_id,
            {
                "id": page_id,
                "module_key": module_key,
                "title": title,
                "url": url,
                "entry_path": "",
                "structure_summary": "",
                "yaml_path": "live/progress.json",
                "status": page_status,
                "blocker_reason": "",
                "recent_event": "",
                "steps": [],
            },
        )
        if title:
            page["title"] = title
        if url:
            page["url"] = url
        return page

    def _write_live_progress(self) -> None:
        progress_path = self.artifact_root / "live" / "progress.json"
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = progress_path.with_suffix(".json.tmp")
        payload = {
            "run_id": self.run_id,
            "updated_at": exploration_now_iso(),
            **self.live_progress,
        }
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp_path.replace(progress_path)

    def _initial_module_key(self, run) -> str:
        with connect() as db:
            modules = exploration_repo.list_module_coverages(db, self.run_id)
        if modules:
            return str(modules[0]["module_key"])
        return "site-entry"

    @staticmethod
    def _run_value(run, key: str, default=None):
        return run[key] if key in run.keys() else default

    def _page_id_for_state(self, page_state: dict) -> str:
        url = str(page_state.get("url") or "")
        if not url:
            return "lifecycle"
        if self.executor:
            for index, visited_url in enumerate(self.executor.pages_visited.keys(), start=1):
                if visited_url == url:
                    return f"page-{index:03d}"
        return "page-001"

    def _publish(self, event_type: str, payload: dict):
        """发布事件"""
        event_bus.publish(self.run_id, event_type, payload)


# 便捷函数
async def run_unified_exploration(
    run_id: str,
    artifact_root: Path,
    start_url: str,
    forbidden_paths: str = "",
    storage_state_path: str = "",
) -> dict:
    """运行统一探索"""
    orchestrator = UnifiedExplorationOrchestrator(
        run_id=run_id,
        artifact_root=artifact_root,
        start_url=start_url,
        forbidden_paths=forbidden_paths,
        storage_state_path=storage_state_path,
    )
    return await orchestrator.run()


def run_unified_exploration_sync(
    run_id: str,
    artifact_root: Path,
    start_url: str,
    forbidden_paths: str = "",
    storage_state_path: str = "",
) -> dict:
    """同步运行统一探索"""
    try:
        # 在开始执行前立即发布初始事件
        event_bus.publish(run_id, "execution_starting", {
            "message": "统一探索编排器正在初始化...",
            "start_url": start_url,
        })

        result = asyncio.run(run_unified_exploration(
            run_id, artifact_root, start_url, forbidden_paths, storage_state_path
        ))
        return result
    except Exception as error:
        # 捕获所有异常并发布错误事件
        import traceback
        error_detail = f"{type(error).__name__}: {str(error)}"
        error_traceback = traceback.format_exc()

        # 发布错误事件到前端
        event_bus.publish(run_id, "execution_error", {
            "message": f"探索执行异常: {error_detail}",
            "error_type": type(error).__name__,
            "error_detail": error_detail,
        })

        # 写入错误日志
        log_path = artifact_root / "logs" / "run.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                f"Unified exploration error:\n{error_detail}\n\nTraceback:\n{error_traceback}\n",
                encoding="utf-8"
            )
        except Exception:
            pass

        # 返回错误结果
        return {
            "status": "blocked",
            "summary": f"探索执行异常中断: {error_detail[:200]}",
            "log": f"{error_detail}\n\n{error_traceback}",
            "log_path": str(log_path),
        }
