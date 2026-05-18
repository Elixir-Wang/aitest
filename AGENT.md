# AI Testing System Agent Instructions

## 0. Highest Priority

The PRD is the source of truth.

When implementing this project, follow the documents under `docs/` strictly. Do not invent product scope, routes, components, data flow, layout structure, or interaction rules that are not supported by the PRD or by the existing frontend template.

If any instruction in this file conflicts with the PRD, follow the PRD and update this file if needed.

## 1. Mandatory References

Before coding, read the relevant PRD documents.

For frontend shell, navigation, page structure, and component rules, always read:

- `docs/01-总览索引/01-01-AI测试系统-PRD确认索引.md`
- `docs/05-前端方案/05-01-AI测试系统-前端总体方案PRD.md`
- `docs/05-前端方案/05-02-AI测试系统-导航与页面映射清单.md`

For module work, also read the matching PRD under:

- `docs/00-产品文档/`
- `docs/03-后端架构与数据/`
- `docs/05-前端方案/`

Do not start implementation from memory. Read the PRD first, then inspect the existing code.

## 2. Frontend Target Directory

The frontend implementation target is:

- `apps/frontend`

The template/reference project is:

- `next-shadcn-admin-dashboard-main`

The reference project must be treated as a source template and design/component reference. Do not directly modify `next-shadcn-admin-dashboard-main` unless the user explicitly asks to change the template itself.

If `apps/frontend` does not exist, create it by copying the required frontend template from `next-shadcn-admin-dashboard-main`, then perform all AI testing system changes inside `apps/frontend`.

## 3. Template Reuse Rules

The frontend must be based on the existing template's structure and visual language.

Required:

- Reuse the template's Next.js app structure.
- Reuse the template's dashboard shell, sidebar, header, theme system, user menu, and layout patterns.
- Reuse shadcn/ui components from the copied template.
- Reuse existing table, card, tabs, dialog, dropdown, badge, sidebar, form, empty-state, and layout patterns before creating anything new.
- Use Lucide Icons for navigation and action icons.
- Keep the UI as an operational admin workspace: restrained, dense enough, easy to scan, and consistent across modules.

Forbidden:

- Do not build a separate UI kit.
- Do not create a separate frontend app outside `apps/frontend`.
- Do not replace the copied dashboard shell with a custom shell.
- Do not create marketing-style pages for product workflows.
- Do not use screenshots, static mockups, or images as substitutes for real in-app UI.
- Do not handwrite custom SVG icons when Lucide Icons are available.
- Do not scatter one-off styles that make modules look unrelated.

## 4. No Guessing Policy

If a requirement is unclear, conflicting, or missing, do not invent a solution.

Required process:

1. Check the relevant PRD.
2. Inspect the copied frontend template and existing components.
3. If still unclear, search for the best current practice from official docs or GitHub examples.
4. Summarize the uncertainty and the selected approach before implementing.

Use GitHub or official documentation for uncertainty around:

- Next.js app router patterns.
- shadcn/ui component usage.
- TanStack Table implementation.
- React Hook Form + Zod integration.
- Tailwind CSS conventions.
- Playwright-related frontend integration.
- Project structure and migration strategy.

Do not silently choose a custom approach when a standard approach exists.

## 5. Navigation And Page Rules

Follow `docs/05-前端方案/05-02-AI测试系统-导航与页面映射清单.md`.

First-version left navigation:

- 工作台: 控制台 `/dashboard`, 任务中心 `/tasks`
- 项目工作区: 项目 `/projects`, 需求 `/projects/:projectId/requirements`, 探索 `/projects/:projectId/exploration`, 知识库 `/projects/:projectId/knowledge`
- 测试资产: 测试用例 `/projects/:projectId/test-cases`, UI 自动化 `/projects/:projectId/automation/ui`, 接口自动化 `/projects/:projectId/automation/api`, 报告中心 `/reports`
- 系统管理: 模型配置 `/settings/models`, 用户与权限 `/settings/users`, 系统设置 `/settings/system`

Rules:

- Left sidebar only contains high-frequency primary entries.
- Do not put second-level functions into persistent sidebar submenus.
- Second-level functions belong inside pages through tabs, segmented controls, card entries, local navigation, or breadcrumbs.
- Project-scoped pages must show project context.
- Project context is controlled by the project switcher, not by a sidebar project tree.
- API automation is `Soon` in version one. It must not expose create, generate, or run actions.

## 6. Layout And Component Rules

Follow `docs/05-前端方案/05-01-AI测试系统-前端总体方案PRD.md`.

Required shared structures:

- `ProjectSwitcher`
- `ModuleTabs`
- `StatusBadge`
- `TaskTimeline`
- `SourceReference`
- `MarkdownPreview`
- `MarkdownEditor`
- `VersionDiffViewer`
- `ConfirmRiskDialog`
- `EmptyState`
- `SoonPage`

Page patterns:

- List pages use `PageShell + PageHeader + PageToolbar + DataTable + Empty/Error/Loading state`.
- Detail pages use `DetailShell + SummaryStrip + PageTabs + MainContent + SidePanel`.
- Review/edit pages use `ReviewShell + left content + right diff/form/source + BottomActionBar`.
- Task/run pages use `RunShell + StatusSummary + TaskTimeline + OutputPanel + ActionPanel`.

Do not create visually different page shells for different modules.

## 7. Data And Mock Policy

Until backend APIs exist, frontend pages may use mock data only when necessary.

Rules:

- Mock data must match the PRD's future backend shape as closely as possible.
- Mock data must live in explicit local data files or clearly named constants.
- Do not scatter mock values through JSX.
- Use TypeScript types for mock records and component props.
- Status values shown to users must be Chinese, not raw backend enum names.
- Write actions without backend support must be disabled, simulated safely, or clearly marked as mock.
- Guest/read-only states should disable write actions rather than hiding the whole workflow.

## 8. Dependency And Architecture Policy

Do not add dependencies casually.

Before adding a dependency:

- Check whether the copied template already includes the needed package.
- Check whether shadcn/ui or existing template components solve the problem.
- If still needed, verify the package choice using official docs or GitHub examples.
- Explain why the dependency is required.

Do not change package manager, Next.js config, TypeScript config, Tailwind config, or build tooling unless required by the PRD or by a verified best practice.

## 9. Verification Requirements

Every frontend change must leave `apps/frontend` runnable.

After implementation:

1. Run the available checks from inside `apps/frontend`, usually:
   - `npm run lint`
   - `npm run build`
2. Start the local dev server when needed.
3. Open changed routes in a browser and verify:
   - the app loads,
   - routes are reachable,
   - the existing dashboard shell is used,
   - text does not overlap,
   - navigation remains usable,
   - no obvious console or runtime errors appear.

If checks or browser verification cannot be run, explain the exact reason.

Do not claim completion for a frontend task that cannot be opened in the app.

## 10. Implementation Order

For the first frontend phase:

1. Create `apps/frontend` from `next-shadcn-admin-dashboard-main`.
2. Confirm the copied app starts unchanged.
3. Align app name, metadata, and shell branding.
4. Replace sidebar navigation according to PRD.
5. Add project context and project switcher.
6. Add shared page structures and domain components.
7. Add skeleton pages for the PRD routes.
8. Fill module workflows incrementally from the matching PRDs.

Each step must keep `apps/frontend` runnable.

## 11. Git And Existing Changes

The worktree may contain user changes.

Do not revert user changes unless the user explicitly asks for it.

Before editing, inspect related files and fit new work into the current codebase. Keep changes scoped to the requested task.

Do not modify `next-shadcn-admin-dashboard-main` during product implementation unless the user explicitly requests template changes.

## 12. Final Response Requirements

When finishing a task, report:

- Files changed.
- PRD sections followed.
- Verification commands run and results.
- Browser routes checked.
- Any unresolved uncertainty or dependency on user confirmation.
