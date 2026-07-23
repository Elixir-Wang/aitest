from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


LocatorStrategy = Literal["role", "label", "placeholder", "test_id", "text", "css", "xpath"]
StepKind = Literal[
    "navigate",
    "click",
    "fill",
    "select_option",
    "check",
    "uncheck",
    "press",
    "upload",
    "wait_visible",
    "click_parameter_text",
]
AssertionKind = Literal["visible", "hidden", "text", "url", "value"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LocatorPlan(StrictModel):
    strategy: LocatorStrategy
    role: str = ""
    name: str = ""
    value: str = ""
    exact: bool = True
    evidence_refs: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_strategy_fields(self):
        if self.strategy == "role" and (not self.role or not self.name):
            raise ValueError("role locator 必须包含 role 和 name。")
        if self.strategy in {"label", "placeholder", "test_id", "text", "css", "xpath"} and not (
            self.value or self.name
        ):
            raise ValueError(f"{self.strategy} locator 必须包含 value 或 name。")
        return self


class ElementPlan(StrictModel):
    key: str = Field(min_length=1)
    locator: LocatorPlan


class PageObjectPlan(StrictModel):
    page_key: str = Field(min_length=1)
    class_name: str = Field(pattern=r"^[A-Z][A-Za-z0-9]*Page$")
    file_path: str = Field(pattern=r"^pages/generated/[A-Za-z0-9_./-]+\.py$")
    route: str = ""
    elements: list[ElementPlan] = Field(default_factory=list)


class StepPlan(StrictModel):
    source_step_id: str = Field(min_length=1)
    kind: StepKind
    page_key: str = Field(min_length=1)
    element_key: str = ""
    value_ref: str = ""
    value: str = ""

    @model_validator(mode="after")
    def validate_target(self):
        if self.kind not in {"navigate", "click_parameter_text"} and not self.element_key:
            raise ValueError(f"{self.kind} 步骤必须包含 element_key。")
        if self.kind == "click_parameter_text" and not self.value_ref:
            raise ValueError("click_parameter_text 步骤必须包含 value_ref。")
        if self.kind in {"fill", "select_option", "press", "upload"} and not (self.value_ref or self.value):
            raise ValueError(f"{self.kind} 步骤必须包含 value_ref 或 value。")
        return self


class AssertionPlan(StrictModel):
    source_expected_result_id: str = Field(min_length=1)
    kind: AssertionKind
    page_key: str = ""
    element_key: str = ""
    expected_ref: str = ""
    expected: str = ""

    @model_validator(mode="after")
    def validate_target(self):
        if self.kind != "url" and (not self.page_key or not self.element_key):
            raise ValueError(f"{self.kind} 断言必须包含 page_key 和 element_key。")
        if self.kind in {"text", "url", "value"} and not (self.expected_ref or self.expected):
            raise ValueError(f"{self.kind} 断言必须包含 expected_ref 或 expected。")
        return self


class ArtifactPlan(StrictModel):
    test_file: str = Field(pattern=r"^testcases/generated/[A-Za-z0-9_./-]+\.py$")
    data_file: str = Field(pattern=r"^data/projects/[A-Za-z0-9_./-]+\.(?:yaml|yml|json)$")
    plan_file: str = Field(pattern=r"^data/projects/[A-Za-z0-9_./-]+\.plan\.json$")


class AutomationPlan(StrictModel):
    schema_version: Literal["v1"] = "v1"
    project_id: str = Field(min_length=1)
    automation_case_id: str = Field(min_length=1)
    source_test_case_id: str = Field(min_length=1)
    source_test_case_version: int = Field(ge=1)
    environment_id: str = Field(min_length=1)
    exploration_run_id: str = ""
    parameters: list[str] = Field(default_factory=list)
    page_objects: list[PageObjectPlan] = Field(default_factory=list)
    steps: list[StepPlan] = Field(default_factory=list)
    assertions: list[AssertionPlan] = Field(default_factory=list)
    artifacts: ArtifactPlan

    @model_validator(mode="after")
    def validate_project_namespace(self):
        if len(self.parameters) != len(set(self.parameters)):
            raise ValueError("参数名称不能重复。")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in self.parameters):
            raise ValueError("参数名称必须是合法的 Python 标识符。")
        project_key = re.sub(r"_+", "_", re.sub(r"[^a-zA-Z0-9_]+", "_", self.project_id.lower())).strip("_")
        page_prefix = f"pages/generated/{project_key}/"
        test_prefix = f"testcases/generated/{project_key}/"
        data_prefix = f"data/projects/{project_key}/cases/"
        if any(not page.file_path.startswith(page_prefix) for page in self.page_objects):
            raise ValueError("Page Object 路径必须位于当前业务项目命名空间。")
        if not self.artifacts.test_file.startswith(test_prefix):
            raise ValueError("测试文件路径必须位于当前业务项目命名空间。")
        if not self.artifacts.data_file.startswith(data_prefix) or not self.artifacts.plan_file.startswith(data_prefix):
            raise ValueError("数据和计划文件路径必须位于当前业务项目命名空间。")
        return self


__all__ = [
    "ArtifactPlan",
    "AssertionPlan",
    "AutomationPlan",
    "ElementPlan",
    "LocatorPlan",
    "PageObjectPlan",
    "StepPlan",
]
