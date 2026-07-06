# 测试用例评审、采纳率与不采纳反馈 Spec

## 背景

当前仓库已经存在测试用例集生成链路：

- 后端 Agent：`apps/backend/app/agents/test_case_generation/`
- 后端服务：`apps/backend/app/services/test_case_service.py`
- 后端 API：`apps/backend/app/api/v1/test_cases.py`
- 后端仓储：`apps/backend/app/repositories/test_case_repo.py`
- 后端 schema：`apps/backend/app/schemas/test_case.py`
- 数据库初始化：`apps/backend/app/seed/init_db.py`
- 前端页面：`apps/frontend/src/app/(main)/test-cases/page.tsx`
- 前端 API 类型：`apps/frontend/src/lib/api-client.ts`

现有 `test_cases.status` 已支持 `draft`、`ready_for_review`、`approved`、`rejected`，生成完成后写入 `ready_for_review`。前端目前只在测试用例集详情弹窗中展示用例字段，没有逐条采纳或不采纳操作，也没有记录不采纳原因。Dashboard 已存在“测试用例采纳率”的展示语义，但测试用例评审侧尚未形成可计算的真实数据闭环。

本轮目标是在现有测试用例集基础上增加独立评审界面，允许用户逐条采纳或不采纳测试用例。不采纳时弹窗采集反馈信息，反馈不强制填写。下次重新生成同一个测试用例集时，生成 Agent 才参考这些不采纳信息，避免再次生成同类问题。

## 目标

- 为每个测试用例集提供独立评审页面。
- 用户可以对每条测试用例执行“采纳”和“不采纳”。
- 不采纳时打开弹窗采集不采纳信息。
- 不采纳信息允许为空。
- 用例评审状态需要持久化。
- 采纳率需要基于真实评审状态计算并展示。
- 重新生成测试用例集时，后端把历史不采纳用例及反馈注入测试用例生成输入。
- 首次生成不参考不采纳信息。
- 普通查看列表页继续保留，评审页作为更适合逐条处理的工作台。
- 前端页面需要精致、清晰、高效，符合测试资产评审场景，而不是营销页或大面积装饰页。

## 非目标

- 不生成 UI 自动化代码。
- 不执行自动化测试。
- 不做测试计划管理。
- 不新增独立“评审批次”模型。
- 不做多人协同锁定。
- 不做强制填写拒绝原因。
- 不把不采纳信息同步到需求文档。
- 不对已生成用例做语义去重或自动合并。
- 不引入新的 Agent；继续复用 `test_case_generation` Agent。
- 不改变现有创建测试用例集入口的核心流程。

## 术语

### 采纳

用户认可该测试用例可进入后续测试资产沉淀或自动化建设。持久化状态为 `approved`。

### 不采纳

用户认为该测试用例当前不适合保留或推进。持久化状态为 `rejected`。用户可以填写不采纳原因，也可以跳过说明。

### 待评审

测试用例生成后的默认状态。持久化状态为 `ready_for_review`。

### 采纳率

推荐公式：

```text
approved_count / (approved_count + rejected_count)
```

只统计已经做出评审决策的用例，不把待评审用例计入分母。这样刚生成但尚未评审的用例集不会被错误显示为低采纳率。

### 评审进度

推荐公式：

```text
(approved_count + rejected_count) / case_count
```

用于表达还有多少用例未处理。

## 推荐方案

采用“复用现有状态字段 + 少量反馈字段 + 独立评审页”的方案。

原因：

- `test_cases.status` 已经覆盖评审状态，不需要新建一套平行状态模型。
- 用户需求是逐条采纳、不采纳和下次生成参考反馈，当前最小必要数据是状态、反馈、评审人、评审时间。
- 独立评审页比详情弹窗更适合高频浏览、逐条判断和查看采纳率。
- 重新生成是天然的反馈注入时机，符合“下次生成测试用例才参考不采纳信息”的要求。

## 数据模型

### `test_cases` 表扩展

新增字段：

```sql
review_feedback TEXT NOT NULL DEFAULT '',
reviewed_by TEXT NOT NULL DEFAULT '',
reviewed_at TEXT
```

字段含义：

- `review_feedback`：不采纳反馈。采纳时清空或保持为空。
- `reviewed_by`：最近一次评审操作人。
- `reviewed_at`：最近一次评审时间。

不新增单独 `test_case_reviews` 表。当前需求只需要记录每条用例的当前评审结论和反馈，不需要审计完整历史。

### 状态约束

沿用现有约束：

```text
draft | ready_for_review | approved | rejected
```

生成完成后的用例继续写入 `ready_for_review`。

## 后端契约

### Schema

在 `apps/backend/app/schemas/test_case.py` 增加：

```python
TestCaseReviewStatus = Literal["ready_for_review", "approved", "rejected"]

class TestCaseReviewIn(BaseModel):
    status: TestCaseReviewStatus
    review_feedback: str = Field(default="", max_length=1000)

class TestCaseReviewStatsOut(BaseModel):
    case_count: int
    approved_count: int
    rejected_count: int
    pending_count: int
    reviewed_count: int
    adoption_rate: float
    review_progress: float
```

扩展 `TestCaseOut`：

```python
review_feedback: str = ""
reviewed_by: str = ""
reviewed_at: str | None = None
```

扩展 `TestCaseSetOut`：

```python
review_stats: TestCaseReviewStatsOut
```

### API

新增接口：

```text
PATCH /projects/{project_id}/test-case-sets/{set_id}/cases/{case_id}/review
```

请求：

```json
{
  "status": "rejected",
  "review_feedback": "步骤缺少异常分支，预期结果不可验证"
}
```

响应：

```json
{
  "case": {
    "id": "tcs-xxx-tc-001",
    "status": "rejected",
    "review_feedback": "步骤缺少异常分支，预期结果不可验证",
    "reviewed_by": "user-1",
    "reviewed_at": "2026-07-06 12:00:00"
  },
  "review_stats": {
    "case_count": 20,
    "approved_count": 11,
    "rejected_count": 3,
    "pending_count": 6,
    "reviewed_count": 14,
    "adoption_rate": 0.7857,
    "review_progress": 0.7
  }
}
```

权限：

- 读取详情沿用 `current_user`。
- 评审操作建议使用 `require_admin`，与创建和重新生成测试用例集保持一致。

状态规则：

- `approved`：清空 `review_feedback`，写入 `reviewed_by`、`reviewed_at`。
- `rejected`：保存 `review_feedback.strip()`，允许空字符串，写入 `reviewed_by`、`reviewed_at`。
- `ready_for_review`：用于撤销评审结论，清空 `review_feedback`，清空或更新评审字段均可。推荐清空 `reviewed_by`、`reviewed_at`，让语义更干净。

错误处理：

- 项目不存在：`404 NOT_FOUND`
- 用例集不存在或不属于项目：`404 NOT_FOUND`
- 用例不存在或不属于用例集：`404 NOT_FOUND`
- 非管理员操作：`403 PERMISSION_DENIED`
- 生成中用例集评审：允许评审已有用例，但如果重新生成会替换用例，前端需要提示。若当前实现生成中通常没有完整用例，后端不需要额外限制。

## 后端实现边界

### Repository

在 `test_case_repo.py` 增加：

- `find_case_by_id(db, case_id)`
- `update_case_review(db, case_id, status, review_feedback, reviewed_by)`
- `review_stats_by_set(db, test_case_set_id)`
- `list_rejected_case_feedback_by_set(db, test_case_set_id)`

`review_stats_by_set` 应在 SQL 层聚合，避免每次序列化都全量拉取用例后在 Python 里统计。

### Service

在 `test_case_service.py` 增加：

- `review_test_case(project_id, set_id, case_id, payload, actor)`

并扩展：

- `_serialize_case`
- `_serialize_set`
- `regenerate_test_case_set`
- `_generation_input_snapshot`
- `_build_generation_input`

序列化用例集时统一带 `review_stats`。列表页也可以展示采纳率，不必只有详情页可见。

### 重新生成反馈注入

重新生成时收集当前用例集里 `status = 'rejected'` 的用例：

```json
[
  {
    "title": "登录失败提示校验",
    "module": "登录",
    "priority": "P1",
    "preconditions": "用户已打开登录页",
    "steps": ["输入错误密码", "点击登录"],
    "expected_result": "提示密码错误",
    "review_feedback": "缺少账号锁定边界，不适合作为主流程用例"
  }
]
```

注入规则：

- 仅 `regenerate_test_case_set` 注入。
- 首次 `create_test_case_set` 不注入。
- 反馈为空时保留用例标题、模块、预期结果，并明确 `review_feedback` 为空。
- 不让模型推测用户拒绝原因。

## Agent 契约

扩展 `TestCaseGenerationInput`：

```python
rejected_case_feedback: list[RejectedTestCaseFeedback] = Field(default_factory=list)
```

新增 schema：

```python
class RejectedTestCaseFeedback(BaseModel):
    title: str
    module: str = ""
    priority: str = ""
    preconditions: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    review_feedback: str = ""
```

更新 `apps/backend/app/agents/test_case_generation/skills/test-case-generation/SKILL.md`：

- 如果输入包含 `rejected_case_feedback`，生成时必须参考这些反馈。
- 避免再次输出与被拒绝用例高度相似的问题用例。
- 如果 `review_feedback` 为空，只能把该用例视为“用户未采纳的反例”，不得编造拒绝原因。
- 不要为了规避反例而漏掉需求中的关键业务路径，应以更准确的步骤、预期结果或覆盖角度重新表达。

## 前端信息架构

### 入口

现有 `/test-cases` 列表页继续保留。

新增操作入口：

- 表格行操作增加 `评审`
- 点击跳转：

```text
/test-cases/{setId}/review
```

也可以在详情弹窗中增加 `进入评审` 按钮，但不把评审主流程放在弹窗内。

### 新页面路径

```text
apps/frontend/src/app/(main)/test-cases/[setId]/review/page.tsx
```

页面加载策略：

- 从 URL 获取 `setId`。
- 如果项目上下文是单项目，使用当前项目 ID 请求详情。
- 如果是全部项目视图，需要先从列表或查询参数拿到 `project_id`。推荐入口跳转时带查询参数：

```text
/test-cases/{setId}/review?project={projectId}
```

这样新页面不需要跨项目搜索。

## 前端页面设计

### 设计定位

主题：测试评审台。

目标用户是测试人员或项目管理员，需要快速判断 AI 生成用例是否值得采纳。界面应偏操作台和资产评审，不做 landing page，不用大 hero，不用装饰性渐变和卡片堆叠。

### 视觉系统

颜色：

- 页面背景：`#F7F8FA`
- 主文字：`#101828`
- 辅助文字：`#667085`
- 分割线：`#D0D5DD`
- 主操作蓝：`#2563EB`
- 采纳绿：`#16A34A`
- 不采纳红：`#DC2626`
- 待评审琥珀：`#F59E0B`
- 面板白：`#FFFFFF`

字体：

- 主体使用现有项目字体栈。
- 数据数字使用 `font-mono` 或现有等宽工具类，便于采纳率和计数对齐。

圆角：

- 面板、按钮、状态 chip 保持 6px 到 8px。
- 不使用大圆角卡片。

### 布局

桌面端：

```text
┌──────────────────────────────────────────────────────────────┐
│ 面包屑 / 用例集名称                         返回列表 重新生成 │
├──────────────────────────────────────────────────────────────┤
│ 采纳率  评审进度  已采纳  未采纳  待评审                 │
├──────────────────────┬───────────────────────────────────────┤
│ 筛选 / 搜索           │ 当前用例详情                         │
│ 模块分组用例列表       │ 标题 / 模块 / 优先级 / 状态           │
│ - 用例 A              │ 前置条件                             │
│ - 用例 B              │ 步骤                                 │
│ - 用例 C              │ 预期结果                             │
│                      │ 不采纳反馈                           │
├──────────────────────┴───────────────────────────────────────┤
│                      采纳  不采纳  回到待评审                 │
└──────────────────────────────────────────────────────────────┘
```

移动端：

- 顶部统计条横向滚动或两列网格。
- 用例列表和详情纵向排列。
- 操作栏固定在底部。

### 顶部统计条

展示：

- `采纳率`
- `评审进度`
- `已采纳`
- `未采纳`
- `待评审`

采纳率展示规则：

- `reviewed_count = 0` 时显示 `--`
- 否则显示百分比，保留 1 位小数

评审进度展示规则：

- `case_count = 0` 时显示 `0%`
- 否则显示百分比，保留 1 位小数

### 左侧列表

功能：

- 搜索标题、模块、预期结果。
- 筛选：全部、待评审、已采纳、未采纳。
- 按模块分组。
- 每条用例显示：标题、优先级、状态、反馈摘要。

状态视觉：

- `ready_for_review`：琥珀色细边或点标。
- `approved`：绿色状态。
- `rejected`：红色状态，并显示反馈摘要；反馈为空时显示“未填写原因”。

### 右侧详情

展示：

- 标题
- 模块
- 优先级
- 状态
- 前置条件
- 步骤
- 预期结果
- 不采纳反馈
- 更新时间

步骤使用有序列表，保持稳定宽度，避免因为内容变化导致布局跳动。

### 操作栏

按钮：

- `采纳`：绿色主按钮或绿色 outline，使用 `Check` 图标。
- `不采纳`：红色 outline，使用 `X` 或 `CircleX` 图标。
- `回到待评审`：中性按钮，使用 `RotateCcw` 图标。

交互：

- 点击 `采纳` 直接调用评审接口。
- 点击 `不采纳` 打开弹窗。
- 点击 `回到待评审` 清空反馈并重置状态。
- 操作成功后更新当前用例、左侧列表和顶部统计。
- 当前用例处理完成后，推荐自动选中下一条待评审用例；如果没有下一条，保持当前用例选中。

### 不采纳弹窗

标题：

```text
不采纳此用例
```

说明：

```text
可以补充原因，重新生成时会参考这些信息。也可以不填写。
```

字段：

- Label：`不采纳原因`
- Placeholder：`例如：步骤缺少异常分支、预期结果不可验证、与需求不一致`
- 最大长度：1000

按钮：

- `取消`
- `跳过说明并不采纳`
- `保存不采纳`

不采纳信息为空时，前端仍提交：

```json
{
  "status": "rejected",
  "review_feedback": ""
}
```

## 前端状态模型

推荐本页内部状态：

```ts
type ReviewFilter = "all" | "ready_for_review" | "approved" | "rejected";

type RejectDialogState = {
  open: boolean;
  caseId: string;
  feedback: string;
};
```

页面级状态：

- `testCaseSet`
- `selectedCaseId`
- `filter`
- `searchText`
- `rejectDialog`
- `savingCaseId`

不需要引入全局 store。

## API Client 类型

扩展 `ApiTestCase`：

```ts
review_feedback: string;
reviewed_by: string;
reviewed_at: string | null;
```

新增：

```ts
export type ApiTestCaseReviewStats = {
  case_count: number;
  approved_count: number;
  rejected_count: number;
  pending_count: number;
  reviewed_count: number;
  adoption_rate: number;
  review_progress: number;
};

export type ApiTestCaseReviewUpdate = {
  status: "ready_for_review" | "approved" | "rejected";
  review_feedback: string;
};

export type ApiTestCaseReviewResult = {
  case: ApiTestCase;
  review_stats: ApiTestCaseReviewStats;
};
```

扩展 `ApiTestCaseSet`：

```ts
review_stats: ApiTestCaseReviewStats;
```

## 采纳率生成和展示

### 后端计算

后端作为采纳率真源，避免前端和 Dashboard 分别实现一套算法。

推荐 SQL 聚合：

```sql
SELECT
  COUNT(*) AS case_count,
  SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved_count,
  SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected_count,
  SUM(CASE WHEN status = 'ready_for_review' THEN 1 ELSE 0 END) AS pending_count
FROM test_cases
WHERE test_case_set_id = ?
```

Python 计算：

```python
reviewed_count = approved_count + rejected_count
adoption_rate = approved_count / reviewed_count if reviewed_count else 0
review_progress = reviewed_count / case_count if case_count else 0
```

### 前端展示

采纳率卡片：

- `reviewed_count === 0`：显示 `--`
- 否则：`formatPercent(adoption_rate)`

评审进度卡片：

- `case_count === 0`：显示 `0%`
- 否则：`formatPercent(review_progress)`

## 重新生成行为

### 当前行为

`regenerate_test_case_set` 会创建新的 generation run，执行后 `replace_cases` 删除旧用例并写入新用例。

### 新行为

创建 regeneration run 前：

1. 查询当前用例集 rejected 用例和反馈。
2. 写入 generation run 的 `input_json` 快照。
3. 执行生成时从快照或当前库中构建 `TestCaseGenerationInput.rejected_case_feedback`。

推荐把反馈写入 `input_json`，确保后台任务执行时上下文稳定，不受后续用户继续评审影响。

### 注意

重新生成完成后旧用例会被替换，新用例状态重新进入 `ready_for_review`。采纳率也基于新用例重新计算。

## 测试方案

### 后端

更新或新增 `apps/backend/tests/test_test_case_set_service.py`：

- 生成完成后用例默认状态仍为 `ready_for_review`。
- 采纳用例后状态为 `approved`，反馈为空，统计正确。
- 不采纳用例且填写反馈后状态为 `rejected`，反馈持久化，统计正确。
- 不采纳用例且反馈为空时允许成功。
- 回到待评审会清空反馈，统计正确。
- 非当前项目的 set/case 返回 404。
- 非管理员评审返回 403。
- 重新生成时 rejected 反馈进入 generation input snapshot。
- 首次创建不携带 rejected 反馈。

### 前端契约测试

新增或更新 `apps/frontend/tests/test-case-review-page-contract.test.mjs`：

- 页面包含采纳率、评审进度、已采纳、未采纳、待评审。
- 页面存在 `采纳`、`不采纳`、`回到待评审` 操作。
- 不采纳弹窗包含 `不采纳原因`。
- 不采纳弹窗包含 `跳过说明并不采纳`。
- 列表页行操作包含 `评审`。

### 轻量验证

后端：

```powershell
cd apps/backend
uv run pytest tests/test_test_case_set_service.py
```

前端：

```powershell
cd apps/frontend
npm test -- tests/test-case-review-page-contract.test.mjs
```

如果现有项目测试命令不同，应优先沿用仓库已有 package scripts。

## 风险和取舍

### 不记录历史评审记录

本方案只保存当前状态和当前反馈。优点是实现简单，契约清晰。缺点是无法追踪某条用例的多次评审历史。当前需求没有审计要求，暂不引入历史表。

### 采纳率分母选择

采纳率使用已评审用例作为分母，而不是全部用例。这样更符合“采纳决策质量”的含义。评审覆盖程度由“评审进度”单独表达。

### 重新生成替换旧用例

现有 `replace_cases` 会删除旧用例。重新生成后旧评审状态自然失效。 rejected 反馈会在生成前被保存到 run snapshot，保证 Agent 能参考旧反馈。

### 空反馈的语义

空反馈只表示“用户不采纳但未说明原因”。Agent 不能据此编造问题原因，只能把该用例作为反例，避免高度相似输出。

## 实施顺序

1. 扩展数据库字段和 schema。
2. 增加 repository 层评审更新、统计聚合、 rejected 反馈查询。
3. 增加 service 和 API 评审接口。
4. 扩展序列化输出和前端 API 类型。
5. 扩展 Agent 输入 schema 和 prompt。
6. 在重新生成链路中注入 rejected 反馈。
7. 新增独立评审页面。
8. 在测试用例集列表页增加 `评审` 入口。
9. 补后端服务测试和前端契约测试。
10. 运行后端和前端相关测试。

## 验收标准

- 测试用例集列表页可以进入独立评审页面。
- 评审页面能展示用例列表、用例详情、采纳率和评审进度。
- 点击采纳后用例状态变为已采纳，统计即时更新。
- 点击不采纳后弹出反馈窗口。
- 不填写反馈也能完成不采纳。
- 填写反馈后反馈能持久化并在页面展示。
- 用例可以从已采纳或未采纳回到待评审。
- 重新生成同一个用例集时，历史不采纳反馈进入 Agent 输入。
- 首次生成测试用例集时不携带不采纳反馈。
- 后端相关测试通过。
- 前端契约测试通过。
