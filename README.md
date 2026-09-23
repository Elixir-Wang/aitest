# aitest

AI 驱动的测试平台：上传需求文档后自动完成解析、澄清与版本管理，由智能体生成测试用例，并串联站点探索、UI 自动化与接口自动化执行、失败诊断自愈、性能压测与报告产出。

## 核心能力

- 需求文档分析与版本管理、澄清写回与模块评审
- 知识库检索增强（项目知识库 / 全局知识库）
- Playwright 站点探索与模块覆盖、障碍记录
- 用例生成（AI + 手动）、评审与覆盖矩阵
- UI 自动化（pytest + Playwright）、接口自动化（pytest + requests）
- 失败诊断与自愈、Locust 性能脚本生成与运行
- 模型配置与智能体分配、Agent Runtime（LangChain）
- 统一任务中心、报告中心、操作审计日志与权限分层
- 执行进度与日志通过 SSE 实时推送

## 技术栈

- 后端：FastAPI + SQLAlchemy + SQLite + LangChain
- 前端：Next.js（App Router）+ React + TypeScript + Tailwind CSS + shadcn/ui

## 目录结构

```
apps/backend   FastAPI 后端服务
apps/frontend  Next.js 前端应用
apps/start     本地一键启动 / 停止脚本
docs           产品与架构文档
```

## 快速开始

后端（默认监听 `http://127.0.0.1:18000`）：

```bash
cd apps/backend
uv sync
uv run python -m app.server
```

前端（默认监听 `http://127.0.0.1:3000`）：

```bash
cd apps/frontend
npm install
npm run dev
```

默认管理员账号：`admin / admin`。
