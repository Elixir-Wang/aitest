"""Probe MiniMax thinking controls through the project's LangChain adapter.

Run from apps/backend:
    uv run python scripts/probe_minimax_thinking.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.agents.model_selection import build_agent_model, resolve_model_selection


CAPABILITY_ID = "knowledge_query"
DEFAULT_PROMPT = "请用一句中文回答：9.11 和 9.8 哪个数字更大？只输出结论。"


@dataclass(frozen=True)
class ProbeCase:
    name: str
    extra_body: dict[str, Any] | None


def probe_cases() -> list[ProbeCase]:
    return [
        ProbeCase("baseline-no-extra-body", None),
        ProbeCase("thinking-disabled", {"thinking": {"type": "disabled"}}),
        ProbeCase(
            "thinking-disabled-reasoning-split",
            {"thinking": {"type": "disabled"}, "reasoning_split": True},
        ),
        ProbeCase(
            "thinking-adaptive-reasoning-split",
            {"thinking": {"type": "adaptive"}, "reasoning_split": True},
        ),
    ]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--capability-id", default=CAPABILITY_ID)
    args = parser.parse_args()

    selection = resolve_model_selection(args.capability_id)
    print(
        json.dumps(
            {
                "capability_id": args.capability_id,
                "provider": selection.provider,
                "model": selection.model,
                "base_url": selection.base_url,
                "prompt": args.prompt,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    for case in probe_cases():
        print(f"\n=== {case.name} ===")
        print("extra_body:", json.dumps(case.extra_body, ensure_ascii=False))
        model = build_agent_model(selection, extra_body=case.extra_body)
        try:
            response = await model.ainvoke(args.prompt)
        except Exception as exc:
            print("error:", repr(exc))
            continue
        print(json.dumps(summarize_response(response), ensure_ascii=False, indent=2))


def summarize_response(response: Any) -> dict[str, Any]:
    content = getattr(response, "content", "")
    content_text = content_to_text(content)
    additional_kwargs = getattr(response, "additional_kwargs", {}) or {}
    response_metadata = getattr(response, "response_metadata", {}) or {}
    usage_metadata = getattr(response, "usage_metadata", {}) or {}
    reasoning_content = additional_kwargs.get("reasoning_content") or getattr(response, "reasoning_content", "")
    reasoning_details = additional_kwargs.get("reasoning_details")
    return {
        "content_preview": compact(content_text),
        "content_has_think_tag": "<think>" in content_text.lower() or "<thinking>" in content_text.lower(),
        "reasoning_content_preview": compact(reasoning_content),
        "has_reasoning_content": bool(reasoning_content),
        "has_reasoning_details": bool(reasoning_details),
        "additional_kwargs_keys": sorted(additional_kwargs.keys()),
        "response_metadata": response_metadata,
        "usage_metadata": usage_metadata,
    }


def content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, Iterable):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(content)


def compact(value: Any, *, limit: int = 500) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    return text[:limit] + ("..." if len(text) > limit else "")


if __name__ == "__main__":
    asyncio.run(main())
