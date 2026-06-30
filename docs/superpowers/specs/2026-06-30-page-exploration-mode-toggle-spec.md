# 页面探索方式显式切换 Spec

## 背景

当前页面探索已有两类业务意图：

- 目标探索：用户给出明确探索目标，系统围绕目标执行探索与验证。
- 自主探索：用户只指定入口或范围，系统对当前页面或范围做功能盘点。

现有代码中，探索任务创建表单和后端接口主要承载 `goal`、`scope`、`forbidden_paths`、预算等字段，没有显式承载“探索方式”。这会导致后端或 Agent 需要从目标文本中判断用户到底想做目标探索还是自主探索，判断结果不稳定，也不符合“不要让 Agent 猜业务意图”的原则。

本规范要求前端提供一个类似昼夜切换的二段式切换控件，由用户显式指定探索方式；后端只接收并执行该方式，不再由 Agent 判断使用哪种探索方式。

## 目标

1. 新建和编辑探索任务时，前端提供“目标探索 / 自主探索”二段式切换。
2. 默认选择“目标探索”。
3. 前端提交请求时必须携带探索方式字段。
4. 后端保存探索方式，并在启动探索时传入执行上下文。
5. Agent 不负责判断使用目标探索还是自主探索。
6. 不设计“未传字段时后端自动兜底判断”的逻辑。

## 非目标

- 不在本次改造中完整实现模板体系、GoalCompletionEvaluator 或受控 Orchestrator。
- 不让后端根据 `goal` 是否为空自动决定探索方式。
- 不恢复旧字段 `execution_mode`、`interaction_mode`。
- 不改变登录策略、验证码策略、执行预算的现有语义。

## 术语

### 目标探索

产品展示名：`目标探索`

接口值：

```ts
"goal"
```

含义：

- 用户有明确目标。
- `goal` 是核心输入。
- 后续可进入模板选择、目标验证、目标完成判断等链路。

### 自主探索

产品展示名：`自主探索`

接口值：

```ts
"autonomous"
```

含义：

- 用户希望系统自行盘点页面或范围内主要功能。
- `scope` 是核心输入。
- `goal` 可选，不参与探索方式判断。

## 前端交互

### 控件形式

探索任务表单中增加一个二段式切换控件，视觉形态参考昼夜模式切换：

- 左侧：目标探索
- 右侧：自主探索
- 当前选中项有滑块或高亮背景
- 切换是单选，不允许为空

推荐位置：

- 放在“探索范围”之前。
- 让用户先决定探索方式，再填写范围、目标和限制。

### 默认值

新建探索任务时：

```ts
explorationMode: "goal"
```

编辑探索任务时：

- 使用后端返回的 `exploration_mode` 回填。
- 不根据 `goal`、`scope` 或历史产物推断。

### 表单行为

目标探索：

- 显示“探索目标”字段。
- “探索目标”字段保持当前 AI 生成能力。
- 不强制本次改造新增必填校验，是否必填由后续目标探索规则决定。

自主探索：

- 仍可显示“探索目标”字段，但文案应弱化为可选补充。
- 更推荐将字段标签展示为“补充目标”或保留“探索目标”，并通过 placeholder 表达“可选”。
- 不允许前端因为目标为空而切回目标探索或阻止自主探索。

### 建议文案

切换控件标题：

```text
探索方式
```

选项文案：

```text
目标探索
自主探索
```

选项辅助说明可以只在 Tooltip 或紧凑说明中出现：

```text
目标探索：围绕明确目标验证页面流程。
自主探索：自动盘点当前页面或范围内的主要功能。
```

## 前端数据结构

在探索表单类型中增加字段：

```ts
type ExplorationMode = "goal" | "autonomous";

type ExplorationForm = {
  title: string;
  projectId: string;
  environmentId: string;
  requirementDocId: string;
  explorationMode: ExplorationMode;
  scope: string;
  forbiddenPaths: string;
  goal: string;
  notes: string;
  maxPages: string;
  maxActions: string;
  timeoutMinutes: string;
};
```

空表单默认值：

```ts
const emptyExplorationForm: ExplorationForm = {
  title: "",
  projectId: "",
  environmentId: "",
  requirementDocId: "",
  explorationMode: "goal",
  scope: "",
  forbiddenPaths: "",
  goal: "",
  notes: "",
  maxPages: "50",
  maxActions: "1000",
  timeoutMinutes: "120",
};
```

创建和更新 payload 必须包含：

```ts
{
  exploration_mode: explorationForm.explorationMode
}
```

## 后端接口契约

### 请求字段

`CreateExplorationRunRequest` 增加：

```python
exploration_mode: Literal["goal", "autonomous"] = Field(..., description="探索方式")
```

`UpdateExplorationRunRequest` 增加：

```python
exploration_mode: Literal["goal", "autonomous"] | None = Field(None, description="探索方式")
```

说明：

- 创建请求中 `exploration_mode` 必须由前端传入。
- 后端不根据 `goal`、`scope`、`notes` 推断探索方式。
- 后端不调用 Agent 做探索方式分类。

### 响应字段

探索任务响应增加：

```python
exploration_mode: str
```

前端列表、详情、编辑弹窗均使用该字段展示和回填。

## 数据库变更

`exploration_runs` 增加字段：

```sql
exploration_mode TEXT NOT NULL DEFAULT 'goal'
  CHECK(exploration_mode IN ('goal', 'autonomous'))
```

说明：

- 默认值用于数据库结构约束和历史数据迁移。
- 新创建请求仍要求前端显式传入 `exploration_mode`。
- 历史数据迁移为 `goal`，不做文本推断。

Repository 支持：

- `create(..., exploration_mode: str)`
- `update(..., exploration_mode=...)`
- `find_by_id`、`find_detail_by_id` 原样返回该字段。

## 执行链路

启动探索时，服务层从 run_config 读取：

```python
exploration_mode = run_config["exploration_mode"]
```

构造 Agent prompt 或后续 Orchestrator input 时必须显式传入：

```text
探索方式: 目标探索
```

或：

```text
探索方式: 自主探索
```

执行规则：

- `exploration_mode == "goal"`：Agent/Orchestrator 按目标探索执行，不再判断“目标是否明确”来切换到自主探索。
- `exploration_mode == "autonomous"`：Agent/Orchestrator 按自主盘点执行，不再因为 `goal` 有内容而切回目标探索。

后续如果引入 `GoalClassifier`，其职责只能是：

- 在 `goal` 模式内部选择目标模板。
- 不能决定 `goal` 与 `autonomous` 的模式切换。

## 产物字段

页面 YAML、summary 或 run 级产物应记录：

```yaml
exploration_mode: goal
```

或：

```yaml
exploration_mode: autonomous
```

人类可读报告中展示：

```text
探索方式：目标探索
```

或：

```text
探索方式：自主探索
```

## 兼容策略

历史任务：

- 迁移后 `exploration_mode = 'goal'`。
- 不扫描历史 `goal` 文本。
- 不根据历史产物判断模式。

新任务：

- 前端默认 `goal`。
- 请求必须带 `exploration_mode`。
- 如果请求缺少该字段，应按请求校验失败处理，而不是后端静默补齐。

## 错误处理

非法值：

```json
{
  "exploration_mode": "unknown"
}
```

应返回 422 或现有请求校验错误。

缺少字段：

- 创建请求缺少 `exploration_mode` 时返回请求校验错误。
- 不允许后端从 `goal` 是否为空推断。

## 测试要求

### 后端测试

1. 创建探索任务时传 `exploration_mode = "goal"`，数据库保存为 `goal`。
2. 创建探索任务时传 `exploration_mode = "autonomous"`，数据库保存为 `autonomous`。
3. 创建探索任务缺少 `exploration_mode` 返回校验错误。
4. 创建探索任务传非法值返回校验错误。
5. 更新探索任务可修改 `exploration_mode`。
6. 启动探索时 run_config 包含 `exploration_mode`。
7. Agent prompt 或 Orchestrator input 中包含显式探索方式。

### 前端测试

1. 新建探索任务弹窗默认选中“目标探索”。
2. 用户切换到“自主探索”后，payload 中 `exploration_mode = "autonomous"`。
3. 编辑已有任务时，切换控件按后端返回值回填。
4. 切换探索方式不会清空 `scope`、`goal`、`forbiddenPaths`。
5. 自主探索下 `goal` 为空也允许保存，前提是其他现有必填项满足。

## 验收标准

1. 前端创建探索任务时，用户可以通过二段式切换选择“目标探索”或“自主探索”。
2. 默认选中“目标探索”。
3. 请求 payload 明确包含 `exploration_mode`。
4. 后端保存并返回 `exploration_mode`。
5. 编辑任务时可回显并修改探索方式。
6. 启动探索时执行上下文明确包含探索方式。
7. 代码中不存在“根据 goal 文本判断目标探索/自主探索”的逻辑。
8. 新任务缺少 `exploration_mode` 不会被后端静默兜底。

## 推荐实施顺序

1. 后端增加 schema、数据库字段、repository create/update 支持。
2. 后端响应序列化补充 `exploration_mode`。
3. 前端类型、表单默认值和 payload 增加 `explorationMode`。
4. 前端增加二段式切换控件。
5. 启动探索 prompt/input 注入探索方式。
6. 补充后端和前端测试。
