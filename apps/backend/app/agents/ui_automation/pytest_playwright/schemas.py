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
    "wait_for_response",
    "commit_value",
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
    business_step_id: str = ""
    title: str = ""
    visible: bool = True
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
    after_step_id: str = ""
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
    schema_version: Literal["v2"]
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
        for index, step in enumerate(self.steps):
            if step.kind != "wait_for_response":
                continue
            if index == 0 or self.steps[index - 1].kind not in {"click", "press"}:
                raise ValueError("wait_for_response 必须紧跟发送消息的 click 或 press 步骤。")
            if self.steps[index - 1].page_key != step.page_key:
                raise ValueError("wait_for_response 必须与前一个发送步骤属于同一页面。")
        step_ids = {step.source_step_id for step in self.steps}
        business_step_ids = {step.business_step_id for step in self.steps if step.business_step_id}
        if any(step.business_step_id and not step.title for step in self.steps):
            raise ValueError("显式业务步骤映射必须包含 title。")
        missing_mappings = [
            step.source_step_id
            for step in self.steps
            if not step.business_step_id or not step.title
        ]
        if missing_mappings:
            raise ValueError(
                "v2 自动化计划的每个动作都必须包含 business_step_id 和 title: "
                + ", ".join(missing_mappings)
            )
        titles_by_business_step: dict[str, str] = {}
        for step in self.steps:
            existing_title = titles_by_business_step.setdefault(step.business_step_id, step.title)
            if existing_title != step.title:
                raise ValueError(f"同一业务步骤 {step.business_step_id} 必须使用一致的 title。")
        if any(not re.fullmatch(r"[A-Za-z0-9_.:-]+", step_id) for step_id in business_step_ids):
            raise ValueError("business_step_id 包含非法字符。")
        invalid_checkpoints = [
            assertion.after_step_id
            for assertion in self.assertions
            if assertion.after_step_id and assertion.after_step_id not in step_ids
        ]
        if invalid_checkpoints:
            raise ValueError(f"断言检查点不存在: {', '.join(invalid_checkpoints)}")
        return self

    def require_generation_contract(
        self, source_business_steps: dict[str, str] | None = None
    ) -> AutomationPlan:
        if source_business_steps is not None:
            invalid_ids = sorted(
                {
                    step.business_step_id
                    for step in self.steps
                    if step.business_step_id not in source_business_steps
                }
            )
            if invalid_ids:
                raise ValueError("business_step_id 不存在于原始用例: " + ", ".join(invalid_ids))
            mismatched_titles = sorted(
                {
                    step.business_step_id
                    for step in self.steps
                    if step.title != source_business_steps[step.business_step_id]
                }
            )
            if mismatched_titles:
                raise ValueError(
                    "业务步骤 title 必须与原始用例 action 一致: " + ", ".join(mismatched_titles)
                )
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
