# Project Version Management Specification

## ADDED Requirements

### Requirement: Project version bootstrap

系统 SHALL 为每个真实项目维护至少一个项目版本和一个显式当前版本，系统保留项目不参与该规则。

#### Scenario: New project is created

- **WHEN** 管理员创建一个新项目
- **THEN** 系统 SHALL 在同一事务内创建版本 `1.0.0`
- **AND** SHALL 将 `1.0.0` 设置为该项目当前版本
- **AND** 项目创建成功响应 SHALL 包含当前版本摘要

#### Scenario: Project bootstrap transaction fails

- **WHEN** 项目、初始版本或当前版本引用中的任一步骤失败
- **THEN** 系统 SHALL 回滚整个项目创建事务
- **AND** SHALL NOT 留下没有当前版本的真实项目

### Requirement: Idempotent legacy migration

系统 SHALL 在首次迁移时为存量真实项目建立 `1.0.0`，并将历史需求关联到所属项目的该版本。

#### Scenario: Existing project has no project version

- **GIVEN** 存量项目尚无项目版本
- **WHEN** 系统执行版本迁移
- **THEN** 系统 SHALL 创建唯一的 `1.0.0`
- **AND** SHALL 将其设置为项目当前版本
- **AND** SHALL 将项目内未关联版本的历史需求关联到该版本

#### Scenario: Migration runs more than once

- **GIVEN** 项目已经存在 `1.0.0` 且历史需求已经完成关联
- **WHEN** 系统再次执行同一迁移
- **THEN** 系统 SHALL NOT 创建重复版本
- **AND** SHALL NOT 改写已有有效版本关联

#### Scenario: Reserved project is encountered

- **WHEN** 迁移扫描到系统保留项目 `__all_projects__`
- **THEN** 系统 SHALL 跳过该项目
- **AND** SHALL NOT 为其创建项目版本

### Requirement: Project-scoped version listing

系统 SHALL 仅在项目作用域内提供版本读取和维护能力，不提供全局版本管理入口。

#### Scenario: User views project versions

- **GIVEN** 用户对项目具有可见权限
- **WHEN** 用户进入项目内的版本管理页面
- **THEN** 系统 SHALL 返回且仅返回该项目的版本
- **AND** SHALL 按语义版本数字分量降序排列
- **AND** SHALL 标识当前版本及每个版本的需求数量

#### Scenario: User attempts cross-project access

- **WHEN** 用户通过项目 A 的版本接口请求项目 B 的版本 ID
- **THEN** 系统 SHALL 拒绝该请求
- **AND** SHALL NOT 返回或修改项目 B 的版本数据

#### Scenario: User looks for global version management

- **WHEN** 用户访问系统全局导航
- **THEN** 系统 SHALL NOT 提供全局版本管理入口
- **AND** 版本创建和维护 SHALL 仅出现在具体项目内

### Requirement: Project version creation

系统 SHALL 允许项目管理员创建三段式项目版本，并保证同一项目内版本号唯一。

#### Scenario: Valid version is created

- **GIVEN** 管理员输入当前项目中不存在的合法版本号 `1.1.0`
- **WHEN** 管理员提交创建请求
- **THEN** 系统 SHALL 创建该项目版本
- **AND** SHALL 保存名称、说明和可选计划发布日期

#### Scenario: New version uses default behavior

- **WHEN** 管理员创建版本且未显式传入 `set_as_default`
- **THEN** 系统 SHALL 将 `set_as_default` 视为 `true`
- **AND** SHALL 在同一事务内把新版本设置为项目当前版本

#### Scenario: New version does not become current

- **WHEN** 管理员创建版本并明确设置 `set_as_default` 为 `false`
- **THEN** 系统 SHALL 创建版本
- **AND** SHALL 保持项目原当前版本不变

#### Scenario: Duplicate project version

- **GIVEN** 当前项目已经存在 `1.1.0`
- **WHEN** 管理员再次创建 `1.1.0`
- **THEN** 系统 SHALL 拒绝请求并返回稳定的版本重复错误
- **AND** SHALL NOT 创建第二条版本记录

### Requirement: Project version format

系统 MUST 只接受无前缀的 `MAJOR.MINOR.PATCH` 三段式版本号，并按数字语义处理各分量。

#### Scenario: Valid semantic version core

- **WHEN** 用户提交 `0.1.0`、`1.0.0` 或 `12.34.56`
- **THEN** 系统 SHALL 接受版本格式
- **AND** SHALL 保存对应的主版本、次版本和修订版本数字分量

#### Scenario: Unsupported version format

- **WHEN** 用户提交 `v1.0.0`、`1.0`、`1.0.0-beta`、负数分量或包含无意义前导零的版本号
- **THEN** 系统 SHALL 拒绝请求并返回稳定的版本格式错误
- **AND** SHALL NOT 自动修正或猜测用户意图

#### Scenario: Numeric version ordering

- **GIVEN** 项目同时存在 `1.9.0` 和 `1.10.0`
- **WHEN** 系统返回版本列表
- **THEN** `1.10.0` SHALL 排在 `1.9.0` 之前

### Requirement: Current project version

系统 SHALL 通过项目保存的显式版本引用确定当前版本，不得动态推断。

#### Scenario: Administrator changes current version

- **GIVEN** 目标版本属于当前项目
- **WHEN** 管理员执行设为当前版本操作
- **THEN** 系统 SHALL 原子更新项目当前版本引用
- **AND** SHALL 在操作日志记录变更前后版本

#### Scenario: Version with highest number is not current

- **GIVEN** 项目当前版本为 `1.5.1` 且同时存在 `2.0.0`
- **WHEN** 系统创建需求或展示当前版本
- **THEN** 系统 SHALL 使用显式指定的 `1.5.1`
- **AND** SHALL NOT 因 `2.0.0` 数值更大而自动切换

#### Scenario: Target version belongs to another project

- **WHEN** 管理员尝试将其他项目的版本设为当前版本
- **THEN** 系统 SHALL 拒绝操作
- **AND** 项目当前版本 SHALL 保持不变

### Requirement: Project version maintenance

系统 SHALL 允许项目管理员编辑版本元数据，但不得修改已经创建的版本标识。

#### Scenario: Version metadata is updated

- **WHEN** 管理员修改版本名称、说明或计划发布日期
- **THEN** 系统 SHALL 保存元数据变更
- **AND** SHALL 保持版本号和数字分量不变
- **AND** SHALL 记录操作日志

#### Scenario: Version identifier update is attempted

- **WHEN** 更新请求尝试修改版本号
- **THEN** 系统 SHALL 拒绝该字段或拒绝请求
- **AND** 已有版本标识 SHALL 保持不变

#### Scenario: Non-administrator attempts maintenance

- **WHEN** 非管理员用户尝试创建、编辑、删除版本或切换当前版本
- **THEN** 系统 SHALL 拒绝写操作
- **AND** 仍可按项目可见权限读取版本列表

### Requirement: Safe project version deletion

系统 SHALL 只允许删除非当前且未被任何需求引用的项目版本。

#### Scenario: Empty non-current version is deleted

- **GIVEN** 版本不是当前版本且需求数量为零
- **WHEN** 管理员确认删除
- **THEN** 系统 SHALL 删除该版本
- **AND** SHALL 记录删除操作日志

#### Scenario: Current version deletion is attempted

- **GIVEN** 目标版本是项目当前版本
- **WHEN** 管理员尝试删除该版本
- **THEN** 系统 SHALL 返回版本为当前版本的冲突错误
- **AND** SHALL 要求先选择其他当前版本

#### Scenario: Referenced version deletion is attempted

- **GIVEN** 至少一个需求关联目标版本
- **WHEN** 管理员尝试删除该版本
- **THEN** 系统 SHALL 返回版本正在使用的冲突错误
- **AND** SHALL NOT 删除版本或关联需求

### Requirement: Requirement project version association

系统 SHALL 要求每个真实项目中的需求关联该项目的一个项目版本。

#### Scenario: New requirement omits version

- **GIVEN** 项目存在有效当前版本
- **WHEN** 用户新建需求且未提供 `project_version_id`
- **THEN** 后端 SHALL 自动关联项目当前版本
- **AND** 创建响应 SHALL 返回关联版本摘要

#### Scenario: User selects another project version

- **GIVEN** 用户在新建需求页面选择当前项目的非当前版本
- **WHEN** 用户提交需求
- **THEN** 系统 SHALL 关联用户选择的版本
- **AND** SHALL NOT 强制改回项目当前版本

#### Scenario: Requirement version belongs to another project

- **WHEN** 新建或更新需求请求提供其他项目的版本 ID
- **THEN** 系统 SHALL 拒绝请求
- **AND** SHALL NOT 创建或修改需求

#### Scenario: Project has no current version

- **WHEN** 新建需求未指定版本且项目异常缺少当前版本
- **THEN** 系统 SHALL 拒绝创建并返回当前版本缺失错误
- **AND** SHALL NOT 创建无版本需求

#### Scenario: Files are appended to existing requirement

- **WHEN** 用户为已有需求追加来源文件
- **THEN** 系统 SHALL 保持该需求原项目版本关联
- **AND** SHALL NOT 在追加文件流程要求或接受新的版本选择

### Requirement: Requirement version reassignment

系统 SHALL 允许有权限的用户将需求迁移到同一项目的其他版本，并保留审计记录。

#### Scenario: Requirement is moved to another version

- **GIVEN** 来源版本和目标版本属于同一项目
- **WHEN** 用户确认修改需求所属版本
- **THEN** 系统 SHALL 更新需求的 `project_version_id`
- **AND** SHALL 在操作日志保存来源版本和目标版本
- **AND** SHALL NOT 创建新的需求内容修订版本

#### Scenario: Reassignment target is unchanged

- **WHEN** 用户提交的目标版本与需求当前版本相同
- **THEN** 系统 SHALL 保持需求关联不变
- **AND** SHALL NOT 生成误导性的迁移日志

### Requirement: Requirement version presentation and filtering

系统 SHALL 在需求列表和详情中展示所属项目版本，并允许项目需求列表按版本进行服务端筛选。

#### Scenario: Requirement list is opened

- **WHEN** 用户打开项目需求列表
- **THEN** 系统 SHALL 展示每个需求的版本号及可选版本名称
- **AND** 默认 SHALL 展示全部项目版本的需求

#### Scenario: User filters by project version

- **GIVEN** 用户选择当前项目的一个版本
- **WHEN** 前端请求需求列表
- **THEN** 后端 SHALL 在数据查询层只返回关联该版本的需求
- **AND** 前端 SHALL 展示当前筛选条件

#### Scenario: Invalid filter version is supplied

- **WHEN** 需求列表筛选参数引用不存在或属于其他项目的版本
- **THEN** 系统 SHALL 拒绝筛选请求
- **AND** SHALL NOT 泄露其他项目的版本或需求数据

#### Scenario: New requirement form is opened

- **WHEN** 用户在项目内打开新建需求页面
- **THEN** 系统 SHALL 加载该项目版本下拉列表
- **AND** SHALL 默认选中项目当前版本
- **AND** SHALL 允许用户改选该项目的其他版本

### Requirement: Project and requirement version terminology

系统 SHALL 在 API、界面和文档中区分项目版本与需求内容修订版本。

#### Scenario: Requirement detail contains both version concepts

- **GIVEN** 需求已关联项目版本且存在多个内容修订版本
- **WHEN** 用户查看需求详情
- **THEN** 界面 SHALL 使用“所属版本”表示项目版本
- **AND** SHALL 使用“需求版本”或“修订记录”表示内容修订版本
- **AND** SHALL NOT 使用同一个无上下文的“版本”标签混合两种含义
