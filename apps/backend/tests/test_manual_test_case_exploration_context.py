from pathlib import Path

import yaml


def test_build_exploration_context_normalizes_pages_operations_and_redacts_values(monkeypatch, tmp_path: Path) -> None:
    from app.core import settings
    from app.services.manual_test_case_generation import exploration_context_builder as builder

    project_id = "project-1"
    exploration_root = tmp_path / project_id / "page_exploration"
    pages_root = exploration_root / "pages"
    pages_root.mkdir(parents=True)
    (pages_root / "page-login.yaml").write_text(
        yaml.safe_dump(
            {
                "elements": [
                    {"element_key": "username", "name": "用户名", "role": "textbox", "action_type": "fill"},
                    {"element_key": "password", "name": "密码", "role": "textbox", "action_type": "fill"},
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    (exploration_root / "operations.yaml").write_text(
        yaml.safe_dump(
            {
                "operations": [
                    {
                        "key": "login",
                        "page_path": "/login",
                        "steps": [
                            {
                                "action": "fill",
                                "element_key": "password",
                                "value": "secret-value",
                                "expected": ["输入框展示掩码内容"],
                            }
                        ],
                    }
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(settings, "PROJECT_FILE_STORAGE_ROOT", tmp_path)
    monkeypatch.setattr(
        builder.page_exploration_service,
        "list_project_pages",
        lambda actor, project_id: [
            {
                "id": "page-login",
                "title": "登录页",
                "display_name": "用户登录",
                "breadcrumb": ["首页", "登录"],
                "entry_path": "/login",
                "structure_summary": "账号密码登录表单",
            }
        ],
    )
    monkeypatch.setattr(
        builder.page_exploration_service,
        "get_project_page_yaml_content",
        lambda actor, project_id, page_id: {
            "content": (pages_root / f"{page_id}.yaml").read_text(encoding="utf-8")
        },
    )

    context = builder.build_exploration_context(
        actor={"id": "u-admin"},
        project_id=project_id,
        description="验证用户登录密码",
        include_exploration_artifacts=True,
    )

    assert context is not None
    assert context.source_count == 2
    assert context.pages[0].display_name == "用户登录"
    assert context.pages[0].elements[0].name in {"用户名", "密码"}
    assert context.operations[0].steps[0].value == "<redacted-password>"


def test_build_exploration_context_skips_broken_page_and_returns_warning(monkeypatch) -> None:
    from app.services.manual_test_case_generation import exploration_context_builder as builder

    monkeypatch.setattr(
        builder.page_exploration_service,
        "list_project_pages",
        lambda actor, project_id: [{"id": "broken", "title": "损坏页面"}],
    )

    def raise_broken(*_args):
        raise ValueError("invalid yaml")

    monkeypatch.setattr(builder.page_exploration_service, "get_project_page_yaml_content", raise_broken)
    monkeypatch.setattr(builder, "_read_operations", lambda project_id: [])

    context = builder.build_exploration_context(
        actor={"id": "u-admin"},
        project_id="project-1",
        description="验证页面",
        include_exploration_artifacts=True,
    )

    assert context is not None
    assert context.pages == []
    assert context.warnings == ["探索页面 broken 无法解析，已跳过。"]


def test_build_exploration_context_can_be_disabled(monkeypatch) -> None:
    from app.services.manual_test_case_generation import exploration_context_builder as builder

    monkeypatch.setattr(
        builder.page_exploration_service,
        "list_project_pages",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not read artifacts")),
    )

    assert builder.build_exploration_context(
        actor={"id": "u-admin"},
        project_id="project-1",
        description="只根据描述生成",
        include_exploration_artifacts=False,
    ) is None
