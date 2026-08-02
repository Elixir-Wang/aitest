from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


ValueType = Literal["string", "integer", "number", "boolean", "object", "array", "file", "any"]
StepPhase = Literal["setup", "main", "verify", "cleanup"]
ParameterLocation = Literal["path", "query", "header", "cookie", "json_body", "form", "multipart", "raw_body"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParameterTarget(StrictModel):
    location: ParameterLocation
    path: str = Field(min_length=1, max_length=500)

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("参数目标 path 必须使用以 / 开头的 JSON Pointer。")
        return value

    def legacy_pointer(self) -> str:
        prefixes = {
            "path": "/request/path_params",
            "query": "/request/query",
            "header": "/request/headers",
            "cookie": "/request/cookies",
            "json_body": "/request/json",
            "form": "/request/form",
            "multipart": "/request/multipart_form",
            "raw_body": "/request/body",
        }
        if self.location == "raw_body" and self.path == "/":
            return prefixes[self.location]
        return f"{prefixes[self.location]}{self.path}"


class LiteralValueSource(StrictModel):
    type: Literal["literal"]
    value: Any = None


class UserInputValueSource(StrictModel):
    type: Literal["user_input"]
    name: str = Field(min_length=1, max_length=100)


class EnvironmentValueSource(StrictModel):
    type: Literal["environment"]
    key: str = Field(min_length=1, max_length=100)


class SecretValueSource(StrictModel):
    type: Literal["secret"]
    key: str = Field(min_length=1, max_length=100)


class ScenarioValueSource(StrictModel):
    type: Literal["scenario"]
    name: str = Field(min_length=1, max_length=100)


class StepOutputValueSource(StrictModel):
    type: Literal["step_output"]
    step_id: str = Field(min_length=1, max_length=100)
    variable: str = Field(min_length=1, max_length=100)


class GeneratedValueSource(StrictModel):
    type: Literal["generated"]
    generator: Literal["uuid4", "timestamp_ms", "timestamp_iso", "random_string"]
    length: int | None = Field(default=None, ge=1, le=128)

    @model_validator(mode="after")
    def validate_length(self) -> GeneratedValueSource:
        if self.generator == "random_string" and self.length is None:
            raise ValueError("random_string 生成器必须指定 length。")
        if self.generator != "random_string" and self.length is not None:
            raise ValueError("只有 random_string 生成器允许指定 length。")
        return self


class ObjectValueSource(StrictModel):
    type: Literal["object"]
    properties: dict[str, Any] = Field(default_factory=dict, max_length=100)

    @field_validator("properties")
    @classmethod
    def validate_properties(cls, value: dict[str, Any]) -> dict[str, Any]:
        return {
            str(name): VALUE_SOURCE_ADAPTER.validate_python(source).model_dump(exclude_none=True)
            for name, source in value.items()
        }


ValueSource: TypeAlias = Annotated[
    LiteralValueSource
    | UserInputValueSource
    | EnvironmentValueSource
    | SecretValueSource
    | ScenarioValueSource
    | StepOutputValueSource
    | GeneratedValueSource
    | ObjectValueSource,
    Field(discriminator="type"),
]
VALUE_SOURCE_ADAPTER = TypeAdapter(ValueSource)


class ScenarioBinding(StrictModel):
    target: ParameterTarget
    source: ValueSource
    required: bool = True
    transform: Literal["string", "integer", "number", "boolean", "json_encode", "url_encode"] | None = None


class ScenarioExtractor(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    source: Literal["json_body", "header", "cookie", "text_regex", "sse_event_json", "status_code"] = "json_body"
    path: str = ""
    event: str = ""
    occurrence: Literal["first", "last", "all"] = "first"
    value_type: ValueType = "any"
    required: bool = True
    sensitive: bool = False

    @model_validator(mode="after")
    def validate_source_fields(self) -> ScenarioExtractor:
        if self.source in {"json_body", "sse_event_json", "header", "cookie", "text_regex"} and not self.path:
            raise ValueError(f"{self.source} 提取器必须指定 path。")
        if self.source == "sse_event_json" and not self.event:
            raise ValueError("SSE 提取器必须指定 event。")
        return self


class StatusCodeAssertion(StrictModel):
    type: Literal["status_code"]
    expected: int = Field(ge=100, le=599)


class JsonPathAssertion(StrictModel):
    type: Literal["jsonpath_equals", "jsonpath_exists", "jsonpath_type"]
    path: str = Field(min_length=1, max_length=500)
    expected: Any = None


class HeaderAssertion(StrictModel):
    type: Literal["header"]
    name: str = Field(min_length=1, max_length=200)
    operator: Literal["equals", "contains", "exists"] = "equals"
    expected: Any = None


class SchemaAssertion(StrictModel):
    type: Literal["schema"]
    schema_ref: str = Field(min_length=1, max_length=500)


class SseEventAssertion(StrictModel):
    type: Literal["sse_event"]
    event: str = Field(min_length=1, max_length=200)
    path: str = ""
    operator: Literal["equals", "contains", "exists"] = "exists"
    expected: Any = None


class TextAssertion(StrictModel):
    type: Literal["text"]
    operator: Literal["equals", "contains", "matches"]
    expected: str


ScenarioAssertion: TypeAlias = Annotated[
    StatusCodeAssertion | JsonPathAssertion | HeaderAssertion | SchemaAssertion | SseEventAssertion | TextAssertion,
    Field(discriminator="type"),
]
ASSERTION_ADAPTER = TypeAdapter(ScenarioAssertion)


class WaitControlConfig(StrictModel):
    duration_ms: int = Field(ge=0, le=300_000)


class ConditionControlConfig(StrictModel):
    source: ValueSource
    operator: Literal["equals", "not_equals", "contains", "not_contains", "truthy", "falsy", "gt", "gte", "lt", "lte"]
    expected: Any = None


class AssignControlConfig(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    source: ValueSource


class ScenarioPlanNode(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    type: Literal["api_request", "condition", "wait", "assign"]
    phase: StepPhase = "main"
    endpoint_id: str | None = None
    name: str = Field(default="", max_length=200)
    request_overrides: dict[str, Any] = Field(default_factory=dict)
    bindings: list[ScenarioBinding] = Field(default_factory=list, max_length=200)
    extractors: list[ScenarioExtractor] = Field(default_factory=list, max_length=100)
    assertions: list[ScenarioAssertion] = Field(default_factory=list, max_length=100)
    control_config: dict[str, Any] = Field(default_factory=dict)
    on_failure: Literal["stop", "continue", "always_run"] = "stop"
    enabled: bool = True

    @model_validator(mode="after")
    def validate_node_contract(self) -> ScenarioPlanNode:
        if self.type == "api_request" and not self.endpoint_id:
            raise ValueError(f"{self.type} 步骤必须指定 endpoint_id。")
        if self.type != "api_request" and self.endpoint_id:
            raise ValueError(f"{self.type} 步骤不允许指定 endpoint_id。")
        config_models = {
            "wait": WaitControlConfig,
            "condition": ConditionControlConfig,
            "assign": AssignControlConfig,
        }
        config_model = config_models.get(self.type)
        if config_model is not None:
            self.control_config = config_model.model_validate(self.control_config).model_dump(exclude_none=True)
        elif self.control_config:
            raise ValueError("api_request 步骤不允许 control_config。")
        return self


class ScenarioPlanEdge(StrictModel):
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)
    condition: str = Field(default="success", min_length=1, max_length=100)


class ScenarioPlanResult(StrictModel):
    schema_version: Literal[2] = 2
    graph_version: Literal[1] = 1
    scenario_name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    nodes: list[ScenarioPlanNode] = Field(default_factory=list, max_length=100)
    edges: list[ScenarioPlanEdge] = Field(default_factory=list, max_length=200)
    warnings: list[str] = Field(default_factory=list, max_length=30)
    unresolved_items: list[str] = Field(default_factory=list, max_length=30)


class PlannerFieldProposal(StrictModel):
    target: ParameterTarget
    display_name: str = Field(min_length=1, max_length=200)
    required: bool = True
    value_type: ValueType = "any"
    sensitive: bool = False
    proposal: ValueSource


class PlannerExtractorProposal(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    source: Literal["json_body", "header", "cookie", "text_regex", "sse_event_json", "status_code"] = "json_body"
    path: str = ""
    event: str = ""
    occurrence: Literal["first", "last", "all"] = "first"
    value_type: ValueType = "any"
    required: bool = True
    sensitive: bool = False

    @model_validator(mode="after")
    def validate_source_fields(self) -> PlannerExtractorProposal:
        if self.source in {"json_body", "sse_event_json", "header", "cookie", "text_regex"} and not self.path:
            raise ValueError(f"{self.source} 提取器必须指定 path。")
        return self


class PlannerStepProposal(StrictModel):
    client_step_id: str = Field(min_length=1, max_length=100)
    endpoint_id: str = Field(min_length=1, max_length=100)
    order: int = Field(ge=1, le=100)
    phase: StepPhase = "main"
    name: str = Field(default="", max_length=200)
    fields: list[PlannerFieldProposal] = Field(default_factory=list, max_length=500)
    extractors: list[PlannerExtractorProposal] = Field(default_factory=list, max_length=100)
    assertions: list[ScenarioAssertion] = Field(default_factory=list, max_length=100)
    depends_on: list[str] = Field(default_factory=list, max_length=100)
    on_failure: Literal["stop", "continue", "always_run"] = "stop"
    enabled: bool = True


class PlannerProposal(StrictModel):
    schema_version: Literal[1] = 1
    scenario_name: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    steps: list[PlannerStepProposal] = Field(default_factory=list, min_length=1, max_length=100)


def normalize_legacy_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise ValueError("变量来源必须是结构化对象。")
    normalized = dict(source)
    if normalized.get("type") == "environment" and "key" not in normalized and normalized.get("name"):
        normalized["key"] = normalized.pop("name")
    return VALUE_SOURCE_ADAPTER.validate_python(normalized).model_dump(exclude_none=True)


def normalize_legacy_extractor(extractor: Any) -> dict[str, Any]:
    if not isinstance(extractor, dict):
        raise ValueError("响应提取器必须是结构化对象。")
    normalized = dict(extractor)
    source_map = {
        "response.body": "json_body",
        "response.header": "header",
        "response.status": "status_code",
    }
    normalized["source"] = source_map.get(str(normalized.get("source") or "response.body"), normalized.get("source"))
    if not normalized.get("path") and normalized.get("expression"):
        normalized["path"] = normalized.pop("expression")
    else:
        normalized.pop("expression", None)
    return ScenarioExtractor.model_validate(normalized).model_dump(exclude_none=True)


def normalize_legacy_assertion(assertion: Any) -> dict[str, Any]:
    if not isinstance(assertion, dict):
        raise ValueError("响应断言必须是结构化对象。")
    return ASSERTION_ADAPTER.validate_python(assertion).model_dump(exclude_none=True)


def normalize_legacy_binding(binding: Any) -> dict[str, Any]:
    if not isinstance(binding, dict):
        raise ValueError("参数绑定必须是结构化对象。")
    target = binding.get("target")
    if isinstance(target, dict):
        structured_target = ParameterTarget.model_validate(target)
    elif isinstance(target, str):
        structured_target = parameter_target_from_legacy_pointer(target)
    else:
        raise ValueError("参数绑定目标必须是结构化对象或历史 JSON Pointer。")
    return {
        "target": structured_target.model_dump(),
        "source": normalize_legacy_source(binding.get("source")),
        "required": bool(binding.get("required", True)),
        "transform": binding.get("transform"),
    }


def parameter_target_from_legacy_pointer(pointer: str) -> ParameterTarget:
    mappings = (
        ("/request/path_params", "path"),
        ("/request/query", "query"),
        ("/request/headers", "header"),
        ("/request/cookies", "cookie"),
        ("/request/json", "json_body"),
        ("/request/form", "form"),
        ("/request/multipart_form", "multipart"),
        ("/request/body", "raw_body"),
    )
    for prefix, location in mappings:
        if pointer == prefix or pointer.startswith(f"{prefix}/"):
            suffix = pointer.removeprefix(prefix) or "/"
            return ParameterTarget(location=location, path=suffix)
    if pointer.startswith("/test_data/"):
        return ParameterTarget(location="json_body", path=pointer.removeprefix("/test_data") or "/")
    raise ValueError("绑定目标必须位于受支持的请求字段。")


def binding_to_runtime(binding: ScenarioBinding | dict[str, Any]) -> dict[str, Any]:
    parsed = binding if isinstance(binding, ScenarioBinding) else ScenarioBinding.model_validate(binding)
    result: dict[str, Any] = {
        "target": parsed.target.legacy_pointer(),
        "source": source_to_runtime(parsed.source),
        "required": parsed.required,
    }
    if parsed.transform:
        result["transform"] = parsed.transform
    return result


def extractor_to_runtime(extractor: ScenarioExtractor | dict[str, Any]) -> dict[str, Any]:
    parsed = extractor if isinstance(extractor, ScenarioExtractor) else ScenarioExtractor.model_validate(extractor)
    if parsed.source == "json_body":
        result: dict[str, Any] = {"name": parsed.name, "path": parsed.path}
        if not parsed.required:
            result["required"] = False
        if parsed.value_type != "any":
            result["value_type"] = parsed.value_type
        if parsed.sensitive:
            result["sensitive"] = True
        return result
    source_map = {
        "header": "response.header",
        "status_code": "response.status",
    }
    source = source_map.get(parsed.source, parsed.source)
    result: dict[str, Any] = {
        "name": parsed.name,
        "source": source,
    }
    if not parsed.required:
        result["required"] = False
    if parsed.path:
        result["expression"] = parsed.path
    if parsed.event:
        result["event"] = parsed.event
    if parsed.source == "sse_event_json" and parsed.occurrence != "first":
        result["occurrence"] = parsed.occurrence
    if parsed.value_type != "any":
        result["value_type"] = parsed.value_type
    if parsed.sensitive:
        result["sensitive"] = True
    return result


def source_to_runtime(source: ValueSource | dict[str, Any]) -> dict[str, Any]:
    parsed = source if isinstance(source, BaseModel) else VALUE_SOURCE_ADAPTER.validate_python(source)
    result = parsed.model_dump(exclude_none=True)
    if result["type"] == "environment":
        result["name"] = result.pop("key")
    elif result["type"] == "object":
        result["properties"] = {
            name: source_to_runtime(child)
            for name, child in result.get("properties", {}).items()
        }
    return result


def control_config_to_runtime(step_type: str, config: dict[str, Any]) -> dict[str, Any]:
    if step_type not in {"condition", "assign"}:
        return dict(config)
    result = dict(config)
    if isinstance(result.get("source"), dict):
        result["source"] = source_to_runtime(result["source"])
    return result
