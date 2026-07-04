# Task 3 Report: `PageArtifactWriter.merge_states` 核心写逻辑

## 实现内容

- **创建** `apps/backend/app/services/page_exploration/page_artifact_writer.py`（304 行）
  - `PageArtifactWriter` 类：文件锁 + 读-合并-写 原子操作
  - `MergeResult` / `NewStateObservation` / `NewElementObservation` 数据类
  - `merge_states()`：先到为强合并，支持幂等
  - `read_existing()`：读取 v2.0 yaml（或 None）
  - `_apply_observations()` / `_merge_one_state()` / `_merge_elements()` 等内部方法
  - 修复了 brief 原版 `_merge_elements` 的 bug（匹配逻辑错误导致撞 key 时不更新而新增）

- **创建** `apps/backend/tests/agents/page_exploration/test_page_artifact_writer.py`（97 行，4 个测试）
  - `test_initial_create`：根 state 自动分配 seq=001 ID
  - `test_idempotent_repeat`：同输入第二次调用 state 总数不增
  - `test_first_to_wins_for_conflict`：同 key 先到保留值 + 记录冲突
  - `test_lock_timeout_returns_flag`：`LockTimeout` 异常时 `skipped_due_to_lock=True`

- **修改** `apps/backend/app/agents/page_exploration/tools/artifact_tools.py`
  - 在 `write_page_artifact_tool` docstring 顶部添加 DEPRECATED 标记
  - 注意：`artifact_service.py` 在本项目中不存在，旧写入口实际位于 `artifact_tools.py`

---

## 测试结果

### RED（Step 2，模块未实现时）

```
apps\backend\tests\agents\page_exploration\test_page_artifact_writer.py:5: in <module>
    from app.services.page_exploration.page_artifact_writer import (
E   ModuleNotFoundError: No module named 'app.services.page_exploration.page_artifact_writer'
```

### GREEN（Step 4 + Step 6 最终）

```
apps\backend\tests\agents\page_exploration\test_page_artifact_writer.py::test_initial_create PASSED [ 25%]
apps\backend\tests\agents\page_exploration\test_page_artifact_writer.py::test_idempotent_repeat PASSED [ 50%]
apps\backend\tests\agents\page_exploration\test_page_artifact_writer.py::test_first_to_wins_for_conflict PASSED [ 75%]
apps\backend\tests\agents\page_exploration\test_page_artifact_writer.py::test_lock_timeout_returns_flag PASSED [100%]

============================== 4 passed in 0.20s ==============================
```

全量测试（77 个）：

```
======================= 77 passed, 60 warnings in 3.21s =======================
```

---

## 文件变更

```
 3 files changed, 404 insertions(+), 1 deletion(-)
```

| 文件 | 变更 |
|------|------|
| `apps/backend/app/services/page_exploration/page_artifact_writer.py` | 新增 304 行 |
| `apps/backend/tests/agents/page_exploration/test_page_artifact_writer.py` | 新增 97 行 |
| `apps/backend/app/agents/page_exploration/tools/artifact_tools.py` | 修改 4 行（DEPRECATED marker） |

---

## 自我复盘

### ✅ 通过检查

- 4/4 测试全部 PASS
- 文件锁在 `merge_states` 持有（`with FileLock`）
- `LockTimeout` → `skipped_due_to_lock=True`
- 先到为强：同 key 第二次写入不覆盖，`conflicts` 字段记录冲突
- 幂等性：第二次同输入 `added_state_ids=[]`，state 总数不增
- 旧写入口已标记 DEPRECATED，未破坏其他方法

### ⚠️ 修复的 bug

**Brief 原版 `_merge_elements` 存在严重错误：**

brief 代码用 `slot_key = final_keys[len(existing) + i]` 来匹配已存在元素。

但 `final_keys` 是 `ensure_unique_within_state(keys)` 的结果，对 key 列表去重后：

- `keys = [e["key"] for e in existing] + [obs_keys]`
- `final_keys = list(ensure_unique_within_state(keys))`

若 existing 已有 `button-x`，observations 送来 `button-x`（新值），则：
- `keys = ["button-x", "button-x"]`
- `final_keys = ["button-x", "button-x-2"]`（去重后第二个变成 -2）
- `slot_key = final_keys[0 + 0] = "button-x"` → 匹配成功 ✅（但这是巧合）

若 existing 为空，observations 送来 `button-x`：
- `keys = ["button-x"]`
- `final_keys = ["button-x"]`
- `slot_key = final_keys[0 + 0] = "button-x"` → 匹配失败（因为 `normalized_existing` 是空的）
- 结果：创建新元素 `button-x`，导致同一 key 被添加两次

**修复方案：** 先按**原始 key**匹配（`e["key"] == obs_el.key`），最后统一去重。这样 observation 的 key 直接与现有 key 比对，匹配后去重保证 slot key 唯一。

---

## 需 T6 清理的旧符号位置

```
write_page_artifact_tool (artifact_tools.py):
  - apps/backend/app/agents/page_exploration/tools/__init__.py: 27, 50, 89
  - apps/backend/app/agents/page_exploration/prompts/system_prompt.py: 43
  - apps/backend/app/services/exploration/page_exploration_service.py: 2115
  - apps/backend/tests/agents/page_exploration/tools/test_artifact_tools.py: 8

cache_index (project_pages_service.py):
  - apps/backend/app/services/page_exploration/project_pages_service.py: 37, 257, 259, 265
  - apps/backend/app/services/page_exploration/cache_manager.py: 144
```

---

## 报告文件

`D:\project\test_project\.superpowers\sdd\task-3-report.md`
