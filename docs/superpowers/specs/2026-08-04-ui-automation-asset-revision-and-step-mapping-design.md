# UI 自动化资产修订与业务步骤映射设计

## 文档状态

- 日期：2026-08-04
- 状态：待评审
- 范围：UI 自动化资产重新生成、业务步骤映射修复、生成验证、任务展示
- 不包含：自动修改原始测试用例、重新设计 UI 自动化执行引擎、历史执行结果数据迁移

## 背景

当前 UI 自动化资产详情在旧版本资产缺少业务步骤映射时，会提示用户重新生成资产。用户点击“重新生成”后，系统调用通用 UI 自动化生成接口，根据原始测试用例和探索证据创建新的 generation run。

该流程存在三个问题：

1. 当前资产的测试逻辑、定位器和断言已经正确，但重新生成没有把当前资产作为明确修订基线，可能产生不必要的大范围重写。
2. UI 自动化列表把活动 generation run 与现有资产同时渲染，导致同一用例在重新生成期间显示成两条记录。
3. UI 自动化 generation run 已创建 `task_id`，但任务中心没有采集 UI 自动化生成和执行任务，因此顶部运行任务不显示。

本次实际业务目标不是创建第二条 UI 自动化资产，而是：

> 基于当前正确资产，补全业务步骤映射；在不改变现有执行行为的前提下完成校验，并在必要时运行真实 UI 用例验证。

## 当前问题根因

### 重新生成语义不明确

当前重新生成请求只包含测试用例、环境和探索任务信息，没有携带目标资产、基线生成任务或用户修改要求。后端每次创建新 generation run，并使用新 run ID 生成新的 test、data 和 plan 路径。

因此当前接口表达的是“从源信息重新生成”，而不是“基于当前资产修订”。

### 活动任务与资产被重复展示

列表将以下两类数据直接拼接：

- 已完成生成并持久化的 UI 自动化资产。
- 尚未完成且未成为资产当前 generation run 的生成任务。

重新生成任务的 ID 必然不同于资产当前记录的旧 generation run ID，因此活动任务会被当成一条新的列表记录。

### 任务中心接入不完整

员工注册元数据已经声明：

- `ui_automation_generation_run`
- `ui_automation_run`

但任务服务缺少：

- UI 自动化任务状态映射。
- UI 自动化任务采集函数。
- 顶部运行任务类型注册。

因此任务已创建，但不会出现在任务中心和顶部运行任务区域。

## 设计目标

1. 将“重新生成”改为明确的“基于当前资产修订”。
2. 用户可以填写可选修改要求，并将要求传递给智能体。
3. 用户不填写要求时，系统仍根据检测到的问题执行有目标的最小修订，而不是无目标全量生成。
4. 对于缺少业务步骤映射的问题，优先使用确定性修复，不调用 AI 重写正确代码。
5. 只有确定性修复无法完成或用户要求改变自动化行为时，才调用 AI。
6. AI 修订失败、校验失败或发布失败时，当前可执行资产保持不变。
7. 修订期间，UI 自动化列表只显示原资产一行。
8. UI 自动化修订任务出现在顶部运行任务和任务中心。
9. 修订成功后可以选择自动执行真实 UI 用例验证。
10. 历史执行结果保持只读，不尝试伪造或回填历史运行中的业务步骤。

## 非目标

1. 不允许通过修订流程回写原始手工测试用例或已采纳测试用例。
2. 不在本次设计中提供任意历史版本回滚界面。
3. 不自动重新执行所有历史运行。
4. 不把所有 UI 自动化生成问题都交给 AI 处理。
5. 不允许 AI 在没有证据的情况下修改 locator、断言或业务事实。
6. 不新增独立任务表，继续以 generation run 和 execution run 作为任务事实来源。

## 核心原则

### 当前资产是修订基线

重新生成必须读取当前资产的：

- test 文件。
- data 文件。
- plan 文件。
- 关联 POM。
- 当前 generation run。
- 原始测试用例。
- 当前探索证据。

除非校验证明现有实现无法满足修订目标，否则保留当前执行逻辑。

### 确定性修复优先

业务步骤映射属于结构化元数据问题。只要当前 plan 或测试操作仍保留可追踪的原始步骤引用，就应通过确定性逻辑补全映射，不调用 AI。

### AI 是兜底，不是默认路径

只有以下情况调用 AI：

- 当前资产缺少足够的步骤来源引用，无法确定性映射。
- 当前实现与原始测试用例已经不一致。
- 用户提出需要改变自动化行为的修改要求。
- 当前 plan 无法通过现行生成契约校验，且不能安全自动修复。

### 验证成功后才能发布

所有修订先在隔离工作区执行。只有结构校验、collection 和变更范围校验全部通过后，才能更新正式资产。

## 用户交互设计

### 入口

资产详情页将“重新生成”按钮调整为：

```text
修订自动化
```

如果系统检测到当前资产缺少业务步骤映射，页面显示问题提示：

```text
当前资产缺少业务步骤映射，执行详情只能展示技术动作。
可通过修订自动化补全业务步骤名称和动作分组。
```

### 修订对话框

点击“修订自动化”后打开对话框。

#### 标题

```text
修订 UI 自动化
```

#### 检测到的问题

当问题代码为 `missing_business_step_mapping` 时显示：

```text
当前资产缺少业务步骤映射。
本次修订将优先补全步骤名称和动作分组，不改变现有执行逻辑、定位器和断言。
```

#### 修改要求

提供可选多行文本框：

```text
补充修改要求（可选）
```

占位文案：

```text
例如：保留当前定位器和断言，只补全业务步骤名称和动作分组。
留空时，系统将根据检测到的问题和当前资产进行最小修订。
```

最大长度为 2000 个字符。前后空白在提交前移除。

#### 环境与探索证据

默认继承当前资产最近一次成功 generation run 的：

- `environment_id`
- `exploration_run_id`

用户可以在对话框中修改环境或探索任务。如果继承值已经失效，必须要求用户重新选择，不能静默替换。

#### 验证选项

对话框展示：

```text
静态校验：始终执行
□ 修订成功后立即运行 UI 用例验证
```

静态校验不可关闭。真实 UI 执行默认不勾选，避免无意操作目标环境。

#### 操作按钮

```text
取消
修订并验证
```

提交过程中禁止重复点击。

## 修订原因模型

修订原因必须使用结构化代码，而不是只依赖自然语言。

第一期支持：

```text
missing_business_step_mapping
```

后续可以扩展：

```text
outdated_generation_contract
invalid_locator_evidence
source_test_case_changed
user_requested_change
```

原因代码用于：

- 生成默认修订目标。
- 选择确定性修复器。
- 控制是否需要 AI。
- 生成任务摘要。
- 统计问题和修复成功率。

## 接口设计

### 创建资产修订任务

```http
POST /projects/{project_id}/ui-automation/assets/{asset_id}/revision-runs
```

请求：

```json
{
  "reason_code": "missing_business_step_mapping",
  "instruction": "",
  "environment_id": "env-c3bc1023763dbb16",
  "exploration_run_id": "exp_Am3HGwQW4awyEobW17YWEw",
  "run_after_revision": false
}
```

字段规则：

- `reason_code` 必填，并且必须是服务端支持的修订原因。
- `instruction` 可空，最大 2000 个字符。
- `environment_id` 可空；为空时继承当前资产最近一次成功生成环境。
- `exploration_run_id` 可空；为空时继承当前资产最近一次成功探索任务。
- `run_after_revision` 默认为 `false`。

响应仍使用 UI 自动化 generation run 输出模型，但增加修订字段：

```json
{
  "id": "uigen-new",
  "project_id": "project-1",
  "target_asset_id": "uiasset-1",
  "base_generation_run_id": "uigen-old",
  "generation_mode": "revise",
  "reason_code": "missing_business_step_mapping",
  "instruction": "",
  "run_after_revision": false,
  "status": "queued",
  "task_id": "ui_generation:uigen-new"
}
```

### 保留首次生成接口

现有接口继续负责首次生成：

```http
POST /projects/{project_id}/ui-automation/generation-runs
```

首次生成固定为：

```text
generation_mode = create
target_asset_id = null
base_generation_run_id = null
```

前端不得再通过首次生成接口实现已有资产修订。

## 数据模型

在 `ui_automation_generation_runs` 增加：

```sql
target_asset_id TEXT NULL,
base_generation_run_id TEXT NULL,
generation_mode TEXT NOT NULL DEFAULT 'create',
reason_code TEXT NOT NULL DEFAULT '',
instruction TEXT NOT NULL DEFAULT '',
run_after_revision INTEGER NOT NULL DEFAULT 0,
revision_strategy TEXT NOT NULL DEFAULT ''
```

字段说明：

- `target_asset_id`：本次要修订的资产。
- `base_generation_run_id`：修订开始时资产当前生效的 generation run。
- `generation_mode`：`create` 或 `revise`。
- `reason_code`：结构化修订原因。
- `instruction`：用户补充修改要求。
- `run_after_revision`：修订成功后是否自动创建 execution run。
- `revision_strategy`：实际执行策略，取 `deterministic` 或 `ai`。

资产表继续表示当前生效版本：

```text
ui_automation_assets.id                 保持不变
ui_automation_assets.generation_run_id  成功后切换到新 generation run
ui_automation_assets.source_version     成功后加 1
```

### 并发约束

同一资产同时只能有一个活动修订任务。

创建部分唯一索引：

```sql
CREATE UNIQUE INDEX uq_ui_active_asset_revision
ON ui_automation_generation_runs(target_asset_id)
WHERE target_asset_id IS NOT NULL
  AND status IN ('queued', 'running');
```

重复创建时返回：

```text
409 UI_AUTOMATION_REVISION_ACTIVE
当前资产已有修订任务正在执行。
```

## 状态模型

generation run 使用以下状态：

```text
queued
running
waiting_manual
completed
failed
interrupted
```

状态转换：

```text
queued -> running
running -> completed
running -> waiting_manual
running -> failed
queued/running -> interrupted
```

如果用户选择真实 UI 验证，generation run 在静态修订成功后仍标记为 `completed`，真实执行使用独立 execution run 表示，不混用 generation run 状态。

## 服务端处理流程

### 创建修订任务

服务端依次执行：

1. 校验用户有项目管理权限。
2. 校验资产存在且属于当前项目。
3. 校验资产当前 generation run 存在且已完成。
4. 校验 test、data 和 plan 文件存在。
5. 解析环境与探索任务继承值。
6. 检查资产是否已有活动修订任务。
7. 创建 `generation_mode=revise` 的 generation run。
8. 记录 `target_asset_id` 和 `base_generation_run_id`。
9. 投递后台任务。

如果当前资产文件不完整，返回：

```text
409 UI_AUTOMATION_BASE_ASSET_INCOMPLETE
当前资产文件不完整，无法基于当前版本修订。
```

系统不得在该错误下静默改为首次生成。

### 建立隔离工作区

每个修订任务建立：

```text
ui_automation/.generation-staging/{run_id}/
```

将当前项目 `pytest_playwright` 工程复制到该目录。修订过程中的 AI、renderer 和 pytest collection 全部在隔离工作区执行。

正式工程在发布前保持只读。

后台任务结束后必须删除 staging 目录。服务启动时应清理已进入终态但 staging 目录仍存在的历史残留。

## 业务步骤确定性修复

### 适用条件

原因代码为 `missing_business_step_mapping` 时，服务端首先尝试确定性修复。

确定性修复要求至少满足一种可追踪条件：

- operation 已包含合法 `source_step_id`。
- operation 已包含可唯一映射到原始步骤的旧版步骤 ID。
- plan 中存在能够唯一关联原始步骤的稳定映射字段。

如果一个 operation 可能对应多个原始步骤，确定性修复必须失败并转入 AI 策略，不能猜测。

### 修复规则

对每个 operation：

1. 找到对应原始测试用例步骤。
2. 写入 `business_step_id`，值为原始步骤 ID。
3. 写入 `title`，值为原始步骤的 `action`。
4. 同一原始步骤拆分出的 fill、click、wait、assert 等动作使用相同 `business_step_id`。
5. 保持 operation 原始顺序。
6. 不修改 locator、value、assertion、timeout 和参数引用。

修复后将 plan 升级到当前 schema version。

### 确定性策略输出

成功时记录：

```text
revision_strategy = deterministic
```

并在 `changed_files_json` 中只记录实际修改的 plan 或必要派生文件。

确定性修复不调用模型，不产生模型调用成本。

## AI 修订策略

### 进入条件

满足任一条件时进入 AI 修订：

- 确定性步骤映射无法唯一完成。
- 用户修改要求涉及执行行为。
- 当前 plan 无法被确定性升级到当前契约。
- 当前资产与原始测试用例存在需要判断的差异。

### AI 输入

智能体输入必须包含：

```json
{
  "mode": "revise",
  "reason": {
    "code": "missing_business_step_mapping",
    "description": "当前资产缺少业务步骤映射"
  },
  "user_instruction": "",
  "base_asset": {
    "asset_id": "uiasset-1",
    "generation_run_id": "uigen-old",
    "source_version": 1,
    "test_file_path": "...",
    "data_file_path": "...",
    "plan_file_path": "..."
  },
  "source_test_case": {},
  "exploration_evidence": {}
}
```

### 空修改要求的系统目标

用户不填写修改要求时，系统必须生成以下等价目标：

```text
基于当前 UI 自动化资产进行最小范围修订。

检测到的问题：当前资产缺少业务步骤映射，执行详情无法按照原始测试用例步骤分组展示。

本次目标：
1. 补全 AutomationPlan 中的 business_step_id。
2. 每个业务步骤的 title 使用原始测试用例步骤名称。
3. 同一业务步骤拆分出的技术动作归入同一个业务步骤。
4. 保留当前测试执行逻辑、定位器、断言、参数化和公共封装。
5. 除非当前代码无法满足业务步骤映射契约，否则不得重写测试逻辑。
```

### AI 修改约束

智能体必须：

- 先读取当前 test、data、plan 和关联 POM。
- 在当前资产基础上做最小必要修改。
- 保留仍然有效的人工调整和公共封装。
- 只使用探索证据中可追踪的 locator。
- 保持原始测试用例业务事实不变。
- 说明修改了哪些文件以及修改原因。

智能体不得：

- 无理由重写整个测试文件。
- 删除无法由本次输入证明应当删除的逻辑。
- 修改原始测试用例。
- 编造 locator 或页面路径。
- 写入凭证、Cookie、Token 或宿主机绝对路径。

AI 策略成功时记录：

```text
revision_strategy = ai
```

## 校验规则

### 业务步骤映射校验

每个可见业务步骤必须满足：

- `business_step_id` 非空。
- `business_step_id` 存在于原始测试用例步骤中。
- `title` 与对应原始步骤 `action` 一致。

每个需要展示的自动化 operation 必须满足：

- `business_step_id` 非空。
- 对应业务步骤存在。
- 同一原始步骤拆分出的 operation 使用相同 `business_step_id`。
- operation 顺序与执行顺序一致。

如果原始用例有 22 个步骤，资产计划应能形成 22 个按原始顺序排列的业务步骤组。允许某个业务步骤包含多个技术动作。

### 静态验证

每次修订必须执行：

1. AutomationPlan schema 校验。
2. 业务步骤映射完整性校验。
3. 测试文件与 plan 身份一致性校验。
4. 单测试文件 pytest collection。
5. 全工程 pytest collection。
6. 输出路径安全校验。
7. 变更文件白名单校验。
8. 修订前后行为 diff 校验。

### 行为 diff 校验

当原因仅为 `missing_business_step_mapping` 且用户未提出行为修改要求时，以下内容不应发生实质变化：

- locator。
- 断言。
- 参数化数据。
- 测试执行顺序。
- 等待策略。
- pytest 用例身份。
- 环境和探索证据来源。

如果出现大范围行为变更，任务必须失败并返回：

```text
UI_AUTOMATION_REVISION_SCOPE_EXCEEDED
本次修订超出业务步骤映射范围，未发布修改。
```

## 原子发布

全部校验通过后执行发布：

1. 计算 staging 工作区与正式工程的文件差异。
2. 只允许发布白名单内的生成资产和 POM 文件。
3. 对即将替换的正式文件创建备份。
4. 使用原子文件替换发布修改。
5. 更新原资产记录，不创建新资产。
6. `source_version` 加 1。
7. `generation_run_id` 更新为本次 generation run。
8. 更新 `source_hash`、文件路径和更新时间。
9. 将 generation run 标记为 `completed`。
10. 删除 staging 工作区和临时备份。

任意发布步骤失败时：

- 恢复已经替换的文件。
- 原资产数据库记录保持原值。
- generation run 标记为 `failed`。
- 记录明确失败原因。

修订失败不得将原资产标记为 degraded 或 deprecated。

## 真实 UI 执行验证

如果 `run_after_revision=true`：

1. 修订静态验证和发布成功。
2. generation run 标记为 `completed`。
3. 使用选定环境创建新的 UI automation execution run。
4. 调度真实 UI 执行。
5. 前端跳转到新 execution run 详情。

真实执行失败只影响 execution run，不回滚已经通过静态校验并发布的修订版本。执行失败原因由用户在运行详情中处理。

历史 execution run 保持原样。旧运行缺少映射时继续显示旧版提示，不能使用新 plan 伪造历史步骤结果。

## UI 自动化列表展示

列表行以资产 ID 为稳定身份。

### 首次生成

如果 generation run 没有 `target_asset_id` 且尚未生成资产，可以显示临时生成任务行。

### 已有资产修订

如果 generation run 有 `target_asset_id`，前端必须将活动任务合并到对应资产行：

```text
用例名称：原资产名称
状态：修订中
步骤数：当前原始用例步骤数
更新时间：活动修订任务更新时间
```

不得额外显示第二行。

资产在修订发布前仍保持当前可执行版本，因此允许：

- 查看当前版本。
- 执行当前版本。

执行按钮文案在活动修订期间显示为：

```text
执行当前版本
```

## 资产详情展示

资产详情在存在活动修订任务时显示任务条：

```text
正在修订自动化：补全业务步骤映射
```

任务条展示：

- 当前状态。
- 修订策略；在策略确定前显示“分析中”。
- 用户修改要求摘要。
- 创建时间。
- 任务 ID。

修订完成后刷新：

- 当前资产版本号。
- generation run 历史。
- 业务步骤映射摘要。
- locator 摘要。

## 顶部任务与任务中心

任务服务增加：

```text
ui_automation_generation_run
ui_automation_run
```

UI 自动化生成状态映射：

```text
queued         -> running / 排队中
running        -> running / 修订中或生成中
waiting_manual -> waiting / 等待补充信息
completed      -> completed / 修订完成或生成完成
failed         -> failed / 修订失败或生成失败
interrupted    -> completed / 已中断
```

任务标题：

- 首次生成：`生成 UI 自动化：{测试用例名称}`
- 资产修订：`修订 UI 自动化：{测试用例名称}`
- UI 执行：`执行 UI 自动化：{测试用例名称}`

修订任务详情地址：

```text
/projects/{project_id}/automation/ui/assets/{target_asset_id}?tab=generation
```

首次生成没有资产时使用：

```text
/automation/ui?generationRun={run_id}
```

## 错误处理

需要定义以下错误：

```text
UI_AUTOMATION_REVISION_REASON_UNSUPPORTED
UI_AUTOMATION_BASE_ASSET_INCOMPLETE
UI_AUTOMATION_REVISION_ACTIVE
UI_AUTOMATION_REVISION_MAPPING_AMBIGUOUS
UI_AUTOMATION_REVISION_SCOPE_EXCEEDED
UI_AUTOMATION_REVISION_VALIDATION_FAILED
UI_AUTOMATION_REVISION_PUBLISH_FAILED
```

错误响应必须说明：

- 当前资产是否仍可执行。
- 是否修改了正式文件。
- 是否可以重试。
- 是否需要用户补充修改要求或探索证据。

## 日志与可观测性

generation run 至少记录：

- `generation_mode`
- `reason_code`
- `revision_strategy`
- `target_asset_id`
- `base_generation_run_id`
- 是否调用 AI。
- 模型能力和模型选择信息。
- 确定性映射成功或失败原因。
- 修改文件列表。
- 静态校验结果。
- 发布结果。
- 自动 execution run ID。

关键统计指标：

- 修订任务数量。
- 确定性修复比例。
- AI 兜底比例。
- 修订成功率。
- 范围超限拦截数量。
- 修订平均耗时。
- 修订后真实执行通过率。

## 安全要求

1. 所有文件路径必须限制在当前项目 UI 自动化工程和任务 staging 目录内。
2. staging 目录必须使用服务端生成的 run ID，不接受用户路径。
3. AI 只能访问 staging 工作区。
4. 发布前必须验证所有变更文件处于允许目录。
5. 用户修改要求不能覆盖系统安全约束。
6. 日志不得记录账号、密码、Cookie、Token 或完整存储状态。

## 数据迁移与兼容性

现有 generation run 迁移为：

```text
generation_mode = create
target_asset_id = null
base_generation_run_id = null
reason_code = ''
instruction = ''
run_after_revision = 0
revision_strategy = ''
```

现有资产不需要复制或重建。

旧资产仍可执行。只有用户触发修订时才升级到当前业务步骤映射契约。

前端必须兼容后端暂未返回新增字段的过渡状态，但新修订入口只在后端能力可用时启用。

## 测试设计

### 后端接口测试

1. 已有资产可以创建修订任务。
2. 修订任务正确记录目标资产和基线 generation run。
3. 环境和探索任务可以继承。
4. 失效的继承值返回明确错误。
5. 同一资产不能并发创建两个活动修订任务。
6. 首次生成接口不能携带目标资产字段。
7. 非管理员不能创建修订任务。

### 确定性修复测试

1. 根据 `source_step_id` 补全 `business_step_id`。
2. title 使用原始步骤 action。
3. 同一业务步骤的多个 operation 正确归组。
4. locator、断言和顺序保持不变。
5. 映射不唯一时不猜测并转入 AI。
6. 确定性成功时不调用模型。

### AI 修订测试

1. AI 输入包含当前资产文件和修订原因。
2. 空修改要求生成默认最小修订目标。
3. 用户修改要求正确进入 AI 上下文。
4. AI 只在 staging 工作区修改文件。
5. 大范围无关变更被范围校验拦截。

### 发布测试

1. 校验成功后更新同一资产 ID。
2. 成功后 `source_version` 加 1。
3. 成功后 `generation_run_id` 更新。
4. 校验失败时正式文件不变。
5. 发布中途失败时文件和数据库均回滚。
6. staging 目录在终态后被清理。

### 前端测试

1. 点击“修订自动化”打开对话框。
2. 检测到的问题正确显示。
3. 修改要求可以留空。
4. 留空时请求仍包含 `reason_code`。
5. 重复提交被阻止。
6. 修订期间列表只显示原资产一行。
7. 修订期间可以执行当前版本。
8. 首次生成仍显示临时任务行。
9. 修订完成后资产版本和步骤映射刷新。
10. 选择真实 UI 验证后跳转到新执行详情。

### 任务中心测试

1. UI 修订任务出现在顶部运行任务。
2. UI 修订任务出现在任务中心运行中列表。
3. 任务标题区分首次生成和资产修订。
4. 任务链接进入正确资产详情。
5. UI execution run 同样进入任务中心。

## 验收标准

本设计完成后必须满足：

1. 用户点击修订时可以看到检测问题并输入可选修改要求。
2. 修改要求为空时，系统围绕检测问题执行最小修订，不做无目标全量生成。
3. 缺少业务步骤映射且可确定性修复时，不调用 AI。
4. 需要 AI 时，AI 明确读取当前资产并基于当前实现修改。
5. 原始用例有 22 个步骤时，新 plan 能形成 22 个有序业务步骤组。
6. 仅修复步骤映射时，现有 locator、断言和执行顺序保持不变。
7. 修订失败时，原资产仍可查看和执行。
8. 修订过程中，列表不会出现同名第二条资产记录。
9. 修订任务能在顶部任务和任务中心查看。
10. 用户选择真实执行验证时，修订成功后自动创建新 execution run。
11. 历史执行详情保持历史事实，不被新映射覆盖。

## 推荐实施顺序

1. 扩展 generation run 数据模型和 repository。
2. 新增资产 revision run 接口。
3. 实现业务步骤确定性修复器。
4. 实现隔离工作区、校验和原子发布。
5. 扩展 AI revise 上下文和最小修改约束。
6. 实现修订对话框和前端请求。
7. 修复列表任务与资产合并逻辑。
8. 接入顶部任务和任务中心。
9. 增加真实 UI 执行验证选项。
10. 完成后端、前端和任务中心回归测试。

## 设计决策摘要

- “重新生成”改为“修订自动化”，避免用户误解为创建新资产。
- 修改要求可空，但修订原因不可空。
- 空修改要求使用系统检测问题生成默认目标。
- 业务步骤映射优先确定性修复，AI 仅作为兜底。
- AI 必须在当前资产基础上最小修改。
- 所有修订在 staging 工作区完成并原子发布。
- 修订期间继续使用原资产 ID，列表只显示一行。
- generation run 和 execution run 是任务事实来源，任务中心不新增独立任务状态。
