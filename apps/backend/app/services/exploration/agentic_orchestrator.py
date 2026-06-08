import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.site_exploration import agentic_service
from app.agents.site_exploration.agentic_schemas import AgenticAction, AgenticDecisionOutput, AgenticExplorationInput, AgenticRisk
from app.core.db import connect
from app.core.storage import store_path
from app.repositories import exploration_repo
from app.services.exploration import action_risk, artifact_service as exploration_artifact_service, event_bus
from app.services.exploration.browser_session import BrowserSessionError, PlaywrightBrowserSession


def run_agentic_exploration(
    run_id: str,
    artifact_root: Path,
    *,
    start_url: str,
    forbidden_paths: str = "",
    storage_state_path: str = "",
) -> dict:
    log_path = artifact_root / "logs" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    runner = _AgenticLoopRunner(
        run_id=run_id,
        artifact_root=artifact_root,
        start_url=start_url,
        forbidden_paths=forbidden_paths,
        storage_state_path=storage_state_path,
        log_path=log_path,
    )
    result = runner.run()
    log_path.write_text(result["log"], encoding="utf-8")
    result["log_path"] = store_path(log_path) or ""
    return result


class _AgenticLoopRunner:
    def __init__(
        self,
        *,
        run_id: str,
        artifact_root: Path,
        start_url: str,
        forbidden_paths: str,
        storage_state_path: str,
        log_path: Path,
    ) -> None:
        self.run_id = run_id
        self.artifact_root = artifact_root
        self.start_url = start_url or "about:blank"
        self.forbidden_terms = _split_terms(forbidden_paths)
        self.storage_state_path = storage_state_path
        self.log_path = log_path
        self.log_lines: list[str] = []
        self.pages_by_signature: dict[str, dict] = {}
        self.page_order: list[str] = []
        self.graph_nodes: dict[str, dict] = {}
        self.graph_edges: list[dict] = []
        self.blockers: list[dict] = []
        self.attempted_by_state: dict[str, set[str]] = {}
        self.history: list[str] = []
        self.action_count = 0
        self.turn = 0
        self.live_module_key = "planned-01"
        self.live_module_name = "站点入口"
        self.live_module_entry_path = self.start_url
        self.current_run = None
        self.scope_boundary = _scope_boundary("")
        self.crud_flow = {
            "test_data_name": _crud_test_data_name(run_id),
            "create_started": False,
            "create_verified": False,
            "edit_verified": False,
            "delete_verified": False,
            "blocked_reason": "",
        }
        self._crud_candidate_seen = False
        self._delete_started = False

    def run(self) -> dict:
        run = self._load_run()
        if not run:
            return self._blocked_result("探索任务不存在。", "run_missing", "重新创建探索任务后再试。")
        self.current_run = run

        max_pages = int(_mapping_get(run, "max_pages", 50) or 50)
        max_actions = int(_mapping_get(run, "max_actions", 1000) or 1000)
        max_turns = min(max(max_actions, 1), 200)
        self._configure_live_module(run)
        self.scope_boundary = _scope_boundary(str(_mapping_get(run, "scope", "") or ""))

        self._log(
            "run_started",
            url=self.start_url,
            max_pages=max_pages,
            max_actions=max_actions,
            max_agent_turns=max_turns,
        )
        self._publish("run_progress", {"recent_event": "Agentic Loop 已启动。", "url": self.start_url})
        self._publish_module_progress()

        try:
            with PlaywrightBrowserSession(
                start_url=self.start_url,
                storage_state_path=self.storage_state_path,
                timeout_seconds=45,
            ) as session:
                observation = session.observe()
                observation = self._enter_scope_boundary(session, observation)
                while self.turn < max_turns and self.action_count < max_actions and len(self.pages_by_signature) < max_pages:
                    if self._cancel_requested():
                        self._log("run_cancelled", status="cancelled")
                        return self._result("cancelled", "用户已停止探索。")

                    self.turn += 1
                    page_doc = self._record_observation(observation)
                    self._log(
                        "observe",
                        turn=self.turn,
                        page_id=page_doc["page"]["id"],
                        url=observation.get("url", ""),
                        state_signature=observation.get("state_signature", ""),
                    )
                    self._publish(
                        "agent_observed",
                        {
                            "turn": self.turn,
                            "page_id": page_doc["page"]["id"],
                            "title": page_doc["page"]["title"],
                            "url": page_doc["page"]["url"],
                            "state_signature": observation.get("state_signature", ""),
                        },
                    )

                    if _looks_like_access_block(observation):
                        blocker = self._add_blocker(
                            "access_blocked",
                            page_doc,
                            "页面疑似需要登录、验证码或权限，Agentic Loop 已停止。",
                            "完成登录态、验证码或权限配置后重新探索。",
                            is_blocking=True,
                        )
                        self._publish("blocker_detected", blocker)
                        break

                    decision = self._normalize_decision_for_execution(self._decide(run, observation, max_pages, max_actions, max_turns))
                    decision_record = self._record_decision(page_doc, decision, observation)
                    self._log(
                        "agent_decision",
                        turn=self.turn,
                        decision_type=decision.decision_type,
                        action=decision.action.type if decision.action else "",
                        target=decision.action.target_element_id if decision.action else "",
                        risk=decision.risk.level,
                        reason=decision.reason,
                    )
                    self._publish(
                        "agent_decision",
                        {
                            "turn": self.turn,
                            "decision_type": decision.decision_type,
                            "action_type": decision.action.type if decision.action else "",
                            "target_element_id": decision.action.target_element_id if decision.action else "",
                            "reason": decision.reason,
                            "risk_level": decision.risk.level,
                        },
                    )

                    if decision.decision_type == "finish":
                        break
                    if decision.decision_type == "block":
                        blocker = self._add_blocker(
                            "agent_blocked",
                            page_doc,
                            decision.reason,
                            "人工处理阻塞后重新探索。",
                            decision_id=decision_record["id"],
                            is_blocking=True,
                        )
                        self._publish("blocker_detected", blocker)
                        break
                    if decision.decision_type == "skip":
                        blocker = self._add_blocker(
                            "agent_skipped",
                            page_doc,
                            decision.reason,
                            "人工确认跳过项是否需要调整禁止路径或数据依赖后继续探索。",
                            decision_id=decision_record["id"],
                            is_blocking=False,
                        )
                        self._publish("action_skipped", blocker)
                        self._mark_attempted(observation, decision)
                        continue
                    if decision.decision_type == "record":
                        self._add_step(page_doc, "record", "记录页面状态", decision.reason)
                        continue

                    action_result = self._execute_decision(session, observation, page_doc, decision, decision_record)
                    if action_result.get("executed"):
                        self.action_count += 1
                        self._publish_module_progress(recent_page=page_doc)
                        observation = session.observe()
                        target_doc = self._record_observation(observation)
                        self._record_agent_edge(page_doc, target_doc, decision, decision_record, action_result)
                    else:
                        self._mark_attempted(observation, decision)

        except BrowserSessionError as error:
            self._log("error", message=str(error))
            return self._blocked_result(
                "Agentic Playwright 浏览器会话执行失败。",
                "browser_session_failed",
                f"检查 Playwright 安装、浏览器 channel 配置和目标站点可访问性后重试。真实失败原因：{str(error)[:300]}",
            )

        if not self.pages_by_signature:
            return self._blocked_result("Agentic Loop 未采集到页面事实。", "no_observation", "检查目标 URL、登录态和浏览器运行环境后重试。")

        if self._cancel_requested():
            return self._result("cancelled", "用户已停止探索。")

        self._finalize_crud_flow()
        status = "partial" if any(blocker.get("is_blocking") for blocker in self.blockers) else "completed"
        if self.blockers and status == "completed":
            status = "partial"
        summary = (
            f"Agentic Loop 已探索 {len(self.pages_by_signature)} 个页面/状态，"
            f"执行 {self.action_count} 个动作，记录 {len(self.blockers)} 个阻塞或跳过。"
        )
        self._log("run_completed", status=status, page_count=len(self.pages_by_signature), action_count=self.action_count)
        return self._result(status, summary)

    def _execute_decision(
        self,
        session: PlaywrightBrowserSession,
        observation: dict,
        page_doc: dict,
        decision: AgenticDecisionOutput,
        decision_record: dict,
    ) -> dict:
        action = decision.action
        if action is None:
            return {"executed": False, "status": "skipped", "reason": "决策没有 action。"}

        element = self._element_by_id(observation, action.target_element_id)
        action = self._action_with_test_data(action, element)
        action_payload = action.model_dump()
        action_decision = action_risk.evaluate_action(action_payload, element)
        self._mark_crud_candidate(action_payload, element)

        if self._is_forbidden_target(action, element):
            blocker = self._add_blocker(
                "forbidden_path",
                page_doc,
                "动作目标命中禁止路径或禁止关键词，已跳过。",
                "如需覆盖该功能，请调整禁止路径后重新探索。",
                action=element.get("name") if element else action.type,
                decision_id=decision_record["id"],
                is_blocking=False,
            )
            self._publish("action_skipped", blocker)
            self._log("skipped", turn=self.turn, type="forbidden_path", page_id=page_doc["page"]["id"], action=action.type)
            return {"executed": False, "status": "forbidden_path", "reason": blocker["reason"]}

        boundary_violation = self._scope_boundary_violation(action, element)
        if boundary_violation:
            blocker = self._add_blocker(
                "scope_boundary",
                page_doc,
                boundary_violation,
                "调整探索范围或入口 URL 后重新探索；当前运行只允许覆盖目标范围内的模块。",
                action=element.get("name") if element else action.type,
                decision_id=decision_record["id"],
                is_blocking=False,
            )
            self._publish("action_skipped", blocker)
            self._log("skipped", turn=self.turn, type="scope_boundary", page_id=page_doc["page"]["id"], action=action.type)
            self._mark_attempted(observation, decision)
            return {"executed": False, "status": "scope_boundary", "reason": blocker["reason"]}

        scope_violation = self._crud_scope_violation(action, element, observation, action_decision.risk.level)
        if scope_violation:
            self.crud_flow["blocked_reason"] = scope_violation
            blocker = self._add_blocker(
                "crud_scope_violation",
                page_doc,
                scope_violation,
                "只允许创建、编辑、删除本轮生成的 AI_EXPLORE_* 探索测试数据；如需覆盖真实数据，请人工确认后单独执行。",
                action=element.get("name") if element else action.type,
                decision_id=decision_record["id"],
                is_blocking=False,
            )
            self._publish("action_skipped", blocker)
            self._log("skipped", turn=self.turn, type="crud_scope_violation", page_id=page_doc["page"]["id"], action=action.type)
            self._mark_attempted(observation, decision)
            return {"executed": False, "status": "crud_scope_violation", "reason": blocker["reason"]}

        self._mark_crud_started(action, element)

        try:
            self._publish(
                "action_started",
                {
                    "turn": self.turn,
                    "action_type": action.type,
                    "target_element_id": action.target_element_id,
                    "target_element_name": element.get("name") if element else "",
                    "risk_level": action_decision.risk.level,
                },
            )
            if action.type == "click":
                result = session.click(action.target_element_id)
            elif action.type == "fill":
                result = session.fill(action.target_element_id, action.value or "AI_TEST_search")
            elif action.type == "go_back":
                result = session.go_back()
            elif action.type == "close_modal":
                result = session.close_modal()
            elif action.type == "wait":
                result = session.wait()
            elif action.type == "navigate":
                result = session.navigate(action.url or self.start_url)
            else:
                result = {"status": "skipped", "reason": f"首阶段暂不支持动作：{action.type}"}
        except BrowserSessionError as error:
            result = {"status": "failed", "error": str(error)}

        action_record = {
            "id": f"action-{len(page_doc['actions']) + 1:03d}",
            "type": action.type,
            "element_id": action.target_element_id,
            "element_name": element.get("name") if element else "",
            "before_url": result.get("before_url", page_doc["page"]["url"]),
            "after_url": result.get("after_url", ""),
            "status": result.get("status", "unknown"),
            "state_signature_changed": bool(result.get("state_signature_changed")),
            "decision_id": decision_record["id"],
            "result": result,
        }
        page_doc["actions"].append(action_record)
        decision_record["result_ref"] = action_record["id"]
        self._add_step(
            page_doc,
            "action_result",
            "执行 Agent 动作",
            _action_step_detail(action.type, element.get("name") if element else action.target_element_id, result),
            "failed" if result.get("status") == "failed" else "completed",
        )
        self._log(
            "action_result",
            turn=self.turn,
            status=result.get("status", ""),
            action=action.type,
            target=action.target_element_id,
            risk=action_decision.risk.level,
            before_url=result.get("before_url", ""),
            after_url=result.get("after_url", ""),
            error=result.get("error", ""),
            error_type=result.get("error_type", ""),
            error_summary=result.get("error_summary", ""),
        )
        self._mark_crud_blocked_by_action_failure(action, element, result, action_decision.risk.level)
        self._publish(
            "action_completed",
            {
                "turn": self.turn,
                "action_type": action.type,
                "target_element_id": action.target_element_id,
                "target_element_name": element.get("name") if element else "",
                "risk_level": action_decision.risk.level,
                "status": result.get("status", ""),
                "before_url": result.get("before_url", ""),
                "after_url": result.get("after_url", ""),
                "error_type": result.get("error_type", ""),
                "error_summary": result.get("error_summary", ""),
            },
        )
        self._mark_attempted(observation, decision)
        return {**result, "executed": result.get("status") in {"passed", "unverified"}}

    def _decide(
        self,
        run,
        observation: dict,
        max_pages: int,
        max_actions: int,
        max_turns: int,
    ) -> AgenticDecisionOutput:
        agent_input = AgenticExplorationInput(
            run={
                "id": _mapping_get(run, "id", ""),
                "title": _mapping_get(run, "title", ""),
                "goal": _mapping_get(run, "goal", ""),
                "scope": _mapping_get(run, "scope", ""),
                "forbidden_paths": _mapping_get(run, "forbidden_paths", ""),
                "crud_test_data_name": self.crud_flow["test_data_name"],
            },
            budget={
                "remaining_turns": max(max_turns - self.turn + 1, 0),
                "remaining_pages": max(max_pages - len(self.pages_by_signature), 0),
                "remaining_actions": max(max_actions - self.action_count, 0),
            },
            history_summary="；".join(self.history[-8:]),
            current_observation=self._observation_for_agent(observation),
        )
        try:
            return asyncio.run(agentic_service.decide_next_action(agent_input))
        except Exception as error:
            self._log("agent_decision_fallback", turn=self.turn, reason=str(error)[:300])
            return AgenticDecisionOutput(
                decision_type="block",
                action=None,
                reason=f"模型决策不可用，已停止本轮探索，避免在未知决策下自动点击页面元素。原因：{str(error)[:300]}",
                expected_result="修复模型配置或运行环境后重新探索。",
                risk=AgenticRisk(level="destructive", reason="模型不可用时继续自动执行页面动作可能误触发布、删除或保存。"),
            )

    def _normalize_decision_for_execution(self, decision: AgenticDecisionOutput) -> AgenticDecisionOutput:
        if decision.decision_type == "back" and decision.action is None:
            return decision.model_copy(
                update={"action": AgenticAction(type="go_back", intent="返回上一页面或状态")}
            )
        return decision

    def _observation_for_agent(self, observation: dict) -> dict:
        signature = str(observation.get("state_signature") or "")
        attempted = self.attempted_by_state.setdefault(signature, set())
        payload = dict(observation)
        elements = []
        for element in observation.get("elements") if isinstance(observation.get("elements"), list) else []:
            if not isinstance(element, dict):
                continue
            safe_element = {
                "id": element.get("id", ""),
                "role": element.get("role", ""),
                "name": element.get("name", ""),
                "text": element.get("text", ""),
                "action_type": element.get("action_type", ""),
                "enabled": element.get("enabled", True),
                "visible": element.get("visible", True),
                "risk_hint": element.get("risk_hint", ""),
                "already_attempted": element.get("id", "") in attempted,
            }
            elements.append(safe_element)
        payload["elements"] = elements[:80]
        payload["crud_flow"] = dict(self.crud_flow)
        return payload

    def _record_observation(self, observation: dict) -> dict:
        self._update_crud_flow_from_observation(observation)
        signature = str(observation.get("state_signature") or observation.get("normalized_url") or observation.get("url") or "")
        existing = self.pages_by_signature.get(signature)
        if existing:
            self._publish_module_progress(recent_page=existing)
            return existing
        page_id = f"page-{len(self.pages_by_signature) + 1:03d}"
        title = str(observation.get("title") or observation.get("url") or "未命名页面")
        url = str(observation.get("url") or "")
        structure_summary = str(observation.get("page_text_summary") or "Agentic Loop 已采集页面观察。")
        semantic_title = _infer_page_title(title, url, structure_summary, observation)
        module_name = _infer_module_name(title, url, structure_summary)
        business_summary = _business_summary(semantic_title, structure_summary, observation)
        page_doc = {
            "artifact_schema_version": 2,
            "page": {
                "id": page_id,
                "title": title,
                "semantic_title": semantic_title,
                "url": url,
                "normalized_url": str(observation.get("normalized_url") or observation.get("url") or ""),
                "module": module_name,
                "depth": len(self.pages_by_signature),
                "status": "explored",
                "structure_summary": structure_summary,
            },
            "business_summary": business_summary,
            "states": [
                {
                    "id": "default",
                    "type": "page",
                    "title": semantic_title or title,
                    "state_signature": signature,
                    "elements": [_state_element(element) for element in observation.get("elements", []) if isinstance(element, dict)],
                }
            ],
            "accessibility_tree": [],
            "steps": [],
            "actions": [],
            "forms": observation.get("forms") if isinstance(observation.get("forms"), list) else [],
            "tables": observation.get("tables") if isinstance(observation.get("tables"), list) else [],
            "relations": {"incoming_edges": [], "outgoing_edges": []},
            "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
            "agent_decisions": [],
        }
        self.pages_by_signature[signature] = page_doc
        self.page_order.append(signature)
        self.graph_nodes[page_id] = {
            "id": page_id,
            "title": page_doc["page"]["title"],
            "semantic_title": page_doc["page"]["semantic_title"],
            "url": page_doc["page"]["url"],
            "module": page_doc["page"]["module"],
        }
        self._add_step(page_doc, "observe", "观察页面", page_doc["page"]["structure_summary"])
        self._publish(
            "page_discovered",
            {
                "module_key": self.live_module_key,
                "page_id": page_id,
                "title": page_doc["page"]["semantic_title"] or page_doc["page"]["title"],
                "url": page_doc["page"]["url"],
                "entry_path": page_doc["page"]["normalized_url"],
                "structure_summary": page_doc["page"]["structure_summary"],
                "status": "running",
                "recent_event": "Agentic Loop 观察到页面状态。",
                "steps": page_doc["steps"],
            },
        )
        self._publish_module_progress(recent_page=page_doc)
        return page_doc

    def _record_decision(self, page_doc: dict, decision: AgenticDecisionOutput, observation: dict) -> dict:
        record = {
            "id": f"decision-{len(page_doc['agent_decisions']) + 1:03d}",
            "turn": self.turn,
            "observation_ref": str(observation.get("state_signature") or ""),
            "decision_type": decision.decision_type,
            "action_type": decision.action.type if decision.action else "",
            "target_element_id": decision.action.target_element_id if decision.action else "",
            "reason": decision.reason,
            "expected_result": decision.expected_result,
            "risk": decision.risk.model_dump(),
            "coverage_intent": decision.coverage_intent.model_dump(),
        }
        page_doc["agent_decisions"].append(record)
        self._add_step(page_doc, "agent_decision", "Agent 决策", decision.reason)
        return record

    def _record_agent_edge(
        self,
        source_doc: dict,
        target_doc: dict,
        decision: AgenticDecisionOutput,
        decision_record: dict,
        action_result: dict,
    ) -> None:
        edge = {
            "id": f"edge-{len(self.graph_edges) + 1:03d}",
            "source": source_doc["page"]["id"],
            "target": target_doc["page"]["id"],
            "type": "agent_action",
            "action": decision.action.type if decision.action else decision.decision_type,
            "decision_id": decision_record["id"],
            "result": {
                "status": action_result.get("status", ""),
                "url_changed": bool(action_result.get("url_changed")),
                "state_signature_changed": bool(action_result.get("state_signature_changed")),
            },
        }
        self.graph_edges.append(edge)
        source_doc["relations"]["outgoing_edges"].append(
            {
                "type": "agent_action",
                "action": edge["action"],
                "target": target_doc["page"]["id"],
                "decision_id": decision_record["id"],
            }
        )
        target_doc["relations"]["incoming_edges"].append(
            {
                "type": "agent_action",
                "action": edge["action"],
                "source": source_doc["page"]["id"],
                "decision_id": decision_record["id"],
            }
        )
        self._log("edge_created", edge_id=edge["id"], source=edge["source"], target=edge["target"], type=edge["type"])

    def _add_blocker(
        self,
        reason_type: str,
        page_doc: dict,
        reason: str,
        suggested_action: str,
        *,
        action: str = "",
        decision_id: str = "",
        is_blocking: bool,
    ) -> dict:
        blocker = {
            "id": f"blocker-{len(self.blockers) + 1:03d}",
            "type": reason_type,
            "reason_type": reason_type,
            "module_key": self.live_module_key,
            "page_ref": page_doc["page"]["id"],
            "page": page_doc["page"]["url"],
            "action": action,
            "reason": reason,
            "severity": "blocking" if is_blocking else "warning",
            "suggested_action": suggested_action,
            "decision_id": decision_id,
            "is_blocking": is_blocking,
        }
        self.blockers.append(blocker)
        page_doc["quality"]["blockers"].append(reason)
        self._add_step(page_doc, reason_type, "记录阻塞或跳过", reason, "blocked" if is_blocking else "skipped")
        self._log(reason_type, turn=self.turn, page_id=page_doc["page"]["id"], reason=reason, action=action)
        return blocker

    def _add_step(self, page_doc: dict, step_type: str, title: str, detail: str = "", status: str = "completed") -> None:
        step = {
            "id": f"step-{len(page_doc['steps']) + 1:03d}",
            "type": step_type,
            "title": title,
            "detail": detail,
            "status": status,
            "occurred_at": _now_iso(),
            "source": "agentic_loop",
        }
        page_doc["steps"].append(step)
        self._log(
            "step_recorded",
            page_id=page_doc["page"]["id"],
            page_title=page_doc["page"]["title"],
            url=page_doc["page"]["url"],
            step_id=step["id"],
            step_type=step["type"],
            title=step["title"],
            detail=step["detail"],
            status=step["status"],
            occurred_at=step["occurred_at"],
            source=step["source"],
        )
        self._publish(
            "step_recorded",
            {
                "module_key": self.live_module_key,
                "page_id": page_doc["page"]["id"],
                "step": step,
            },
        )
        self._publish_module_progress(recent_page=page_doc)
        self._persist_live_snapshot()

    def _persist_live_snapshot(self) -> None:
        run = self.current_run or self._load_run()
        if not run:
            return
        try:
            exploration_artifact_service.write_live_exploration_snapshot(
                self.artifact_root,
                run=run,
                summary={
                    "artifact_schema_version": 2,
                    "status": "running",
                    "summary": "Agentic Loop 正在探索页面。",
                    "modules": self._module_summary_payload("running"),
                },
                page_artifacts=[self.pages_by_signature[signature] for signature in self.page_order],
                graph={"nodes": list(self.graph_nodes.values()), "edges": self.graph_edges, "paths": []},
                blockers=self.blockers,
                log_content="\n".join(self.log_lines).rstrip() + "\n" if self.log_lines else "",
            )
        except Exception as error:
            self._log("live_snapshot_failed", message=str(error))

    def _configure_live_module(self, run) -> None:
        self.live_module_key = "planned-01"
        scope = str(_mapping_get(run, "scope", "") or "").strip()
        title = str(_mapping_get(run, "title", "") or "").strip()
        self.live_module_name = scope.splitlines()[0][:80] if scope else title[:80] or "站点入口"
        self.live_module_entry_path = scope or self.start_url

    def _publish_module_progress(self, *, recent_page: dict | None = None) -> None:
        explored = len(self.pages_by_signature)
        planned = max(explored, 1)
        blocking_count = sum(1 for blocker in self.blockers if blocker.get("is_blocking"))
        recent = recent_page["page"] if recent_page else None
        blocker_summary = "无" if blocking_count == 0 else f"{blocking_count} 个页面阻塞"
        self._publish(
            "module_updated",
            {
                "module_id": self.live_module_key,
                "module_key": self.live_module_key,
                "module_name": self.live_module_name,
                "entry_path": self.live_module_entry_path,
                "planned_page_count": planned,
                "explored_page_count": explored,
                "blocked_page_count": blocking_count,
                "action_count": self.action_count,
                "field_count": 0,
                "state_transition_count": len(self.graph_edges),
                "completion_status": "running",
                "completion_summary": _live_module_summary(explored, planned, recent, blocker_summary),
            },
        )

    def _module_summary_payload(self, status: str) -> list[dict]:
        pages = [self.pages_by_signature[signature] for signature in self.page_order]
        explored = len(pages)
        planned = max(explored, 1)
        blocking_count = sum(1 for blocker in self.blockers if blocker.get("is_blocking"))
        recent_page = pages[-1]["page"] if pages else None
        page_titles = []
        for page_doc in pages:
            page = page_doc.get("page") if isinstance(page_doc.get("page"), dict) else {}
            title = str(page.get("semantic_title") or page.get("title") or page.get("url") or "").strip()
            if title and title not in page_titles:
                page_titles.append(title)
        blocker_summary = "无" if blocking_count == 0 else f"{blocking_count} 个页面阻塞"
        completion_status = "running" if status == "running" else ("partial" if status == "partial" else status)
        field_count = sum(
            1
            for page_doc in pages
            for action in page_doc.get("actions", [])
            if action.get("type") == "fill"
        )
        return [
            {
                "module_key": self.live_module_key,
                "module_name": self.live_module_name,
                "status": completion_status,
                "page_progress": f"{explored}/{planned}",
                "planned_page_count": planned,
                "explored_page_count": explored,
                "blocked_page_count": blocking_count,
                "action_count": self.action_count,
                "field_count": field_count,
                "state_transition_count": len(self.graph_edges),
                "latest_page": recent_page.get("semantic_title") or recent_page.get("title") if recent_page else "",
                "main_facts": "、".join(page_titles[:5]) if page_titles else "-",
                "blocker_summary": blocker_summary,
                "knowledge_base_availability": "部分可用" if status == "partial" else ("待确认" if status == "running" else "可用"),
                "entry_path": self.live_module_entry_path,
            }
        ]

    def _mark_attempted(self, observation: dict, decision: AgenticDecisionOutput) -> None:
        if not decision.action or not decision.action.target_element_id:
            return
        signature = str(observation.get("state_signature") or "")
        self.attempted_by_state.setdefault(signature, set()).add(decision.action.target_element_id)
        self.history.append(f"{decision.decision_type}:{decision.action.type}:{decision.action.target_element_id}")

    def _element_by_id(self, observation: dict, element_id: str) -> dict:
        for element in observation.get("elements") if isinstance(observation.get("elements"), list) else []:
            if isinstance(element, dict) and element.get("id") == element_id:
                return element
        return {}

    def _is_forbidden_target(self, action, element: dict) -> bool:
        text = " ".join(
            str(value or "")
            for value in (
                action.type,
                action.url,
                action.target_element_id,
                element.get("name", ""),
                element.get("text", ""),
                element.get("href", ""),
            )
        ).lower()
        return any(term in text for term in self.forbidden_terms)

    def _enter_scope_boundary(self, session: PlaywrightBrowserSession, observation: dict) -> dict:
        if not self.scope_boundary:
            return observation
        allowed_path = str(self.scope_boundary.get("path") or "")
        current_url = str(observation.get("normalized_url") or observation.get("url") or "")
        if _url_matches_path(current_url, allowed_path):
            return observation
        if not _route_label(current_url, prefer_deep=True):
            return observation
        target_url = _same_origin_url(current_url or self.start_url, allowed_path)
        if not target_url:
            return observation
        result = session.navigate(target_url)
        self._log(
            "scope_boundary_entered",
            scope=self.scope_boundary.get("label", ""),
            target_url=target_url,
            before_url=result.get("before_url", current_url),
            after_url=result.get("after_url", ""),
        )
        return session.observe()

    def _scope_boundary_violation(self, action: AgenticAction, element: dict) -> str:
        if not self.scope_boundary:
            return ""
        allowed_label = str(self.scope_boundary.get("label") or "")
        allowed_path = str(self.scope_boundary.get("path") or "")
        if action.type == "navigate" and action.url and not _url_matches_path(action.url, allowed_path):
            return f"探索范围硬边界为 {allowed_label}（{allowed_path}），禁止导航到范围外 URL：{action.url}"
        target_text = " ".join(
            str(value or "")
            for value in (
                action.url,
                element.get("name", ""),
                element.get("text", ""),
                element.get("href", ""),
            )
        )
        target_label = _module_label_from_text(target_text)
        if target_label and target_label != allowed_label:
            return f"探索范围硬边界为 {allowed_label}（{allowed_path}），禁止进入范围外模块：{target_label}。"
        return ""

    def _action_with_test_data(self, action: AgenticAction, element: dict) -> AgenticAction:
        risk = action_risk.classify_action(action.model_dump(), element)
        if action.type == "fill" and risk.level != "safe":
            return action.model_copy(update={"value": self.crud_flow["test_data_name"]})
        return action

    def _mark_crud_candidate(self, action_payload: dict, element: dict) -> None:
        text = _action_text(action_payload, element)
        if action_payload.get("type") == "fill" or _contains_crud_term(text):
            self._crud_candidate_seen = True

    def _mark_crud_started(self, action: AgenticAction, element: dict) -> None:
        text = _action_text(action.model_dump(), element)
        if action.type == "fill" and self.crud_flow["create_verified"]:
            self.crud_flow["edit_verified"] = True
        elif action.type == "fill" or _contains_any(text, ("新建", "创建", "新增", "create", "new", "add", "保存", "提交", "save", "submit")):
            self.crud_flow["create_started"] = True
        if _contains_any(text, ("编辑", "修改", "edit", "update")) and self.crud_flow["create_verified"]:
            self.crud_flow["edit_verified"] = True
        if _contains_any(text, ("删除", "移除", "delete", "remove")):
            self._delete_started = True

    def _crud_scope_violation(self, action: AgenticAction, element: dict, observation: dict, risk_level: str) -> str:
        if risk_level == "safe":
            return ""
        text = _action_text(action.model_dump(), element)
        has_test_data = self._observation_has_test_data(observation) or self.crud_flow["test_data_name"].lower() in text
        is_fill = action.type == "fill"
        is_create_entry = _contains_any(text, ("新建", "创建", "新增", "create", "new", "add"))
        is_save_after_test_input = _contains_any(text, ("保存", "提交", "save", "submit")) and (
            self.crud_flow["create_started"] or self.crud_flow["create_verified"] or has_test_data
        )
        is_edit_target = _contains_any(text, ("编辑", "修改", "edit", "update"))
        is_destructive_target = _contains_any(text, ("删除", "移除", "delete", "remove", "发布", "publish", "发送", "send"))

        if is_fill or is_create_entry or is_save_after_test_input:
            return ""
        if is_edit_target and has_test_data:
            return ""
        if is_destructive_target and has_test_data:
            return ""
        if risk_level == "destructive":
            return f"高风险动作只能作用于本轮探索测试数据 {self.crud_flow['test_data_name']}，当前页面或目标元素未匹配该记录。"
        if is_edit_target:
            return f"编辑动作只能匹配本轮探索测试数据 {self.crud_flow['test_data_name']}，当前目标不是该记录。"
        return ""

    def _update_crud_flow_from_observation(self, observation: dict) -> None:
        has_test_data = self._observation_has_test_data(observation)
        if has_test_data and self.crud_flow["create_started"]:
            self.crud_flow["create_verified"] = True
        if self._delete_started and self.crud_flow["create_verified"] and not has_test_data:
            self.crud_flow["delete_verified"] = True

    def _observation_has_test_data(self, observation: dict) -> bool:
        needle = self.crud_flow["test_data_name"].lower()
        return bool(needle and needle in _observation_text(observation))

    def _mark_crud_blocked_by_action_failure(self, action: AgenticAction, element: dict, result: dict, risk_level: str) -> None:
        if result.get("status") != "failed" or risk_level == "safe":
            return
        reason = str(result.get("error_summary") or result.get("error_type") or result.get("error") or "CRUD 动作执行失败。")
        self.crud_flow["blocked_reason"] = reason[:240]

    def _finalize_crud_flow(self) -> None:
        if not self._crud_candidate_seen:
            return
        if self.crud_flow["create_verified"] and self.crud_flow["edit_verified"] and self.crud_flow["delete_verified"]:
            return
        if any(blocker.get("type") == "crud_incomplete" for blocker in self.blockers):
            return
        page_doc = self._last_page_doc()
        if not page_doc:
            return
        missing = [
            label
            for key, label in (
                ("create_started", "创建已触发"),
                ("create_verified", "创建结果已查询验证"),
                ("edit_verified", "编辑结果已验证"),
                ("delete_verified", "删除结果已验证"),
            )
            if not self.crud_flow[key]
        ]
        reason = f"CRUD 闭环未完成，测试数据 {self.crud_flow['test_data_name']} 缺少：{'、'.join(missing)}。"
        if self.crud_flow["blocked_reason"]:
            reason = f"{reason} 关联阻塞：{self.crud_flow['blocked_reason']}"
        blocker = self._add_blocker(
            "crud_incomplete",
            page_doc,
            reason,
            "修复定位器、弹层或数据依赖后重新探索，确保 AI_EXPLORE_* 测试数据完成创建、查询、编辑、删除闭环。",
            is_blocking=False,
        )
        self._publish("blocker_detected", blocker)

    def _last_page_doc(self) -> dict:
        if not self.page_order:
            return {}
        return self.pages_by_signature.get(self.page_order[-1], {})

    def _result(self, status: str, summary: str) -> dict:
        return {
            "status": status,
            "summary": summary,
            "modules": self._module_summary_payload(status),
            "structured_pages": [self.pages_by_signature[signature] for signature in self.page_order],
            "graph": {"nodes": list(self.graph_nodes.values()), "edges": self.graph_edges, "paths": []},
            "blockers": self.blockers,
            "crud_flow": dict(self.crud_flow),
            "log_lines": self.log_lines,
            "log": "\n".join(self.log_lines).rstrip() + "\n",
            "action_count": self.action_count,
            "field_count": sum(
                1
                for page_doc in self.pages_by_signature.values()
                for action in page_doc.get("actions", [])
                if action.get("type") == "fill"
            ),
            "state_transition_count": len(self.graph_edges),
            "discovery": {
                "visited_count": len(self.pages_by_signature),
                "discovered_link_count": len(self.graph_edges),
                "same_origin_link_count": len(self.graph_edges),
                "clickable_count": sum(len(page.get("actions", [])) for page in self.pages_by_signature.values()),
                "input_count": 0,
                "reason_if_stopped": "Agentic Loop 达到停止条件或无更多可执行动作。",
            },
        }

    def _blocked_result(self, summary: str, reason_type: str, suggested_action: str) -> dict:
        self._log("blocked", type=reason_type, reason=summary)
        return {
            "status": "blocked",
            "summary": summary,
            "modules": self._module_summary_payload("blocked"),
            "reason_type": reason_type,
            "suggested_action": suggested_action,
            "structured_pages": [self.pages_by_signature[signature] for signature in self.page_order],
            "graph": {"nodes": list(self.graph_nodes.values()), "edges": self.graph_edges, "paths": []},
            "blockers": self.blockers,
            "crud_flow": dict(self.crud_flow),
            "log_lines": self.log_lines,
            "log": "\n".join(self.log_lines).rstrip() + "\n",
            "action_count": self.action_count,
            "field_count": 0,
            "state_transition_count": len(self.graph_edges),
        }

    def _load_run(self):
        with connect() as db:
            return exploration_repo.find_by_id(db, self.run_id)

    def _cancel_requested(self) -> bool:
        with connect() as db:
            run = exploration_repo.find_by_id(db, self.run_id)
            return bool(run and run["status"] == "stopping")

    def _log(self, event: str, **payload: Any) -> None:
        self.log_lines.append(json.dumps({"ts": _now_iso(), "event": event, **payload}, ensure_ascii=False))

    def _publish(self, event_type: str, payload: dict) -> None:
        event_bus.publish(self.run_id, event_type, payload)


def _split_terms(value: str) -> list[str]:
    return [item.strip().lower() for item in re.split(r"[\n,，;；]+", value or "") if item.strip()]


def _crud_test_data_name(run_id: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z]+", "", str(run_id or "")).upper()
    if normalized.startswith("EXPLORE"):
        normalized = normalized[len("EXPLORE"):]
    short_code = normalized[:8] or "RUN"
    return f"AI_EXPLORE_{short_code}"


def _action_text(action: dict, element: dict) -> str:
    return " ".join(
        str(value or "")
        for value in (
            action.get("type"),
            action.get("intent"),
            action.get("value"),
            action.get("target_element_id"),
            element.get("name", ""),
            element.get("text", ""),
            element.get("role", ""),
            element.get("href", ""),
        )
    ).lower()


def _observation_text(observation: dict) -> str:
    parts = [
        observation.get("url", ""),
        observation.get("title", ""),
        observation.get("page_text_summary", ""),
    ]
    for element in observation.get("elements") if isinstance(observation.get("elements"), list) else []:
        if isinstance(element, dict):
            parts.extend([element.get("id", ""), element.get("name", ""), element.get("text", ""), element.get("href", "")])
    return " ".join(str(part or "") for part in parts).lower()


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    value = str(value or "").lower()
    return any(term.lower() in value for term in terms)


def _contains_crud_term(value: str) -> bool:
    return _contains_any(
        value,
        (
            "新建",
            "创建",
            "新增",
            "编辑",
            "修改",
            "保存",
            "提交",
            "删除",
            "移除",
            "发布",
            "create",
            "new",
            "add",
            "edit",
            "update",
            "save",
            "submit",
            "delete",
            "remove",
            "publish",
        ),
    )


MODULE_ROUTE_LABELS = {
    "agentStore": "探索广场",
    "workspace": "工作台",
    "agentAnalysis": "效果评测",
    "resource": "资源库",
    "publish": "发布管理",
    "manage": "管理中心",
}


def _scope_boundary(scope: str) -> dict:
    text = str(scope or "")
    for segment, label in MODULE_ROUTE_LABELS.items():
        if label in text:
            return {"label": label, "path": f"/{segment}"}
    return {}


def _url_matches_path(url: str, allowed_path: str) -> bool:
    if not url or not allowed_path:
        return False
    try:
        from urllib.parse import urlparse

        path = urlparse(url).path or "/"
    except Exception:
        return False
    return path == allowed_path or path.startswith(f"{allowed_path}/")


def _same_origin_url(url: str, path: str) -> str:
    if not url or not path:
        return ""
    try:
        from urllib.parse import urlparse, urlunparse

        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return ""
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    except Exception:
        return ""


def _module_label_from_text(value: str) -> str:
    text = str(value or "")
    for label in MODULE_ROUTE_LABELS.values():
        if label in text:
            return label
    for segment, label in MODULE_ROUTE_LABELS.items():
        if segment.lower() in text.lower():
            return label
    return ""


def _looks_like_access_block(observation: dict) -> bool:
    value = " ".join(
        str(observation.get(key) or "")
        for key in ("url", "title", "page_text_summary")
    )
    return bool(re.search(r"login|signin|sign-in|auth|passport|account/login|user/login|登录|登陆|验证码|401|403", value, re.I))


def _state_element(element: dict) -> dict:
    return {
        "id": str(element.get("id") or ""),
        "name": str(element.get("name") or element.get("text") or ""),
        "role": str(element.get("role") or ""),
        "action": str(element.get("action_type") or "inspect"),
        "enabled": element.get("enabled") is not False,
        "visible": element.get("visible") is not False,
        "risk_hint": str(element.get("risk_hint") or ""),
        "primary_selector": element.get("primary_selector") if isinstance(element.get("primary_selector"), dict) else None,
        "fallback_selector": element.get("fallback_selector") if isinstance(element.get("fallback_selector"), dict) else None,
        "needs_confirmation": not _selector_usable(element.get("primary_selector")),
    }


def _selector_usable(selector: object) -> bool:
    if not isinstance(selector, dict):
        return False
    verification = selector.get("verification") if isinstance(selector.get("verification"), dict) else {}
    return bool(verification.get("checked") and verification.get("unique") and verification.get("visible"))


def _action_step_detail(action_type: str, target: str, result: dict) -> str:
    status = result.get("status", "unknown")
    detail = f"{action_type} {target}：{status}"
    if status == "failed":
        reason = str(result.get("error_summary") or result.get("error_type") or result.get("error") or "").strip()
        if reason:
            detail = f"{detail}，原因：{reason[:240]}"
    return detail


def _mapping_get(mapping: object, key: str, default: object = None) -> object:
    if not hasattr(mapping, "keys"):
        return default
    try:
        return mapping[key] if key in mapping.keys() else default
    except (KeyError, TypeError):
        return default


def _infer_module_name(title: str, url: str, page_text: str = "") -> str:
    route_label = _route_label(url, prefer_deep=True)
    if route_label:
        return route_label
    text = _business_keyword_label(page_text)
    if text:
        return text
    title_text = str(title or "").strip()
    if title_text and len(title_text) <= 40:
        return title_text
    try:
        from urllib.parse import urlparse

        first = next((item for item in urlparse(url).path.split("/") if item), "")
        return first or "入口页"
    except Exception:
        return "未分组模块"


def _infer_page_title(title: str, url: str, page_text: str, observation: dict) -> str:
    route_label = _route_label(url, prefer_deep=True)
    keyword_label = _business_keyword_label(page_text)
    element_label = _distinctive_element_label(observation)
    title_text = str(title or "").strip()
    if keyword_label in {"用户洞察", "数据统计"} and keyword_label != title_text:
        return keyword_label
    if route_label and route_label != title_text:
        return route_label
    if keyword_label and keyword_label != title_text:
        return keyword_label
    if element_label and element_label != title_text:
        return element_label
    return title_text or str(url or "").strip() or "未命名页面"


def _business_summary(page_title: str, page_text: str, observation: dict) -> dict:
    action_names = _distinctive_element_names(observation, limit=6)
    forms = observation.get("forms") if isinstance(observation.get("forms"), list) else []
    tables = observation.get("tables") if isinstance(observation.get("tables"), list) else []
    states = []
    if forms:
        states.append(f"表单 {len(forms)} 个")
    if tables:
        states.append(f"表格 {len(tables)} 个")
    headline = _compact_business_text(page_text) or f"{page_title} 页面已采集。"
    return {
        "headline": headline,
        "primary_actions": action_names,
        "filters": [],
        "observed_states": states,
    }


def _route_label(url: str, *, prefer_deep: bool = False) -> str:
    try:
        from urllib.parse import urlparse

        segments = [segment for segment in urlparse(url).path.split("/") if segment]
    except Exception:
        return ""
    labels = {
        "agentStore": "探索广场",
        "workspace": "工作台",
        "agentAnalysis": "效果评测",
        "resource": "资源库",
        "publish": "发布管理",
        "manage": "管理中心",
    }
    if prefer_deep:
        for segment in reversed(segments):
            if segment in labels:
                return labels[segment]
    for segment in segments:
        if segment in labels:
            return labels[segment]
    return ""


def _business_keyword_label(page_text: str) -> str:
    text = str(page_text or "")
    keyword_labels = [
        (("数据统计", "用户洞察"), "用户洞察"),
        (("Token 消耗量", "用户"), "数据统计"),
        (("结果即刻交付", "探索广场"), "探索广场"),
        (("收藏", "探索广场"), "探索广场"),
        (("资源库", "效果评测", "发布管理"), "创作中心"),
        (("空间管理", "文档中心"), "管理中心"),
    ]
    for keywords, label in keyword_labels:
        if all(keyword in text for keyword in keywords):
            return label
    return ""


def _distinctive_element_label(observation: dict) -> str:
    names = _distinctive_element_names(observation, limit=1)
    return names[0] if names else ""


def _distinctive_element_names(observation: dict, *, limit: int) -> list[str]:
    common_names = {
        "创建智能体",
        "探索广场",
        "批量任务",
        "工作台",
        "资源库",
        "效果评测",
        "发布管理",
        "线上观测",
        "自动优化",
        "空间管理",
        "文档中心",
        "收藏",
    }
    names = []
    for element in observation.get("elements", []) if isinstance(observation.get("elements"), list) else []:
        if not isinstance(element, dict):
            continue
        name = str(element.get("name") or element.get("text") or "").strip()
        if not name or name in common_names or "所有者" in name:
            continue
        if name not in names:
            names.append(name)
        if len(names) >= limit:
            break
    return names


def _compact_business_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^标题：[^。]*。", "", text).strip()
    text = re.sub(r"^可交互元素：\d+。链接：\d+。表单：\d+。表格：\d+。", "", text).strip()
    text = text.replace("正文：", "").strip()
    if len(text) <= 140:
        return text
    return text[:139].rstrip() + "…"


def _live_module_summary(explored: int, planned: int, recent_page: dict | None, blocker_summary: str) -> str:
    recent_text = f"最近页面：{recent_page.get('semantic_title') or recent_page['title']}" if recent_page else "最近页面：无"
    if blocker_summary != "无":
        return f"已覆盖 {explored}/{planned} 个页面，{recent_text}，阻塞：{blocker_summary}。"
    return f"已覆盖 {explored}/{planned} 个页面，{recent_text}，探索中。"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
