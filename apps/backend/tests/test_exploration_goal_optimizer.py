import pytest
from fastapi import HTTPException

from app.core import db as core_db
from app.agents.model_selection import ModelSelection
from app.seed.init_db import init_db
from app.services.exploration import goal_optimizer

ACTOR = {"id": "u-admin", "role": "admin", "nickname": "管理员", "username": "admin", "project_scope": "全部项目"}


def _use_temp_db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(core_db, "DATA_DIR", data_dir)
    monkeypatch.setattr(core_db, "DB_PATH", data_dir / "ai_testing.db")
    init_db()
    with core_db.connect() as db:
        db.execute(
            """
            INSERT INTO projects (id, name, status, description, created_by)
            VALUES ('project-test', '测试项目', 'active', 'test', 'u-admin')
            """
        )


def test_optimize_goal_uses_site_exploration_model_and_goal_only(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)
    captured: dict[str, str] = {}

    class FakeModel:
        def invoke(self, prompt: str):
            captured["prompt"] = prompt

            class FakeResponse:
                content = "探索登录后的主要页面访问链路，记录页面加载、权限拦截和异常状态。"

            return FakeResponse()

    def fake_resolve(capability_id: str):
        captured["capability_id"] = capability_id
        return ModelSelection(
            provider="deepseek",
            model="deepseek-chat",
            base_url="https://deepseek.example/v1",
            api_key="sk-test",
        )

    def fake_build_agent_model(selection, *, extra_body=None):
        captured["extra_body"] = extra_body
        return FakeModel()

    monkeypatch.setattr(goal_optimizer, "resolve_model_selection", fake_resolve)
    monkeypatch.setattr(goal_optimizer, "build_agent_model", fake_build_agent_model)

    result = goal_optimizer.optimize_exploration_goal(
        "project-test",
        goal_optimizer.ExplorationGoalOptimizeIn(goal="看看登录后哪些页面有问题"),
        ACTOR,
    )

    assert captured["capability_id"] == "site_exploration"
    assert captured["extra_body"] is None
    assert "看看登录后哪些页面有问题" in captured["prompt"]
    assert "整体目标：..." in captured["prompt"]
    assert "模块一：..." in captured["prompt"]
    assert "每个模块下面使用 1. 2. 3. 的有序步骤" in captured["prompt"]
    assert "不要输出 Markdown 标题" in captured["prompt"]
    assert "不要输出“优化后的探索目标”“以下是”等引导语" in captured["prompt"]
    assert "requirement_doc_id" not in captured["prompt"]
    assert result == {"optimized_goal": "探索登录后的主要页面访问链路，记录页面加载、权限拦截和异常状态。"}


def test_optimize_goal_rejects_blank_goal(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _use_temp_db(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        goal_optimizer.optimize_exploration_goal(
            "project-test",
            goal_optimizer.ExplorationGoalOptimizeIn(goal=" "),
            ACTOR,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "EXPLORATION_GOAL_REQUIRED"


def test_goal_schema_limits_goal_to_4000_chars() -> None:
    with pytest.raises(ValueError):
        goal_optimizer.ExplorationGoalOptimizeIn(goal="x" * 4001)


def test_model_extra_body_disables_minimax_thinking() -> None:
    selection = ModelSelection(
        provider="Minimax",
        model="MiniMax-M3",
        base_url="https://minimax.example/v1",
        api_key="sk-test",
    )

    assert goal_optimizer._model_extra_body(selection) == {"thinking": {"type": "disabled"}}


def test_model_extra_body_only_targets_minimax() -> None:
    selection = ModelSelection(
        provider="deepseek",
        model="deepseek-chat",
        base_url="https://deepseek.example/v1",
        api_key="sk-test",
    )

    assert goal_optimizer._model_extra_body(selection) is None
