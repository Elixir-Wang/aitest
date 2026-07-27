import json
from typing import Any
from urllib.parse import urlparse


HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}

CYBOTSTAR_ASSET_GROUPS = (
    ("/api-reference/knowledge/base/", "知识库 / 基本能力"),
    ("/api-reference/knowledge_v2/base/", "知识库 / 基本能力"),
    ("/api-reference/knowledge_v2/qa/", "知识库 / QA"),
    ("/api-reference/knowledge/image/", "知识库 / 图片"),
    ("/api-reference/knowledge_v2/text/", "知识库 / 文本"),
    ("/api-reference/knowledge_v2/file/", "知识库 / 文件"),
    ("/api-reference/knowledge_v2/folder/", "知识库 / 文件夹"),
    ("/api-reference/conversation/segment/session_file", "智能体 / 会话文件"),
    ("/api-reference/conversation/segment/", "智能体 / 会话"),
    ("/api-reference/conversation/agent_analysis", "智能体 / 智能体统计"),
    ("/api-reference/conversation/", "智能体 / 基本能力"),
    ("/api-reference/chatflow/", "智能体 / 对话流"),
    ("/api-reference/image_conversion/", "文件系统 / 图片转换"),
    ("/api-reference/file/", "文件系统 / 文件"),
    ("/api-reference/multi_agent/", "Multi-Agent / 基本能力"),
    ("/api-reference/batch_task/dataset/", "智能体 / 批量任务-数据集"),
    ("/api-reference/batch_task/task/", "智能体 / 批量任务"),
    ("/api-reference/scheduler/", "调度平台 / 任务"),
)


class OpenAPIParseError(ValueError):
    """Raised when an OpenAPI or Swagger document cannot be parsed."""


def parse_openapi_document(raw: str, *, source_name: str = "") -> dict[str, Any]:
    spec = _load_document(raw, source_name=source_name)
    if not isinstance(spec, dict):
        raise OpenAPIParseError("OpenAPI 文档格式无效。")
    paths = spec.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise OpenAPIParseError("OpenAPI 文档必须包含非空 paths 字段。")

    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    title = _string(info.get("title")) or source_name or "API"
    version = _string(info.get("version")) or _string(spec.get("swagger")) or _string(spec.get("openapi")) or ""
    endpoints = extract_endpoints(spec)
    if not endpoints:
        raise OpenAPIParseError("OpenAPI 文档未解析到可用接口。")
    return {
        "title": title,
        "version": version,
        "endpoint_count": len(endpoints),
        "tags": sorted({tag for endpoint in endpoints for tag in endpoint["tags"]}),
        "endpoints": endpoints,
    }


def extract_endpoints(openapi_spec: dict[str, Any]) -> list[dict[str, Any]]:
    paths = openapi_spec.get("paths", {})
    global_security = openapi_spec.get("security", [])
    endpoints: list[dict[str, Any]] = []
    if not isinstance(paths, dict):
        return endpoints

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        path_parameters = path_item.get("parameters", [])
        for method, method_spec in path_item.items():
            method_lower = method.lower()
            if method_lower not in HTTP_METHODS or not isinstance(method_spec, dict):
                continue
            operation_parameters = method_spec.get("parameters", [])
            parameters = []
            if isinstance(path_parameters, list):
                parameters.extend(path_parameters)
            if isinstance(operation_parameters, list):
                parameters.extend(operation_parameters)
            tags = method_spec.get("tags", ["Other"])
            if not isinstance(tags, list) or not tags:
                tags = ["Other"]
            tags = [_string(tag) or "Other" for tag in tags]
            tags = normalize_operation_tags(openapi_spec, method_spec, tags)
            operation_id = _string(method_spec.get("operationId"))
            endpoints.append(
                {
                    "method": method_lower.upper(),
                    "path": _string(path),
                    "normalized_path": normalize_path(_string(path)),
                    "summary": _string(method_spec.get("summary")),
                    "description": _string(method_spec.get("description")),
                    "tags": tags,
                    "parameters": _resolve_refs(parameters, openapi_spec),
                    "request_body": _resolve_refs(
                        method_spec.get("requestBody") if isinstance(method_spec.get("requestBody"), dict) else {},
                        openapi_spec,
                    ),
                    "responses": _resolve_refs(
                        method_spec.get("responses") if isinstance(method_spec.get("responses"), dict) else {},
                        openapi_spec,
                    ),
                    "auth": {
                        "security": method_spec.get("security", global_security),
                    },
                    "source": {
                        "operation_id": operation_id,
                        "deprecated": bool(method_spec.get("deprecated", False)),
                        "tag_group": tags[0],
                    },
                }
            )
    endpoints.sort(key=lambda item: (item["path"], item["method"]))
    return endpoints


def normalize_operation_tags(
    openapi_spec: dict[str, Any],
    method_spec: dict[str, Any],
    tags: list[str],
) -> list[str]:
    profile = openapi_spec.get("x-adjusted-for-interface-assets")
    if not isinstance(profile, dict) or profile.get("profile") != "cybotstar-assets":
        return tags

    section = _string(method_spec.get("x-sidebar-section"))
    group = _string(method_spec.get("x-sidebar-group"))
    normalized_tag = f"{section} / {group}" if section and group else ""
    if not normalized_tag:
        source_path = urlparse(_string(method_spec.get("x-source-doc-url"))).path.rstrip("/") + "/"
        normalized_tag = next(
            (tag for prefix, tag in CYBOTSTAR_ASSET_GROUPS if source_path.startswith(prefix)),
            "",
        )
    if not normalized_tag:
        return tags
    return [normalized_tag, *tags[1:]]


def normalize_path(path: str) -> str:
    normalized = path.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _resolve_refs(value: Any, root: dict[str, Any], seen: set[str] | None = None) -> Any:
    seen = seen or set()
    if isinstance(value, list):
        return [_resolve_refs(item, root, seen.copy()) for item in value]
    if not isinstance(value, dict):
        return value

    ref = value.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/") and ref not in seen:
        target = _lookup_ref(root, ref)
        if isinstance(target, dict):
            merged = {**target, **{key: item for key, item in value.items() if key != "$ref"}}
            return _resolve_refs(merged, root, {*seen, ref})

    return {key: _resolve_refs(item, root, seen.copy()) for key, item in value.items()}


def _lookup_ref(root: dict[str, Any], ref: str) -> Any:
    current: Any = root
    for raw_part in ref.removeprefix("#/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _load_document(raw: str, *, source_name: str) -> Any:
    content = raw.strip()
    if not content:
        raise OpenAPIParseError("OpenAPI 文档不能为空。")
    try:
        return json.loads(content)
    except json.JSONDecodeError as json_exc:
        try:
            import yaml
        except ImportError as exc:
            raise OpenAPIParseError("OpenAPI 文档不是有效 JSON，当前环境未安装 YAML 解析依赖。") from exc
        try:
            return yaml.safe_load(content)
        except Exception as exc:  # pragma: no cover - depends on optional yaml parser
            name = f"（{source_name}）" if source_name else ""
            raise OpenAPIParseError(f"OpenAPI 文档{name}解析失败。") from json_exc


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
