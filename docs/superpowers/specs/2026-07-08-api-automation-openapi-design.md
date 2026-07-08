# 接口自动化与 OpenAPI 解析 Spec

## 背景

当前项目第一期将接口自动化定义为预留能力：

- 产品文档：`docs/00-产品文档/00-16-AI测试系统-接口自动化预留PRD.md`
- 占位页面：`apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx`
- 既有约束：第一期不创建接口自动化任务、不解析 OpenAPI、不生成 `pytest + requests` 代码、不执行接口测试、不生成接口报告。

本轮需求是把接口自动化从 `Soon` 预留升级为可用模块，参考项目：

```text
D:\BaiduNetdiskDownload\2026-06-10-ai-test-agent-system-platform\ai-test-agent-system-platform
```

参考项目已有可借鉴能力：

- OpenAPI/Swagger URL 或文件解析。
- 接口资产列表、接口详情、请求参数、请求体、响应定义展示。
- 基于接口生成测试计划、测试用例、测试脚本。
- 接口测试脚本查看、编辑、执行、运行记录和报告入口。
- 多接口场景测试的步骤编排、参数依赖和执行监控。

当前项目不能直接照搬参考项目结构。当前项目后端是 `sqlite3 + repository/service/api` 分层，API 统一走 `/api/v1`，前端 API 类型和请求集中在 `apps/frontend/src/lib/api-client.ts`，页面位于 Next App Router 的 `apps/frontend/src/app/(main)` 下。因此接口自动化实现必须符合当前项目结构。

## 目标

- 将 `/projects/[projectId]/automation/api` 从占位页升级为项目级接口自动化工作台。
- 支持从 OpenAPI/Swagger 文档解析接口资产。
- 支持手工维护接口资产。
- 支持基于接口资产生成接口测试用例与 `pytest + requests` 脚本。
- 支持查看、编辑、执行接口自动化脚本。
- 支持记录接口自动化运行结果，并用 `pytest-json-report` 生成系统可读取的 JSON 报告。
- 复用当前项目已有项目权限、环境配置、测试用例、任务和报告中心技术约定。
- 可借鉴参考项目代码的解析逻辑和页面信息架构，但按当前项目重写 API、存储、类型和 UI 结构。

## 非目标

- 不直接复制参考项目的 `FastAPI v2` 路由结构、SQLAlchemy 模型或前端 `ui/lib/api/*` 文件结构。
- 不引入 Postgres、MinIO、MongoDB 或 LangGraph Runtime 作为当前项目接口自动化的前置依赖。
- 不把接口自动化代码导出为 zip 或外部二次开发包。
- 不引入 Allure。Allure CLI 依赖 Java 环境，不符合当前运行条件。
- 不在第一版自研复杂报告分析平台，只保存 JSON 结果、stdout/stderr 和系统内摘要。
- 不绕过当前项目的用户权限、项目可见性和操作日志规则。
- 不在没有接口定义和测试目标的情况下让 Agent 凭空生成接口脚本。
- 第一版不做 Postman Collection、抓包导入、接口 Mock、外部 CI/CD 调度。

## 术语

### 接口文档

用户上传或填写 URL 的 OpenAPI/Swagger 文档。第一版仅支持 OpenAPI/Swagger JSON/YAML 文本解析，不支持 Postman Collection、抓包文件或其他格式。

### 接口资产

从接口文档解析或人工创建的单个接口定义，至少包含方法、路径、名称、描述、标签、参数、请求体、响应、鉴权要求和来源信息。

### 接口测试用例

围绕单个接口或接口场景生成的测试设计，可以来源于接口定义、已采纳系统测试用例或人工录入。

### 接口自动化脚本

系统生成并管理的 `pytest + requests` 代码产物。

### 接口场景

多个接口按业务顺序组合执行的流程，包含数据提取、变量传递、前置条件和断言。

## 当前项目适配原则

### 后端结构

新增代码应沿用当前目录：

```text
apps/backend/app/api/v1/api_automation.py
apps/backend/app/schemas/api_automation.py
apps/backend/app/repositories/api_automation_repo.py
apps/backend/app/services/api_automation/
  __init__.py
  openapi_parser.py
  service.py
  script_generator.py
  runner.py
  reporting.py
apps/backend/app/agents/api_automation/
  __init__.py
  agent.py
  schemas.py
  service.py
  prompts.py
  skills/
    api-test-generation/
      SKILL.md
      references/
        pytest-requests-style.md
        project-test-layout.md
        data-separation.md
        json-report-contract.md
```

说明：

- `api/v1` 只负责路由、依赖注入和响应模型。
- `schemas` 放 Pydantic 输入输出契约。
- `repositories` 只写 sqlite 查询。
- `services/api_automation` 承载解析、任务编排、执行、报告组织逻辑。
- `agents/api_automation` 承载智能体提示词、结构化输出 schema 和代码生成能力。服务层调用智能体，不把 prompt、模型选择和结构化输出细节散落到 API 层。
- 代码生成规范、目录规范、数据分离规范和 JSON 报告契约应放在 `agents/api_automation/skills/api-test-generation/references/`，由智能体 prompt 引用；服务层只负责传入结构化上下文和保存结果。
- OpenAPI 解析能力可以参考参考项目 `backend/app/services/openapi_parser.py`，但要改成当前 sqlite 和项目目录存储方式。
- 敏感值加密复用当前项目 `apps/backend/app/core/environment_credentials.py` 的 Fernet key 管理、加密/解密和 `hash_secret`/`verify_secret` 校验思路；第一版扩展该模块支持 `api_test_environments`，不要重新设计一套 secret 机制。
- 权限复用当前项目 `current_user`、`require_admin` 和 service 层 `_require_visible_project` 风格：查询类接口允许可见项目用户访问；创建、导入、生成、编辑、删除、执行等写操作第一版使用 `require_admin`，保持与测试用例生成和环境管理一致。
- 异步生成复用当前测试用例生成模式：API 层使用 `BackgroundTasks` 启动后台执行，service 创建 generation run，启动时恢复 interrupted/queued/running 状态。

### 前端结构

新增/改造代码应沿用当前目录：

```text
apps/frontend/src/app/(main)/projects/[projectId]/automation/api/page.tsx
apps/frontend/src/app/(main)/projects/[projectId]/automation/api/_components/
  api-document-import-dialog.tsx
  api-endpoint-list.tsx
  api-endpoint-detail.tsx
  api-test-artifacts-panel.tsx
  api-script-editor-dialog.tsx
  api-run-panel.tsx
```

API 类型和请求函数优先追加到：

```text
apps/frontend/src/lib/api-client.ts
```

第一版继续把 API 类型和请求函数追加到 `api-client.ts`，遵循当前集中封装方式；本轮不拆新的前端 API client 文件。

### 数据存储

当前项目使用 `apps/backend/app/seed/schema.py` 初始化 sqlite schema。第一版新增表也放在这里，并补充必要索引。

接口文档原文件、生成脚本、pytest JSON 报告使用项目文件目录：

```text
apps/backend/data/projects/<project_id>/api_automation/
  documents/<document_id>/openapi.yaml
  generated/
    <suite_id>/
      pytest.ini
      conftest.py
      tests/
        test_api_xxx.py
      data/
        test_api_xxx.json
      support/
        client.py
        auth.py
        assertions.py
      README.md
  runs/<run_id>/report.json
  runs/<run_id>/stdout.txt
  runs/<run_id>/stderr.txt
```

数据库保存路径引用、状态、统计信息，不保存大文件正文。

## 功能范围

### 1. 接口文档导入与解析

#### 页面能力

- 在接口自动化页面提供“导入 OpenAPI”入口。
- 支持两种来源：
  - URL：填写 OpenAPI/Swagger JSON/YAML URL。
  - 文件：上传 `.json`、`.yaml`、`.yml`。
- 导入后展示解析结果：接口总数、标签分组、解析失败原因、重复接口处理结果。

#### 后端规则

- URL 导入需要设置超时、内容大小限制和错误提示。
- 文件导入只接受文本格式 OpenAPI/Swagger 文档。
- 解析必须校验 `paths` 字段存在。
- 对 OpenAPI 3.x 和 Swagger 2.0 做基础兼容。
- 同一项目下接口唯一键固定为：`method + normalized_path`。
- 重复导入时第一版采用 upsert：更新接口定义，保留关联脚本和运行历史。

#### 可复用点

参考项目 `OpenAPIParser` 的 tag 分组、路径遍历、参数/请求体/响应提取思路可以复用；数据库创建、文件夹结构创建、返回模型需要按当前项目重写。

### 2. 接口资产管理

#### 页面能力

- 左侧或主区展示接口列表，支持按方法、路径、标签、关键词过滤。
- 接口详情展示：方法、路径、摘要、描述、参数、请求体、响应、鉴权、来源文档。
- 支持人工创建、编辑、删除接口资产。
- 删除接口时，如果已有脚本或运行记录，需要二次确认。

#### 后端 API

```http
GET    /api/v1/projects/{project_id}/api-endpoints
POST   /api/v1/projects/{project_id}/api-endpoints
GET    /api/v1/projects/{project_id}/api-endpoints/{endpoint_id}
PATCH  /api/v1/projects/{project_id}/api-endpoints/{endpoint_id}
DELETE /api/v1/projects/{project_id}/api-endpoints/{endpoint_id}
```

权限：

- `admin` 和 `tester` 可创建、编辑、删除。
- `guest` 只能查看。
- 必须复用项目可见性校验。

### 3. 接口测试生成

#### 从接口列表到自动化用例的实现链路

用户导入 OpenAPI 后，接口列表只是接口资产，不等同于可执行用例。生成自动化需要拆成三层产物：

1. 接口资产：`api_endpoints`，来自 OpenAPI 或人工维护，描述接口定义。
2. 接口自动化用例：`api_test_cases`，描述要测什么、输入数据、预期结果和断言。
3. 接口自动化脚本：`api_test_scripts`，描述怎么用 pytest + requests 执行这些用例。

推荐页面流程：

1. 用户在接口资产列表勾选一个或多个接口。
2. 点击“生成用例/脚本”。
3. 弹窗选择接口环境、生成目标、是否生成安全/异常用例、是否同时生成代码。
4. 后端创建 `api_generation_runs`，状态为 `queued`。
5. 后端读取接口定义、环境摘要、用户测试重点和已采纳测试用例，构造 Agent 输入。
6. Agent 先输出结构化接口自动化用例，不直接写代码。
7. 服务层校验用例：接口 ID 是否存在、请求数据是否缺关键参数、断言是否有依据、敏感值是否未明文落盘。
8. 服务层保存 `api_test_cases`。缺少环境、鉴权或必要参数的用例状态为 `needs_input`。
9. 如果用户选择“同时生成代码”，服务层再把已保存的 API 用例交给脚本生成器生成 pytest 工程。
10. 生成完成后保存 `api_test_scripts`，并把生成任务状态改为 `completed` 或 `failed`。

第一版允许“一键生成用例 + 代码”，但内部实现必须仍然先生成结构化用例，再生成代码。这样后续可以支持只生成用例、人工编辑用例、重新生成代码，而不用重跑全部 AI 流程。

#### 输入

- 单个接口资产。
- 多个接口资产。
- 已采纳测试用例。
- 用户输入的测试点。
- 接口环境配置。
- 用户补充的测试重点，例如鉴权、边界值、错误码、幂等、分页、限流。

#### 输出

- 测试计划摘要。
- 接口测试用例列表。
- AI 基于接口定义或测试点生成的请求数据、预期响应结构和断言建议。
- `pytest + requests` 脚本。
- 每个项目独立的 pytest 工程目录。
- 与测试代码分离的 JSON 测试数据。
- 生成任务状态和失败原因。

#### API 自动化用例结构

接口自动化用例应保存为结构化数据，而不是只存在于生成脚本里：

- 标题、优先级、标签。
- 关联接口 `endpoint_id`，场景用例可关联多个接口步骤。
- 来源：`ai_generated`、`manual`、`approved_test_case`。
- 请求配置：method、path、query、headers 覆盖、body、变量占位符。
- 预期结果：期望状态码、响应字段、响应 schema、错误码。
- 断言列表：断言类型、JSONPath、比较方式、期望值。
- 数据来源标记：哪些值来自 OpenAPI，哪些来自用户测试点，哪些是 AI 生成。
- 状态：`draft`、`ready`、`needs_input`、`archived`。

用例数据落库后，脚本生成器再把请求数据和预期结果写入 `data/*.json`。pytest 测试代码只负责读取 JSON 数据、调用 client、执行断言。

#### 规则

- 生成脚本前必须存在接口资产。
- 生成输入可以来自接口定义、用户测试点或已采纳测试用例。
- 使用已采纳测试用例生成时，只允许引用状态为 `approved` 的测试用例。
- 只基于接口定义或测试点生成时，AI 可以生成请求数据、预期响应结构和断言建议，但必须标记来源为 `ai_generated`，并允许用户在执行前编辑确认。
- 生成脚本不得凭空编造 base_url、token、账号、业务参数。
- 缺少接口环境变量、鉴权配置或必要请求样例时，生成结果必须标记为“需人工补充”，不能直接进入可执行基线。
- 脚本生成应优先使用 `requests.Session`、清晰的 helper 和 pytest 原生断言，避免所有逻辑堆在一个测试函数中。
- 脚本生成只能消费 `ready` 状态的 `api_test_cases`；`needs_input` 用例需要用户补齐数据后才能进入脚本。
- 生成规范不写死在 service 里。代码风格、工程目录、fixture、数据分离、断言和报告契约统一由 `agents/api_automation/skills/api-test-generation/references/` 管理。

#### 后端 API

```http
POST /api/v1/projects/{project_id}/api-automation/generate
GET  /api/v1/projects/{project_id}/api-automation/generation-runs/{run_id}
```

生成任务第一版使用 FastAPI `BackgroundTasks`，沿用测试用例生成任务模式，并同步纳入当前 `task_service` 聚合任务列表。

### 4. 脚本查看、编辑与保存

#### 页面能力

- 在接口详情或测试成果物面板展示脚本列表。
- 支持查看脚本内容。
- 支持编辑脚本并保存。
- 支持恢复到最近一次生成版本。

#### 后端 API

```http
GET   /api/v1/projects/{project_id}/api-scripts/{script_id}
PATCH /api/v1/projects/{project_id}/api-scripts/{script_id}
```

#### 规则

- 脚本文件保存在项目独立 pytest 工程目录。
- 数据库记录脚本元信息、suite 路径、测试代码路径、测试数据路径、关联 endpoint/test_case/generation_run。
- 保存编辑时记录 `updated_by` 和 `updated_at`。
- 不提供 zip 下载。

### 5. 接口自动化执行

#### 页面能力

- 选择环境后执行单个脚本或脚本集合。
- 展示运行状态：queued、running、passed、failed、cancelled。
- 展示 stdout/stderr 摘要、失败原因和 JSON 统计摘要。
- 本次不做前端测试报告可视化页面；前端后续基于 `report.json` 单独设计报告展示。

#### 后端 API

```http
POST /api/v1/projects/{project_id}/api-runs
GET  /api/v1/projects/{project_id}/api-runs/{run_id}
GET  /api/v1/projects/{project_id}/api-runs/{run_id}/logs
GET  /api/v1/projects/{project_id}/api-runs/{run_id}/report
```

#### 执行规则

- 第一版只支持本地 Runner。
- 技术栈为 `pytest + requests + pytest-json-report`。
- 执行目录必须限制在项目生成目录下。
- 运行命令由后端固定模板组装，不允许前端传任意 shell 命令。
- 运行时注入接口环境配置：`API_BASE_URL`、headers、token、用户定义变量。
- 执行环境依赖由 uv 管理。生成的 pytest 工程必须包含 `pyproject.toml` 或等价依赖声明，至少包含 `pytest`、`requests`、`pytest-json-report`；Runner 执行前通过 uv 同步依赖，后续运行可复用已安装环境。
- 同一 suite 下一次执行前，清理上一次该 suite 的 `report.json`、stdout、stderr 和运行临时目录，避免前端读取过期结果。
- 执行完成后必须生成 `report.json`。
- 系统记录运行结果并保存报告路径。

#### 后端执行步骤

1. API 层校验项目权限、脚本归属和环境归属。
2. Service 创建 `api_automation_runs`，状态为 `queued`。
3. Runner 加锁同一 suite，避免同一目录并发写报告。
4. Runner 清理该 suite 上一次临时结果：`report.json`、stdout、stderr、runtime 目录。
5. Runner 加载 `api_environment_id`，解析 base URL、默认 headers、变量、鉴权和 timeout。
6. 如果鉴权为 `login_request`，先执行登录请求，提取 token/cookie，并按 ttl 缓存到本次运行上下文。
7. Runner 写入脱敏版 `<run_dir>/runtime/env.json`，敏感值只通过进程环境变量传入。
8. Runner 在 suite 目录执行 `uv sync` 或等价依赖同步命令。
9. Runner 执行固定 pytest 命令：

```text
uv run pytest tests --json-report --json-report-file=<run_dir>/report.json
```

10. Runner 捕获 stdout/stderr 到 `<run_dir>/stdout.txt` 和 `<run_dir>/stderr.txt`。
11. Reporting 解析 `report.json`，提取 summary、失败用例、耗时、exitcode。
12. Service 更新 `api_automation_runs` 状态、摘要、报告路径和错误信息。

### 6. 接口场景编排

第一版实现接口场景编排。场景能力与接口资产、脚本生成、执行能力同阶段交付，但第一版保持表单式编排，不做复杂拖拽、分支、循环和压测。

#### 能力

- 创建接口场景。
- 为场景添加多个步骤，每个步骤关联一个接口。
- 配置步骤顺序、请求参数、变量提取、断言。
- 生成场景级 pytest 脚本。
- 执行场景级脚本并生成 `report.json`。

#### 非第一版能力

- 可视化拖拽编排。
- 复杂条件分支。
- 循环、并发、压测。

## 数据模型设计

### api_documents

```sql
CREATE TABLE IF NOT EXISTS api_documents (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK(source_type IN ('url', 'file')),
  source_url TEXT NOT NULL DEFAULT '',
  file_path TEXT NOT NULL DEFAULT '',
  version TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('parsed', 'failed')),
  endpoint_count INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

### api_endpoints

```sql
CREATE TABLE IF NOT EXISTS api_endpoints (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  document_id TEXT,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  normalized_path TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]',
  parameters_json TEXT NOT NULL DEFAULT '[]',
  request_body_json TEXT NOT NULL DEFAULT '{}',
  responses_json TEXT NOT NULL DEFAULT '{}',
  auth_json TEXT NOT NULL DEFAULT '{}',
  source_json TEXT NOT NULL DEFAULT '{}',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES api_documents(id) ON DELETE SET NULL,
  UNIQUE(project_id, method, normalized_path)
);
```

### api_generation_runs

```sql
CREATE TABLE IF NOT EXISTS api_generation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  api_environment_id TEXT,
  task_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'interrupted')),
  endpoint_ids_json TEXT NOT NULL DEFAULT '[]',
  source_test_case_ids_json TEXT NOT NULL DEFAULT '[]',
  generation_goal TEXT NOT NULL DEFAULT '',
  options_json TEXT NOT NULL DEFAULT '{}',
  result_summary_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
);
```

### api_test_cases

```sql
CREATE TABLE IF NOT EXISTS api_test_cases (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  endpoint_id TEXT,
  source_test_case_id TEXT,
  generation_run_id TEXT,
  title TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'P2',
  source TEXT NOT NULL CHECK(source IN ('ai_generated', 'manual', 'approved_test_case')) DEFAULT 'ai_generated',
  status TEXT NOT NULL CHECK(status IN ('draft', 'ready', 'needs_input', 'archived')) DEFAULT 'draft',
  tags_json TEXT NOT NULL DEFAULT '[]',
  request_json TEXT NOT NULL DEFAULT '{}',
  expected_json TEXT NOT NULL DEFAULT '{}',
  assertions_json TEXT NOT NULL DEFAULT '[]',
  variables_json TEXT NOT NULL DEFAULT '{}',
  data_origin_json TEXT NOT NULL DEFAULT '{}',
  data_file_path TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
  FOREIGN KEY(source_test_case_id) REFERENCES test_cases(id) ON DELETE SET NULL,
  FOREIGN KEY(generation_run_id) REFERENCES api_generation_runs(id) ON DELETE SET NULL
);
```

### api_test_scripts

```sql
CREATE TABLE IF NOT EXISTS api_test_scripts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  endpoint_id TEXT,
  api_test_case_id TEXT,
  test_case_id TEXT,
  generation_run_id TEXT,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('draft', 'ready', 'needs_input', 'failed')),
  suite_path TEXT NOT NULL,
  test_file_path TEXT NOT NULL,
  data_file_path TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'python',
  framework TEXT NOT NULL DEFAULT 'pytest_requests',
  notes TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  updated_by TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(endpoint_id) REFERENCES api_endpoints(id) ON DELETE SET NULL,
  FOREIGN KEY(api_test_case_id) REFERENCES api_test_cases(id) ON DELETE SET NULL,
  FOREIGN KEY(test_case_id) REFERENCES test_cases(id) ON DELETE SET NULL
);
```

### api_automation_runs

```sql
CREATE TABLE IF NOT EXISTS api_automation_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  api_environment_id TEXT,
  task_id TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'passed', 'failed', 'cancelled', 'interrupted')),
  script_ids_json TEXT NOT NULL DEFAULT '[]',
  command_summary TEXT NOT NULL DEFAULT '',
  stdout_path TEXT NOT NULL DEFAULT '',
  stderr_path TEXT NOT NULL DEFAULT '',
  json_report_path TEXT NOT NULL DEFAULT '',
  summary_json TEXT NOT NULL DEFAULT '{}',
  error_message TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(api_environment_id) REFERENCES api_test_environments(id) ON DELETE SET NULL
);
```

### api_test_environments

接口自动化使用独立环境表，不直接复用偏 UI/探索的 `project_environments`。如需共享 UI 登录态或账号信息，通过 `linked_ui_environment_id` 关联，而不是把 UI 环境当作 API 环境主对象。

```sql
CREATE TABLE IF NOT EXISTS api_test_environments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  linked_ui_environment_id TEXT,
  name TEXT NOT NULL,
  api_base_url TEXT NOT NULL,
  username TEXT NOT NULL DEFAULT '',
  password_encrypted TEXT NOT NULL DEFAULT '',
  password_hash TEXT NOT NULL DEFAULT '',
  auth_type TEXT NOT NULL CHECK(auth_type IN ('none', 'static_bearer', 'static_headers', 'cookie', 'login_request')) DEFAULT 'none',
  auth_config_json TEXT NOT NULL DEFAULT '{}',
  variables_json TEXT NOT NULL DEFAULT '{}',
  default_headers_json TEXT NOT NULL DEFAULT '{}',
  timeout_seconds INTEGER NOT NULL DEFAULT 30,
  verify_ssl INTEGER NOT NULL DEFAULT 1,
  auth_state_ttl_seconds INTEGER NOT NULL DEFAULT 86400,
  description TEXT NOT NULL DEFAULT '',
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
  FOREIGN KEY(linked_ui_environment_id) REFERENCES project_environments(id) ON DELETE SET NULL,
  UNIQUE(project_id, name)
);
```

## API 契约草案

### 导入 OpenAPI

```http
POST /api/v1/projects/{project_id}/api-documents/import
Content-Type: multipart/form-data 或 application/json
```

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| source_type | `url` 或 `file` | 是 | 来源类型 |
| url | string | source_type=url 时必填 | OpenAPI/Swagger 地址 |
| file | file | source_type=file 时必填 | JSON/YAML 文件 |
| name | string | 否 | 文档名称，默认取 info.title 或文件名 |

响应：

```json
{
  "id": "apidoc-xxx",
  "project_id": "project-1",
  "name": "Petstore API",
  "status": "parsed",
  "endpoint_count": 18,
  "created_at": "2026-07-08T00:00:00"
}
```

### 查询接口列表

```http
GET /api/v1/projects/{project_id}/api-endpoints?method=GET&tag=user&search=login
```

### 生成接口脚本

```http
POST /api/v1/projects/{project_id}/api-automation/generate
```

请求：

```json
{
  "endpoint_ids": ["apiend-xxx"],
  "test_case_ids": ["tc-xxx"],
  "api_environment_id": "apienv-xxx",
  "generation_goal": "覆盖正常登录、鉴权失败、参数缺失和错误码",
  "include_security_cases": false,
  "generate_code": true
}
```

响应：

```json
{
  "generation_run_id": "apigen-xxx",
  "status": "queued"
}
```

查询生成结果：

```http
GET /api/v1/projects/{project_id}/api-automation/generation-runs/{run_id}
```

响应：

```json
{
  "id": "apigen-xxx",
  "status": "completed",
  "summary": {
    "test_case_count": 4,
    "script_count": 1,
    "needs_input_count": 1
  },
  "test_cases": [
    {
      "id": "apitc-xxx",
      "endpoint_id": "apiend-xxx",
      "title": "登录成功",
      "status": "ready",
      "source": "ai_generated"
    }
  ],
  "scripts": [
    {
      "id": "apiscript-xxx",
      "status": "ready",
      "suite_path": "apps/backend/data/projects/project-1/api_automation/generated/apisuite-xxx"
    }
  ],
  "error_message": ""
}
```

### 查询和维护接口自动化用例

```http
GET   /api/v1/projects/{project_id}/api-test-cases?endpoint_id=apiend-xxx&status=ready
PATCH /api/v1/projects/{project_id}/api-test-cases/{case_id}
```

用例编辑主要用于补齐 `needs_input` 的请求数据、变量、断言或预期值。用例变更后，用户可以重新生成脚本。

### 从接口自动化用例生成脚本

```http
POST /api/v1/projects/{project_id}/api-automation/scripts/generate
```

请求：

```json
{
  "api_test_case_ids": ["apitc-xxx", "apitc-yyy"],
  "api_environment_id": "apienv-xxx"
}
```

此接口用于用户已经审完 API 用例，只想重新生成 pytest 代码的场景。它只允许消费 `ready` 状态的接口自动化用例。

### 执行脚本

```http
POST /api/v1/projects/{project_id}/api-runs
```

请求：

```json
{
  "script_ids": ["apiscript-xxx"],
  "api_environment_id": "apienv-xxx"
}
```

响应：

```json
{
  "run_id": "apirun-xxx",
  "status": "queued"
}
```

## 页面设计

### 页面布局

路由：

```text
/projects/{projectId}/automation/api
```

建议结构：

```text
PageShell
  顶部操作区：导入 OpenAPI、手工新建接口、生成脚本、执行
  指标条：接口数、脚本数、最近运行、失败数
  Tabs：接口资产 / 测试脚本 / 运行记录 / 场景编排
```

### 接口资产 Tab

- 左侧或上方过滤区：方法、标签、关键词。
- 主列表：方法、路径、摘要、标签、来源、脚本数、最近运行状态。
- 详情抽屉：参数、请求体、响应、关联脚本、生成入口。

### 测试脚本 Tab

- 列表：脚本名、关联接口、状态、更新时间、最近运行。
- 操作：查看、编辑、执行。
- 编辑器：当前项目没有 Monaco/CodeMirror 统一代码编辑器，第一版复用 `apps/frontend/src/components/ui/textarea.tsx` 做脚本文本编辑；本轮不新增 Monaco 依赖。

### 运行记录 Tab

- 列表：运行 ID、状态、环境、脚本数、耗时、创建人、创建时间。
- 操作：查看日志、查看 JSON 摘要。

### 场景编排 Tab

- 第一版交付表单式场景编排，不做空占位。
- 支持创建场景、添加接口步骤、调整步骤顺序、配置请求参数、变量提取和断言。
- 不做拖拽式编排、条件分支、循环、并发和压测。

## 生成脚本规范

### 代码框架最佳实践来源

本模块生成的 pytest 工程遵循以下公开资料中的稳定建议：

- pytest 官方 Good Integration Practices：测试文件使用 `test_*.py` / `*_test.py`，测试函数以 `test_` 开头；推荐将测试放在独立 `tests/` 目录；新项目建议使用 `--import-mode=importlib` 降低导入路径副作用。
- Requests 官方 Advanced Usage：使用 `requests.Session` 复用连接、cookie、默认 headers/auth；请求级参数可以覆盖 session 级默认值；Session 可作为上下文管理器使用，保证资源释放。
- pytest-json-report GitHub README：使用 `--json-report` 生成 JSON；使用 `--json-report-file=PATH` 指定输出路径；报告包含 `summary`、`tests`、`duration`、`exitcode` 等字段，适合被其他应用处理；可通过 `json_metadata` fixture 或 hook 增加 JSON 可序列化元数据。

落地结论：

- 每个项目/套件生成一套独立 pytest 工程，不把多个项目的测试混在同一目录。
- 测试发现遵循 pytest 默认命名：`tests/test_*.py`。
- `pytest.ini` 固定 `--import-mode=importlib` 和必要 marker，避免导入路径污染。
- HTTP 调用统一通过 `support/client.py` 中的 Session client 完成，不在每个测试函数里直接散落 `requests.get/post`。
- 测试数据进入 `data/*.json`，测试代码只读取数据并执行步骤。
- `report.json` 是唯一系统报告契约，生成脚本可通过 `json_metadata` 写入 endpoint_id、script_id、case_id 等元数据，方便后续前端报告展示。

生成目录按项目和套件隔离。每个项目可以有多套接口自动化 pytest 工程，每套工程内部必须做到测试代码和测试数据分离：

```text
apps/backend/data/projects/<project_id>/api_automation/generated/<suite_id>/
  pytest.ini
  conftest.py
  tests/
    test_<safe_endpoint_name>.py
  data/
    test_<safe_endpoint_name>.json
  support/
    __init__.py
    client.py
    auth.py
    assertions.py
  README.md
```

目录职责：

| 路径 | 职责 |
| --- | --- |
| `tests/` | 只放 pytest 测试代码，负责组织用例、调用 client、执行断言。 |
| `data/` | 只放测试数据、参数组合、期望状态码、期望字段，不放执行逻辑。 |
| `support/client.py` | 统一封装 requests.Session、base_url、headers、timeout。 |
| `support/auth.py` | 统一封装鉴权 header/token/cookie 注入。 |
| `support/assertions.py` | 统一封装通用响应断言和 JSON 字段断言。 |
| `conftest.py` | 定义 pytest fixture，加载环境变量和 JSON 测试数据。 |
| `pytest.ini` | 固定测试发现、marker、`--import-mode=importlib` 等项目级 pytest 配置。 |

脚本基本结构：

```python
import os

import requests


BASE_URL = os.environ["API_BASE_URL"].rstrip("/")


def test_login_success():
    response = requests.post(f"{BASE_URL}/login", json={"username": "", "password": ""})

    assert response.status_code == 200
```

规则：

- 不硬编码真实账号、密码、token。
- 不把环境域名写死到脚本。
- 请求 payload、query 参数、headers 样例和预期结果默认进入 `data/*.json`，测试文件只引用数据。
- 参数缺失时生成 TODO 注释，并将脚本状态置为 `needs_input`。
- 断言必须来源于接口响应定义、用户目标或测试用例，不允许无来源猜业务。

## 执行与纯 Python 报告

报告方案选择：

- 正式结果源：`pytest-json-report` 生成机器可读 JSON，供系统统计通过率、失败原因、耗时、失败节点和后续前端报告展示。
- 第一版不生成 `junitxml`；后续接 CI 时再扩展兼容格式。
- 不使用 Allure，因为 Allure CLI 依赖 Java 环境。

执行命令由后端固定：

```text
pytest <script_dir> --json-report --json-report-file=<run_dir>/report.json
```

第一版需要处理：

- 本机未安装 pytest/requests/pytest-json-report 的错误提示。
- 脚本执行超时。
- stdout/stderr 落盘。
- JSON 报告生成失败。
- 运行中服务重启后，将未完成运行标记为 failed 或 interrupted。

## 与现有模块关系

### 接口环境

接口自动化使用独立的 `api_test_environments`，不直接复用偏 UI/探索的 `project_environments`。原因是接口自动化的 base URL、鉴权方式、变量、token 生命周期和 UI 登录态并不总是一致。需要共享信息时，通过 `linked_ui_environment_id` 可选关联 UI 环境。

参考项目的接口环境实现偏“执行配置传参”：`APITest.test_config`、`APITestRun.execution_config`、scenario execute request 中临时传入 `base_url`、`env`、`environment_variables`、`variables`、`headers_override`，执行器再把 `base_url` 注入为 `API_BASE_URL`。这个思路适合作为 runner 输入模型参考，但不适合作为当前项目的产品级环境模型，否则 base URL、鉴权、变量、token 生命周期会分散在测试、运行记录和场景步骤里。

当前项目采用“环境中心 + 运行时解析”方案：

- 环境是项目内可管理资产，由 `api_test_environments` 统一保存。
- 测试脚本、场景和运行记录只引用 `api_environment_id`，不复制整份环境配置。
- 执行开始时生成一次运行时环境快照，写入本次运行目录，保证历史运行可追溯。
- 生成脚本不感知数据库结构，只读取 runner 注入的 runtime config。
- 敏感值只在后端解密和注入，脚本文件、测试数据文件、JSON 报告、stdout/stderr 不保存明文 secret。

接口环境负责：

- `api_base_url`：接口自动化专用 base URL。不要强制复用 UI `site_url`，因为 UI 域名和 API 网关地址经常不同。
- `username`、`password_encrypted`、`password_hash`：接口登录可用的账号密码，复用现有加密思路，但存放在接口环境表中。
- `auth_type`：`none`、`static_bearer`、`static_headers`、`cookie`、`login_request`。
- `auth_config_json`：鉴权配置，例如 header 名称、cookie 名称、登录接口路径、token 提取规则。敏感值只保存引用或加密值。
- `variables_json`：非敏感变量，例如 tenant_id、region、默认分页参数、业务枚举。
- `default_headers_json`：非敏感默认 header，例如 `Accept-Language`、`X-Client-Version`。
- `timeout_seconds`、`verify_ssl`：请求执行参数。
- `auth_state_ttl_seconds`：接口鉴权状态或 token 的有效期配置。
- `linked_ui_environment_id`：可选关联 UI 环境，仅用于需要借用 UI 账号说明或登录态的特殊情况。

执行时：

- Runner 根据 `api_environment_id` 加载 `api_base_url`、变量和鉴权配置。
- Runner 在 `<run_dir>/runtime/env.json` 生成本次运行环境快照，包含非敏感配置、脱敏后的鉴权摘要和变量名清单。
- Runner 通过进程环境变量传入敏感值，例如 `API_AUTH_TOKEN`、`API_AUTH_COOKIE`、`API_PASSWORD`，执行结束后不持久化这些明文值。
- `support/auth.py` 根据运行时注入的环境变量、加密 secret 或登录接口结果生成 header/cookie。
- 生成脚本只读取 `API_BASE_URL`、`API_AUTH_*`、`API_VAR_*` 等运行时变量，不写死敏感值。
- `report.json`、stdout、stderr 中需要脱敏 token、cookie、password、authorization 等字段。

第一版鉴权范围：

- 必做：`none`、`static_bearer`、`static_headers`、`cookie`、`login_request`。
- `login_request` 限定为普通 HTTP 登录请求获取 token/cookie，例如账号密码 JSON 登录、表单登录、固定 header 登录。配置内容包括登录接口路径、method、请求体模板、token/cookie 提取路径、注入 header/cookie 的规则。
- 不做：复杂 OAuth 浏览器授权流、MFA、短信/验证码自动处理。这类场景后续再和 UI 环境或手工授权联动。

推荐环境配置 UI 分区：

- 基础信息：环境名称、API Base URL、说明、是否默认环境。
- 默认请求：默认 headers、timeout、verify SSL。
- 变量：非敏感变量，以 key/value 维护，用于路径、query、body 和断言模板。
- 鉴权：按 `auth_type` 切换表单；静态 token/cookie/header 使用加密保存；登录鉴权配置登录接口、方法、请求体模板、token 提取路径、header/cookie 注入规则。
- 账号：接口登录账号密码，可选；只在 `login_request` 或用户明确需要时填写。
- 缓存策略：token/auth state 的 ttl，默认 86400 秒；过期后下一次运行重新获取。

推荐运行时解析顺序：

1. 读取 `api_environment_id` 对应环境。
2. 合并环境默认 headers、变量和本次运行临时覆盖项。
3. 按 `auth_type` 解析鉴权：无鉴权、静态 bearer、静态 headers、cookie 或登录接口获取 token。
4. 生成运行时配置和脱敏快照。
5. 使用 uv 同步依赖并执行 pytest。
6. 解析 `pytest-json-report`，保存运行摘要并清理/覆盖同 suite 上一次临时结果。

第一版先不做跨项目共享环境。每个项目拥有自己的接口环境，避免账号、base URL 和 secret 在项目间误用。后续如果确实需要组织级公共环境，再抽象通用 secret 表和环境模板。

### 测试用例

接口自动化可以关联 `test_cases`：

- 已采纳测试用例可作为生成输入。
- 运行结果可以回写关联关系，但第一版不强制改变测试用例评审状态。

### 报告中心

接口自动化报告使用纯 Python JSON 结果策略：

- 系统保存 `report.json` 路径和运行摘要。
- 系统从 JSON 报告中读取总数、通过数、失败数、耗时和失败摘要。
- 本次不做前端测试报告可视化页面，只展示运行状态和必要摘要。
- 后续前端报告页以 `report.json` 为唯一数据源进行单独设计。

### 任务中心

脚本生成和执行纳入当前 `task_service` 聚合任务模式，而不是新建独立任务中心：

- 生成任务 source_type：`api_automation_generation_run`，task_id：`api_automation_generation:{run_id}`。
- 执行任务 source_type：`api_automation_run`，task_id：`api_automation_run:{run_id}`。
- `task_service.RUNNING_INDICATOR_SOURCE_TYPES` 增加上述 source type。
- `task_service.STATUS_META_BY_SOURCE_TYPE` 增加生成和执行状态映射。
- `_collect_visible_tasks` 增加接口自动化 generation/run 聚合，项目可见性沿用现有 project scope 判断。
- `app.main.startup` 增加接口自动化中断恢复：将服务重启前处于 `queued`、`running` 的生成/执行任务标记为 `failed` 或 `interrupted`。

第一版直接集成任务中心运行态展示，避免生成/执行任务只在接口自动化页面可见。

## 参考项目复用清单

### 可直接借鉴思路

- `OpenAPIParser` 的解析流程：读取 `info`、遍历 `paths`、提取 method/path/tags/parameters/requestBody/responses。
- API 测试页面的信息架构：接口资产、详情、成果物、执行入口。
- 成果物概念：测试计划、测试用例、测试脚本、执行结果、报告。
- AI 生成弹窗的输入项：OpenAPI URL/文件、脚本格式、脚本语言、测试重点。
- 多接口场景生成的概念：选择接口、分析业务关联、步骤顺序、数据依赖。

### 需要按当前项目重写

- SQLAlchemy model/repository 改为 sqlite repository 函数。
- `/api/v2` 路由改为 `/api/v1`。
- `ui/lib/api/*` 改为当前 `src/lib/api-client.ts` 或当前项目 API 封装风格。
- 参考项目的 MinIO/Attachment 成果物体系改为当前项目文件目录 + sqlite 元数据。
- 参考项目的 `api-tests` 页面路径改为当前 `/projects/[projectId]/automation/api`。
- 参考项目中的模拟执行逻辑不能作为正式执行链路，当前项目必须由后端 Runner 固定命令执行。

## 分阶段实现建议

### 阶段 1：接口资产、OpenAPI 解析和场景编排

- 新增 schema 表。
- 新增 OpenAPI URL/文件导入 API。
- 新增接口列表/详情/手工维护 API。
- 新增接口场景和场景步骤 API。
- 改造接口自动化页面，从 Soon 变为接口资产工作台。
- 场景编排 Tab 第一版可用，支持表单式步骤顺序、参数、变量提取和断言配置。
- 补后端 parser 单元测试和前端契约测试。

### 阶段 2：脚本生成和编辑

- 新增脚本生成 API。
- 新增脚本元数据和文件存储。
- 页面支持生成、查看、编辑、保存脚本。
- 接入模型能力时新增 `api_test_generation` 或等价 capability。

### 阶段 3：本地执行和 JSON 结果落库

- 新增执行 API、运行记录表、日志文件。
- 后端固定 uv + pytest-json-report 命令模板。
- 执行前清理同一 suite 上一次运行产物。
- 页面展示运行状态、日志和 JSON 摘要。
- 本阶段不做前端测试报告可视化。
- 服务重启恢复未完成运行状态。

## 验收标准

### 阶段 1 验收

- `/projects/{projectId}/automation/api` 不再显示 Soon 占位，而是显示接口资产工作台。
- 用户可以通过 OpenAPI URL 或文件导入接口。
- 导入后能看到接口列表和详情。
- 重复导入同一 method/path 不产生重复接口。
- 无效 OpenAPI 文档返回明确错误。
- guest 不能创建、编辑、删除接口。
- 第一版只支持 OpenAPI/Swagger JSON/YAML 导入，不出现 Postman/抓包导入口。
- 用户可以创建接口场景，添加多个接口步骤，配置步骤顺序、参数、变量提取和断言。

### 阶段 2 验收

- 用户可以选择接口生成 `pytest + requests` 脚本。
- 缺少必要环境/鉴权/参数时，脚本状态为 `needs_input`，页面提示待补充项。
- 用户可以查看、编辑、保存脚本。
- 脚本生成不硬编码 base_url、账号、密码、token。

### 阶段 3 验收

- 用户可以选择环境执行接口脚本。
- 执行结果保存为运行记录。
- 页面可以查看 stdout/stderr 摘要。
- 成功生成 JSON 报告时系统可展示通过率、失败数和耗时摘要。
- pytest/requests/pytest-json-report 缺失时给出明确提示，不吞错。
- 执行依赖通过 uv 同步安装，不要求用户手动逐个 pip install。
- 同一 suite 再次执行时，上一次 `report.json`、stdout、stderr 被清理，不读取过期结果。
- 前端不提供测试报告可视化页，后续基于 `report.json` 另行设计。

## 已决策内容

| 优先级 | 模块/对象 | 决策 | 影响 |
| --- | --- | --- | --- |
| P0 | 鉴权范围 | 第一版纳入 `login_request` 自动获取 token/cookie，同时支持 `none`、`static_bearer`、`static_headers`、`cookie`。`login_request` 只覆盖普通 HTTP 登录，不覆盖 OAuth 浏览器授权、MFA、短信/验证码。 | 鉴权档案 UI 需要提供登录请求配置；Runner 执行前需要处理登录、token 提取、header/cookie 注入和脱敏。 |
| P1 | Secret 存储 | 第一版不抽象通用 secret 表。token、cookie、password 等敏感值复用 `app/core/environment_credentials.py` 的 Fernet key 管理、加密/解密和 hash 校验思路，扩展支持 `api_test_environments`，存入接口环境表的加密字段或 `auth_config_json` 中的加密值。 | 实现更简单，接口环境先闭环；后续 UI/API 需要共享 secret 时，再迁移到通用 secret 表。 |
| P1 | 权限模型 | 复用当前 `current_user`、`require_admin`、`_require_visible_project` 风格。查询类接口允许可见项目用户访问；导入、创建、生成、编辑、删除、执行第一版要求 admin。 | 与现有测试用例生成、环境管理权限保持一致，避免单独发明 tester 写权限。 |
| P1 | 后台任务 | 复用测试用例生成的 `BackgroundTasks + generation_runs + startup recover` 模式，并纳入 `task_service` 聚合任务列表。 | 生成和执行任务可在任务中心看到，服务重启后状态可恢复。 |
| P2 | 脚本编辑器 | 当前前端没有统一代码编辑器组件，第一版复用 `Textarea`，不新增 Monaco/CodeMirror。 | 减少依赖和 UI 复杂度，后续再做代码编辑体验增强。 |

## 质量与验证计划

后续编码时至少补充：

- `openapi_parser` 单元测试：OpenAPI 3 JSON/YAML、Swagger 2、无 paths、重复 method/path。
- repository/service 测试：项目权限、upsert、删除保护、脚本保存、运行状态恢复。
- API 测试：导入、列表、详情、生成、执行错误路径。
- secret 测试：接口环境账号、token、cookie 加密保存、解密读取、hash 校验、报告和日志脱敏。
- 任务中心测试：接口自动化生成/执行任务能被 `task_service` 聚合，重启恢复能处理 queued/running 状态。
- 前端契约测试：页面路由、导入弹窗、接口列表空态/成功态、错误提示。
- 执行链路最小集成测试：用本地 dummy OpenAPI 生成脚本，并通过 mock runner 或临时脚本验证运行记录落库。
