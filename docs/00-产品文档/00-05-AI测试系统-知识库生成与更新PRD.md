# 00-05 AI 测试系统 · 知识库生成与更新 PRD（项目知识库）

> **范围声明**：本文档描述当前工作区代码实现的"项目知识库检索对话 + 检索来源设置"能力；全局/公司知识库文档管理（上传、文件夹、转换）见 PRD 00-22。
>
> 基线日期：2026-07-26
>
> 事实源：`apps/frontend/src/app/(main)/knowledge/page.tsx`、`apps/frontend/src/components/ai-testing/knowledge-search-settings.tsx`、`apps/backend/app/api/v1/knowledge.py`、`apps/backend/app/services/knowledge/service.py`、`apps/backend/app/services/knowledge/global_service.py`、`apps/backend/app/agents/knowledge/service.py`、`apps/backend/app/agents/knowledge/agent.py`、`apps/backend/app/seed/schema.py`、`apps/backend/app/seed/seeds.py` 当前工作区源码（含未提交代码）

---

## 1. 范围与目标

### 1.1 目标

- 让用户可以向"当前项目"或"全部项目"提问，把可命中的项目内产物作为上下文喂给知识 Agent，生成可追溯答案
- 让检索范围可被细粒度控制（全局 / 项目两级，来源类型开关）
- 让对话历史可被追溯、被复用（conversation_id 续聊）
- 查询必须包含最终需求（最终需求为最高业务事实依据）

### 1.2 项目知识库 vs 全局知识库边界

| 维度 | 项目知识库（本文） | 全局/公司知识库（PRD 00-22） |
| --- | --- | --- |
| 对象 | 检索对话、来源开关、对话历史 | 文档/文件夹/库 CRUD、上传、转换 |
| 路由 | `/knowledge`、`/projects/:projectId/knowledge` | `/global-knowledge-bases` |
| API 前缀 | `/api/v1/knowledge*`、`/api/v1/projects/:projectId/knowledge*` | `/api/v1/global-knowledge*`、`/api/v1/company-knowledge-bases*` |
| 内容 | 内存会话 + LLM Agent 调用 | 物理文件 + 数据库记录 |
| 角色 | 项目成员可检索；admin 可改开关 | 仅 admin |
| 复用关系 | 把 PRD 00-22 的可见 md 文件作为来源之一（`company_knowledge`） | 提供方 |

### 1.3 知识库状态（知识库就绪度）

系统对每个项目维护以下知识库就绪状态（本仓库**当前无前端状态展示**，后端逻辑已实现于 `service.py` 的 blockers 机制）：

| 状态 | 含义 | 可用于正式测试用例生成 |
| --- | --- | --- |
| **构建中 / 阻塞（blocker）** | 有来源启用但无可读内容，或源文件物理路径缺失 | 不可（需要 AI 协助处理阻塞） |
| **已就绪（无阻塞）** | 至少一个启用的来源有可读内容 | 可用 |

阻塞消息示例：
- "需求文档「XX」当前版本文件不存在。"
- "当前启用的检索来源没有可读取内容。"
- "当前没有可读取的公司知识库文件。"

---

## 2. 知识库对话问答

### 2.1 用户入口与页面路由

| 入口 | 路由 | 模式 | 说明 |
| --- | --- | --- | --- |
| 知识库（主入口） | `/knowledge` | 三 Tab：知识库问答 / 公司知识库 / 检索设置 | 统一入口，同时支持跨项目与项目内对话 |
| 项目知识库 | `/projects/:projectId/knowledge` | 旧路由（已合并到 `/knowledge`） | 保留兼容，实际功能通过 `/knowledge` 的项目切换实现 |

前端实现：
- `apps/frontend/src/app/(main)/knowledge/page.tsx`
- `apps/frontend/src/components/ai-testing/knowledge-search-settings.tsx`

### 2.2 前端页面结构（`/knowledge` 单页三 Tab）

```
知识库页面
├── Tab 1：知识库问答（project / all 模式）
│   ├── 范围切换：全部项目 / 指定项目
│   ├── 模型选择（capability_id = "knowledge_query"）
│   ├── 思考过程显示开关（show_thinking）
│   ├── 对话历史侧边栏（展开/收起/新建/删除）
│   ├── 快捷问题按钮（查需求 / 看探索 / 查来源 / 看模块）
│   ├── 消息流区域（user + assistant 消息对）
│   │   ├── Assistant 消息支持展开"深度思考"（thinking_delta 渲染）
│   │   └── 加载状态：PulsatingDots 动画
│   └── 输入框（含停止按钮）
├── Tab 2：公司知识库（文档目录树 + Markdown 预览）
│   ├── 知识库列表页（创建/查看/编辑/删除）
│   ├── 知识库详情页（目录树 + 文件预览）
│   └── 文件夹/文件 CRUD（新建文件夹/上传 Markdown/删除）
└── Tab 3：检索设置
    ├── 5 种来源开关（Switch 控件）
    ├── 全局模式 / 项目模式标签
    └── 恢复全局设置按钮（仅项目模式可见）
```

### 2.3 快捷问题（4 个）

| 按钮文案 | Prompt |
| --- | --- |
| 查需求 | 帮我查询当前项目最终需求文档中的核心业务规则。 |
| 看探索 | 帮我总结当前项目探索记录覆盖了哪些页面和模块。 |
| 查来源 | 帮我追踪当前项目关键结论的来源依据，包括需求版本、探索记录和对应位置。 |
| 看模块 | 帮我按知识库模块梳理当前项目的业务域、页面事实、规则条目和模块之间的关系。 |

### 2.4 查询模型配置

- 前端通过 `GET /model-assignments` 获取当前 `knowledge_query` capability 的模型分配
- 通过 `PUT /model-assignments/knowledge_query` 更新（仅 admin 可操作）
- 后端使用 `resolve_model_selection("knowledge_query")` 路由到对应模型

### 2.5 流式响应

事件类型（SSE）：`message_delta / thinking_delta / metadata / error / done`

| 事件 | 字段 | 说明 |
| --- | --- | --- |
| `message_delta.delta` | string | 正文增量（累加到消息 body） |
| `thinking_delta.delta` | string | 思考增量（仅当 `show_thinking=true`；前端渲染为有序列表） |
| `metadata.result` | `KnowledgeQueryResult` | 包含 conversation、messages、answer |
| `error` | `code/message/result` | 错误时持久化对话；code=`KNOWLEDGE_AGENT_TIMEOUT` |
| `done` | — | 流式结束 |

前端处理逻辑（`page.tsx`）：
- `message_delta`：追加到 assistant 消息 body
- `thinking_delta`：追加到 assistant 消息 `thinking` 字段，追加 `thinkingStartedAt`
- `metadata`：持久化 conversation，更新 `activeProjectConversationId`
- `error`：持久化 conversation + 结果后抛出，移除空 assistant 消息
- AbortError：保留已有内容的 assistant 消息，丢弃空消息

### 2.6 多轮对话

- 首次查询无 `conversation_id`，服务端创建新会话（title = 问题前 28 字符）
- 后续查询携带 `conversation_id`，续接历史对话
- 对话历史持久化，刷新页面仍可加载（`GET /knowledge/conversations`）
- 删除对话：只删除当前用户的对话（仓库层校验）

### 2.7 思考过程展示

- 模型支持 `thinking_toggle`（`show_thinking` 参数控制）
- 支持模型：MiniMax、DeepSeek（provider 或 model name 包含关键字）
- 其他模型：`extra_body.thinking={type:"disabled"}`
- 前端展示：可折叠有序列表，含"思考中/已思考"状态 + 用时（如"用时 12 秒"）
- `thinking_delta` 脱敏：移除 `<!-- source_metadata -->`、工具调用行、序号前缀

---

## 3. 检索来源设置

### 3.1 5 种来源类型

| source_type | 含义 | 实际读取 |
| --- | --- | --- |
| `final_requirements` | 当前项目最终需求 Markdown | `documents` 中 `current_version_id` 对应版本的物理文件（通过 `resolve_stored_path` 解析） |
| `explorations` | 当前项目页面探索产物 | `exploration_artifacts` 中 `artifact_type='page_yaml'` 且 `.yaml` 后缀、可解码、非空 |
| `test_cases` | 当前项目已采纳测试用例 | `test_cases` 中 `status='approved'`（字段拼接为 Markdown） |
| `api_information` | 当前项目接口资产 + 接口场景 | `api_endpoints` + `api_scenarios`（各自拼接为 Markdown） |
| `company_knowledge` | 全局/公司知识库可见 md 文件 | `global_knowledge_vault_files` 中 `conversion_status ∈ {success, completed, available}`；优先读物理 `markdown_path`，回退 `markdown_content` 字段 |

### 3.2 默认值

```python
DEFAULT_KNOWLEDGE_SEARCH_SOURCES = {
    "final_requirements": True,   # 必须启用
    "explorations": True,
    "test_cases": False,
    "api_information": False,
    "company_knowledge": True,
}
```

### 3.3 继承语义（全局 / 项目两级）

解析顺序（`resolve_knowledge_search_settings`）：
1. project（项目自定义）→ origin=`project`，`inherited=False`
2. global（全局设置）→ origin=`global`，`inherited=True`
3. system（默认值）→ origin=`system`，`inherited=scope != "__all_projects__"`

DELETE 项目设置 → 恢复到全局值（前端"恢复全局设置"按钮）

### 3.4 与请求参数的关系

| 请求参数 | 行为 |
| --- | --- |
| `include_requirements=False` | 跳过 `final_requirements/explorations/test_cases/api_information` 四类，仅保留 `company_knowledge` |
| `include_company_knowledge=False` | 强制关闭 `company_knowledge` |

### 3.5 校验规则

- 必须至少有 1 个 `enabled=True` 的来源（`KNOWLEDGE_SEARCH_SOURCE_REQUIRED`）
- 来源类型必须在白名单（`KNOWLEDGE_SEARCH_SOURCE_TYPES`）中
- 非 admin 修改设置返回 403 `KNOWLEDGE_SEARCH_SETTINGS_FORBIDDEN`

---

## 4. 知识库生成与更新（非向量检索）

### 4.1 检索机制：LLM Agentic RAG

本系统**不使用向量检索**。知识查询流程：

```
用户问题
  → service._collect_query_input() 收集所有启用来源的文件内容
  → service._collect_project_sources()
       ├─ final_requirements: 读 source_document_versions 物理文件
       ├─ explorations: 读 exploration_artifacts YAML
       ├─ test_cases: 从 test_case_repo 读已采纳用例
       └─ api_information: 从 api_automation_repo 读接口资产
  → service._collect_company_knowledge_sources()（公司知识库）
  → 组装为 KnowledgeQueryInput（source_documents 列表）
  → knowledge_agent_service.stream_knowledge_agent()
       ├─ 虚拟文件系统：每个 source_doc 生成一个虚拟文件
       ├─ Agent prompt: 告知文件路径清单，要求先用 glob/grep 定位
       └─ Agent 工具：read_file / grep / glob（Deep Agents StateBackend）
  → 流式 yield message_delta / thinking_delta / metadata
```

### 4.2 来源文件虚拟路径映射

Agent 可见的虚拟文件系统结构（`agent/service.py` `_virtual_files`）：

```
/README.md               ← 知识库文件清单（含来源优先级说明）
/final-requirements/     ← 最终需求（业务事实最高依据）
/explorations/           ← 探索产物
/test-cases/             ← 已采纳测试用例
/api-information/        ← 接口资产与场景
/company-knowledge/     ← 公司知识库 md 文件
```

每个文件顶部含 JSON 元数据注释：`<!-- source_metadata: {...} -->`，用于核对来源。

### 4.3 阻塞处理

- 源文件路径解析失败 / 文件不存在：进入 blocker 列表（不抛错）
- 所有来源无内容：返回 blocker 列表，不再调用 Agent
- 全部项目模式：只要有任何 source_documents，blockers 自动清空

### 4.4 失败与降级

| 场景 | 行为 |
| --- | --- |
| Agent 调用失败 | 返回固定提示 `KNOWLEDGE_QUERY_FAILED_MESSAGE` |
| Agent 超时（300s） | 返回 `KNOWLEDGE_QUERY_TIMEOUT_MESSAGE` + error 事件 |
| 来源全部失效 | 返回 blocker 列表（不调用 Agent） |
| 公司知识库无可见文件 | 返回 `当前没有可读取的公司知识库文件。` |

---

## 5. 跨项目对话（`__all_projects__`）

### 5.1 虚拟项目

`__all_projects__` 是系统保留的"虚拟项目"：

```python
# apps/backend/app/seed/seeds.py:907-916
INSERT INTO projects (id, name, status, description, created_by)
VALUES ('__all_projects__', '全部项目知识库', 'archived',
        '系统保留项目，用于全部项目知识库对话历史。', 'system')
```

- 状态为 `archived`，不显示在项目列表
- 用于承载"全部项目"会话历史
- 由 `_ensure_all_projects_conversation_scope` 在首次访问时自动创建

### 5.2 跨项目查询流程

```
stream_all_project_knowledge_query()
  → project_repo.list_visible(db, actor) 收集所有可见项目
  → 逐项目调用 _collect_project_sources()
  → source_documents 跨越所有项目
  → project_id=""、project_name="全部项目"
  → knowledge_agent_service（统一 Agent）
```

### 5.3 统一接口路径

| 范围 | 对话列表 | 对话详情 | 查询 |
| --- | --- | --- | --- |
| 项目级 | `GET /projects/:projectId/knowledge/conversations` | `GET /projects/:projectId/knowledge/conversations/:id` | `POST /projects/:projectId/knowledge/query/stream` |
| 全部项目 | `GET /knowledge/conversations` | `GET /knowledge/conversations/:id` | `POST /knowledge/query/stream` |
| 检索设置 | `GET /projects/:projectId/knowledge/search-settings` | — | — |
| 全局设置 | `GET /knowledge/search-settings` | — | — |

---

## 6. 数据模型

### 6.1 `knowledge_conversations`

对话会话表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | UUID |
| `project_id` | TEXT NOT NULL FK→projects | 真实项目 ID 或 `__all_projects__` |
| `title` | TEXT NOT NULL DEFAULT '新对话' | 前 28 字符问题 |
| `created_by` | TEXT NOT NULL FK→users | 创建者 |
| `created_at` | TEXT NOT NULL | ISO 时间戳 |
| `updated_at` | TEXT NOT NULL | ISO 时间戳 |

索引：
- `idx_knowledge_conversations_project_updated`：`(project_id, created_by, updated_at)`

### 6.2 `knowledge_conversation_messages`

对话消息表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | TEXT PRIMARY KEY | UUID |
| `conversation_id` | TEXT NOT NULL FK→knowledge_conversations | 所属对话 |
| `role` | TEXT NOT NULL CHECK(role IN ('user', 'assistant')) | 角色 |
| `content` | TEXT NOT NULL | 消息正文 |
| `used_requirement_versions_json` | TEXT NOT NULL DEFAULT '[]' | Agent 调用了哪些需求版本 |
| `created_at` | TEXT NOT NULL | ISO 时间戳 |

索引：
- `idx_knowledge_conversation_messages_conversation_created`：`(conversation_id, created_at)`

### 6.3 `knowledge_search_source_settings`

检索来源开关表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `scope_key` | TEXT NOT NULL | `__all_projects__` 或具体 `project_id` |
| `source_type` | TEXT NOT NULL | `final_requirements/explorations/test_cases/api_information/company_knowledge` |
| `enabled` | INTEGER NOT NULL CHECK(enabled IN (0,1)) | 0=关闭，1=开启 |
| `created_by` | TEXT NOT NULL | 创建者 |
| `updated_by` | TEXT NOT NULL | 更新者 |
| `created_at` | TEXT NOT NULL | ISO 时间戳 |
| `updated_at` | TEXT NOT NULL | ISO 时间戳 |

主键：`(scope_key, source_type)` — 每个 scope 每个 source_type 只有一条记录。

---

## 7. API 路由清单（按 `knowledge.py` 顺序）

### 7.1 全局检索设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/knowledge/search-settings` | 获取全局检索来源设置 |
| PUT | `/knowledge/search-settings` | 更新全局检索来源设置（仅 admin） |

### 7.2 项目检索设置

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/projects/:projectId/knowledge/search-settings` | 获取项目检索来源设置（含继承语义） |
| PUT | `/projects/:projectId/knowledge/search-settings` | 更新项目检索来源设置（仅 admin） |
| DELETE | `/projects/:projectId/knowledge/search-settings` | 删除项目设置，恢复到全局（仅 admin） |

### 7.3 项目查询

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/projects/:projectId/knowledge/query` | 项目内同步查询 |
| POST | `/projects/:projectId/knowledge/query/stream` | 项目内流式（SSE）查询 |

### 7.4 全部项目查询

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/knowledge/query/stream` | 全部项目流式（SSE）查询 |

### 7.5 全部项目对话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/knowledge/conversations` | 全部项目对话列表 |
| GET | `/knowledge/conversations/:conversationId` | 全部项目对话详情 |
| DELETE | `/knowledge/conversations/:conversationId` | 删除全部项目对话 |

### 7.6 项目对话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/projects/:projectId/knowledge/conversations` | 项目内对话列表 |
| GET | `/projects/:projectId/knowledge/conversations/:conversationId` | 项目内对话详情 |
| DELETE | `/projects/:projectId/knowledge/conversations/:conversationId` | 删除项目内对话 |

实现依据：`apps/backend/app/api/v1/knowledge.py`

---

## 8. 前端页面清单

| 路由 | 组件 | Tab | 说明 |
| --- | --- | --- | --- |
| `/knowledge` | `knowledge/page.tsx` | — | 知识库统一入口页 |
| — | `ProjectKnowledgeWorkspace`（内联组件） | 知识库问答 | 流式对话、快捷问题、模型选择、历史管理 |
| — | `CompanyKnowledgeVault`（内联组件） | 公司知识库 | 目录树 + Markdown 预览（完整 CRUD） |
| — | `KnowledgeSearchSettings` | 检索设置 | 5 种来源开关、全局/项目切换 |

关键子组件（均在 `knowledge/page.tsx` 内）：
- `ProjectKnowledgeWorkspace`：对话主体（消息列表 + 输入框 + 快捷按钮）
- `KnowledgeChatTopControls`：新建对话 / 深度思考 / 展开历史
- `ChatMessage`：消息渲染（含思考展开详情）
- `CompanyKnowledgeVault`：公司知识库目录 + 预览
- `CompanyTreeNode`：目录树递归节点

---

## 9. 验收规则

| ID | 验收内容 | 核对依据路径 |
| --- | --- | --- |
| AC-01 | `/knowledge` 三个 Tab 均正常切换，内容正确 | `apps/frontend/src/app/(main)/knowledge/page.tsx:1171-1304` |
| AC-02 | 发起流式查询，事件依次出现 `message_delta → metadata → done` | `apps/frontend/src/app/(main)/knowledge/page.tsx:720-781` |
| AC-03 | 关闭 `company_knowledge` 后，回答引用中不含公司知识库文档；操作日志 `company_knowledge_files` 为空 | `apps/backend/app/services/knowledge/service.py:635-670` |
| AC-04 | 把项目级 `test_cases` 关闭并保留全局 `test_cases` 开启，项目内查询不应包含用例上下文 | `apps/backend/app/services/knowledge/service.py:628-629` |
| AC-05 | 管理员修改全局检索设置后，未自定义的项目查询立刻反映新设置（继承语义） | `apps/backend/app/services/knowledge/service.py:62-87` |
| AC-06 | 把项目设置改回全局值后（DELETE），项目内查询回到全局默认 | `apps/backend/app/services/knowledge/service.py:121-126` |
| AC-07 | 管理员以外角色 PUT 设置返回 403 `KNOWLEDGE_SEARCH_SETTINGS_FORBIDDEN` | `apps/backend/app/services/knowledge/service.py:138-140` |
| AC-08 | 对话历史持久化，刷新页面后仍可加载；删除对话后列表已移除 | `apps/frontend/src/app/(main)/knowledge/page.tsx:504-578` |
| AC-09 | `show_thinking=true` 时，Assistant 消息出现可折叠思考详情 | `apps/frontend/src/app/(main)/knowledge/page.tsx:733-751` |
| AC-10 | 快捷问题（查需求/看探索/查来源/看模块）点击后自动填入输入框 | `apps/frontend/src/app/(main)/knowledge/page.tsx:1735-1748` |
| AC-11 | 查询模型选择（`knowledge_query` capability）正常加载和保存 | `apps/frontend/src/app/(main)/knowledge/page.tsx:406-447` |
| AC-12 | 阻塞状态（所有来源无内容）：返回 blocker 列表而非调用 Agent | `apps/backend/app/services/knowledge/service.py:224-229` |
| AC-13 | 上传到公司知识库的 `.docx` 转换失败时，该文件不作为检索来源出现 | `apps/backend/app/services/knowledge/service.py:649`（`conversion_status` 过滤） |
| AC-14 | `__all_projects__` 虚拟项目不显示在项目列表（status=archived） | `apps/backend/app/seed/seeds.py:911-915` |
| AC-15 | 全部项目查询收集所有可见项目的来源 | `apps/backend/app/services/knowledge/service.py:548-564` |

---

## 10. 未实现 / 缺口清单

以下功能在旧 PRD 中描述或 PRD 其他章节提及，但**当前代码中无前端入口**，记录于此以便后续补充：

| 缺口 | 描述 | 相关 PRD 章节 |
| --- | --- | --- |
| 知识库状态三态展示 | 知识库"构建中 / 阻塞 / 已发布"三态目前无独立前端状态页；blocker 消息以内联文本形式出现在查询结果中 | §1.3（本文） |
| 阻塞清单展示页 | 阻塞页应展示阻塞清单、来源位置、影响范围、建议动作、AI 协助处理入口；当前仅有 blocker 消息文本 | §1.3、PRD 00-12 |
| 知识图谱 | 文档 12.5 提及知识图谱，当前无实现 | PRD 00-12 §12.5 |
| Wiki 健康状态展示 | 文档 12.1 提及 Wiki 健康状态展示，当前无前端入口 | PRD 00-12 §12.1 |
| 版本变化日志入口 | 文档 12.1 提及版本变化日志入口，当前无前端入口 | PRD 00-12 §12.1 |
| 同步查询（非流式） | `POST /projects/:projectId/knowledge/query` 已实现，但前端当前仅使用流式接口 | `apps/backend/app/api/v1/knowledge.py:46-52` |

---

## 11. 已知不实现项

以下能力在旧 PRD 中描述，但本仓库代码已删除或从未实现，**不应在评审中描述为已上线**：

- 项目知识库自动构建 / 版本化 / 章节级 diff
- "llm-wiki / Raw Sources / Wiki Layer / Schema Layer" 三层结构
- 知识库健康检查 / lint 调度器
- 知识库导入向导（OCR/PDF/Confluence 同步等）
- 知识库可视化目录树
- 项目工作稿中间层（已下线，当前直接读取 `documents.current_version_id` 对应版本）

---

## 12. 实现依据（精确路径）

| 类别 | 路径 |
| --- | --- |
| 后端服务 | `apps/backend/app/services/knowledge/service.py`（核心） |
| 后端 Agent | `apps/backend/app/agents/knowledge/service.py`、`apps/backend/app/agents/knowledge/agent.py` |
| 后端 Schema | `apps/backend/app/schemas/knowledge.py` |
| 后端路由 | `apps/backend/app/api/v1/knowledge.py` |
| 后端种子数据 | `apps/backend/app/seed/seeds.py:907-916`（`__all_projects__` 虚拟项目） |
| 数据库 Schema | `apps/backend/app/seed/schema.py`（`knowledge_conversations`、`knowledge_conversation_messages`、`knowledge_search_source_settings`、`global_knowledge_bases`、`global_knowledge_folders`、`global_knowledge_vault_files` 表） |
| 前端页面 | `apps/frontend/src/app/(main)/knowledge/page.tsx` |
| 前端检索设置组件 | `apps/frontend/src/components/ai-testing/knowledge-search-settings.tsx` |
| 前端 API 客户端 | `apps/frontend/src/lib/api-client.ts`（`knowledge.*` 命名空间） |
