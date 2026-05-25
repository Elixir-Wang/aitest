from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.agents.definitions import AgentDefinition
from app.agents.runtime import (
    _build_model_provider,
    _extract_usage,
    _supports_structured_output,
    _serialize_final_output,
    resolve_agent_model,
    resolve_agent_model_selection,
    run_agent,
    AgentModelSelection,
)
from app.core.db import connect
from pydantic import BaseModel


class AgentRuntimeTest(unittest.TestCase):
    def test_resolve_agent_model_uses_enabled_assigned_model(self):
        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'openai-compatible', 'gpt-selected', 'https://api.example.com/v1', 'sk-test', '', 'enabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('raw_requirement_format_converter', 'mp-1')"
                )

            model = resolve_agent_model(
                AgentDefinition(
                    id="raw_requirement_format_converter",
                    name="原始需求格式转换智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        self.assertEqual(model, "gpt-selected")

    def test_resolve_agent_model_selection_exposes_enabled_assignment_metadata(self):
        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'openai-compatible', 'gpt-selected', 'https://api.example.com/v1', 'sk-test', '', 'enabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('raw_requirement_format_converter', 'mp-1')"
                )

            selection = resolve_agent_model_selection(
                AgentDefinition(
                    id="raw_requirement_format_converter",
                    name="原始需求格式转换智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        self.assertEqual(selection.model, "gpt-selected")
        self.assertEqual(selection.model_provider_id, "mp-1")
        self.assertEqual(selection.provider, "openai-compatible")
        self.assertEqual(selection.base_url, "https://api.example.com/v1")
        self.assertEqual(selection.api_key, "sk-test")
        self.assertTrue(selection.using_assignment)

    def test_resolve_agent_model_keeps_default_when_assignment_is_disabled(self):
        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'openai-compatible', 'gpt-disabled', 'https://api.example.com/v1', 'sk-test', '', 'disabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('raw_requirement_format_converter', 'mp-1')"
                )

            model = resolve_agent_model(
                AgentDefinition(
                    id="raw_requirement_format_converter",
                    name="原始需求格式转换智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        self.assertEqual(model, "gpt-default")

    def test_build_model_provider_requires_api_key(self):
        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'openai-compatible', 'gpt-selected', 'https://api.example.com/v1', '', '', 'enabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('raw_requirement_format_converter', 'mp-1')"
                )

            selection = resolve_agent_model_selection(
                AgentDefinition(
                    id="raw_requirement_format_converter",
                    name="原始需求格式转换智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        with self.assertRaisesRegex(ValueError, "未保存 API Key"):
            _build_model_provider(selection)

    def test_build_model_provider_treats_deepseek_as_openai_compatible(self):
        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'DeepSeek', 'deepseek-chat', 'https://api.deepseek.com', 'sk-test', '', 'enabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('requirement_merge', 'mp-1')"
                )

            selection = resolve_agent_model_selection(
                AgentDefinition(
                    id="requirement_merge",
                    name="需求归并智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        self.assertIsNotNone(_build_model_provider(selection))

    def test_build_model_provider_uses_stored_plain_api_key(self):
        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'DeepSeek', 'deepseek-chat', 'https://api.deepseek.com', 'sk-plain', '', 'enabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('requirement_merge', 'mp-1')"
                )

            selection = resolve_agent_model_selection(
                AgentDefinition(
                    id="requirement_merge",
                    name="需求归并智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        self.assertEqual(selection.api_key, "sk-plain")
        self.assertIsNotNone(_build_model_provider(selection))

    def test_build_model_provider_requires_agent_model_assignment(self):
        with isolated_model_store():
            selection = resolve_agent_model_selection(
                AgentDefinition(
                    id="raw_requirement_format_converter",
                    name="原始需求格式转换智能体",
                    description="",
                    instructions="",
                    model="gpt-default",
                )
            )

        with self.assertRaisesRegex(ValueError, "未分配可用模型配置"):
            _build_model_provider(selection)

    def test_run_agent_passes_assigned_model_provider_to_runner(self):
        captured = {}

        class Result:
            final_output = "完成"
            raw_responses = []
            new_items = []
            usage = {"requests": 1}

        async def fake_run(agent, prompt, *, run_config=None, **_kwargs):
            captured["agent_model"] = agent.model
            captured["prompt"] = prompt
            captured["run_config_model"] = run_config.model
            captured["model_provider"] = run_config.model_provider
            captured["trace_metadata"] = run_config.trace_metadata
            return Result()

        with isolated_model_store():
            with connect() as db:
                db.execute(
                    """
                    INSERT INTO model_providers
                      (id, provider, model, base_url, api_key, description, status, created_by)
                    VALUES
                      ('mp-1', 'openai-compatible', 'gpt-selected', 'https://api.example.com/v1', 'sk-test', '', 'enabled', 'u-admin')
                    """
                )
                db.execute(
                    "INSERT INTO agent_model_assignments (agent_id, model_provider_id) VALUES ('raw_requirement_format_converter', 'mp-1')"
                )

            with patch("app.agents.runtime.Runner.run", fake_run):
                result = asyncio.run(run_agent("raw_requirement_format_converter", "转换这个需求文件"))

        self.assertEqual(result.output, "完成")
        self.assertEqual(result.model, "gpt-selected")
        self.assertEqual(result.model_provider_id, "mp-1")
        self.assertEqual(captured["agent_model"], "gpt-selected")
        self.assertEqual(captured["run_config_model"], "gpt-selected")
        self.assertIsNotNone(captured["model_provider"])
        self.assertEqual(captured["trace_metadata"]["model_provider_id"], "mp-1")

    def test_extract_usage_prefers_result_usage_model_dump(self):
        class Usage:
            def model_dump(self):
                return {"requests": 1, "input_tokens": 10, "output_tokens": 20}

        class Result:
            usage = Usage()
            raw_responses = []

        self.assertEqual(
            _extract_usage(Result()),
            {"requests": 1, "input_tokens": 10, "output_tokens": 20},
        )

    def test_extract_usage_falls_back_to_latest_raw_response_usage(self):
        class Usage:
            total_tokens = 30
            input_tokens = 10
            output_tokens = 20

        class Response:
            usage = Usage()

        class Result:
            usage = None
            raw_responses = [Response()]

        self.assertEqual(
            _extract_usage(Result()),
            {"total_tokens": 30, "input_tokens": 10, "output_tokens": 20},
        )

    def test_serialize_final_output_preserves_structured_model(self):
        class ResultModel(BaseModel):
            title: str
            count: int

        self.assertEqual(
            _serialize_final_output(ResultModel(title="需求解析", count=2)),
            {"title": "需求解析", "count": 2},
        )

    def test_structured_output_only_enabled_for_openai_provider(self):
        self.assertTrue(_supports_structured_output(AgentModelSelection(model="gpt-5.4-mini", provider="openai")))
        self.assertFalse(_supports_structured_output(AgentModelSelection(model="deepseek-chat", provider="DeepSeek")))
        self.assertFalse(
            _supports_structured_output(AgentModelSelection(model="custom-model", provider="openai-compatible"))
        )


class isolated_model_store:
    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "ai_testing.db"
        self.patch = patch("app.core.db.DB_PATH", db_path)
        self.patch.start()
        with connect() as db:
            db.executescript(
                """
                CREATE TABLE model_providers (
                  id TEXT PRIMARY KEY,
                  provider TEXT NOT NULL,
                  model TEXT NOT NULL,
                  base_url TEXT NOT NULL DEFAULT '',
                  api_key TEXT NOT NULL DEFAULT '',
                  description TEXT NOT NULL DEFAULT '',
                  status TEXT NOT NULL DEFAULT 'enabled',
                  created_by TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE agent_model_assignments (
                  agent_id TEXT PRIMARY KEY,
                  model_provider_id TEXT NOT NULL,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def __exit__(self, exc_type, exc, tb):
        self.patch.stop()
        self.temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
