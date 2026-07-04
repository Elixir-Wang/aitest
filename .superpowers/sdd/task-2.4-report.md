# Task 2.4: `toast_filter` 报告

## 实现的文件

- `apps/backend/app/agents/page_exploration/utils/toast_filter.py` — 核心实现
- `apps/backend/tests/agents/page_exploration/utils/test_toast_filter.py` — 6 个测试用例

## 实现内容

### `is_toast(info: dict) -> bool`
- `role in {"dialog", "alertdialog"}` 或 `aria_modal == True` → 返回 `False`（永远不是 toast）
- `role in {"status", "alert"}` 且 `timeout_ms <= 5000` 或在已知容器中 → 返回 `True`
- 无 role 但命中已知容器（`.ant-message`、`.ant-notification`、`.toast`、`.snackbar` 等）→ 返回 `True`

### `filter_snapshot(snapshot: Iterable[dict]) -> list[dict]`
- 过滤掉所有 toast 元素，返回剩余元素列表

## 测试结果

### RED (Step 2)

```
ModuleNotFoundError: No module named 'app.agents.page_exploration.utils.toast_filter'
```

### GREEN (Step 4)

```
tests/agents/page_exploration/utils/test_toast_filter.py
  test_is_toast_role_status                  PASSED
  test_is_toast_role_alert_short_timeout     PASSED
  test_dialog_not_toast                      PASSED
  test_alert_without_timeout_not_toast       PASSED
  test_known_ant_message_container            PASSED
  test_filter_snapshot_drops_toasts           PASSED

6 passed in 0.10s
```

## Git Commit

- **SHA:** `e7ea22c15`
- **Subject:** `feat(page_exploration): toast_filter 启发式`
- **Files:** 2 个新文件，78 行插入

## Self-Review

- [x] 6/6 tests pass
- [x] Commit message matches exactly
- [x] `filter_snapshot` 正确过滤 toasts
- [x] `is_toast` 正确处理 `role=dialog`（NOT toast）和 `role=alert` 无 timeout（NOT toast）
- [x] 测试代码与 brief 完全一致

## 注意事项

- 实现中 `known_container` 的匹配逻辑使用 `any(seg in dom_path for seg in _KNOWN_TOAST_CONTAINERS)`，substring 匹配而非精确匹配，这是预期行为
- brief 中 `test_filter_snapshot_drops_toasts` 的 `timeout_ms: 4000` 被判定为 toast（<= 5000），符合预期
