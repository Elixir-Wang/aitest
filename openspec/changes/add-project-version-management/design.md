## Context

当前 `projects` 表不保存版本信息，`source_documents` 只通过 `project_id` 归属项目。系统已有的 `source_document_versions` 表用于保存同一需求文档的内容修订历史，其 `version_no` 是递增序号，不能承担项目发布版本语义。

本变更跨越数据库迁移、项目服务、需求上传与编辑、API 和项目内前端导航。当前数据库为 SQLite，应用通过 `app.seed.schema` 建立规范 schema，并通过 `app.seed.seeds` 中的幂等迁移兼容存量数据库。项目更新权限目前由管理员承担，项目版本维护沿用这一权限边界。

## Goals / Non-Goals

**Goals:**

- 为每个真实项目建立独立的项目版本集合。
- 保证每个真实项目存在一个显式当前版本，并将其作为新需求的后端默认值。
- 允许需求关联或迁移到同一项目的指定版本。
- 在项目内部提供完整但轻量的版本维护入口。
- 通过约束、事务、审计和幂等迁移保证关联完整性。
- 明确区分项目版本与需求内容修订版本。

**Non-Goals:**

- 不为项目版本增加规划、发布、归档等状态。
- 不实现发布审批、发布说明、迭代燃尽或版本冻结流程。
- 不提供跨项目或全局版本管理页面。
- 不允许一个需求同时关联多个项目版本；跨版本交付的需求应迁移或拆分。
- 不改变现有需求内容版本、需求分析和文件追加机制。
- 第一阶段不为历史测试集、自动化资产或执行报告补充项目版本快照；这些资产继续通过需求关联工作，后续需要版本化报告时另行设计不可变快照。

## Decisions

### 1. 使用独立项目版本实体

新增 `project_versions`，而不是在 `projects` 上保存自由文本版本号，也不复用 `source_document_versions`。

建议字段：

```text
project_versions
  id                  TEXT PRIMARY KEY
  project_id          TEXT NOT NULL
  version             TEXT NOT NULL
  version_major       INTEGER NOT NULL
  version_minor       INTEGER NOT NULL
  version_patch       INTEGER NOT NULL
  name                TEXT NOT NULL DEFAULT ''
  description         TEXT NOT NULL DEFAULT ''
  planned_release_at  TEXT NULL
  created_by          TEXT NOT NULL
  created_at          TEXT NOT NULL
  updated_at          TEXT NOT NULL
```

数据库 SHALL 对 `(project_id, version)` 建立唯一约束，并对 `project_id`、版本数字分量建立查询索引。`source_documents.project_version_id` 引用 `project_versions.id`，删除策略为限制删除。

选择独立实体是因为一个项目存在多个版本，而每个版本还需要名称、说明、计划日期、需求数量和审计信息。自由文本字段无法保证唯一性和引用完整性。

### 2. 项目保存显式当前版本引用

在 `projects` 增加 `default_version_id`。产品界面使用“当前版本”这一名称，API 和数据库继续使用 `default_version_id`，表达其作为新需求默认值的用途。

不得使用字符串最大值、创建时间或语义版本最大值动态推断当前版本。例如先创建 `2.0.0` 后补建 `1.5.1` 时，业务默认值仍应由用户选择决定。

项目创建事务按以下顺序执行：

1. 创建项目。
2. 创建项目的 `1.0.0`。
3. 将 `projects.default_version_id` 指向该版本。
4. 提交事务。

真实项目在事务提交后 MUST 存在当前版本。系统保留项目 `__all_projects__` 不参与该约束。

### 3. 版本号限定为三段式语义版本

第一阶段只接受 `MAJOR.MINOR.PATCH`，例如 `1.0.0`、`1.12.3`。不接受 `v1.0.0`、两段版本、预发布标记或构建元数据。

后端使用统一解析函数校验并提取三个非负整数分量。每个分量禁止无意义前导零，版本列表按 `major`、`minor`、`patch` 降序排列。前端校验只用于即时反馈，后端校验是最终约束。

保存数字分量而不是在查询中拆分字符串，可以避免 SQLite 字符串排序将 `1.10.0` 排在 `1.9.0` 之前或之后的不确定实现。

### 4. 版本标识创建后不可修改

版本创建后，`version` 及其数字分量不可通过更新 API 修改。管理员可以编辑名称、说明和计划发布日期。

如果未被需求引用且不是当前版本，用户可以删除并重新创建错误版本号。该规则避免版本号修改后审计记录、书签和外部引用改变含义。

### 5. 新版本默认切换为当前版本

创建版本请求包含 `set_as_default`，默认值为 `true`。创建和切换当前版本在同一事务内完成。

该设计满足“新需求默认关联最新创建版本”的常见体验，同时保留创建未来版本但暂不切换默认值的能力。API 响应明确返回 `is_default`，前端不得仅根据列表第一项判断。

### 6. 需求关联由后端补全和校验

`source_documents` 增加 `project_version_id`。新建需求时：

- 请求未提供 `project_version_id` 时，后端读取项目的 `default_version_id`。
- 请求提供版本 ID 时，后端校验版本属于当前 `project_id`。
- 项目不存在当前版本、版本不存在或版本跨项目时，后端拒绝创建。
- 追加文件模式沿用已有需求的项目版本，不接收新的版本选择。

需求基础信息更新可以修改 `project_version_id`，但目标版本必须属于同一项目。迁移不创建新的需求内容版本，因为它改变的是需求元数据归属，不是需求正文；迁移必须记录变更前后版本到操作日志。

### 7. 删除采用引用保护而不是级联删除

版本删除必须同时满足：

- 版本属于当前项目。
- 版本不是项目当前版本。
- 没有任何需求引用该版本。

不满足条件时返回稳定的冲突错误。不得把需求级联删除或自动迁移到其他版本。项目删除仍可通过项目级联删除其版本，因为项目删除已有独立的资产保护规则。

### 8. 版本只在项目作用域维护

新增项目内路由 `/projects/{projectId}/versions`，并在项目导航中增加“版本管理”页签。不存在 `/versions` 全局管理页面。

页面展示版本号、名称、需求数量、计划发布日期、创建时间和当前版本标记，提供：

- 创建版本。
- 编辑版本元数据。
- 设为当前版本。
- 查看该版本需求。
- 删除符合条件的空版本。

普通可见项目用户可以读取版本；创建、编辑、切换当前版本和删除沿用项目管理权限，仅管理员可执行。

### 9. 需求列表展示所属版本

需求列表和详情序列化增加简要对象：

```json
{
  "project_version": {
    "id": "pver-...",
    "version": "1.1.0",
    "name": "会员能力升级",
    "is_default": true
  }
}
```

项目范围需求页展示全部版本的需求，不提供版本切换器；“所属版本”列仅显示版本号，不拼接版本名称。新建需求表单仍默认选中当前版本并允许改选。

### 10. API 使用项目嵌套路由

项目版本 API：

```text
GET    /projects/{project_id}/versions
POST   /projects/{project_id}/versions
PATCH  /projects/{project_id}/versions/{version_id}
DELETE /projects/{project_id}/versions/{version_id}
POST   /projects/{project_id}/versions/{version_id}/set-default
```

创建请求：

```json
{
  "version": "1.1.0",
  "name": "会员能力升级",
  "description": "",
  "planned_release_at": null,
  "set_as_default": true
}
```

更新请求不包含 `version`。设置当前版本使用独立命令端点，以便集中执行权限、项目归属、事务和审计逻辑。

建议稳定错误码：

```text
PROJECT_VERSION_INVALID
PROJECT_VERSION_EXISTS
PROJECT_VERSION_NOT_FOUND
PROJECT_VERSION_PROJECT_MISMATCH
PROJECT_DEFAULT_VERSION_MISSING
PROJECT_VERSION_IS_DEFAULT
PROJECT_VERSION_IN_USE
```

### 11. 所有版本变更进入操作日志

版本创建、编辑、设为当前版本、删除和需求迁移均复用现有 `operation_log_service.record_change`。日志记录项目、版本 ID、展示版本号、操作者以及必要的 before/after，不新增平行审计系统。

## Risks / Trade-offs

- [项目与版本形成相互引用，迁移时可能暂时为空] → 新增字段先允许空值，迁移事务完成回填后执行完整性校验；业务服务保证真实项目提交后始终存在当前版本。
- [SQLite 无法直接把新增列改为 NOT NULL] → 规范 schema 对新数据库声明最终约束，存量迁移采用可恢复的表重建或应用不变量，并运行 `foreign_key_check` 与空值检查。
- [并发创建相同版本] → 依赖数据库唯一约束兜底，并把冲突转换为稳定业务错误。
- [并发切换当前版本] → 使用单事务更新项目指针，最终只存在一个引用值，不维护冗余 `is_default` 标志。
- [删除版本时出现检查后写入竞态] → 引用外键使用限制删除，服务层预检仅用于友好错误，数据库约束负责最终一致性。
- [没有版本状态，历史版本仍可被新需求选择] → 这是本次明确的轻量化产品决策；用户通过当前版本获得默认值，手动选择仍允许关联任意现存版本。
- [需求迁移会改变通过需求动态推导的版本归属] → 第一阶段通过操作日志保留变更历史；不可变测试资产版本快照作为后续独立能力设计。

## Migration Plan

1. 在规范 schema 中增加 `project_versions`、项目当前版本引用、需求项目版本引用和必要索引。
2. 在系统迁移入口增加幂等迁移函数，检测表和列是否已存在。
3. 对每个非保留项目按 `(project_id, '1.0.0')` 查找或创建初始版本。
4. 将缺少当前版本的项目指向其 `1.0.0`。
5. 将 `project_version_id` 为空的历史需求关联到所属项目的 `1.0.0`。
6. 校验不存在跨项目需求版本引用、真实项目缺少当前版本或需求缺少版本的情况。
7. 执行 SQLite `PRAGMA foreign_key_check`，有违规时中止启动并报告具体表和记录。
8. 发布后先验证版本列表和需求默认关联，再开放版本写操作。

迁移必须可重复执行。回滚应用版本时保留新增表和字段，旧代码忽略这些字段；不得在自动回滚中删除版本或清空需求关联。

## Open Questions

无。第一阶段的产品边界已经确定：版本无状态、仅项目内维护、单需求单版本、新建版本默认成为当前版本。
