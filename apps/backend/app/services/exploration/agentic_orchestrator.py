import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agents.site_exploration import agentic_service
from app.agents.site_exploration.agentic_schemas import AgenticAction, AgenticDecisionOutput, AgenticExplorationInput
from app.core.db import connect
from app.core.storage import store_path
from app.repositories import exploration_repo
from app.services.exploration import action_risk, event_bus
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

    def run(self) -> dict:
        run = self._load_run()
        if not run:
            return self._blocked_result("探索任务不存在。", "run_missing", "重新创建探索任务后再试。")

        max_pages = int(_mapping_get(run, "max_pages", 50) or 50)
        max_actions = int(_mapping_get(run, "max_actions", 1000) or 1000)
        max_turns = min(max(max_actions, 1), 200)
        self._configure_live_module(run)

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
        action_payload = action.model_dump()
        action_decision = action_risk.evaluate_action(action_payload, element)

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
            return agentic_service.fallback_decision(agent_input)

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
        return payload

    def _record_observation(self, observation: dict) -> dict:
        signature = str(observation.get("state_signature") or observation.get("normalized_url") or observation.get("url") or "")
        existing = self.pages_by_signature.get(signature)
        if existing:
            self._publish_module_progress(recent_page=existing)
            return existing
        page_id = f"page-{len(self.pages_by_signature) + 1:03d}"
        title = str(observation.get("title") or observation.get("url") or "未命名页面")
        page_doc = {
            "artifact_schema_version": 2,
            "page": {
                "id": page_id,
                "title": title,
                "url": str(observation.get("url") or ""),
                "normalized_url": str(observation.get("normalized_url") or observation.get("url") or ""),
                "module": _infer_module_name(title, str(observation.get("url") or "")),
                "depth": len(self.pages_by_signature),
                "status": "explored",
                "structure_summary": str(observation.get("page_text_summary") or "Agentic Loop 已采集页面观察。"),
            },
            "states": [
                {
                    "id": "default",
                    "type": "page",
                    "title": title,
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
            "url": page_doc["page"]["url"],
            "module": page_doc["page"]["module"],
        }
        self._add_step(page_doc, "observe", "观察页面", page_doc["page"]["structure_summary"])
        self._publish(
            "page_discovered",
            {
                "module_key": self.live_module_key,
                "page_id": page_id,
                "title": page_doc["page"]["title"],
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
        self._publish(
            "step_recorded",
            {
                "module_key": self.live_module_key,
                "page_id": page_doc["page"]["id"],
                "step": step,
            },
        )
        self._publish_module_progress(recent_page=page_doc)

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
        progress_percent = min(100, round((explored / planned) * 100))
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
                "recent_page_title": str(recent.get("title") or "") if recent else "",
                "recent_page_url": str(recent.get("url") or "") if recent else "",
                "blocker_summary": blocker_summary,
                "progress_percent": progress_percent,
                "page_progress_text": f"{explored}/{planned} 页面",
            },
        )

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

    def _result(self, status: str, summary: str) -> dict:
        return {
            "status": status,
            "summary": summary,
            "structured_pages": [self.pages_by_signature[signature] for signature in self.page_order],
            "graph": {"nodes": list(self.graph_nodes.values()), "edges": self.graph_edges, "paths": []},
            "blockers": self.blockers,
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
            "reason_type": reason_type,
            "suggested_action": suggested_action,
            "structured_pages": [self.pages_by_signature[signature] for signature in self.page_order],
            "graph": {"nodes": list(self.graph_nodes.values()), "edges": self.graph_edges, "paths": []},
            "blockers": self.blockers,
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


def _infer_module_name(title: str, url: str) -> str:
    text = str(title or "").strip()
    if text and len(text) <= 40:
        return text
    try:
        from urllib.parse import urlparse

        first = next((item for item in urlparse(url).path.split("/") if item), "")
        return first or "入口页"
    except Exception:
        return "未分组模块"


def _live_module_summary(explored: int, planned: int, recent_page: dict | None, blocker_summary: str) -> str:
    recent_text = f"最近页面：{recent_page['title']}" if recent_page else "最近页面：无"
    if blocker_summary != "无":
        return f"已覆盖 {explored}/{planned} 个页面，{recent_text}，阻塞：{blocker_summary}。"
    return f"已覆盖 {explored}/{planned} 个页面，{recent_text}，探索中。"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
