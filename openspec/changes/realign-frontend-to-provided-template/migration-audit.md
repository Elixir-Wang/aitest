## 迁移盘点

### 当前错误简化版 `apps/frontend`

保留为迁移素材：

- `src/lib/api.ts`：统一 API envelope、错误和登录失效处理思路。
- `src/components/project-switcher.tsx`：项目切换器领域行为。
- `src/components/available-actions.tsx`：available_actions 展示行为。
- `src/app/(main)/**/page.tsx`：第一阶段页面信息架构和中文文案。
- `tests/test_frontend_contracts.py`：轻量契约检查思路。

废弃：

- `src/app/login/page.tsx`：独立登录页，不符合模板内置登录复用要求。
- `src/app/(main)/layout.tsx`：简化版手写 shell。
- `src/app/globals.css`、`src/components/ui.tsx`：手写卡片/按钮/标签风格。
- `package.json`、`package-lock.json`、`next.config.mjs`、`tsconfig.json`：Next 14 / React 18 简化工程配置。
- `.next`、`node_modules`、`tests/__pycache__`：生成物，不迁移。

### 模板 `next-shadcn-admin-dashboard-main`

关键技术栈：

- Next.js 16.2.6
- React 19.2.6
- Tailwind CSS 4.1.5
- shadcn 4.7.0
- Lucide React 1.14.0
- React Hook Form 7.75.0
- Zod 4.4.3
- TanStack Table 8.21.3
- Zustand 5.0.13
- Biome 2.4.15

关键路径：

- 内置登录表单：`src/app/(main)/auth/_components/login-form.tsx`
- 登录页：`src/app/(main)/auth/v1/login/page.tsx`、`src/app/(main)/auth/v2/login/page.tsx`
- 注册页：`src/app/(main)/auth/v1/register/page.tsx`、`src/app/(main)/auth/v2/register/page.tsx`
- Dashboard shell：`src/app/(main)/dashboard/layout.tsx`
- Sidebar：`src/app/(main)/dashboard/_components/sidebar/app-sidebar.tsx`
- 导航配置：`src/navigation/sidebar/sidebar-items.ts`
- UI 组件：`src/components/ui/*`
- 偏好设置 store：`src/stores/preferences/*`
- 工具函数：`src/lib/*`

### 本机与后端验证

- Node.js：`v24.15.0`
- npm：`11.12.1`
- Node/npm 满足模板 Next.js 16 / React 19 的运行前提。
- 后端 API base URL：`http://localhost:8000/api/v1`
- 已确认：
  - `POST /api/v1/auth/login` 可用，默认管理员登录成功。
  - `GET /api/v1/auth/me` 携带 token 可返回 admin。
  - `GET /api/v1/projects` 携带 token 可返回统一响应和 trace_id。
  - 未授权响应返回统一错误结构。
