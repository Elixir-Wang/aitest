# 00-22 AI 测试系统 · 全局知识库 PRD

> 范围声明：本文档描述 AI 测试系统的**全局知识库（公司知识库）**功能——独立于项目的跨项目可复用素材库，由管理员上传与管理，向所有项目作为检索来源开放。
>
> 术语说明：在本系统中，**公司知识库** = **全局知识库** = **Global Knowledge Vault**，底层路由前缀为 `/global-knowledge`（OpenAPI tag `global-knowledge`），前端在 `/knowledge` 页面"公司知识库" Tab 内展示。

> 不在本文档范围：项目内知识检索会话（PRD 00-05）、对话历史（PRD 00-05）、非 Markdown 格式自动转换。

---

## 0. 事实源

- **基线日期**：2026-07-26
- **事实源路径**：

| 层级 | 路径 |
| --- | --- |
| 前端页面 | `apps/frontend/src/app/(main)/knowledge/page.tsx`（公司知识库 Tab） |
| 前端组件 | `apps/frontend/src/components/ai-testing/knowledge-search-settings.tsx`（`company_knowledge` 来源配置） |
| 后端路由 | `apps/backend/app/api/v1/global_knowledge.py` |
| 后端服务 | `apps/backend/app/services/knowledge/global_service.py` |
| 后端仓库 | `apps/backend/app/repositories/global_knowledge_repo.py` |
| 数据库 Schema | `apps/backend/app/seed/schema.py`（`global_knowledge_bases` / `global_knowledge_folders` / `global_knowledge_vault_files`） |

---

## 1. 范围与目标

### 1.1 目标

- 提供一个跨项目可用的"通用知识"容器，让规范、模板、最佳实践等内容被多个项目复用
- 让知识问答 Agent 能把全局知识作为 5 个检索来源之一（`company_knowledge`），无需重复生产
- 在权限上把"写"收敛到 admin，避免普通用户误改公司级内容

### 1.2 与项目知识库的关系

- **独立存储**：全局知识库与项目知识库（PRD 00-05）在数据库层面完全独立，共用 `global_knowledge_bases` 系列表，不与项目表关联
- **跨项目复用**：同一份全局知识可被所有项目通过检索来源开关（`company_knowledge`）引用
- **检索来源对接**：在 `knowledge-search-settings.tsx` 中，`company_knowledge` 来源类型对应遍历所有全局知识库的 Markdown 文件，作为项目/全部项目知识问答的上下文来源之一

### 1.3 边界

- 不存储项目特有需求（进 PRD 00-05 需求文档）
- 不做章节级 diff / 版本化：文件仅保存当前版本，旧版本不可回溯
- 不做富文本自动转换：仅接受 `.md` 文件上传
- 不复用项目需求上传接口：全局知识库使用独立接口 `/global-knowledge/...`

---

## 2. 数据模型

### 2.1 `global_knowledge_bases`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | TEXT | PRIMARY KEY | 格式 `gkb-<hex8>` |
| `name` | TEXT | NOT NULL, UNIQUE | 知识库名称，全局唯一 |
| `description` | TEXT | NOT NULL DEFAULT '' | 描述 |
| `status` | TEXT | NOT NULL, CHECK IN ('processing', 'available', 'conversion_failed') | 状态，当前仅在序列化中提供 |
| `root_folder_id` | TEXT | | 根文件夹 ID |
| `created_by` | TEXT | NOT NULL | 创建者用户 ID |
| `created_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |

### 2.2 `global_knowledge_folders`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | TEXT | PRIMARY KEY | 格式 `gkfld-<hex8>` |
| `knowledge_base_id` | TEXT | NOT NULL, FK → global_knowledge_bases(id) ON DELETE CASCADE | 所属知识库 |
| `parent_id` | TEXT | FK → global_knowledge_folders(id) ON DELETE CASCADE | 父文件夹，NULL 表示根文件夹 |
| `name` | TEXT | NOT NULL | 文件夹名称 |
| `sort_order` | INTEGER | NOT NULL DEFAULT 0 | 排序权重 |
| `created_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |

**索引与约束**：

- `UNIQUE(knowledge_base_id, parent_id, name)`：同级目录下文件夹名唯一
- **部分唯一索引** `idx_global_knowledge_root_folder_name(knowledge_base_id, name) WHERE parent_id IS NULL`：根文件夹名在知识库内唯一（同一知识库内不能有两个同名根文件夹）
- `FOREIGN KEY(knowledge_base_id) REFERENCES global_knowledge_bases(id) ON DELETE CASCADE`
- `FOREIGN KEY(parent_id) REFERENCES global_knowledge_folders(id) ON DELETE CASCADE`

### 2.3 `global_knowledge_vault_files`

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | TEXT | PRIMARY KEY | 格式 `gkfile-<hex8>` |
| `knowledge_base_id` | TEXT | NOT NULL, FK → global_knowledge_bases(id) ON DELETE CASCADE | 所属知识库 |
| `folder_id` | TEXT | NOT NULL, FK → global_knowledge_folders(id) ON DELETE CASCADE | 所属文件夹 |
| `original_filename` | TEXT | NOT NULL | 上传时的原始文件名 |
| `display_name` | TEXT | NOT NULL | 显示名称 |
| `file_type` | TEXT | NOT NULL DEFAULT '' | 文件类型后缀 |
| `file_size` | INTEGER | NOT NULL DEFAULT 0 | 文件大小（字节） |
| `raw_path` | TEXT | NOT NULL DEFAULT '' | 原始文件存储路径 |
| `markdown_path` | TEXT | NOT NULL DEFAULT '' | Markdown 文件存储路径 |
| `markdown_content` | TEXT | NOT NULL DEFAULT '' | Markdown 正文内容 |
| `conversion_status` | TEXT | NOT NULL, CHECK IN ('queued', 'running', 'success', 'failed') | 转换状态，当前上传 `.md` 直接为 `success` |
| `conversion_summary` | TEXT | NOT NULL DEFAULT '' | 转换摘要 |
| `sort_order` | INTEGER | NOT NULL DEFAULT 0 | 排序权重 |
| `created_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |
| `updated_at` | TEXT | NOT NULL DEFAULT CURRENT_TIMESTAMP | |

**索引与约束**：

- `UNIQUE(folder_id, display_name)`：同一文件夹下文件名唯一
- `FOREIGN KEY(knowledge_base_id) REFERENCES global_knowledge_bases(id) ON DELETE CASCADE`
- `FOREIGN KEY(folder_id) REFERENCES global_knowledge_folders(id) ON DELETE CASCADE`

### 2.4 附加索引

| 索引名 | 表 | 字段 | 说明 |
| --- | --- | --- | --- |
| `idx_global_knowledge_bases_updated` | `global_knowledge_bases` | `updated_at` | 按更新时间排序 |
| `idx_global_knowledge_folders_base_parent` | `global_knowledge_folders` | `knowledge_base_id, parent_id, sort_order` | 按知识库+父文件夹+排序查询 |
| `idx_global_knowledge_vault_files_folder` | `global_knowledge_vault_files` | `folder_id, sort_order, display_name` | 按文件夹+排序查询 |

> 实现依据：`apps/backend/app/seed/schema.py`

---

## 3. API 路由清单

路由前缀：`/api/v1/global-knowledge`，由 `apps/backend/app/api/v1/global_knowledge.py` 注册。

| # | 方法 | 路径 | 角色 | 说明 |
| --- | --- | --- | --- | --- |
| 1 | GET | `/global-knowledge/bases` | any | 列出全部知识库，支持 `keyword` 过滤 |
| 2 | POST | `/global-knowledge/bases` | admin | 创建知识库，自动创建同名根文件夹 |
| 3 | PATCH | `/global-knowledge/bases/:base_id` | admin | 更新知识库名称/描述，同步根文件夹名 |
| 4 | GET | `/global-knowledge/bases/:base_id/tree` | any | 获取知识库树视图（文件夹+文件嵌套结构） |
| 5 | DELETE | `/global-knowledge/bases/:base_id` | admin | 删除知识库（含物理目录清理） |
| 6 | POST | `/global-knowledge/bases/:base_id/folders` | admin | 在指定文件夹下创建子文件夹 |
| 7 | POST | `/global-knowledge/bases/:base_id/folders/:folder_id/files` | admin | 上传 Markdown 文件到指定文件夹（多文件 multipart） |
| 8 | GET | `/global-knowledge/bases/:base_id/files/:file_id` | any | 读取文件详情（含 markdown_content） |
| 9 | DELETE | `/global-knowledge/bases/:base_id/files/:file_id` | admin | 删除文件（含物理路径清理） |
| 10 | DELETE | `/global-knowledge/bases/:base_id/folders/:folder_id` | admin | 删除文件夹（级联删除子文件夹+物理目录） |

> 服务层内部方法（非 HTTP 路由）：`upsert_markdown_file(base_id, folder_id, display_name, markdown_content, actor)` — 当同名文件已存在时原子替换，失败时回滚，供内部脚本/Agent 调用。

---

## 4. 功能规格

### 4.1 知识库 CRUD

**列表**（GET `/bases`）

- 返回 `{ items: [...] }`，每项含：id、name、description、status、status_label、root_folder_id、file_count、created_at、updated_at、available_actions
- 支持 `keyword` 参数对 name 和 description 模糊搜索

**创建**（POST `/bases`）

- 校验：name 非空，不重名（`GLOBAL_KNOWLEDGE_BASE_NAME_EXISTS`）
- 自动生成根文件夹（`root_folder_id`，与 base 同名）
- 创建后调用 `_serialize_base` 序列化返回

**更新**（PATCH `/bases/:base_id`）

- 修改 name/description；name 仍须在知识库间唯一
- 同步更新根文件夹名称（`update_folder_name`）

**删除**（DELETE `/bases/:base_id`）

- 仅 admin
- 递归删除物理目录 `global_knowledge_base_dir(base_id)`
- 级联删除数据库记录（文件夹、文件 ON DELETE CASCADE）
- 返回 `{ deleted: true, id: base_id }`

### 4.2 文件夹管理

**创建文件夹**（POST `/bases/:base_id/folders`）

- `parent_id`：指定父文件夹 ID（NULL 为根）
- 校验：name 非空、不能含 `/` 或 `\`、不能仅由点号组成
- 同级目录唯一约束违反时返回 `GLOBAL_KNOWLEDGE_FOLDER_NAME_EXISTS`
- 自动创建物理子目录 `global_knowledge_folder_dir`

**删除文件夹**（DELETE `/bases/:base_id/folders/:folder_id`）

- 仅 admin；不允许删除根文件夹（`GLOBAL_KNOWLEDGE_ROOT_FOLDER_DELETE_FORBIDDEN`）
- 递归查询所有子文件夹 ID（CTE `descendant_folder_ids`）
- 批量删除物理目录 + 数据库记录

### 4.3 文件管理

**上传文件**（POST `/bases/:base_id/folders/:folder_id/files`）

- 仅接受 `.md` 格式（`VAULT_UPLOAD_ALLOWED_TYPES = {'md'}`）
- 多文件上传：逐文件串行处理；失败时清理已落盘内容
- 存储路径：
  - 原始文件：`folders/<folder_id>/raw/<file_id>-<safe_name>`
  - Markdown：`folders/<folder_id>/markdown/<file_id>.md`
- `conversion_status` 直接写入 `success`（`.md` 即 Markdown）

**读取文件**（GET `/bases/:base_id/files/:file_id`）

- 返回完整文件信息，含 `markdown_content`、`raw_path`、`markdown_path`
- 物理文件优先读取，缺失时回退 `markdown_content` 字段

**删除文件**（DELETE `/bases/:base_id/files/:file_id`）

- 仅 admin
- 删除 `raw_path` 与 `markdown_path` 两个物理文件（带路径边界校验）
- 删除数据库记录

### 4.4 树视图（GET `/bases/:base_id/tree`）

- 返回 `{ base, root }`，`root` 是完整嵌套结构
- 文件夹节点：`id、type='folder'、name、parent_id、is_root、sort_order、children`
- 文件节点：`id、type='file'、name、display_name、file_type、file_size、conversion_status、sort_order、created_at、updated_at`
- 排序：`sort_order` 升序，再按 `name` 字典序

### 4.5 原子 Upsert（内部方法）

`upsert_markdown_file(base_id, folder_id, display_name, markdown_content, actor)`：

- 同名文件已存在时原子替换（写临时文件 + `os.replace` 原子覆盖）
- 失败时 `_restore_file` 回滚到旧内容
- 用于内部脚本/Agent 批量写入，当前未被 HTTP 路由直接调用

---

## 5. 前端页面清单

**页面路由**：`/knowledge`（`apps/frontend/src/app/(main)/knowledge/page.tsx`）

单页包含三个 Tab（`knowledgeScopes`）：

| Tab | 路由 key | 图标 | 说明 |
| --- | --- | --- | --- |
| 知识库问答 | `project` | FolderKanban | 项目级/全部项目知识问答（PRD 00-05） |
| **公司知识库** | `company` | Building2 | 全局知识库管理 Tab |
| 检索设置 | `settings` | Settings2 | 检索来源配置（含 `company_knowledge` 开关） |

**公司知识库 Tab 内部结构**：

- **列表视图**（`companyView === 'list'`）：Table 展示全部 base，含名称、描述、文件数量、更新时间、操作列（查看/编辑/删除）；Toolbar 支持搜索和新建
- **详情视图**（`companyView === 'detail'`）：
  - 左侧目录树：可展开/折叠、支持按名称搜索、显示文件
  - 右侧主区域：文件预览（MarkdownPreview）或文件夹内容卡片
  - 面包屑导航：base → 文件夹 → 文件
  - 操作：新建文件夹、上传 Markdown、删除

**检索设置组件**：`KnowledgeSearchSettings`（`apps/frontend/src/components/ai-testing/knowledge-search-settings.tsx`），支持配置 `company_knowledge` 来源的开启/关闭。

---

## 6. 与项目知识库的关系

- 全局知识库独立存储于 `global_knowledge_*` 三张表，与项目知识库（需求文档、探索产物）完全隔离
- 在检索设置中开启 `company_knowledge` 来源后，项目/全部项目知识问答可将全局知识作为上下文来源之一
- 关闭 `company_knowledge` 后，检索不再引用全局知识文件
- 全局知识不参与项目知识库的自动构建流程

---

## 7. 验收规则

| # | 验收条件 | 核对依据路径 |
| --- | --- | --- |
| AC-01 | 管理员创建知识库 → 自动产生同名根文件夹；同名知识库创建返回 `GLOBAL_KNOWLEDGE_BASE_NAME_EXISTS` | `global_service.py` create_base → `global_knowledge_repo.py` create_base + create_folder |
| AC-02 | 同名根文件夹禁止创建（`idx_global_knowledge_root_folder_name` 部分唯一索引） | `schema.py` CREATE UNIQUE INDEX ... WHERE parent_id IS NULL |
| AC-03 | 同一文件夹下禁止同名文件（`UNIQUE(folder_id, display_name)`） | `schema.py` `global_knowledge_vault_files` UNIQUE 约束；`global_service.py` `_save_vault_file` 捕获 UNIQUE 异常 |
| AC-04 | 非 admin 用户调用写接口返回 403 | `global_service.py` `_require_admin`；`global_knowledge.py` 所有写路由均依赖此校验 |
| AC-05 | 上传 `.md` 成功；上传非 `.md` 文件返回 `GLOBAL_KNOWLEDGE_FILE_TYPE_NOT_ALLOWED` | `global_service.py` `_validate_vault_upload_filename`；前端 `CompanyUploadDialog` 仅接受 `.md/.markdown` |
| AC-06 | 上传同名文件返回 `GLOBAL_KNOWLEDGE_FILE_NAME_EXISTS` | `global_service.py` `_save_vault_file` 捕获 UNIQUE 异常 |
| AC-07 | 删除根文件夹返回 `GLOBAL_KNOWLEDGE_ROOT_FOLDER_DELETE_FORBIDDEN` | `global_service.py` `delete_folder` 校验 `folder_id == base['root_folder_id']` |
| AC-08 | 删除知识库同步清理物理目录 | `global_service.py` `delete_base` 调用 `shutil.rmtree(global_knowledge_base_dir(base_id))` |
| AC-09 | 任意登录用户可读取文件（GET 接口无需 admin） | `global_knowledge.py` GET 路由无 `_require_admin` 调用 |
| AC-10 | 检索设置中 `company_knowledge` 来源可独立开关，影响项目知识问答的上下文来源 | `knowledge-search-settings.tsx` `sourceDefinitions` 包含 `company_knowledge`；`knowledge/page.tsx` 渲染 `KnowledgeSearchSettings` |
| AC-11 | 公司知识库 Tab 列表支持按名称/描述关键字搜索 | `knowledge/page.tsx` `filteredCompanyRows` 过滤逻辑；`global_knowledge.py` GET `/bases` 支持 `keyword` 参数 |
| AC-12 | 文件夹树支持展开/折叠/搜索；上传 Markdown 后刷新树视图 | `knowledge/page.tsx` `CompanyTreeNode` + `CompanyKnowledgeVault` 组件；`openFolderUpload` → `refreshCompanyTree` |
