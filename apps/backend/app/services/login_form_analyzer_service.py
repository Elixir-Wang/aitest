import asyncio
import base64
import json
import re
from pathlib import Path

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.agents.model_selection import build_agent_model, resolve_model_selection
from app.core import settings
from app.services.captcha_solver_service import CAPTCHA_MODEL_CAPABILITY_ID


class LoginFormAnalyzerError(RuntimeError):
    pass


class LoginFormAnalysisOutput(BaseModel):
    username_element_id: str = Field(default="")
    password_element_id: str = Field(default="")
    captcha_image_element_id: str = Field(default="")
    captcha_input_element_id: str = Field(default="")
    agreement_element_id: str | None = None
    login_button_element_id: str = Field(default="")


def _build_login_form_analyzer_model():
    selection = resolve_model_selection(CAPTCHA_MODEL_CAPABILITY_ID)
    return build_agent_model(selection)


def _element_for_id(elements: list[dict], element_id: str) -> dict | None:
    for element in elements:
        if str(element.get("element_id") or "") == element_id:
            return element
    return None


def _locator_for_element(elements: list[dict], element_id: str) -> dict:
    element = _element_for_id(elements, element_id)
    if not element:
        return {}
    locator = element.get("locator")
    if isinstance(locator, dict) and locator.get("type"):
        return locator
    selector = str(element.get("stable_selector") or element.get("selector") or "").strip()
    if selector:
        return {"type": "css", "value": selector}
    return {}


def _heuristic_agreement_locator(elements: list[dict]) -> dict:
    for element in elements:
        text = str(element.get("text") or "")
        class_name = str(element.get("class_name") or "").lower()
        tag = str(element.get("tag") or "").lower()
        if tag == "a" and len(text) <= 12:
            continue
        if re.search(r"我已阅读|read and agree|accept.*terms", text, re.IGNORECASE):
            locator = element.get("locator")
            if isinstance(locator, dict) and locator.get("type"):
                return locator
            return {"type": "text", "value": "我已阅读并同意"}
        if "checkbox" in class_name and re.search(r"协议|privacy|agreement|terms|我已阅读", text, re.IGNORECASE):
            locator = element.get("locator")
            if isinstance(locator, dict) and locator.get("type"):
                return locator
    for element in elements:
        class_name = str(element.get("class_name") or "").lower()
        aria_checked = str(element.get("aria_checked") or "").lower()
        if "checkbox" in class_name and aria_checked in {"", "false"}:
            locator = element.get("locator")
            if isinstance(locator, dict) and locator.get("type"):
                return locator
    return {}


def analyze_login_form(page_image_path: Path, elements: list[dict]) -> dict:
    path = Path(page_image_path)
    if not path.is_file():
        raise LoginFormAnalyzerError("登录页截图不存在。")

    if not elements:
        return {"strategy": "heuristic"}

    try:
        image_bytes = path.read_bytes()
    except OSError as exc:
        raise LoginFormAnalyzerError("读取登录页截图失败。") from exc

    encoded = base64.b64encode(image_bytes).decode("ascii")
    compact_elements = json.dumps(elements[:60], ensure_ascii=False)
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    "你是 Web 登录页分析助手。根据页面截图和元素列表，识别登录表单关键控件。\n"
                    "只返回 JSON，不要解释。字段：\n"
                    "- username_element_id: 用户名/账号输入框元素 ID\n"
                    "- password_element_id: 密码输入框元素 ID\n"
                    "- captcha_image_element_id: 图形验证码图片元素 ID\n"
                    "- captcha_input_element_id: 图形验证码输入框元素 ID\n"
                    "- agreement_element_id: 用户协议/隐私政策勾选区域元素 ID（可为 label、自定义 checkbox 容器，不要选纯链接），没有则 null\n"
                    "- login_button_element_id: 主登录按钮元素 ID\n"
                    "所有 ID 必须来自 elements 列表中的 element_id。\n"
                    f"elements={compact_elements}"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            },
        ]
    )

    try:
        model = _build_login_form_analyzer_model()
        if not hasattr(model, "bind_tools"):
            response = asyncio.run(model.ainvoke({"messages": [message]}))
        else:
            agent = create_agent(
                model=model,
                tools=[],
                system_prompt=(
                    "你是 Web 登录页分析助手。\n"
                    "根据页面截图和元素列表，识别登录表单关键控件。\n"
                    "要求：\n"
                    "1. 只输出结构化结果，不要输出解释、JSON 代码块或额外文本。\n"
                    "2. 所有 element_id 必须来自输入 elements 列表。\n"
                    "3. 找不到时对应字段返回空字符串；agreement_element_id 可以返回 null。\n"
                    "4. 不要猜测不存在的元素。"
                ),
                response_format=ToolStrategy(LoginFormAnalysisOutput),
            )
            response = asyncio.run(agent.ainvoke({"messages": [message]}))
    except ValueError as exc:
        raise LoginFormAnalyzerError(str(exc)) from exc
    except Exception as exc:
        raise LoginFormAnalyzerError("登录页元素规划失败。") from exc

    raw_response = str(getattr(response, "content", response) or "").strip()
    _write_debug_payload(page_image_path, raw_response)
    payload = _extract_structured_payload(response)
    username_locator = _locator_for_element(elements, str(payload.username_element_id or ""))
    password_locator = _locator_for_element(elements, str(payload.password_element_id or ""))
    captcha_image_locator = _locator_for_element(elements, str(payload.captcha_image_element_id or ""))
    captcha_input_locator = _locator_for_element(elements, str(payload.captcha_input_element_id or ""))
    agreement_locator = _locator_for_element(elements, str(payload.agreement_element_id or ""))
    if not agreement_locator:
        agreement_locator = _heuristic_agreement_locator(elements)
    login_button_locator = _locator_for_element(elements, str(payload.login_button_element_id or ""))

    if not username_locator or not password_locator or not captcha_image_locator or not captcha_input_locator or not login_button_locator:
        return {"strategy": "heuristic"}

    return {
        "strategy": "planned",
        "username_locator": username_locator,
        "password_locator": password_locator,
        "captcha_image_locator": captcha_image_locator,
        "captcha_input_locator": captcha_input_locator,
        "agreement_locator": agreement_locator,
        "login_button_locator": login_button_locator,
        "username_selector": username_locator.get("value", ""),
        "password_selector": password_locator.get("value", ""),
        "captcha_image_selector": captcha_image_locator.get("value", ""),
        "captcha_input_selector": captcha_input_locator.get("value", ""),
        "agreement_selector": agreement_locator.get("value", ""),
        "login_button_selector": login_button_locator.get("value", ""),
        "has_agreement_checkbox": bool(agreement_locator),
    }


def _extract_structured_payload(response):
    if hasattr(response, "structured_response") and response.structured_response is not None:
        return response.structured_response
    content = getattr(response, "content", None)
    if isinstance(content, LoginFormAnalysisOutput):
        return content
    if isinstance(content, str):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LoginFormAnalyzerError("登录页元素规划结果缺少结构化输出。") from exc
        return LoginFormAnalysisOutput.model_validate(payload)
    if isinstance(response, dict) and "structured_response" in response:
        return response["structured_response"]
    raise LoginFormAnalyzerError("登录页元素规划结果缺少结构化输出。")


def _write_debug_payload(page_image_path: Path, raw_response: str) -> None:
    if not raw_response:
        return
    debug_dir = Path(settings.PROJECT_FILE_STORAGE_ROOT) / "debug" / "login-form-analysis"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / f"{Path(page_image_path).stem}.txt"
    debug_path.write_text(raw_response + "\n", encoding="utf-8")
