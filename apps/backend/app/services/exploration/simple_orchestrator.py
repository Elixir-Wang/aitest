"""
极简探索执行器 - 只做最基本的页面访问和元素采集
删除所有复杂功能：LLM规划、Agent决策、重试逻辑等
"""

import json
from pathlib import Path

from app.services.exploration.browser_session import PlaywrightBrowserSession
from app.services.exploration import event_bus as exploration_event_bus
from app.services.exploration.time_utils import exploration_now_iso
from app.core.storage import store_path


def run_simple_exploration(
    run_id: str,
    artifact_root: Path,
    start_url: str,
    forbidden_paths: str = "",
    storage_state_path: str = "",
) -> dict:
    """
    极简探索：只访问起始页面并采集元素

    流程：
    1. 发布开始事件
    2. 启动浏览器
    3. 导航到起始URL
    4. 采集页面元素
    5. 保存结果
    6. 发布完成事件
    """

    log_path = artifact_root / "logs" / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_and_publish(event_type: str, message: str, data: dict = None):
        """同时写日志和发布事件"""
        timestamp = exploration_now_iso()
        log_line = f"[{timestamp}] {event_type}: {message}\n"

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"日志写入失败: {e}")

        try:
            event_data = data or {}
            event_data["message"] = message
            event_data["timestamp"] = timestamp
            exploration_event_bus.publish(run_id, event_type, event_data)
        except Exception as e:
            print(f"事件发布失败: {e}")

    try:
        # 1. 开始
        log_and_publish("run_started", "开始简化探索", {
            "mode": "simple",
            "start_url": start_url,
        })

        # 2. 启动浏览器
        log_and_publish("browser_starting", "正在启动浏览器...")

        with PlaywrightBrowserSession(
            start_url=start_url,
            storage_state_path=storage_state_path,
            timeout_seconds=30,
        ) as browser:

            log_and_publish("browser_started", "浏览器已启动")

            # 3. 导航
            log_and_publish("navigation_starting", f"导航到: {start_url}")

            nav_result = browser.navigate(start_url)

            if nav_result.get("status") != "passed":
                error_msg = nav_result.get("error", "导航失败")
                log_and_publish("navigation_failed", error_msg, {
                    "error": error_msg,
                    "url": start_url,
                })

                return {
                    "status": "blocked",
                    "summary": f"导航失败: {error_msg}",
                    "log_path": store_path(log_path) or "",
                }

            log_and_publish("navigation_success", "导航成功", {
                "url": nav_result.get("after_url", start_url),
            })

            # 4. 采集元素
            log_and_publish("observation_starting", "正在采集页面元素...")

            observation = browser.observe()

            title = observation.get("title", "")
            url = observation.get("url", start_url)
            normalized_url = observation.get("normalized_url") or url
            elements = observation.get("elements", [])
            page_artifact = _structured_page_artifact(
                url=url,
                normalized_url=normalized_url,
                title=title,
                elements=elements,
                forms=observation.get("forms", []),
                tables=observation.get("tables", []),
                summary=observation.get("page_text_summary", ""),
            )

            log_and_publish("observation_completed", f"采集完成，发现 {len(elements)} 个元素", {
                "title": title,
                "url": url,
                "element_count": len(elements),
            })

            # 5. 保存结果
            log_and_publish("saving_results", "正在保存结果...")

            # 保存页面数据
            pages_file = artifact_root / "pages.json"
            pages_data = {
                "pages": [{
                    "id": "page-001",
                    "url": url,
                    "title": title,
                    "element_count": len(elements),
                    "elements": elements[:100],  # 最多保存100个元素
                    "captured_at": exploration_now_iso(),
                }]
            }
            pages_file.write_text(
                json.dumps(pages_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            # 保存摘要
            summary_file = artifact_root / "summary.json"
            summary_data = {
                "status": "completed",
                "summary": f"完成探索，采集1个页面，发现 {len(elements)} 个元素",
                "pages_count": 1,
                "elements_count": len(elements),
                "start_url": start_url,
                "actual_url": url,
                "page_title": title,
            }
            summary_file.write_text(
                json.dumps(summary_data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            log_and_publish("results_saved", "结果已保存", {
                "pages_file": str(pages_file),
                "summary_file": str(summary_file),
            })

            # 6. 完成
            log_and_publish("run_completed", "探索完成", {
                "status": "completed",
                "pages_count": 1,
                "elements_count": len(elements),
            })

            return {
                "status": "completed",
                "summary": f"完成探索：采集1个页面，发现 {len(elements)} 个元素",
                "structured_pages": [page_artifact],
                "graph": {
                    "nodes": [
                        {
                            "id": "page-001",
                            "url": url,
                            "title": title or url,
                        }
                    ],
                    "edges": [],
                    "paths": [],
                },
                "blockers": [],
                "pages_count": 1,
                "elements_count": len(elements),
                "log_path": store_path(log_path) or "",
                "log": log_path.read_text(encoding="utf-8") if log_path.exists() else "",
            }

    except Exception as e:
        error_msg = f"探索异常: {type(e).__name__}: {str(e)}"
        log_and_publish("error", error_msg, {"exception": str(e)})

        import traceback
        traceback_text = traceback.format_exc()

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n=== EXCEPTION TRACEBACK ===\n{traceback_text}\n")
        except:
            pass

        return {
            "status": "blocked",
            "summary": error_msg,
            "log_path": store_path(log_path) or "",
            "log": traceback_text,
        }


def _structured_page_artifact(
    *,
    url: str,
    normalized_url: str,
    title: str,
    elements: list[dict],
    forms: list[dict],
    tables: list[dict],
    summary: str,
) -> dict:
    actions = []
    accessibility_tree = []
    for index, element in enumerate(elements, start=1):
        element_id = str(element.get("id") or f"element-{index:03d}")
        selector = element.get("primary_selector") or element.get("fallback_selector") or {}
        selector_code = selector.get("code") if isinstance(selector, dict) else str(selector or "")
        selector_kind = selector.get("kind") if isinstance(selector, dict) else ""
        role = str(element.get("role") or element.get("action_type") or "element")
        name = str(element.get("name") or element.get("text") or role)
        action_type = str(element.get("action_type") or ("fill" if role in {"textbox", "input"} else "click"))
        actions.append(
            {
                "id": element_id,
                "element_id": element_id,
                "name": name,
                "role": role,
                "action_type": action_type,
                "locator_hint": selector_code,
                "recommended_locator": selector_code,
                "selector_kind": selector_kind,
                "risk_hint": str(element.get("risk_hint") or "normal"),
                "status": "observed",
            }
        )
        accessibility_tree.append(
            {
                "id": element_id,
                "role": role,
                "name": name,
                "locator_hint": selector_code,
                "fallback_locator": selector_code,
            }
        )

    return {
        "page": {
            "id": "page-001",
            "url": url,
            "title": title or url,
            "normalized_url": normalized_url or url,
            "module": "站点入口",
            "depth": 0,
            "status": "explored",
            "structure_summary": summary or f"已采集页面，发现 {len(elements)} 个可交互元素。",
        },
        "accessibility_tree": accessibility_tree,
        "actions": actions,
        "forms": forms if isinstance(forms, list) else [],
        "tables": tables if isinstance(tables, list) else [],
        "relations": {"incoming_edges": [], "outgoing_edges": []},
        "quality": {"confidence": "observed", "needs_confirmation": False, "blockers": []},
        "steps": [
            {
                "id": "step-001",
                "type": "observe",
                "title": "采集页面事实",
                "detail": summary or f"发现 {len(elements)} 个可交互元素。",
                "status": "completed",
                "source": "runner",
                "occurred_at": exploration_now_iso(),
            }
        ],
    }
