# 手工测试用例 AI 生成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有手工新建测试用例表单中增加基于用户描述和项目探索产物的单条测试用例 AI 生成能力。

**Architecture:** 新增一个单条手工测试用例 Agent，复用现有模型选择、`SkillMiddleware` 和结构化输出机制。后端通过独立的探索上下文构建模块读取当前项目页面 YAML 与 `operations.yaml`，完成脱敏、相关性排序和限额后交给 Agent；前端只负责输入、覆盖确认和结果填充。

**Tech Stack:** FastAPI、Pydantic v2、LangChain structured output、Next.js/React/TypeScript、现有 `apiRequest` 和契约测试。

## Global Constraints

- AI 生成仅在 `新建测试用例` 模式可用。
- 关联探索产物时使用当前项目全部可用产物，不增加逐个产物选择器。
- AI 生成接口只返回预览，不创建数据库记录。
- 备注字段不由 AI 生成，也不被覆盖。
- 空目标表单直接应用；非空目标表单必须确认覆盖。
- 用户在 AI 请求期间新增的内容不得被静默覆盖。
- 探索产物解析失败时尽可能降级，不因单个坏产物导致整体生成失败。
- 不改变现有测试用例集生成流程。
- 不引入新的依赖或数据库表。

---

### Task 1: 定义后端单条生成契约与失败测试

**Files:**
- Create: `apps/backend/app/agents/manual_test_case_generation/__init__.py`
- Create: `apps/backend/app/agents/manual_test_case_generation/schemas.py`
- Create: `apps/backend/app/services/manual_test_case_generation/__init__.py`
- Create: `apps/backend/app/services/manual_test_case_generation/exploration_context_builder.py`
- Create: `apps/backend/app/services/manual_test_case_generation/service.py`
- Modify: `apps/backend/app/schemas/test_case.py`
- Modify: `apps/backend/app/api/v1/test_cases.py`
- Test: `apps/backend/tests/test_manual_test_case_ai_generation.py`

**Interfaces:**
- Produces `ManualTestCaseAiGenerateIn`, `ManualTestCaseAiGenerateOut`。
- Produces `ManualTestCaseGenerationResult` and `ManualTestCaseGenerationStep`。
- Produces `build_exploration_context(actor, project_id, description, include_exploration_artifacts)`。
- Produces `generate_manual_test_case_preview(actor, project_id, payload)`。

- [ ] **Step 1: Write failing schema and service tests**

覆盖：空描述校验、步骤必须有动作和预期、探索关闭时不读取产物、无产物降级、接口不落库、Agent 结构化结果映射。

- [ ] **Step 2: Run focused tests and verify failure**

Run: `rtk pytest -q tests/test_manual_test_case_ai_generation.py` from `apps/backend`。

Expected: FAIL because the new modules, models and route do not exist。

- [ ] **Step 3: Implement the minimal Pydantic contracts**

新增单条用例输入、输出、探索页面/元素/操作上下文模型，并保持与现有 `ApiManualTestCaseCreate` 的字段映射兼容。

- [ ] **Step 4: Add route and service seams**

新增 `POST /projects/{project_id}/test-cases/ai-generate`，接口层只做权限、参数和错误映射；生成服务暂时使用可替换的上下文构建器和 Agent 调用 seam。

- [ ] **Step 5: Run focused tests and verify contract behavior**

Run: `rtk pytest -q tests/test_manual_test_case_ai_generation.py`。

Expected: schema、路由契约和服务边界测试通过，尚未覆盖真实探索解析细节。

### Task 2: 实现探索产物上下文构建

**Files:**
- Modify: `apps/backend/app/services/manual_test_case_generation/exploration_context_builder.py`
- Modify: `apps/backend/app/services/page_exploration/service.py` only if an existing public helper cannot satisfy the seam
- Test: `apps/backend/tests/test_manual_test_case_exploration_context.py`

**Interfaces:**
- Consumes existing project page YAML and `page_exploration/operations.yaml` storage。
- Produces normalized `ExplorationContext` with pages, operations, warnings and truncation metadata。

- [ ] **Step 1: Write failing context builder tests**

使用临时项目存储验证页面字段提取、操作字段提取、去重、相关性排序、限额裁剪和损坏文件降级。

- [ ] **Step 2: Run context tests and verify failure**

Run: `rtk pytest -q tests/test_manual_test_case_exploration_context.py` from `apps/backend`。

- [ ] **Step 3: Implement page and operation normalization**

优先复用现有 `page_exploration_service.list_project_pages`、`get_project_page_yaml_content` 以及当前 replay models/存储约定；不在路由层复制文件路径逻辑。

- [ ] **Step 4: Implement deterministic ranking, dedupe and limits**

使用用户描述关键词对页面、元素和操作评分；保留所有页面摘要，优先保留相关详情；达到字符或对象限额时按对象粒度裁剪。

- [ ] **Step 5: Implement sensitive-value redaction**

对密码、Token、Authorization、Cookie 和常见 Secret 字段脱敏；确保脱敏发生在 Agent Prompt 组装之前。

- [ ] **Step 6: Run context tests and verify pass**

Run: `rtk pytest -q tests/test_manual_test_case_exploration_context.py`。

### Task 3: 实现单条测试用例 Agent

**Files:**
- Create: `apps/backend/app/agents/manual_test_case_generation/agent.py`
- Create: `apps/backend/app/agents/manual_test_case_generation/service.py`
- Create: `apps/backend/app/agents/manual_test_case_generation/skills/manual-test-case-generation/SKILL.md`
- Create: `apps/backend/app/agents/manual_test_case_generation/skills/manual-test-case-generation/references/manual-case-format.md`
- Create: `apps/backend/app/agents/manual_test_case_generation/skills/manual-test-case-generation/references/exploration-context-rules.md`
- Test: `apps/backend/tests/test_manual_test_case_generation_agent.py`

**Interfaces:**
- Consumes `ManualTestCaseGenerationInput`。
- Produces `ManualTestCaseGenerationResult`。
- Reuses `resolve_model_selection`, `build_agent_model`, `thinking_disabled_extra_body`, `SkillMiddleware` and `ToolStrategy`。

- [ ] **Step 1: Write failing Agent tests**

使用 fake chat model 验证结构化输出类型、Prompt 包含用户描述和探索上下文、没有探索上下文时不出现空上下文块。

- [ ] **Step 2: Run Agent tests and verify failure**

Run: `rtk pytest -q tests/test_manual_test_case_generation_agent.py`。

- [ ] **Step 3: Implement Agent schema and factory**

单 Agent、无工具、SkillMiddleware 动态加载、`ToolStrategy(ManualTestCaseGenerationResult)`。

- [ ] **Step 4: Implement Prompt assembly and result parsing**

固定输出标题、前置条件、步骤及步骤预期；将模型输出校验为非空结构化结果；将生成说明限制为事实依据和推断说明。

- [ ] **Step 5: Integrate Agent into preview service**

服务流程为项目校验 → 上下文构建 → Agent 调用 → 结果校验 → 合并 warnings/source summary → 返回预览；不写数据库。

- [ ] **Step 6: Run Agent and service tests**

Run: `rtk pytest -q tests/test_manual_test_case_generation_agent.py tests/test_manual_test_case_ai_generation.py`。

### Task 4: 接入前端 API 类型与 AI 生成交互

**Files:**
- Modify: `apps/frontend/src/lib/api-client.ts`
- Modify: `apps/frontend/src/app/(main)/test-cases/page.tsx`
- Modify: `apps/frontend/tests/test-case-set-dialog-contract.test.mjs`
- Test: `apps/frontend/tests/manual-test-case-ai-generation-contract.test.mjs`

**Interfaces:**
- Consumes `POST /projects/{project_id}/test-cases/ai-generate`。
- Produces existing `ManualTestCaseForm` field values and generated step IDs。

- [ ] **Step 1: Write failing frontend contract tests**

覆盖 AI 按钮位置、仅 case 模式展示、关联开关默认开启、请求字段、空表单直接应用、非空表单确认覆盖、备注保留和请求期间编辑检测。

- [ ] **Step 2: Run focused frontend tests and verify failure**

Run: `node --test tests/manual-test-case-ai-generation-contract.test.mjs` from `apps/frontend`。

- [ ] **Step 3: Add API client types**

新增请求和响应类型，保持 `ApiManualTestCaseCreate` 不变；使用现有 `apiRequest` 调用接口。

- [ ] **Step 4: Add form state and AI input dialog**

在创建方式卡片右侧加入 `AI 生成`，增加描述输入、关联探索产物开关、生成中状态和待应用结果状态。

- [ ] **Step 5: Implement conditional apply/overwrite flow**

生成成功后基于当前表单检查目标字段；空表单直接应用，非空表单弹出覆盖确认；取消时保留原表单和待应用结果；应用时重新生成步骤 ID，备注不改。

- [ ] **Step 6: Run focused frontend tests**

Run: `node --test tests/manual-test-case-ai-generation-contract.test.mjs tests/test-case-set-dialog-contract.test.mjs`。

### Task 5: 集成验证与回归检查

**Files:**
- Modify only files required by failing tests from Tasks 1-4。
- Test: existing backend and frontend test suites。

- [ ] **Step 1: Run backend focused suite**

Run: `rtk pytest -q tests/test_manual_test_case_ai_generation.py tests/test_manual_test_case_exploration_context.py tests/test_manual_test_case_generation_agent.py`。

- [ ] **Step 2: Run frontend focused suite**

Run: `node --test tests/manual-test-case-ai-generation-contract.test.mjs tests/test-case-set-dialog-contract.test.mjs`。

- [ ] **Step 3: Run type/lint checks for touched frontend files**

Run: `pnpm exec biome check src/app/(main)/test-cases/page.tsx src/lib/api-client.ts tests/manual-test-case-ai-generation-contract.test.mjs tests/test-case-set-dialog-contract.test.mjs` from `apps/frontend`。

- [ ] **Step 4: Run relevant existing backend regression tests**

Run: `rtk pytest -q tests/test_test_case_set_service.py tests/test_test_case_generation_agent.py` from `apps/backend`。

- [ ] **Step 5: Inspect final diff and verify no unrelated files changed**

Use `rtk git diff --stat` and `rtk git status --short` with the known dirty-worktree baseline; do not revert unrelated user changes。

