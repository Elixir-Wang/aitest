from pathlib import Path

import pytest

from app.services import captcha_solver_service


def test_solve_letter_captcha_returns_normalized_uppercase(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image_path = tmp_path / "captcha.png"
    image_path.write_bytes(b"fake-png")

    class FakeResponse:
        content = "ab12"

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(captcha_solver_service, "build_captcha_solver_model", lambda: FakeModel())

    result = captcha_solver_service.solve_letter_captcha(image_path)

    assert result == "ab12"


def test_solve_letter_captcha_strips_non_alphanumeric(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image_path = tmp_path / "captcha.png"
    image_path.write_bytes(b"fake-png")

    class FakeResponse:
        content = "x9-k"

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(captcha_solver_service, "build_captcha_solver_model", lambda: FakeModel())

    assert captcha_solver_service.solve_letter_captcha(image_path) == "x9k"


def test_solve_letter_captcha_rejects_empty_model_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    image_path = tmp_path / "captcha.png"
    image_path.write_bytes(b"fake-png")

    class FakeResponse:
        content = "   "

    class FakeModel:
        async def ainvoke(self, _messages):
            return FakeResponse()

    monkeypatch.setattr(captcha_solver_service, "build_captcha_solver_model", lambda: FakeModel())

    with pytest.raises(captcha_solver_service.CaptchaSolverError):
        captcha_solver_service.solve_letter_captcha(image_path)


def test_solve_letter_captcha_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(captcha_solver_service.CaptchaSolverError):
        captcha_solver_service.solve_letter_captcha(tmp_path / "missing.png")


def test_build_captcha_solver_model_uses_site_exploration(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    def fake_resolve(capability_id: str):
        captured["capability_id"] = capability_id
        raise ValueError("stop")

    monkeypatch.setattr(captcha_solver_service, "resolve_model_selection", fake_resolve)

    with pytest.raises(ValueError, match="stop"):
        captcha_solver_service.build_captcha_solver_model()

    assert captured["capability_id"] == "site_exploration"


def test_extract_captcha_code_returns_plain_answer() -> None:
    assert captcha_solver_service.extract_captcha_code("6MXK") == "6MXK"


def test_extract_captcha_code_strips_think_tags() -> None:
    raw = "`think`The captcha appears to be GMXK`/think`GMXK"
    assert captcha_solver_service.extract_captcha_code(raw) == "GMXK"


def test_extract_captcha_code_extracts_from_minimax_thinking_blob() -> None:
    raw = (
        "thinkTheuserwantsthecharactersfromthecaptchaimageIcarefullylookattheimage"
        "andappeartobeGMXKthinkGMXK"
    )
    assert captcha_solver_service.extract_captcha_code(raw) == "GMXK"


def test_extract_captcha_code_rejects_overlong_garbage() -> None:
    raw = "think这是一段没有验证码结果的思考过程think"
    with pytest.raises(captcha_solver_service.CaptchaSolverError):
        captcha_solver_service.extract_captcha_code(raw)


def test_extract_captcha_code_rejects_common_language_fragment() -> None:
    with pytest.raises(captcha_solver_service.CaptchaSolverError):
        captcha_solver_service.extract_captcha_code("froman")
