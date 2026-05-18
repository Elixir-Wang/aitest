## Why

当前 PRD 已经完成系统范围、角色权限、项目边界、前端布局、后端架构和数据模型的第一轮确认，但还缺少可以进入编码的第一阶段变更边界。需要先建立用户权限、项目上下文、统一 API、任务中心和基础数据模型这些系统地基，避免后续需求分析、站点探索、知识库、用例生成和自动化模块各自重复实现权限、项目、状态、任务和页面壳层。

本变更将 PRD 中已确认的第一版权限、项目管理、前端导航、任务中心、系统设置和统一后端规范收敛为一个可实施切片，为后续业务模块提供稳定的前后端基础。

## What Changes

- 建立登录、当前用户、三类角色和基础权限控制能力：
  - 管理员拥有全部项目和系统配置读写权限。
  - 测试工程师只能查看和操作分配项目。
  - 访客可查看管理员可见内容，但所有写操作禁用。
- 建立项目管理基础能力：
  - 项目列表、项目详情、新建、编辑、归档、恢复。
  - 项目成员分配，支持管理员分配测试工程师。
  - 项目编码唯一，项目作为后续资产隔离边界。
- 建立前端导航与项目上下文：
  - 左侧只展示分组和一级模块。
  - 页面内使用 Tabs 或局部导航承载二级功能。
  - 右上角项目切换器支持“全部项目”和“指定项目”工作分区。
  - 项目强绑定页面必须指定项目后才能执行写操作。
- 建立任务中心基础能力：
  - 定义 TaskRun、TaskEvent、任务列表、任务详情、任务状态、事件时间线、日志摘要和结果跳转。
  - 支持排队中、运行中、等待人工、成功、失败、已取消、已过期状态展示。
  - 支持查看、重试、取消、去处理、查看结果等基础动作框架。
- 建立系统设置基础入口：
  - 文件存储、本地 Runner、Playwright、Allure、Agent 安全策略配置入口。
  - 第一阶段只实现配置保存、查看和连通性/可用性检查占位，不实现真实 Agent 编排。
- 建立统一后端规范：
  - `/api/v1` 前缀。
  - 统一成功、列表、详情、错误和长任务创建响应结构。
  - 所有响应包含 `trace_id`。
  - 后端统一计算 `available_actions`，前端只负责展示。
  - Service 层执行权限校验、状态门禁和事务控制。
- 建立 SQLite 基础模型：
  - 用户、项目、项目成员、任务、任务事件、系统设置、审计/事件基础表。
  - 为后续来源引用、业务对象状态和文件产物引用预留字段与约束。

暂不实现：

- 需求文档分析、澄清写回、需求评审。
- 站点探索和候选需求生成。
- 知识库生成、更新和发布。
- 测试用例生成、评审和采纳。
- UI 自动化代码生成、本地执行和 Allure 报告归档。
- 失败诊断、自愈补丁生成、应用和验证。
- 接口自动化能力；第一版仍为 Soon 占位。
- Agent Runtime 的真实编排、模型调用和 Skill 调度。

## Capabilities

### New Capabilities

- `user-access-control`: 登录、当前用户、三类角色、项目可见性和写操作权限门禁。
- `project-workspace`: 项目管理、项目成员分配、项目归档、项目上下文和项目资产入口。
- `navigation-project-context`: 左侧一级导航、页面内二级导航、项目切换器、全部项目/指定项目工作分区。
- `task-center-foundation`: TaskRun、TaskEvent、任务列表、任务详情、状态展示、重试/取消/结果跳转框架。
- `system-settings-foundation`: 文件存储、本地 Runner、Playwright、Allure 和 Agent 安全策略的基础配置入口。
- `api-platform-foundation`: 统一 API 响应、错误码、trace_id、available_actions、权限校验、状态门禁和审计事件基础。

### Modified Capabilities

无。当前 `openspec/specs/` 下没有已存在能力规格，本变更只新增第一阶段基础能力。

## Impact

- 前端：
  - 影响 `apps/frontend` 的应用壳层、左侧导航、页面布局、项目切换器、用户菜单、权限态展示、任务中心页面、系统设置页面和基础 API 适配层。
  - 参考 `next-shadcn-admin-dashboard-main` 的后台壳层和 shadcn/ui 组件体系。
- 后端：
  - 影响 `apps/backend` 的 FastAPI 应用初始化、认证会话、用户、项目、任务、设置、统一响应、错误处理、权限依赖、Service/Repository/Storage 基础结构。
  - 所有 API 使用 `/api/v1` 前缀，并返回 `trace_id`。
- 数据库：
  - 引入 SQLite 基础表：users、projects、project_members、task_runs、task_events、system_settings、audit_events。
  - 为后续需求、探索、知识库、用例、自动化和报告模块保留项目隔离、任务关联、状态审计和文件路径引用模式。
- 依赖：
  - 前端使用 Next.js、React、shadcn/ui、Tailwind CSS、Lucide Icons、React Hook Form、Zod、TanStack Table。
  - 后端使用 Python、FastAPI、SQLite、SQLAlchemy 或 SQLModel、Pydantic、本地任务运行封装。
- 上游依据：
  - `docs/00-产品文档/00-01-AI测试系统-PRD.md`
  - `docs/00-产品文档/00-02-AI测试系统-权限管理PRD.md`
  - `docs/00-产品文档/00-06-AI测试系统-项目管理PRD.md`
  - `docs/00-产品文档/00-12-AI测试系统-任务中心PRD.md`
  - `docs/00-产品文档/00-15-AI测试系统-系统设置PRD.md`
  - `docs/03-后端架构与数据/03-01-AI测试系统-后端架构PRD.md`
  - `docs/03-后端架构与数据/03-02-AI测试系统-数据模型PRD.md`
  - `docs/05-前端方案/05-01-AI测试系统-前端总体方案PRD.md`
  - `docs/05-前端方案/05-02-AI测试系统-导航与页面映射清单.md`
