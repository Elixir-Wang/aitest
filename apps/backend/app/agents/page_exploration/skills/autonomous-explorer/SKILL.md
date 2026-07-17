---
name: autonomous-explorer
description: "First-time full-page exploration with complete element execution and test-data cleanup."
---

# Autonomous Explorer

自主探索是首次页面建档，不是目标流程探索。

## 必须执行

- 先采集页面快照，再建立元素清单和页面状态清单。
- 所有按钮、链接、Tab、菜单、弹窗、表单字段、筛选、分页和列表操作都必须执行。
- 删除、清空、重置、发布、授权、退出登录和提交类操作不跳过，按页面真实流程执行。
- 创建或修改数据时使用本轮生成的测试数据。
- 每次动作后重新快照，记录成功、失败、跳转、弹窗、Toast、字段变化和数据变化。
- 本轮创建的条目必须在结束前删除，并验证删除成功。

## 状态推进

```
snapshot -> inventory -> execute one element -> snapshot -> verify -> enqueue new state/elements
```

只有以下条件同时满足时才能完成：

- 没有待执行元素；
- 没有待验证页面状态；
- 所有动作都有结果记录；
- 本轮测试数据已清理或明确记录清理失败。

## 禁止

- 不要用 3-7 个 todo 代替元素覆盖清单。
- 不要因为动作看起来危险而跳过。
- 不要把只采集快照或只发现元素当作交互完成。
- 不要把其他模块的导航点击当作目标页面功能覆盖。
