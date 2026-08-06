import json
from typing import Any

from app.services.api_automation.asyncapi_parser import parse_asyncapi_document
from app.services.api_automation.openapi_parser import OpenAPIParseError, parse_openapi_document


def parse_interface_document(raw: str, *, source_name: str = "") -> dict[str, Any]:
    document = _load_for_detection(raw, source_name=source_name)
    if isinstance(document, dict) and document.get("asyncapi"):
        return parse_asyncapi_document(raw, source_name=source_name)
    return parse_openapi_document(raw, source_name=source_name)


def _load_for_detection(raw: str, *, source_name: str) -> Any:
    content = raw.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise OpenAPIParseError("接口文档不是有效 JSON，当前环境未安装 YAML 解析依赖。") from exc
        try:
            return yaml.safe_load(content)
        except Exception as exc:
            name = f"（{source_name}）" if source_name else ""
            raise OpenAPIParseError(f"接口文档{name}解析失败。") from exc
