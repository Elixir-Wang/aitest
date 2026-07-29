from __future__ import annotations


def group_collection_items(items: list[dict]) -> list[dict]:
    groups: list[dict] = []
    seen: dict[tuple[str, str, tuple[str, ...]], str] = {}
    counts: dict[tuple[str, str], int] = {}

    for item in items:
        item_type = str(item.get("type") or "").strip()
        status = str(item.get("status") or "").strip()
        if not item_type or not status:
            continue
        actions = _normalized_actions(item.get("actions"))
        identity = (item_type, status, tuple(sorted(actions)))
        if identity in seen:
            continue

        base = (item_type, status)
        counts[base] = counts.get(base, 0) + 1
        suffix = "" if counts[base] == 1 else f":{counts[base]}"
        group_key = f"{item_type}:{status}{suffix}"
        seen[identity] = group_key
        groups.append(
            {
                "key": group_key,
                "type": item_type,
                "status": status,
                "representative": str(item.get("name") or "").strip(),
                "actions": actions,
            }
        )

    return groups


def _normalized_actions(value) -> list[str]:
    if not isinstance(value, list):
        return []
    actions: list[str] = []
    for item in value:
        action = str(item or "").strip()
        if action and action not in actions:
            actions.append(action)
    return actions


__all__ = ["group_collection_items"]
