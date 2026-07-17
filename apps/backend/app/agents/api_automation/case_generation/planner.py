from dataclasses import dataclass
from typing import Any, Literal


OracleStatus = Literal["confirmed", "inferred", "needs_confirmation"]


@dataclass(frozen=True)
class ApiTestPoint:
    key: str
    category: Literal["positive", "negative", "boundary", "security"]
    description: str
    oracle_status: OracleStatus


def plan_api_test_points(
    endpoint: dict[str, Any],
) -> list[ApiTestPoint]:
    points: list[ApiTestPoint] = []
    request_body = endpoint.get("request_body") or {}
    body_schema = _json_schema(request_body)
    properties = body_schema.get("properties") or {}
    required_fields = [str(name) for name in body_schema.get("required") or []]

    if _has_success_response(endpoint):
        points.append(
            ApiTestPoint(
                key="success.minimum_valid",
                category="positive",
                description="使用所有必填字段构造最小合法请求。",
                oracle_status="confirmed",
            )
        )

    for field_name in required_fields:
        points.append(
            ApiTestPoint(
                key=f"body.required.{field_name}.missing",
                category="negative",
                description=f"请求体缺少必填字段 {field_name}。",
                oracle_status=_negative_oracle_status(endpoint),
            )
        )

    if request_body.get("required"):
        points.extend(
            [
                ApiTestPoint(
                    key="request_body.missing",
                    category="negative",
                    description="请求不发送 requestBody。",
                    oracle_status=_negative_oracle_status(endpoint),
                ),
                ApiTestPoint(
                    key="request_body.empty_object",
                    category="negative",
                    description="请求发送空 JSON 对象。",
                    oracle_status=_negative_oracle_status(endpoint),
                ),
            ]
        )

    for field_name, schema in properties.items():
        if field_name in required_fields:
            points.extend(_required_field_value_points(str(field_name), schema, endpoint))
        if _looks_like_date_field(str(field_name), schema):
            points.append(
                ApiTestPoint(
                    key=f"body.{field_name}.invalid_format",
                    category="negative",
                    description=f"字段 {field_name} 使用非法日期格式。",
                    oracle_status=_negative_oracle_status(endpoint),
                )
            )

    date_pairs = _date_pairs(properties, required_fields)
    for start_name, end_name in date_pairs:
        if (start_name, end_name) == ("start_date", "end_date"):
            equals_key = "body.date_relation.start_equals_end"
            after_key = "body.date_relation.start_after_end"
        else:
            relation_prefix = f"{start_name}_{end_name}"
            equals_key = f"body.date_relation.{relation_prefix}.equals"
            after_key = f"body.date_relation.{relation_prefix}.after"
        points.extend(
            [
                ApiTestPoint(
                    key=equals_key,
                    category="boundary",
                    description=f"字段 {start_name} 与 {end_name} 相等。",
                    oracle_status=_negative_oracle_status(endpoint),
                ),
                ApiTestPoint(
                    key=after_key,
                    category="boundary",
                    description=f"字段 {start_name} 晚于 {end_name}。",
                    oracle_status=_negative_oracle_status(endpoint),
                ),
            ]
        )

    for parameter in endpoint.get("parameters") or []:
        if parameter.get("in") != "header" or not parameter.get("required"):
            continue
        name = str(parameter.get("name") or "").strip()
        if not name or parameter.get("x-source") != "security":
            continue
        points.append(
            ApiTestPoint(
                key=f"header.required.{name}.empty",
                category="security",
                description=f"鉴权 Header {name} 使用空字符串覆盖默认值。",
                oracle_status=_negative_oracle_status(endpoint),
            )
        )

    return _deduplicate_points(points)


def _json_schema(request_body: dict[str, Any]) -> dict[str, Any]:
    content = request_body.get("content") or {}
    for media_type in sorted(content):
        schema = content[media_type].get("schema") if isinstance(content[media_type], dict) else None
        if isinstance(schema, dict):
            return schema
    return {}


def _has_success_response(endpoint: dict[str, Any]) -> bool:
    return any(str(status).startswith("2") for status in (endpoint.get("responses") or {}))


def _negative_oracle_status(endpoint: dict[str, Any]) -> OracleStatus:
    responses = endpoint.get("responses") or {}
    if any(str(status) in {"400", "401", "403", "422"} for status in responses):
        return "inferred"
    if any(str(status).startswith("4") or str(status).startswith("5") for status in responses):
        return "needs_confirmation"
    return "needs_confirmation"


def _looks_like_date_field(name: str, schema: dict[str, Any]) -> bool:
    name_lower = name.lower()
    description = str(schema.get("description") or "").lower()
    return schema.get("format") in {"date", "date-time"} or "date" in name_lower or "日期" in description


def _required_field_value_points(
    field_name: str,
    schema: dict[str, Any],
    endpoint: dict[str, Any],
) -> list[ApiTestPoint]:
    oracle_status = _negative_oracle_status(endpoint)
    points = [
        ApiTestPoint(
            key=f"body.required.{field_name}.null",
            category="negative",
            description=f"必填字段 {field_name} 传入 null。",
            oracle_status=oracle_status,
        ),
        ApiTestPoint(
            key=f"body.required.{field_name}.invalid_type",
            category="negative",
            description=f"必填字段 {field_name} 传入与 schema 不一致的类型。",
            oracle_status=oracle_status,
        ),
    ]
    if schema.get("type") == "string":
        points.insert(
            0,
            ApiTestPoint(
                key=f"body.required.{field_name}.empty",
                category="negative",
                description=f"必填字符串字段 {field_name} 传入空字符串。",
                oracle_status=oracle_status,
            ),
        )
    return points


def _date_pairs(properties: dict[str, Any], required_fields: list[str]) -> list[tuple[str, str]]:
    names = set(properties)
    pairs: list[tuple[str, str]] = []
    for start_name, end_name in (
        ("start_date", "end_date"),
        ("start_time", "end_time"),
        ("begin_date", "end_date"),
        ("from", "to"),
    ):
        if start_name in names and end_name in names:
            pairs.append((start_name, end_name))
    if not pairs and len(required_fields) == 2:
        first, second = required_fields
        if _looks_like_date_field(first, properties.get(first, {})) and _looks_like_date_field(second, properties.get(second, {})):
            pairs.append((first, second))
    return pairs


def _deduplicate_points(points: list[ApiTestPoint]) -> list[ApiTestPoint]:
    seen: set[str] = set()
    result: list[ApiTestPoint] = []
    for point in points:
        if point.key in seen:
            continue
        seen.add(point.key)
        result.append(point)
    return result
