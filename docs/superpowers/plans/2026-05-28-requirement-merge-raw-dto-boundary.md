# 需求归并智能体输出边界改造方案

## 问题

需求归并 V2 的语义簇决策阶段直接把智能体输出送入 `RequirementClusterDecision` 强类型模型。模型偶尔返回 `merged`、`deduplicate`、`included`、`covered` 等业务同义词，导致 Pydantic `Literal` 校验失败，整次合并候选稿无法生成。

## 目标

- 智能体输出先进入宽松 Raw DTO。
- 服务端在单一边界层把 Raw DTO 归一化为内部 Canonical DTO。
- 后续归并流程只消费 Canonical DTO。
- 保留强校验：缺失片段、未知片段、无法归一化的片段状态仍然失败。
- 不再为每个新错误在业务流程里零散补丁。

## 设计

### Raw DTO

新增：

- `RequirementClusterDecisionRaw`
- `RequirementClusterDecisionItemRaw`

Raw DTO 对 `decision` 和 `coverage_status` 使用普通字符串，不使用 `Literal`。

### Canonical DTO

保留现有：

- `RequirementClusterDecision`
- `RequirementClusterDecisionItem`

它们继续使用内部枚举，作为后端稳定契约。

### 转换边界

在 `requirement_merge_service.py` 中新增转换函数：

- `_canonicalize_cluster_decision_payload`
- `_normalize_cluster_decision`
- `_normalize_merge_status`

流程：

1. `parsed` -> `RequirementClusterDecisionRaw`
2. Raw 状态归一化
3. 生成 dict
4. `RequirementClusterDecision.model_validate(...)`
5. 执行缺失/未知 fragment 校验

## 验证

- 覆盖分类漏返补跑。
- 覆盖 `decision = deduplicate`。
- 覆盖片段状态 `included / deduplicated / covered`。
- 覆盖未知簇级 decision 由片段状态推导。
