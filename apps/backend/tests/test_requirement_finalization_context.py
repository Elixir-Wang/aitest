import json
from pathlib import Path

import pytest


def test_finalization_context_filters_no_op_and_unprocessed_p2_p3(tmp_path, monkeypatch):
    from app.services.document import finalization_context as context

    standard_path = tmp_path / "standard.md"
    standard_path.write_text("# 标准需求\n", encoding="utf-8")

    analysis = {
        "id": "analysis-1",
        "output_json": json.dumps(
            {
                "understanding_markdown": "# 初步需求\n",
                "clarification_items": [
                    {"id": "clar-001", "priority": "P0", "question": "P0?"},
                    {"id": "clar-002", "priority": "P2", "question": "P2?"},
                    {"id": "clar-003", "priority": "P3", "question": "P3?"},
                ],
            },
            ensure_ascii=False,
        ),
        "primary_mapping_id": "map-1",
    }

    class Repo:
        @staticmethod
        def find_by_project_and_id(db, project_id, document_id):
            return {"id": document_id, "name": "需求"}

        @staticmethod
        def find_file_mapping(db, mapping_id):
            return {
                "id": "map-1",
                "original_filename": "standard.md",
                "markdown_file_path": str(standard_path),
            }

        @staticmethod
        def find_primary_file_mapping(db, document_id):
            return None

        @staticmethod
        def list_file_mappings(db, document_id):
            return []

    class AnswerRepo:
        @staticmethod
        def list_answers(db, analysis_id):
            return [
                {
                    "question_id": "clar-001",
                    "apply_status": "applied",
                    "answer_markdown": "P0 已确认",
                    "insertion_anchor": "规则",
                },
                {
                    "question_id": "clar-002",
                    "apply_status": "not_applicable",
                    "answer_markdown": "无需处理",
                    "insertion_anchor": "",
                },
            ]

    monkeypatch.setattr(context, "document_repo", Repo)
    monkeypatch.setattr(context, "requirement_clarification_answer_repo", AnswerRepo)

    result = context.build_finalization_context(
        object(),
        project_id="project-1",
        document_id="doc-1",
        analysis=analysis,
    )

    assert [item.question_id for item in result.handled_clarifications] == ["clar-001"]


def test_finalization_context_blocks_open_p0(tmp_path, monkeypatch):
    from fastapi import HTTPException

    from app.services.document import finalization_context as context

    standard_path = tmp_path / "standard.md"
    standard_path.write_text("# 标准需求\n", encoding="utf-8")

    analysis = {
        "id": "analysis-1",
        "output_json": json.dumps(
            {
                "understanding_markdown": "# 初步需求\n",
                "clarification_items": [{"id": "clar-001", "priority": "P0", "question": "P0?"}],
            },
            ensure_ascii=False,
        ),
        "primary_mapping_id": "map-1",
    }

    class Repo:
        @staticmethod
        def find_by_project_and_id(db, project_id, document_id):
            return {"id": document_id, "name": "需求"}

    class AnswerRepo:
        @staticmethod
        def list_answers(db, analysis_id):
            return []

    monkeypatch.setattr(context, "document_repo", Repo)
    monkeypatch.setattr(context, "requirement_clarification_answer_repo", AnswerRepo)

    with pytest.raises(HTTPException) as exc_info:
        context.build_finalization_context(object(), project_id="project-1", document_id="doc-1", analysis=analysis)

    assert exc_info.value.status_code == 409


def test_finalization_context_treats_no_op_p0_as_handled_but_internal_only(tmp_path, monkeypatch):
    from app.services.document import finalization_context as context

    standard_path = tmp_path / "standard.md"
    standard_path.write_text("# 标准需求\n", encoding="utf-8")

    analysis = {
        "id": "analysis-1",
        "output_json": json.dumps(
            {
                "understanding_markdown": "# 初步需求\n",
                "clarification_items": [{"id": "clar-001", "priority": "P0", "question": "P0?"}],
            },
            ensure_ascii=False,
        ),
        "primary_mapping_id": "map-1",
    }

    class Repo:
        @staticmethod
        def find_by_project_and_id(db, project_id, document_id):
            return {"id": document_id, "name": "需求"}

        @staticmethod
        def find_file_mapping(db, mapping_id):
            return {
                "id": "map-1",
                "original_filename": "standard.md",
                "markdown_file_path": str(standard_path),
            }

        @staticmethod
        def find_primary_file_mapping(db, document_id):
            return None

        @staticmethod
        def list_file_mappings(db, document_id):
            return []

    class AnswerRepo:
        @staticmethod
        def list_answers(db, analysis_id):
            return [
                {
                    "question_id": "clar-001",
                    "apply_status": "not_applicable",
                    "answer_markdown": "无需处理",
                    "insertion_anchor": "",
                }
            ]

    monkeypatch.setattr(context, "document_repo", Repo)
    monkeypatch.setattr(context, "requirement_clarification_answer_repo", AnswerRepo)

    result = context.build_finalization_context(
        object(),
        project_id="project-1",
        document_id="doc-1",
        analysis=analysis,
    )

    assert result.handled_clarifications == []
