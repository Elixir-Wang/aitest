# 自主探索与目标探索分离及产物增量合并 Spec

## 1. 背景

页面探索包含两种完全不同的业务：

1. 自主探索：页面此前没有探索产物，需要首次建立页面知识库，完整记录页面结构、元素、可执行操作、状态变化、阻塞点和可复用定位器，并生成基线产物。
2. 目标探索：页面已有探索产物，开发新增了功能，需要围绕新增功能进行定向探索，将新增事实、元素、状态和交互增量合并到既有产物的合适位置。

两种模式不能共享任务规划、状态管理、终止判定和产物写入逻辑。两者只共享底层浏览器操作和存储基础设施。

## 2. 目标

### 2.1 自主探索

- 以目标页面为边界完成首次页面建档。
- 发现页面主要区域、导航入口、按钮、链接、Tab、菜单、弹窗、抽屉、表单控件和列表操作。
- 对安全交互进行点击、填写、展开、切换等操作并验证结果。
- 记录元素语义、定位器、动作、前后状态和执行结果。
- 生成完整的机器可读产物和人类可读页面文档。
- 对所有元素执行真实交互，并记录执行前后状态、结果和清理结果。

### 2.2 目标探索

- 读取既有页面产物和状态树。
- 围绕用户指定的新增功能或变化点进行定向探索。
- 只访问完成目标所需的页面状态、弹窗、菜单和流程。
- 将新增或变更的元素、状态、交互和定位器增量合并到既有产物。
- 保留既有产物中未受影响的内容、顺序和引用关系。
- 对无法确认的冲突保留证据并标记人工确认，禁止静默覆盖。

## 3. 非目标

- 不通过一个 Prompt 同时兼容两套探索逻辑。
- 不让目标探索重新执行完整页面盘点。
- 不让自主探索因为一个粗粒度 todo 完成而提前结束。
- 页面内所有元素都属于自主探索的可执行范围，包括删除、清空、重置、发布、授权、退出登录、提交类按钮以及敏感字段。
- 执行前由编排器生成隔离测试数据；执行后必须重新 snap，记录成功、失败、确认弹窗、页面跳转、数据变化或阻塞结果。
- 需要创建、编辑或发布测试条目时，必须在流程结束阶段删除或清理本次探索产生的测试数据。
- 不自动合并无法确认归属的元素。
- 不使用 Agent 自己输出的“已完成”作为唯一业务完成判定。

## 4. 模式契约

任务创建时必须明确传入 exploration_mode：autonomous 或 goal。

### 4.1 autonomous

- start_url 必填。
- scope 必填，用于定义首次建档边界。
- goal 可选，只作为关注点，不能缩小为单一路径目标。
- 不依赖 base_artifact_id。
- 目标对象是“目标页面 + 页面内可探索状态 + 页面内交互元素覆盖”。

默认规则：

- 锁定目标页面及其页面内弹层、菜单、抽屉和 Tab 状态。
- 不因为左侧导航存在就扩展到其他模块。
- 页面内跳转到其他路由时记录为页面出口；是否继续由 scope 决定。
- 必须先建立元素清单，再执行安全交互。
- 必须记录所有已发现元素，包括操作按钮、敏感字段和当前不可执行控件。
- 所有可执行元素必须进入执行队列并完成真实交互验证。

### 4.2 goal

- start_url 必填。
- goal 必填，描述新增功能或变化点。
- base_artifact_id 必填，或由页面身份自动解析。
- scope 可选，用于限制增量探索范围。
- 目标对象是“新增功能对应的目标路径、页面状态、元素和产物增量”。

默认规则：

- 先读取基线产物，识别已有页面、区域、元素和状态。
- 以用户目标为唯一主线，不做全量页面盘点。
- 只执行目标所需动作，不遍历无关按钮和列表。
- 每个新增事实必须关联到一个既有页面或明确的新页面。
- 完成后生成增量补丁，通过合并器写入基线产物。

## 5. 总体架构

ExplorationService
  ├─ AutonomousRunOrchestrator
  │   ├─ AutonomousExplorerAgent
  │   ├─ CoverageState
  │   ├─ CoverageCompletionEvaluator
  │   └─ FullArtifactWriter
  └─ GoalRunOrchestrator
      ├─ GoalExplorerAgent
      ├─ GoalState
      ├─ GoalCompletionEvaluator
      ├─ DeltaArtifactWriter
      └─ ArtifactMergeService

两条链路只共享：Playwright 观察和动作工具、locator 校验、URL 与页面身份归一化、事件持久化、测试数据和产物存储基础设施。

Agent 只能返回当前轮的结构化决策。编排器负责执行动作、维护状态、校验范围、判断完成和提交产物。

## 6. 自主探索流程

1. 创建 autonomous run。
2. 初始化目标页面身份和探索范围。
3. 访问页面并执行基线 snap。
4. 识别页面区域和全部可交互元素。
5. 建立 CoverageState 和 pending 队列。
6. 选择一个 pending 元素或页面状态。
7. 选择下一个元素并直接执行动作。
8. 重新 snap，验证前后变化。
9. 记录 InteractionFact。
10. 发现新状态、新元素和新入口。
11. 回到可复现状态，继续处理 pending 队列。
12. 覆盖完成后生成完整基线产物。

自主探索元素状态：discovered、pending、executing、verified、blocked、failed、skipped_out_of_scope、not_unique、not_visible。

所有元素默认进入 discovered/pending 并实际执行；只有工具失败、元素不可见、定位器不唯一、页面权限或环境阻塞时，才允许进入对应异常状态。

自主探索完成必须满足：

- pending_element_count 等于 0；
- pending_state_count 等于 0；
- unexplained_interaction_count 等于 0；
- 完整页面产物已写入。

达到预算但仍有 pending 项时，状态必须是 partial，不能是 completed。

所有元素必须实际执行并完成结果验证后才能进入 verified；仅发现元素、采集快照或打开页面不算完成交互探索。

## 7. 目标探索流程

1. 创建 goal run。
2. 加载 base_artifact_id 对应的基线产物。
3. 解析目标为可验证子步骤。
4. 定位目标页面和已有合并锚点。
5. 执行新增功能流程。
6. 每轮 snap 验证目标完成判据。
7. 生成 DeltaArtifact。
8. 校验增量归属、重复项和冲突。
9. 合并到基线产物，写入新的 artifact version。
10. 输出合并摘要。

目标探索完成必须满足：

- 所有目标子步骤已完成或被明确阻塞；
- 每个 completed 子步骤都有 evidence ref；
- 所有增量事实都关联到页面或明确的新页面；
- DeltaArtifact 已生成；
- 合并校验成功；
- 新产物版本已成功写入。

若合并存在冲突，状态必须是 partial 或 blocked，不能直接 completed。

## 8. 产物模型

页面产物至少包含：

- artifact_id 和 artifact_version；
- page_id、canonical_path、title、identity_key；
- 页面区域和元素；
- 页面状态树；
- 交互记录；
- blockers 和清理结果；
- merge_history；
- source_run_id、last_full_exploration_at、last_incremental_exploration_at。

元素事实至少包含：

- element_id；
- stable_key；
- role、name、label、semantic_context；
- locators；
- visible、enabled；
- source run_id、exploration_mode、evidence_refs；
- lifecycle。

元素、状态和交互事实生命周期：added、existing、updated、deprecated、conflicted、blocked。

目标探索不得删除既有事实。确认原事实失效时，先写入 deprecated，再写入新的 added 或 updated 事实，并保留证据。

## 9. 增量合并规则

### 9.1 合并锚点顺序

1. 稳定 page_id。
2. identity_key。
3. 规范化路径和页面标题。
4. 稳定 region_id。
5. 元素 stable_key。
6. 已验证的语义上下文和邻近元素关系。

无法找到稳定锚点时，不得自动合并到猜测位置，必须标记 conflicted。

### 9.2 新元素

只有同时满足以下条件才可新增：

- 不存在相同 stable_key；
- 元素属于已确认页面和区域；
- locator 通过唯一性和可见性校验；
- 存在事件或状态证据。

### 9.3 已有元素更新

只有以下变化可以更新基线：

- label、name 或可见文案变化；
- locator 变化且新 locator 已验证；
- enabled 或 visible 变化；
- 所属区域变化且有明确证据；
- 新增动作或状态关系。

未经证据确认的字段不得覆盖既有值。

### 9.4 全元素真实执行和测试数据清理

自主探索不区分危险元素，不写入风险等级、危险标记、跳过原因或等待授权状态。页面内所有可执行元素都必须按真实页面流程执行。

执行要求：

1. 记录元素的 role、name、label、上下文、定位器、可见性和可用性。
2. 对输入字段使用本轮生成的测试数据，禁止把真实业务数据当作测试输入。
3. 对创建、编辑、保存、提交、发布、删除、清空、重置、授权和退出登录等操作直接执行。
4. 执行前保存页面状态和本轮生成的测试数据；执行后重新 snap，记录页面跳转、Toast、数据变化、错误或阻塞原因。
5. 如果本轮创建了条目、Agent、资源或其他业务数据，必须记录其唯一标识，并在探索结束阶段执行删除或清理。
6. 清理动作本身也必须执行、验证并记录；清理失败时，run 结果必须明确展示未清理数据。

对于敏感字段：

- 记录字段类型、label、placeholder、必填状态、校验规则和定位器。
- 使用合成测试值并在事件中标记 data_source=test。
- 产物不得保存真实密码、Token、身份证号或密钥，只保存字段元数据、测试值类型和脱敏结果。

### 9.5 重复和冲突

相同页面、区域、role/name 和 stable_key 的事实视为重复，不生成重复节点；重复记录进入 merge_history。

以下情况视为冲突：

- 相同 stable_key 对应不同页面；
- 同一元素出现互相矛盾的 locator；
- 页面身份无法唯一匹配；
- 新旧状态关系无法判断；
- 证据不足以确认变更。

冲突处理：保留基线事实、保留增量事实、写入 evidence_refs、产物标记 partial/conflicted、提示人工确认。禁止静默覆盖。

## 10. Agent 与编排器职责

Agent 负责：

- 解释页面语义；
- 选择当前轮候选动作；
- 判断元素是否与当前目标相关；
- 归纳动作结果；
- 提供合并锚点建议。

编排器负责：

- 模式隔离；
- 页面范围控制；
- 动作执行；
- 测试数据生成、生命周期管理和清理；
- 元素和状态去重；
- 覆盖队列或目标子步骤管理；
- 完成判定；
- 产物写入、增量合并和冲突处理；
- run 最终状态。

Agent 不得直接标记自主探索完成、覆盖基线产物、删除既有元素或构造未经快照验证的定位器。

## 11. 代码落点

现有目标探索相关 Prompt、page-explorer skill、subgoals.yaml 和目标完成逻辑继续服务于 goal 模式，但 autonomous 模式不得加载它们。

建议新增：

- apps/backend/app/agents/page_exploration/autonomous_agent.py
- apps/backend/app/agents/page_exploration/prompts/autonomous_system_prompt.py
- apps/backend/app/agents/page_exploration/skills/autonomous-explorer/SKILL.md
- apps/backend/app/agents/page_exploration/state/coverage_state.py
- apps/backend/app/agents/page_exploration/services/autonomous_orchestrator.py
- apps/backend/app/agents/page_exploration/services/coverage_completion.py
- apps/backend/app/agents/page_exploration/services/coverage_artifact_writer.py
- apps/backend/app/services/page_exploration/delta_artifact.py
- apps/backend/app/services/page_exploration/artifact_merge_service.py
- apps/backend/app/services/page_exploration/artifact_conflict_service.py
- apps/backend/app/services/page_exploration/artifact_identity.py

Runner 必须显式分流：

if exploration_mode == autonomous：调用 AutonomousRunOrchestrator。
if exploration_mode == goal：调用 GoalRunOrchestrator。
不允许仅通过同一个 Agent 工厂增加 mode 参数来复用全部逻辑。

## 12. 状态和停止原因

通用 run 状态：queued、running、completed、partial、blocked、failed、cancelled。

自主探索停止原因：coverage_complete、budget_exhausted、page_scope_exhausted、all_remaining_actions_dangerous、blocked_by_auth、blocked_by_permission、blocked_by_locator、manual_cancelled、technical_failure。

目标探索停止原因：goal_complete、goal_blocked、merge_complete、merge_conflict、budget_exhausted、scope_exhausted、manual_cancelled、technical_failure。

## 13. 报告要求

自主探索报告必须包含：页面身份、探索范围、区域清单、元素总数、已验证数量、阻塞数量、未覆盖数量、状态树、交互记录、定位器、产物路径、测试数据清理结果、停止原因和覆盖率。

目标探索报告必须包含：基线产物版本、用户目标、已完成子步骤和证据、新增元素、变更元素、新增状态和交互、合并位置、重复项、冲突项、新产物版本和停止原因。

## 14. 验收标准

### 14.1 自主探索

1. 对没有基线产物的工作台执行 autonomous，生成完整页面产物。
2. 工作台页面内的按钮、Tab、菜单、弹窗、表单控件和安全操作进入元素清单。
3. 每个安全元素都有执行或明确失败记录。
4. 所有元素都必须实际执行并记录结果。
5. 本轮创建的条目必须在探索结束前删除，并验证删除成功。
6. 敏感字段使用合成测试数据执行填写和校验，产物只保留脱敏结果。
6. 仅点击其他左侧导航不能计入工作台页面功能覆盖。
7. 存在 pending 元素时不能 completed。
8. 达到预算时必须 partial。

### 14.2 目标探索

1. 对已有工作台产物执行新增功能探索，只访问新增功能相关路径。
2. 新增按钮、弹窗、字段和状态合并到既有页面正确区域。
3. 既有无关元素保持不变。
4. 重复运行不生成重复元素或重复页面。
5. 无法确认合并位置时生成冲突，不静默写入。
6. 每个新增事实都有事件证据。
7. 合并成功后产生新的 artifact version，并保留 merge history。

### 14.3 模式隔离

1. autonomous 不加载 goal 的 subgoal 完成终止规则。
2. goal 不执行全量页面覆盖循环。
3. autonomous 不依赖 subgoals.yaml 判定完成。
4. goal 不要求页面所有元素都被点击。
5. 两种模式的报告字段、停止原因和产物效果不同。

## 15. 实施阶段

### 阶段一：模式隔离与止血
- 增加明确的 exploration_mode 分流。
- 拆分两个 Agent 工厂和两个 system prompt。
- 禁止 autonomous 使用 goal 的 todo 终止规则。
- 禁止 goal 进入 autonomous 覆盖循环。
- 增加模式隔离测试。

### 阶段二：自主探索覆盖状态
- 实现 CoverageState。
- 实现元素 pending 队列和页面状态队列。
- 实现自主探索确定性完成判定。
- 增加覆盖率和未覆盖项报告。

### 阶段三：目标增量产物
- 实现 DeltaArtifact。
- 实现页面身份和区域锚点。
- 实现新增、更新、重复和冲突处理。
- 实现新 artifact version 和 merge history。

### 阶段四：前端和回归验证
- 展示自主探索覆盖率。
- 展示目标探索的增量和合并位置。
- 展示冲突和人工确认项。
- 完成首次自主探索与新增功能目标探索的端到端测试。

## 16. 最终原则

自主探索 = 首次页面建档 + 页面功能覆盖 + 生成完整基线产物。
目标探索 = 已有产物上的新增功能探索 + 证据化增量合并。

自主探索不能依赖目标探索的完成逻辑。目标探索不能退化成自主探索的全量重跑。Agent 负责观察和建议，编排器负责边界、状态、完成和写入。任何产物覆盖都必须有证据，任何不确定合并都必须显式冲突。