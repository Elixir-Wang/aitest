# Task 2.3: dom_signature 哈希 — 实现报告

## 概述

实现 `dom_signature` 语义哈希工具函数，基于元素 source 的 role + name + aria_label 生成稳定的 SHA256 哈希值。

## 测试结果

### RED（实现前）

```
ModuleNotFoundError: No module named 'app.agents.page_exploration.utils.dom_signature'
```

### GREEN（实现后）

```
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_stable_for_same_content PASSED
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_ignores_ref_but_sensitive_to_role PASSED
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_sensitive_to_role_change PASSED
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_sensitive_to_name_change PASSED
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_sensitive_to_aria_change PASSED
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_format_is_sha256_prefix PASSED
tests/agents/page_exploration/utils/test_dom_signature.py::test_signature_empty_returns_seed PASSED

7 passed in 0.09s
```

## 文件变更

| 文件 | 变更 |
|------|------|
| `apps/backend/app/agents/page_exploration/utils/dom_signature.py` | 新增 |
| `apps/backend/tests/agents/page_exploration/utils/test_dom_signature.py` | 新增 |

## 实现细节

- **函数**: `compute_dom_signature(elements: Iterable[dict]) -> str`
- **返回格式**: `"sha256:" + sha256_hexdigest`（总长度 71 字符）
- **哈希内容**: `(fingerprint_dict, element_key)` 元组列表
  - `fingerprint_dict` = `{"role", "name", "aria_label"}`（仅语义字段）
  - 忽略: `inferred`, `placeholder`, `test_id`, `text`, `ref`, `class`, `xpath` 等
- **JSON 序列化**: `sort_keys=True, separators=(",", ":")` 保证确定性
- **纯函数**: 无 I/O，无副作用

## 自检

- [x] 7/7 测试通过（pristine output）
- [x] 提交信息匹配: `feat(page_exploration): dom_signature 语义哈希`
- [x] Commit SHA: `009557325`
- [x] 纯函数实现，无 I/O
- [x] 格式验证: `sha256:` 前缀 + 64 字符 hex

## 潜在关注点

无。
