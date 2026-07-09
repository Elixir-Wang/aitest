#!/usr/bin/env python3
"""Convert Mintlify API reference pages into an OpenAPI 3.0.3 document."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head", "trace"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-url", required=True, help="Mintlify API reference root/introduction URL")
    parser.add_argument("--output", required=True, help="Output OpenAPI JSON path")
    parser.add_argument("--title", default="Generated OpenAPI", help="OpenAPI info.title")
    parser.add_argument("--version", default="1.0.0", help="OpenAPI info.version")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout in seconds")
    parser.add_argument("--max-pages", type=int, default=0, help="Limit pages for smoke testing")
    parser.add_argument("--no-fallback", action="store_true", help="Skip metadata-only pages")
    parser.add_argument(
        "--profile",
        choices=["generic", "cybotstar-assets"],
        default="generic",
        help="Post-processing profile. cybotstar-assets expands auth headers for interface asset import.",
    )
    args = parser.parse_args()
    expand_security_headers = args.profile == "cybotstar-assets"

    root_url = args.root_url.rstrip("/")
    base_url = origin(root_url)
    root_html = fetch_text(root_url, args.timeout)
    page_paths = discover_api_reference_paths(decode_next_flight_text(root_html))
    if "/api-reference/introduction" in page_paths:
        page_paths.remove("/api-reference/introduction")
    if args.max_pages > 0:
        page_paths = page_paths[: args.max_pages]

    spec: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {
            "title": args.title,
            "version": args.version,
            "description": f"Generated from {args.root_url}",
        },
        "paths": OrderedDict(),
        "components": {"securitySchemes": OrderedDict()},
        "x-generated-from": base_url,
        "x-source-page-count": len(page_paths),
        "x-imported-operation-count": 0,
        "x-minimal-operations": [],
        "x-duplicate-operations": [],
    }

    seen: dict[tuple[str, str], dict[str, str]] = {}
    for page_path in page_paths:
        page_url = urljoin(base_url, page_path)
        try:
            page_html = fetch_text(page_url, args.timeout)
        except Exception as exc:
            print(f"warning: failed to fetch {page_url}: {exc}", file=sys.stderr)
            continue

        decoded = decode_next_flight_text(page_html)
        data = extract_openapi_reference_data(decoded)
        if data:
            operation = build_operation_from_reference(
                data,
                page_url,
                spec,
                expand_security_headers=expand_security_headers,
            )
        elif args.no_fallback:
            continue
        else:
            operation = build_minimal_operation(decoded, page_url)

        if not operation:
            continue

        method = operation.pop("_method").lower()
        path = operation.pop("_path")
        key = (method, path)
        if key in seen:
            spec["x-duplicate-operations"].append(
                {
                    "method": method,
                    "path": path,
                    "kept": seen[key].get("title", ""),
                    "skipped": operation.get("summary", ""),
                    "url": page_url,
                }
            )
            continue

        spec["paths"].setdefault(path, OrderedDict())[method] = operation
        seen[key] = {"title": operation.get("summary", ""), "url": page_url}
        spec["x-imported-operation-count"] += 1
        if operation.get("x-source-warning"):
            spec["x-minimal-operations"].append(
                {
                    "href": page_path,
                    "openapi": f"{method} {path}",
                    "title": operation.get("summary", ""),
                }
            )

    if not spec["paths"]:
        raise SystemExit("No OpenAPI operations were generated.")

    if not spec["components"]["securitySchemes"]:
        spec["components"].pop("securitySchemes", None)
        if not spec["components"]:
            spec.pop("components", None)

    if args.profile == "cybotstar-assets":
        spec["x-adjusted-for-interface-assets"] = {
            "profile": "cybotstar-assets",
            "auth_headers_added_to_parameters": True,
            "request_body_restored_from_source_pages": True,
            "source": "Mintlify openApiReferenceData with interface-asset post-processing",
        }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "pages": len(page_paths),
                "operations": spec["x-imported-operation-count"],
                "minimal_operations": len(spec["x-minimal-operations"]),
                "duplicates": len(spec["x-duplicate-operations"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def fetch_text(url: str, timeout: float) -> str:
    request = Request(url, headers={"User-Agent": "codex-mintlify-openapi-converter/1.0"})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def discover_api_reference_paths(source: str) -> list[str]:
    paths: OrderedDict[str, None] = OrderedDict()
    for value in re.findall(r'href=["\']([^"\']+)["\']', source):
        if value.startswith("/api-reference/"):
            paths[value.split("#", 1)[0]] = None
    for value in re.findall(r'"href":"([^"]+)"', source):
        if value.startswith("/api-reference/"):
            paths[value.split("#", 1)[0]] = None
    for value in re.findall(r"/api-reference/[A-Za-z0-9_./%-]+", source):
        paths[value.split("#", 1)[0]] = None
    return list(paths.keys())


def decode_next_flight_text(source: str) -> str:
    decoded_parts = [html.unescape(source)]
    pattern = re.compile(r"self\.__next_f\.push\(\[1,\"((?:\\.|[^\"\\])*)\"\]\)</script>", re.DOTALL)
    for match in pattern.finditer(source):
        raw = match.group(1)
        try:
            decoded_parts.append(json.loads(f'"{raw}"'))
        except json.JSONDecodeError:
            decoded_parts.append(raw.encode("utf-8").decode("unicode_escape", errors="ignore"))
    return "\n".join(decoded_parts)


def extract_openapi_reference_data(text: str) -> dict[str, Any] | None:
    for marker in ('"openApiReferenceData":', "openApiReferenceData:"):
        start = text.find(marker)
        while start >= 0:
            value_start = start + len(marker)
            value = parse_json_value_at(text, value_start)
            if isinstance(value, dict) and isinstance(value.get("operation"), dict):
                return value
            start = text.find(marker, start + len(marker))
    return None


def parse_json_value_at(text: str, start: int) -> Any:
    i = skip_space(text, start)
    if text.startswith('"$undefined"', i) or text.startswith("$undefined", i):
        return None
    if i >= len(text) or text[i] != "{":
        return None
    end = find_matching_brace(text, i)
    if end < 0:
        return None
    try:
        return json.loads(text[i : end + 1])
    except json.JSONDecodeError:
        return None


def skip_space(text: str, start: int) -> int:
    while start < len(text) and text[start].isspace():
        start += 1
    return start


def find_matching_brace(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        char = text[i]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def build_operation_from_reference(
    data: dict[str, Any],
    page_url: str,
    spec: dict[str, Any],
    *,
    expand_security_headers: bool = False,
) -> dict[str, Any] | None:
    operation = data.get("operation") or {}
    dependencies = data.get("dependencies") or {}
    method = str(operation.get("method") or "").lower()
    path = str(operation.get("path") or "").strip()
    if method not in HTTP_METHODS or not path:
        return None

    result: dict[str, Any] = {
        "_method": method,
        "_path": normalize_path(path),
        "operationId": safe_string(operation.get("operationId")),
        "summary": safe_string(operation.get("summary") or operation.get("title")),
        "description": safe_string(operation.get("description")),
        "tags": operation.get("tags") if isinstance(operation.get("tags"), list) else ["default"],
        "parameters": resolve_parameters(operation.get("parameters"), dependencies),
        "responses": resolve_responses(operation.get("responses"), dependencies),
        "x-source-doc-url": page_url,
    }

    request_body = resolve_request_body(operation.get("requestBody"), dependencies)
    if request_body:
        result["requestBody"] = request_body

    security, security_schemes = resolve_security(operation.get("security"), dependencies, spec)
    if security:
        result["security"] = security
    if expand_security_headers and security_schemes:
        result["parameters"] = merge_security_header_parameters(result.get("parameters", []), security_schemes)

    return {key: value for key, value in result.items() if value not in ("", None, [], {})}


def resolve_parameters(value: Any, dependencies: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = dependencies.get("parameters") if isinstance(dependencies.get("parameters"), dict) else {}
    items = value if isinstance(value, list) else []
    resolved = []
    for item in items:
        if isinstance(item, str) and isinstance(parameters.get(item), dict):
            resolved.append(clean_schema_metadata(parameters[item]))
        elif isinstance(item, dict):
            resolved.append(clean_schema_metadata(item))
    return resolved


def resolve_request_body(value: Any, dependencies: dict[str, Any]) -> dict[str, Any]:
    body = dependencies.get("requestBody")
    if isinstance(value, str) and isinstance(body, dict) and isinstance(body.get(value), dict):
        return clean_schema_metadata(body[value])
    if isinstance(body, dict) and "content" in body:
        return clean_schema_metadata(body)
    if isinstance(value, dict):
        return clean_schema_metadata(value)
    return {}


def resolve_responses(value: Any, dependencies: dict[str, Any]) -> dict[str, Any]:
    response_deps = dependencies.get("responses") if isinstance(dependencies.get("responses"), dict) else {}
    responses: dict[str, Any] = {}
    if isinstance(value, dict):
        for status, response in value.items():
            if isinstance(response, str) and isinstance(response_deps.get(response), dict):
                responses[str(status)] = clean_schema_metadata(response_deps[response])
            elif isinstance(response, dict):
                responses[str(status)] = clean_schema_metadata(response)
    if not responses:
        responses["200"] = {"description": "OK"}
    return responses


def resolve_security(
    value: Any,
    dependencies: dict[str, Any],
    spec: dict[str, Any],
) -> tuple[list[dict[str, list[str]]], list[dict[str, Any]]]:
    security_deps = dependencies.get("security") if isinstance(dependencies.get("security"), dict) else {}
    items = value if isinstance(value, list) else []
    result: list[dict[str, list[str]]] = []
    resolved_schemes: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str) and isinstance(security_deps.get(item), dict):
            security_requirement: dict[str, list[str]] = {}
            for scheme_name, scheme in iter_security_schemes(security_deps[item]):
                spec["components"]["securitySchemes"][scheme_name] = scheme
                security_requirement[scheme_name] = []
                resolved_schemes.append(scheme)
            if security_requirement:
                result.append(security_requirement)
        elif isinstance(item, dict):
            result.append(item)
    return result, resolved_schemes


def iter_security_schemes(value: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(value, dict):
        return []
    if safe_string(value.get("name")):
        name = safe_string(value.get("name"))
        location = safe_string(value.get("in")) or "header"
        return [
            (
                security_scheme_name(name),
                {
                    "type": safe_string(value.get("type")) or "apiKey",
                    "name": name,
                    "in": location,
                },
            )
        ]

    schemes = []
    for raw_name, raw_scheme in value.items():
        if not isinstance(raw_scheme, dict):
            continue
        name = safe_string(raw_scheme.get("name")) or safe_string(raw_scheme.get("key"))
        location = safe_string(raw_scheme.get("in")) or "header"
        if not name:
            continue
        scheme_name = safe_string(raw_name) or security_scheme_name(name)
        schemes.append(
            (
                scheme_name,
                {
                    "type": safe_string(raw_scheme.get("type")) or "apiKey",
                    "name": name,
                    "in": location,
                },
            )
        )
    return schemes


def merge_security_header_parameters(
    parameters: list[dict[str, Any]],
    security_schemes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(parameters)
    existing = {
        (safe_string(parameter.get("in")).lower(), safe_string(parameter.get("name")).lower())
        for parameter in merged
        if isinstance(parameter, dict)
    }
    for scheme in security_schemes:
        if safe_string(scheme.get("type")) != "apiKey" or safe_string(scheme.get("in")) != "header":
            continue
        name = safe_string(scheme.get("name"))
        key = ("header", name.lower())
        if not name or key in existing:
            continue
        merged.insert(
            0,
            {
                "name": name,
                "in": "header",
                "required": True,
                "description": "鉴权 header",
                "schema": {"type": "string"},
                "x-source": "security",
            },
        )
        existing.add(key)
    return merged


def build_minimal_operation(text: str, page_url: str) -> dict[str, Any] | None:
    metadata = extract_current_page_metadata(text, page_url)
    if not metadata:
        return None
    openapi_value = safe_string(metadata.get("openapi"))
    parts = openapi_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() not in HTTP_METHODS:
        return None
    path = normalize_path(parts[1])
    operation = {
        "_method": parts[0].lower(),
        "_path": path,
        "summary": safe_string(metadata.get("title")),
        "description": safe_string(metadata.get("description")),
        "tags": ["default"],
        "responses": {"200": {"description": "OK"}},
        "x-source-doc-url": page_url,
        "x-source-warning": "Source page does not expose structured openApiReferenceData; generated from page metadata only.",
    }
    parameters = path_parameters_from_template(path)
    if parameters:
        operation["parameters"] = parameters
    return operation


def extract_current_page_metadata(text: str, page_url: str) -> dict[str, Any] | None:
    slug = urlparse(page_url).path.lstrip("/")
    marker = '"pageMetadata":'
    start = text.find(marker)
    while start >= 0:
        metadata = parse_json_value_at(text, start + len(marker))
        if isinstance(metadata, dict):
            href = safe_string(metadata.get("href")).lstrip("/")
            if safe_string(metadata.get("openapi")) and (slug in href or href.endswith(slug)):
                return metadata
        start = text.find(marker, start + len(marker))
    return None


def normalize_path(path: str) -> str:
    normalized = path.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", normalized)


def path_parameters_from_template(path: str) -> list[dict[str, Any]]:
    parameters = []
    for name in re.findall(r"{([^}/]+)}", path):
        parameters.append(
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
        )
    return parameters


def clean_schema_metadata(value: Any) -> Any:
    if isinstance(value, list):
        return [clean_schema_metadata(item) for item in value]
    if not isinstance(value, dict):
        return value
    cleaned = {}
    for key, item in value.items():
        if key in {"uniqueKey", "typeLabel", "isRequired"}:
            continue
        cleaned[key] = clean_schema_metadata(item)
    return cleaned


def safe_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def security_scheme_name(header_name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", header_name.strip()).strip("_").lower()
    return name or "api_key"


if __name__ == "__main__":
    raise SystemExit(main())
