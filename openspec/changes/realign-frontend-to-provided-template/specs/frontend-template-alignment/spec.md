## ADDED Requirements

### Requirement: 模板基线
AI 测试系统前端 SHALL 以 `next-shadcn-admin-dashboard-main` 作为 `apps/frontend` 的工程基线，并 MUST 保留模板的核心技术栈、目录结构、布局系统和组件体系。

#### Scenario: 使用模板技术栈
- **WHEN** 开发者查看 `apps/frontend/package.json`
- **THEN** 系统使用模板一致的 Next.js、React、Tailwind CSS v4、shadcn/ui、Lucide、React Hook Form、Zod、TanStack Table、Zustand 和 Biome 依赖与脚本

#### Scenario: 保留模板目录结构
- **WHEN** 开发者查看 `apps/frontend/src`
- **THEN** 系统保留模板的 App Router、`components/ui`、`config`、`hooks`、`lib`、`navigation`、`stores`、`styles` 和共置式 route `_components` 结构

#### Scenario: 不以简化壳层继续开发
- **WHEN** 实施本变更
- **THEN** 系统不得继续使用上一轮简化版 `apps/frontend` 的手写 layout、手写全局卡片样式和独立 `/login` 页面作为主实现

### Requirement: 内置登录复用
AI 测试系统前端 SHALL 复用模板内置登录模块，并 MUST 将其登录表单接入后端 `/api/v1/auth/login`。

#### Scenario: 登录表单对接后端
- **WHEN** 用户在模板登录页输入用户名或邮箱和密码并提交
- **THEN** 前端调用 `POST /api/v1/auth/login`，处理 `{ data, trace_id }` 成功响应，并在成功后进入 AI 测试系统业务首页

#### Scenario: 登录失败展示
- **WHEN** 后端返回统一错误响应
- **THEN** 登录页展示后端 `error.message` 中的中文错误文案，并保留 trace_id 用于排查

#### Scenario: 禁止公开注册
- **WHEN** 用户访问模板注册入口或注册页面
- **THEN** 系统不得提供公开注册能力，并展示管理员创建账号的提示或重定向到登录页

### Requirement: 模板导航与项目上下文
AI 测试系统前端 SHALL 基于模板 sidebar 和 dashboard layout 实现一级导航、顶部区域和项目上下文，不 SHALL 在左侧常驻展示二级菜单或项目树。

#### Scenario: 左侧一级导航
- **WHEN** 已登录用户进入后台
- **THEN** 左侧导航使用模板 sidebar 展示 AI 测试系统的一级模块分组，而不是模板示例业务导航

#### Scenario: 页面内二级导航
- **WHEN** 用户进入项目详情、任务中心、系统设置或后续业务模块
- **THEN** 页面内使用 Tabs、面包屑、局部入口或分段控件承载二级结构，左侧不展开常驻二级菜单

#### Scenario: 项目切换器位置
- **WHEN** 用户访问项目相关页面
- **THEN** 系统在模板顶部区域或页面 header 中展示项目切换器，并支持“全部项目”和指定项目分区

### Requirement: 业务页面迁移
AI 测试系统前端 SHALL 将第一阶段页面迁移到模板共置式路由结构，并 MUST 保持后端 API、权限禁用态、available_actions 和中文状态展示。

#### Scenario: 基础页面可访问
- **WHEN** 管理员登录后打开控制台、项目列表、项目详情、任务中心、任务详情、用户与权限、系统设置和模型配置入口
- **THEN** 页面在模板 dashboard shell 内渲染，并使用模板组件体系展示内容

#### Scenario: available_actions 展示
- **WHEN** 后端返回对象的 available_actions
- **THEN** 前端按模板按钮、菜单或确认弹窗展示 enabled、disabled_reason、risk_level 和 confirm_required，不自行推断核心权限

#### Scenario: 接口自动化 Soon
- **WHEN** 用户进入接口自动化页面
- **THEN** 系统在模板页面结构内展示 Soon 状态，并禁止创建、生成或执行接口自动化任务

### Requirement: 运行验证
AI 测试系统前端迁移完成后 SHALL 通过模板级和业务级运行验证。

#### Scenario: 依赖安装
- **WHEN** 开发者在 `apps/frontend` 执行 `npm install`
- **THEN** 依赖安装成功，并生成与模板技术栈一致的 lockfile

#### Scenario: 开发服务启动
- **WHEN** 开发者执行 `npm run dev`
- **THEN** Next.js 开发服务启动成功，并能访问登录页和后台页面

#### Scenario: 浏览器登录链路
- **WHEN** 后端运行在 `/api/v1` 且用户使用默认管理员登录
- **THEN** 浏览器登录请求成功，不出现 CORS、Failed to fetch、路由跳转失败或 token 未保存问题
