# 硅基员工动态办公室实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `/agents` 的内联 SVG 办公室替换为可交互的 PixiJS + Spine 协作办公室，使用确认背景、四部门工作岛、CEO 视觉占位和 13 个可区分角色。

**Architecture:** React 组件负责生命周期、DOM 可访问性按钮和详情抽屉回调；单个 `OfficeScene` 负责背景、工位、部门装饰、CEO 和 Spine 人物。员工业务状态保持现有模型，人物随机动作与睡眠属于独立表现状态；现有 9 套 Spine 皮肤通过稳定角色清单、岗位配饰、色彩和动作预设扩展为 13 个可区分角色，并为未来设计师资产保留同一接口。

**Tech Stack:** Next.js 16、React 19、TypeScript、PixiJS 8、Spine Pixi v8、CSS Modules、Node test runner。

## Global Constraints

- 背景源为 `apps/backend/gj_bg.webp`，浏览器只加载前端静态副本。
- 不修改 `/agents/employees` 或运行任务 API。
- CEO 使用稳定标识 `office-ceo`，当前不绑定后端、不参与统计、不提供伪交互。
- 保留员工点击详情、状态语义和轮询。
- 视觉睡眠不修改 `Agent.state`。
- 不引入新的动画框架、全局状态或轮询。
- 不修改用户现有数据库和需求目录改动。
- 不创建 Git 提交，除非用户明确要求。

---

### Task 1: 部门布局与角色清单

**Files:**
- Create: `apps/frontend/src/scene/characters/character-manifest.ts`
- Modify: `apps/frontend/src/scene/layout/officeLayout.ts`
- Modify: `apps/frontend/src/components/ai-testing/silicon-office/agent-roster.ts`
- Test: `apps/frontend/tests/silicon-office-motion-contract.test.mjs`

**Interfaces:**
- Produces: `getCharacterProfile(agentId)`, `CEO_CHARACTER_PROFILE`, `buildDepartmentOfficeLayout(employees)`。
- Consumes: `SiliconEmployee`, `Agent`, `Desk`。

- [ ] 增加失败测试，验证四个部门、稳定岛内排序、未知部门 fallback 和 CEO 稳定标识。
- [ ] 运行 `node --test tests/silicon-office-motion-contract.test.mjs`，确认新增断言先失败。
- [ ] 创建 13 个角色配置，包含 Spine 皮肤、岗位标签、配饰类型、强调色、默认朝向和动作偏好。
- [ ] 增加部门工作岛坐标和员工座位映射，保持现有 `Agent`/`Desk` 接口。
- [ ] 更新 `buildOfficeAgents` 使用部门布局，不改变后端员工结构。
- [ ] 再次运行目标测试，确认布局和清单断言通过。

### Task 2: 背景与场景装饰

**Files:**
- Create: `apps/frontend/public/assets/office/silicon-office-bg.webp`
- Modify: `apps/frontend/src/scene/assets/loadOfficeAssets.ts`
- Modify: `apps/frontend/src/scene/OfficeScene.ts`
- Modify: `apps/frontend/src/scene/entities/DeskEntity.ts`
- Test: `apps/frontend/tests/silicon-office-motion-contract.test.mjs`

**Interfaces:**
- Consumes: `buildDepartmentOfficeLayout` 生成的固定场景坐标。
- Produces: 背景 Sprite、部门铭牌、协作光轨、CEO 总裁台和固定视觉位置。

- [ ] 增加失败测试，要求背景 URL 指向 `silicon-office-bg.webp`，场景包含四部门与 CEO。
- [ ] 运行目标测试，确认背景和 CEO 断言失败。
- [ ] 将确认的二进制背景复制到前端静态资源目录。
- [ ] 更新办公室资源加载器，加载新背景并保持桌椅失败降级。
- [ ] 在 `OfficeScene` 中绘制四部门工作岛、低对比协作链路和中心 CEO 总裁台。
- [ ] 确保 CEO 不进入 `agents`、员工统计或点击回调。
- [ ] 运行目标测试，确认场景结构断言通过。

### Task 3: Spine 人物差异与表现状态

**Files:**
- Modify: `apps/frontend/src/scene/characters/SpineCharacter.ts`
- Modify: `apps/frontend/src/scene/entities/AgentEntity.ts`
- Modify: `apps/frontend/src/scene/systems/AnimationSystem.ts`
- Test: `apps/frontend/tests/silicon-office-motion-contract.test.mjs`

**Interfaces:**
- Consumes: `CharacterProfile`。
- Produces: 精确皮肤选择、岗位配饰、头部/面部低频动作、休息/睡眠表现和业务状态打断。

- [ ] 增加失败测试，验证角色清单驱动皮肤和配饰，睡眠表现不写入 `Agent.state`。
- [ ] 运行目标测试，确认人物表现断言失败。
- [ ] 让 `SpineCharacter` 接收角色配置并优先使用清单皮肤，缺失时回退到稳定哈希皮肤。
- [ ] 在 `AgentEntity` 增加轻量岗位配饰/识别图形，确保重复 Spine 皮肤仍可区分。
- [ ] 在 `AnimationSystem` 增加基于员工 ID 的稳定随机节奏，调度眨眼、头部姿态和空闲休息。
- [ ] 业务状态变为 active 或用户点击时立即结束休息表现。
- [ ] 在减少动态效果下关闭随机表现动作。
- [ ] 运行目标测试，确认人物状态断言通过。

### Task 4: React 场景接入与无障碍

**Files:**
- Modify: `apps/frontend/src/components/ai-testing/silicon-office/office-canvas.tsx`
- Modify: `apps/frontend/src/components/ai-testing/silicon-office/office-canvas.module.css`
- Test: `apps/frontend/tests/silicon-office-motion-contract.test.mjs`

**Interfaces:**
- Consumes: `agents`, `onAgentSelect`, `OfficeScene.init/updateAgents/resize/destroy`。
- Produces: 单个 Pixi Canvas、ResizeObserver 生命周期和透明 DOM 员工按钮层。

- [ ] 增加失败测试，验证 React 组件实例化/销毁 `OfficeScene`、更新员工和保留可访问性按钮。
- [ ] 运行目标测试，确认 React 接入断言失败。
- [ ] 用场景挂载容器替换内联 SVG 人物和桌面实现。
- [ ] 使用 `ResizeObserver` 驱动 `scene.resize`，卸载时销毁场景。
- [ ] 保留 DOM 员工按钮层，按钮包含姓名、状态和当前任务，并触发现有详情抽屉。
- [ ] 增加加载和资源降级样式，宽/中/窄屏保持完整办公室可见。
- [ ] 运行目标测试，确认 React 生命周期与无障碍断言通过。

### Task 5: 验证与视觉检查

**Files:**
- Modify if required: 上述相关文件
- Test: `apps/frontend/tests/silicon-office-motion-contract.test.mjs`

**Interfaces:**
- Produces: 可构建、可交互、视觉符合 spec 的动态办公室。

- [ ] 运行 `node --test tests/silicon-office-motion-contract.test.mjs`。
- [ ] 运行 `npx biome check` 覆盖所有修改的 TypeScript、TSX 和 CSS 文件。
- [ ] 运行 `npx tsc --noEmit`。
- [ ] 启动前端并使用 Browser 打开 `/agents`，检查背景、CEO、四部门、人物点击和响应式。
- [ ] 检查浏览器控制台无新增错误。
- [ ] 运行 `git diff --check` 并确认只修改计划范围文件。
