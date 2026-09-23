import ast
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class RuntimeBlock:
    name: str
    requires: frozenset[str]
    symbols: tuple[str, ...]


BLOCKS = {
    "common": RuntimeBlock(
        "common", frozenset(), ("_json_path", "_payload_kwargs")
    ),
    "dynamic_values": RuntimeBlock("dynamic_values", frozenset(), ("_resolve",)),
    "response_assertions": RuntimeBlock(
        "response_assertions", frozenset({"common"}), ("_assert_response",)
    ),
    "endpoint_assertions": RuntimeBlock(
        "endpoint_assertions", frozenset({"common"}), ("_assert_endpoint_success",)
    ),
    "bindings": RuntimeBlock(
        "bindings",
        frozenset({"common"}),
        ("_variable", "_source", "_transform", "_set_pointer", "_apply_bindings"),
    ),
    "conditions": RuntimeBlock("conditions", frozenset({"bindings"}), ("_condition",)),
    "extractors": RuntimeBlock("extractors", frozenset({"common"}), ("_extract",)),
    "sse": RuntimeBlock(
        "sse",
        frozenset({"common", "response_assertions"}),
        ("SSE_MEASUREMENT_SINK", "_SSE_PATH_TOKEN", "set_sse_measurement_sink", "_sse_values", "_sse_matches", "_sse_metric_roles", "_execute_sse"),
    ),
    "scenario": RuntimeBlock("scenario", frozenset({"common", "response_assertions"}), ("ScenarioUser",)),
    "endpoint": RuntimeBlock("endpoint", frozenset({"common"}), ("EndpointUser",)),
    "load_shape": RuntimeBlock("load_shape", frozenset(), ()),
}


def resolve_blocks(requested: set[str]) -> list[RuntimeBlock]:
    resolved: list[RuntimeBlock] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        block = BLOCKS[name]
        for dependency in sorted(block.requires):
            visit(dependency)
        visited.add(name)
        resolved.append(block)

    for name in ("common", *sorted(requested - {"common"})):
        visit(name)
    return resolved


def source_for_blocks(blocks: list[RuntimeBlock]) -> str:
    source_path = Path(__file__).parents[1] / "scenario_runtime.py"
    source_text = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    lines = source_text.splitlines(keepends=True)
    definitions: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = node
    block_names = {block.name for block in blocks}
    imports = ["json", "random"]
    if block_names & {"scenario", "sse", "dynamic_values", "bindings"}:
        imports.append("time")
    if block_names & {"dynamic_values", "bindings"}:
        imports.append("uuid")
    if block_names & {"sse", "conditions", "extractors"}:
        imports.append("re")
    if "load_shape" in block_names:
        imports.append("math")
    locust_imports = ["HttpUser", "between", "events", "task"]
    if "load_shape" in block_names:
        locust_imports.insert(1, "LoadTestShape")
    chunks = [
        "\n".join(f"import {name}" for name in imports)
        + "\nfrom typing import Any\n\nfrom locust import "
        + ", ".join(locust_imports),
    ]
    emitted: set[str] = set()
    for block in blocks:
        for symbol in block.symbols:
            if symbol in emitted:
                continue
            emitted.add(symbol)
            node = definitions[symbol]
            chunks.append("".join(lines[node.lineno - 1 : node.end_lineno]).rstrip())
    return "\n\n".join(chunks)
