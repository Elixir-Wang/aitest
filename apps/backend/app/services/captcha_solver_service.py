import asyncio
import base64
import re
from pathlib import Path

from langchain_core.messages import HumanMessage

from app.agents.model_selection import build_agent_model, resolve_model_selection

# 验证码识别优先使用 ddddocr（开源、稳定、无内容限制），失败时回退到 AI 模型
CAPTCHA_MODEL_CAPABILITY_ID = "page_exploration"
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

# 尝试导入 ddddocr
try:
    import ddddocr
    _DDDDOCR_AVAILABLE = True
    _ocr_instance = None
except ImportError:
    _DDDDOCR_AVAILABLE = False
    _ocr_instance = None


def init_captcha_solver():
    """初始化验证码识别器（应用启动时调用，预热模型避免首次识别慢）"""
    global _ocr_instance
    if _DDDDOCR_AVAILABLE and _ocr_instance is None:
        import ddddocr
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)
        print("✅ ddddocr 验证码识别模型已预热")


class CaptchaSolverError(RuntimeError):
    pass


def build_captcha_solver_model():
    selection = resolve_model_selection(CAPTCHA_MODEL_CAPABILITY_ID)
    return build_agent_model(selection)


def extract_captcha_code(raw: str, expected_length: int | None = None) -> str:
    text = str(raw or "").strip()
    if not text:
        raise CaptchaSolverError("字母验证码识别结果为空。")

    text = _THINK_TAG_PATTERN.sub("", text).strip()
    compact = _NORMALIZE_PATTERN.sub("", text)
    if 3 <= len(compact) <= 6:
        if compact.lower() in _COMMON_WORDS:
            raise CaptchaSolverError("无法从模型输出中提取有效验证码。")
        return _validate_expected_length(compact, expected_length)

    end_match = re.search(r"(?:appeartobe|answeris|resultis|captchais|codeis|is)([A-Za-z0-9]{3,6})$", compact, re.IGNORECASE)
    if end_match:
        return _validate_expected_length(end_match.group(1), expected_length)

    for part in reversed(re.split(r"think", text, flags=re.IGNORECASE)):
        part_compact = _NORMALIZE_PATTERN.sub("", part)
        if 3 <= len(part_compact) <= 6:
            if part_compact.lower() in _COMMON_WORDS:
                continue
            return _validate_expected_length(part_compact, expected_length)

    for marker in ("answer", "result", "captcha", "code"):
        marker_match = re.search(rf"{marker}([A-Za-z0-9]{{3,6}})", compact, re.IGNORECASE)
        if marker_match:
            token = marker_match.group(1)
            if token.lower() not in _COMMON_WORDS and len(set(token.lower())) > 1:
                return _validate_expected_length(token, expected_length)

    raise CaptchaSolverError("无法从模型输出中提取有效验证码。")


def solve_letter_captcha(image_path: Path, expected_length: int | None = None) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise CaptchaSolverError("验证码截图不存在。")

    try:
        image_bytes = path.read_bytes()
    except OSError as exc:
        raise CaptchaSolverError("读取验证码截图失败。") from exc

    if not image_bytes:
        raise CaptchaSolverError("验证码截图为空。")

    # ✅ 优化：只使用 ddddocr，快速且成本低
    # 如果识别失败，直接抛出错误让上层重试，而不是回退到慢速的 AI 模型
    if _DDDDOCR_AVAILABLE:
        return _solve_with_ddddocr(image_bytes, expected_length)

    # 如果 ddddocr 不可用，才使用 AI 模型（这种情况很少见）
    return _solve_with_ai_model(image_bytes, expected_length)


def _solve_with_ddddocr(image_bytes: bytes, expected_length: int | None = None) -> str:
    """使用 ddddocr 识别验证码"""
    global _ocr_instance
    if _ocr_instance is None:
        import ddddocr
        _ocr_instance = ddddocr.DdddOcr(show_ad=False)

    raw = _ocr_instance.classification(image_bytes)
    result = _NORMALIZE_PATTERN.sub("", raw)

    if not result:
        raise CaptchaSolverError("ddddocr 识别结果为空。")

    return _validate_expected_length(result, expected_length)


def _solve_with_ai_model(image_bytes: bytes, expected_length: int | None = None) -> str:
    """使用 AI 模型识别验证码（回退方案）"""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    length_instruction = (
        f"只输出 {expected_length} 位验证码字符本身，区分大小写。"
        if expected_length
        else "只输出 4-6 位验证码字符本身，区分大小写。"
    )
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    "请识别图片中的文本字符。\n"
                    f"{length_instruction}\n"
                    "注意区分大小写和相似字符（0/O, 1/l, i/I, 8/B等）。\n"
                    "直接输出字符，不要有任何解释。"
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
    return extract_captcha_code(raw, expected_length=expected_length)


def _validate_expected_length(value: str, expected_length: int | None) -> str:
    if expected_length is None:
        return value

    actual_length = len(value)
    if actual_length == expected_length:
        return value

    raise CaptchaSolverError(
        f"验证码识别结果长度不符，识别出 {actual_length} 位但页面要求 {expected_length} 位。"
    )
