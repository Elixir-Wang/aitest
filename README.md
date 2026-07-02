# AI 测试系统

本仓库是 AI 测试系统的产品文档、前端应用和后端服务的统一工作区。系统面向测试团队，围绕项目管理、需求文档分析、站点探索、知识库沉淀、测试用例生成、UI 自动化执行、报告中心和任务追踪形成一条从需求到测试资产的工作流。

## 目录结构

```text
.
├── apps/
│   ├── backend/   # FastAPI 后端服务，提供鉴权、项目、需求、知识库、Agent、任务等 API
│   └── frontend/  # Next.js 前端应用，承载 AI 测试系统的管理后台界面
├── docs/          # 产品 PRD、前端方案、后端架构与实施计划
└── outputs/       # 探索、实现和集成过程中的输出文档
```

## 核心能力

- 项目、用户权限、环境、模型配置和操作日志管理。
- 需求文件上传、标准化、版本管理、需求分析、澄清问题和 AI 文档编辑。
- 页面/站点探索，沉淀页面事实、探索报告和候选需求线索。
- 项目知识库与全局知识库管理，并支持基于知识库的问答。
- 基于最终需求生成测试用例集，并通过任务中心追踪异步处理过程。
- UI 自动化、报告中心、失败诊断等测试执行闭环能力的页面和后端预留。

## 技术栈

- 前端：Next.js、React、TypeScript、Tailwind CSS、shadcn/Radix UI、Biome。
- 后端：Python 3.12、FastAPI、Pydantic、SQLite、本地文件存储、LangChain / OpenAI Agents / deepagents。
- 自动化方向：pytest、Playwright、Allure，接口自动化为后续预留能力。

## 快速启动

### 后端

```powershell
cd apps/backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

后端 API 默认挂载在：

```text
http://localhost:8000/api/v1
```

### 前端

```powershell
cd apps/frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:3000
```

## 检查与测试

后端测试：

```powershell
cd apps/backend
uv run pytest
```

前端检查：

```powershell
cd apps/frontend
npm run check
npx tsc --noEmit
```

前端模板历史文件可能存在格式差异。修改前端时优先对本次触碰文件做定向检查，避免引入无关格式化变更。

## 文档入口

- 产品总览与确认顺序：`docs/01-总览索引/01-01-AI测试系统-PRD确认索引.md`
- 产品 PRD：`docs/00-产品文档/`
- 后端架构与数据模型：`docs/03-后端架构与数据/`
- 前端总体方案与导航映射：`docs/05-前端方案/`
- 迭代规格与实施计划：`docs/superpowers/specs/`、`docs/superpowers/plans/`

## 子项目说明

- 后端更多说明见 `apps/backend/README.md`。
- 前端更多说明见 `apps/frontend/README.md`。
