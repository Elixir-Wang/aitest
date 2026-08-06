from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.services.api_automation.openapi_parser import OpenAPIParseError, _load_document, _resolve_refs, _string, normalize_path


def parse_asyncapi_document(raw: str, *, source_name: str = "") -> dict[str, Any]:
    spec = _load_document(raw, source_name=source_name)
    if not isinstance(spec, dict) or not _string(spec.get("asyncapi")):
        raise OpenAPIParseError("AsyncAPI 文档格式无效。")
    channels = spec.get("channels")
    if not isinstance(channels, dict) or not channels:
        raise OpenAPIParseError("AsyncAPI 文档必须包含非空 channels 字段。")

    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    endpoints = _extract_channels(spec)
    if not endpoints:
        raise OpenAPIParseError("AsyncAPI 文档未解析到可用 WebSocket 接口。")
    return {
        "format": "asyncapi",
        "title": _string(info.get("title")) or source_name or "Realtime API",
        "version": _string(info.get("version")) or _string(spec.get("asyncapi")),
        "endpoint_count": len(endpoints),
        "tags": sorted({tag for endpoint in endpoints for tag in endpoint["tags"]}),
        "endpoints": endpoints,
    }


def _extract_channels(spec: dict[str, Any]) -> list[dict[str, Any]]:
    channels = spec.get("channels") if isinstance(spec.get("channels"), dict) else {}
    operations = spec.get("operations") if isinstance(spec.get("operations"), dict) else {}
    result: list[dict[str, Any]] = []
    for channel_id, raw_channel in channels.items():
        if not isinstance(raw_channel, dict):
            continue
        channel = _resolve_refs(raw_channel, spec)
        address = normalize_path(_string(channel.get("address")))
        if not address or address == "/":
            continue
        server = _channel_server(raw_channel, spec)
        protocol = _string(server.get("protocol")).lower()
        if protocol not in {"ws", "wss", "websocket"}:
            continue

        message_schemas = _operation_message_schemas(channel_id, operations, spec)
        if not message_schemas:
            message_schemas = _named_channel_message_schemas(channel)
        action = "bidirectional" if {"send", "receive"}.issubset(message_schemas) else next(iter(message_schemas), "")
        connection_url = _connection_url(server, address, protocol)
        send_schema = message_schemas.get("send", {})
        receive_schema = message_schemas.get("receive", {})
        result.append(
            {
                "protocol": "websocket",
                "method": "",
                "path": address,
                "normalized_path": normalize_path(address),
                "summary": _string(channel.get("title")) or _string(channel.get("summary")) or str(channel_id),
                "description": _string(channel.get("description")),
                "tags": ["Realtime / WebSocket"],
                "parameters": [],
                "request_body": {"content": {"application/json": {"schema": send_schema}}} if send_schema else {},
                "responses": {
                    "200": {
                        "description": "WebSocket receive message",
                        "content": {"application/json": {"schema": receive_schema}},
                    }
                }
                if receive_schema
                else {},
                "auth": {"security": server.get("security", [])},
                "operation_action": action,
                "connection_url": connection_url,
                "message_schemas": message_schemas,
                "source": {
                    "channel_id": str(channel_id),
                    "source_doc_url": _string(channel.get("x-source-doc-url")),
                    "document_format": "asyncapi",
                },
                "source_channel_id": str(channel_id),
            }
        )
    return result


def _channel_server(channel: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    servers = channel.get("servers")
    if isinstance(servers, list) and servers:
        resolved = _resolve_refs(servers[0], spec)
        if isinstance(resolved, dict):
            return resolved
    root_servers = spec.get("servers")
    if isinstance(root_servers, dict):
        return next((value for value in root_servers.values() if isinstance(value, dict)), {})
    return {}


def _operation_message_schemas(channel_id: str, operations: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    schemas: dict[str, Any] = {}
    expected_ref = f"#/channels/{channel_id}"
    for raw_operation in operations.values():
        if not isinstance(raw_operation, dict):
            continue
        channel_ref = raw_operation.get("channel")
        if not isinstance(channel_ref, dict) or channel_ref.get("$ref") != expected_ref:
            continue
        action = _string(raw_operation.get("action")).lower()
        if action not in {"send", "receive"}:
            continue
        messages = raw_operation.get("messages")
        if not isinstance(messages, list) or not messages:
            continue
        resolved = _resolve_refs(messages[0], spec)
        if isinstance(resolved, dict) and isinstance(resolved.get("payload"), dict):
            schemas[action] = resolved["payload"]
    return schemas


def _named_channel_message_schemas(channel: dict[str, Any]) -> dict[str, Any]:
    messages = channel.get("messages")
    if not isinstance(messages, dict):
        return {}
    result: dict[str, Any] = {}
    for name, message in messages.items():
        if not isinstance(message, dict) or not isinstance(message.get("payload"), dict):
            continue
        lowered = str(name).lower()
        if "send" in lowered:
            result["send"] = message["payload"]
        elif "receive" in lowered:
            result["receive"] = message["payload"]
    return result


def _connection_url(server: dict[str, Any], address: str, protocol: str) -> str:
    host = _string(server.get("host"))
    if not host:
        raw_url = _string(server.get("url"))
        parsed = urlparse(raw_url)
        host = parsed.netloc
        protocol = parsed.scheme or protocol
    pathname = _string(server.get("pathname"))
    path = address if not pathname or pathname == address else f"{pathname.rstrip('/')}/{address.lstrip('/')}"
    return f"{protocol if protocol in {'ws', 'wss'} else 'wss'}://{host}{normalize_path(path)}"
