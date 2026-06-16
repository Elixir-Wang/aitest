import asyncio
import base64
import re
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.agents.model_selection import build_agent_model, resolve_model_selection

# 复用站点探索已分配的模型，无需单独注册验证码识别能力。
CAPTCHA_MODEL_CAPABILITY_ID = "site_exploration"
_NORMALIZE_PATTERN = re.compile(r"[^A-Za-z0-9]")
_THINK_TAG_PATTERN = re.compile(
    r"`(?:think|thinking)`[\s\S]*?`(?:/think|/thinking)`",
    re.IGNORECASE,
)
_COMMON_WORDS = {
    "that",
    "this",
    "with",
    "from",
    "have",
    "user",
    "image",
    "look",
    "care",
    "fully",
    "want",
    "lets",
    "the",
    "appe",
    "arto",
    "be",
    "think",
    "output",
    "characters",
    "captcha",
    "froman",
}


class CaptchaSolverError(RuntimeError):
    pass


def build_captcha_solver_model():
    selection = resolve_model_selection(CAPTCHA_MODEL_CAPABILITY_ID)
    return build_agent_model(selection)


def extract_captcha_code(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        raise CaptchaSolverError("字母验证码识别结果为空。")

    text = _THINK_TAG_PATTERN.sub("", text).strip()
    compact = _NORMALIZE_PATTERN.sub("", text)
    if 3 <= len(compact) <= 6:
        if compact.lower() in _COMMON_WORDS:
            raise CaptchaSolverError("无法从模型输出中提取有效验证码。")
        return compact

    end_match = re.search(r"(?:appeartobe|answeris|resultis|captchais|codeis|is)([A-Za-z0-9]{3,6})$", compact, re.IGNORECASE)
    if end_match:
        return end_match.group(1)

    for part in reversed(re.split(r"think", text, flags=re.IGNORECASE)):
        part_compact = _NORMALIZE_PATTERN.sub("", part)
        if 3 <= len(part_compact) <= 6:
            if part_compact.lower() in _COMMON_WORDS:
                continue
            return part_compact

    for marker in ("answer", "result", "captcha", "code"):
        marker_match = re.search(rf"{marker}([A-Za-z0-9]{{3,6}})", compact, re.IGNORECASE)
        if marker_match:
            token = marker_match.group(1)
            if token.lower() not in _COMMON_WORDS and len(set(token.lower())) > 1:
                return token

    raise CaptchaSolverError("无法从模型输出中提取有效验证码。")


def solve_letter_captcha(image_path: Path) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise CaptchaSolverError("验证码截图不存在。")

    try:
        image_bytes = path.read_bytes()
    except OSError as exc:
        raise CaptchaSolverError("读取验证码截图失败。") from exc

    if not image_bytes:
        raise CaptchaSolverError("验证码截图为空。")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    "这是一张登录页字母验证码图片。"
                    "只输出 4-6 位验证码字符本身，区分大小写。"
                    "禁止输出解释、思考过程、标点或空格。"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encoded}"},
            },
        ]
    )

    try:
        model = build_captcha_solver_model()
        response = asyncio.run(model.ainvoke([message]))
    except ValueError as exc:
        raise CaptchaSolverError(str(exc)) from exc
    except Exception as exc:
        raise CaptchaSolverError("字母验证码识别失败。") from exc

    raw = str(getattr(response, "content", response) or "").strip()
    return extract_captcha_code(raw)
