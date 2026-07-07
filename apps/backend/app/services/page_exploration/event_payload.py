# apps/backend/app/services/page_exploration/event_payload.py

import json


def _compact_event_payload(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except TypeError:
            value = str(value)
    value = " ".join(value.split())
    return value[:240]


def _clean_compact_payload(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value not in ("", None, [], {})}


def _status_display(kind: str, title: str, summary: str) -> dict:
    return {"kind": kind, "title": title, "summary": summary}
