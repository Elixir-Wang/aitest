# AI 测试系统前端

`apps/frontend` 是 AI 测试系统的前端实现目录，基于 `next-shadcn-admin-dashboard-main` 模板继续改造。

## 工作流规则

- 不再使用 OpenSpec 进行前端规划、实现或验收。
- `next-shadcn-admin-dashboard-main` 只作为模板参考和回归对照。
- 产品范围以 `docs/05-前端方案` 和 `docs/00-产品文档` 为准。
- 产品导航只展示 AI 测试系统入口，不把模板示例业务作为产品入口。

## 启动

```powershell
npm install
npm run dev
```

默认地址：

```text
http://localhost:3000
```

## 登录

正式登录路由：

```text
/auth/v1/login
```

第一版不开放公开注册。账号由管理员在“用户与权限”中创建并分配项目。

当前前端使用本地演示登录态，提交登录表单后会写入本地 token 和用户信息。后续接入后端时，需要把登录表单替换为调用后端登录 API，并在 401/token 失效时清理本地状态后跳转登录页。

## 项目上下文

项目上下文由 `ProjectSwitcher` 和 `project-context-store` 管理：

- 控制台、任务中心、报告中心允许“全部项目”。
- 需求、探索、知识库、测试用例、UI 自动化、接口自动化必须使用指定项目。
- 侧边栏中的项目作用域路由使用当前项目解析，不应硬编码为某一个项目。

## 检查

```powershell
npm run check
npx tsc --noEmit
```

当前模板文件中仍存在一批历史 CRLF/LF 格式差异，可能导致全量 `npm run check` 输出大量格式诊断。修改前端时优先对本次触碰文件运行定向 Biome 检查，避免把无关模板文件一起格式化。
