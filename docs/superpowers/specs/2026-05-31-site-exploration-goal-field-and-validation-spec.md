# 站点探索目标字段与目标验证规范

## 背景

当前探索任务使用 `description` 承载“探索目标”，例如：

```text
每篇文章内容的超链接和按钮，不能跳转到登陆页面
```

但 `description` 语义过泛，既像备注，也像说明。后端执行器、产物和完成状态没有把它当成必须验证的目标，导致系统可以在完成页面采集后标记 `completed`，但没有证明用户目标已经达成。

本规范要求彻底移除探索任务中 `description` 作为目标字段的职责，改为明确的 `goal` 字段，并为后续目标验证建立数据契约和状态规则。

## 目标

- 将探索任务的“探索目标”字段从 `description` 改为 `goal`。
- 将人工备注从目标语义中拆出，使用 `notes` 表达。
- 后端、前端、报告、YAML 产物统一使用 `goal`。
- 新接口不再返回探索任务级 `description`。
- 为 `goal` 建立目标验证产物 `checks/goal-validation.yaml`。
- 任务完成状态不再只由页面采集决定，必须考虑目标验证结果。

## 非目标

- 不在本规范中实现复杂自然语言理解。
- 不要求第一版支持所有类型目标。
- 不对历史探索产物做全量重写。
- 不改变需求文档、知识库、项目环境等其他业务对象里的 `description` 字段。
- 不把危险按钮、提交按钮、删除按钮等高风险动作强行点击。

## 字段语义

探索任务字段必须按以下语义拆分：

| 字段 | 含义 | 是否参与执行 |
| --- | --- | --- |
| `scope` | 探索范围，决定去哪儿探索 | 是 |
| `forbidden_paths` | 禁止路径，决定不能去哪儿 | 是 |
| `goal` | 探索目标，决定要验证什么 | 是 |
| `notes` | 人工备注或补充说明 | 否 |

示例：

```yaml
scope: 探索全部文章页面
forbidden_paths: ''
goal: 每篇文章内容的超链接和按钮，不能跳转到登陆页面
notes: ''
```

## 数据库改造

### 1. 新表结构

`exploration_runs` 必须包含：

```sql
goal TEXT NOT NULL DEFAULT '',
notes TEXT NOT NULL DEFAULT ''
```

`description` 不再作为探索任务字段保留。

### 2. SQLite 迁移

由于 SQLite 删除列能力受版本影响，推荐使用重建表迁移：

1. 创建 `exploration_runs_new`，字段与现表一致，但删除 `description`，新增 `goal` 和 `notes`。
2. 从旧表拷贝数据：

```sql
goal = COALESCE(description, '')
notes = ''
```

3. 删除旧表。
4. 重命名新表为 `exploration_runs`。
5. 重建索引、外键和约束。

迁移后，历史任务原 `description` 内容应出现在 `goal` 中。

## API 契约

### 创建探索任务

请求：

```json
{
  "environment_id": "env-1",
  "title": "塞伯坦-文档",
  "scope": "探索全部文章页面",
  "forbidden_paths": "",
  "goal": "每篇文章内容的超链接和按钮，不能跳转到登陆页面",
  "notes": ""
}
```

不再接受 `description` 作为探索目标字段。若请求包含 `description`，第一版可直接返回 `400 INVALID_FIELD`，避免继续混用。

### 更新探索任务

请求字段：

```json
{
  "title": "塞伯坦-文档",
  "environment_id": "env-1",
  "scope": "探索全部文章页面",
  "forbidden_paths": "",
  "goal": "每篇文章内容的超链接和按钮，不能跳转到登陆页面",
  "notes": ""
}
```

### 探索任务响应

响应必须返回：

```json
{
  "id": "explore-1",
  "title": "塞伯坦-文档",
  "scope": "探索全部文章页面",
  "forbidden_paths": "",
  "goal": "每篇文章内容的超链接和按钮，不能跳转到登陆页面",
  "notes": ""
}
```

响应中不得返回探索任务级 `description`。

## 后端改造范围

### Schema

修改：

- `ExplorationRunCreateIn.description` -> `goal`
- `ExplorationRunUpdateIn.description` -> `goal`
- `ExplorationRunOut.description` -> `goal`
- 新增 `notes`

### Repository

所有 `exploration_runs` 读写 SQL 替换：

- `description` -> `goal`
- 新增 `notes`

包括：

- 创建探索任务
- 更新探索任务
- 列表查询
- 详情查询
- 启动探索
- 停止探索
- 删除探索

### Serializer

`serialize_exploration_run` 必须输出 `goal` 和 `notes`，不输出 `description`。

### Service

所有业务逻辑从 `run["goal"]` 读取探索目标。

禁止继续使用：

```python
run["description"]
```

表达探索目标。

### Orchestrator

站点探索执行器必须把 `goal` 写入运行上下文，并传给产物生成逻辑。

## 前端改造范围

### 类型

`ExplorationRun`：

```ts
type ExplorationRun = {
  scope: string;
  forbidden_paths: string;
  goal: string;
  notes: string;
};
```

不得继续使用 `description` 表达探索目标。

### 表单

编辑/创建表单字段：

- “探索范围”绑定 `scope`
- “禁止路径”绑定 `forbidden_paths`
- “探索目标”绑定 `goal`
- “备注”绑定 `notes`

### 展示

探索计划页展示：

```text
探索目标    {run.goal}
备注        {run.notes || "-"}
```

如果 `goal` 为空，展示 `-`，但不从 `notes` 或其他字段推断。

## 产物契约

### run.yaml

必须写：

```yaml
run:
  scope: 探索全部文章页面
  forbidden_paths: ''
  goal: 每篇文章内容的超链接和按钮，不能跳转到登陆页面
  notes: ''
```

不得写探索任务级：

```yaml
description: ...
```

### summary.yaml

必须包含：

```yaml
goal: 每篇文章内容的超链接和按钮，不能跳转到登陆页面
goal_validation:
  status: pending | passed | partial | failed | skipped
  summary: ''
```

### 探索报告

报告摘要必须使用 `goal`：

```md
- 探索目标：每篇文章内容的超链接和按钮，不能跳转到登陆页面
```

不得从 `description` 读取目标。

## 目标验证产物

新增产物：

```text
checks/goal-validation.yaml
```

结构：

```yaml
goal: 每篇文章内容的超链接和按钮，不能跳转到登陆页面
status: passed
summary: 已验证 52 个页面，链接 120 个，按钮 388 个，失败 0 个，未验证 0 个。
stats:
  page_count: 52
  link_checked_count: 120
  button_checked_count: 388
  failed_count: 0
  unverified_count: 0
items:
  - page_id: page-001
    page_url: https://www.cybotstar.cn/document/manual/87
    element_type: link
    element_name: 快速开始
    action: inspect_href
    before_url: https://www.cybotstar.cn/document/manual/87
    after_url: https://www.cybotstar.cn/document/manual/82/
    result: passed
    reason: 未命中登录页、权限页或验证码页
```

### 状态含义

| 状态 | 含义 |
| --- | --- |
| `pending` | 尚未执行目标验证 |
| `passed` | 目标验证全部通过 |
| `partial` | 存在未验证项或弱证据，但未发现明确失败 |
| `failed` | 发现目标违反项 |
| `skipped` | 目标为空或暂不支持该目标类型 |

## 第一版目标验证规则

第一版只支持以下目标模板：

```text
每篇文章内容的超链接和按钮，不能跳转到登陆页面
```

可通过关键词识别：

- 包含 `每篇文章`
- 包含 `超链接` 或 `链接`
- 包含 `按钮`
- 包含 `不能跳转到登陆页面` 或 `不能跳转到登录页面`

### 登录页判定

点击或访问后的页面命中以下任一条件，判定失败：

- URL path/query 包含 `login`、`signin`、`sign-in`、`auth`
- 页面标题包含 `登录`、`登陆`、`Login`、`Sign in`
- 页面正文包含明显登录表单文案：`用户名`、`密码`、`验证码`、`登录`
- HTTP 状态或页面事实表达 `401`、`403`、`permission_denied`

### 链接验证

对文章正文范围内链接：

1. 记录 href。
2. 同域链接可通过访问目标 URL 验证。
3. 外链第一版不作为失败，记录为 `skipped` 或 `unverified`。
4. 命中登录页判定时，记录 `failed`。

### 按钮验证

对文章正文范围内按钮：

1. 过滤危险按钮，例如删除、提交、支付、确认、发布等。
2. 对普通按钮执行点击。
3. 点击后记录 `before_url`、`after_url`、页面标题和登录页判定结果。
4. 点击后需要恢复原页面，避免影响后续探索。
5. 名称为 `BUTTON` 或空名称时，不得静默算通过；应记录为 `unverified` 或 `partial`。

## 完成状态规则

探索任务状态必须同时考虑页面采集和目标验证：

| 页面采集 | 目标验证 | 任务状态 |
| --- | --- | --- |
| 完成 | `passed` | `completed` |
| 完成 | `partial` | `partial` |
| 完成 | `failed` | `blocked` 或 `partial`，由失败严重度决定 |
| 完成 | `pending` | `partial` |
| 完成 | `skipped` | `completed`，仅当 `goal` 为空 |
| 异常 | 任意 | `blocked` |

如果 `goal` 非空但没有 `goal-validation.yaml`，不得仅因为页面采集完成就标记目标已完成。

## 前端展示

探索概览新增“目标验证”区块：

```text
目标验证
目标：每篇文章内容的超链接和按钮，不能跳转到登陆页面
结果：部分完成
页面：52/52
链接：已验证 120，失败 0
按钮：已验证 300，未验证 88
风险：按钮名称不可识别，无法确认点击后是否跳登录
```

展示规则：

- `passed` 显示绿色通过。
- `partial` 显示黄色部分完成。
- `failed` 显示红色未通过。
- `pending` 显示待验证。
- 无 `goal` 时显示“未设置探索目标”。

## 报告展示

探索报告必须新增章节：

```md
## 目标验证结果

- 目标：...
- 结论：通过 / 部分通过 / 未通过 / 未验证
- 链接验证：...
- 按钮验证：...
- 失败项：...
- 未验证项：...
```

如果 `goal` 非空但目标验证未执行，报告必须明确写：

```text
目标验证未执行，当前 completed/partial 状态不能证明探索目标已达成。
```

## 验收标准

- 创建探索任务时，API 接收 `goal`，不接收 `description`。
- 更新探索任务时，API 更新 `goal`，不更新 `description`。
- 探索任务响应中包含 `goal` 和 `notes`，不包含探索任务级 `description`。
- 历史 `description` 数据迁移后出现在 `goal`。
- 前端“探索目标”输入框绑定 `goal`。
- `run.yaml`、`summary.yaml` 和报告均使用 `goal`。
- 当 `goal` 非空但没有目标验证产物时，任务不能被解释为目标已达成。
- 当前示例目标能生成 `checks/goal-validation.yaml`。
- 按钮名称为空或 `BUTTON` 时，不能静默计为通过。
- 报告能区分页面采集完成和目标验证通过。

## 测试要求

### 后端

新增或更新测试：

- 创建任务保存 `goal` 和 `notes`。
- 更新任务保存 `goal` 和 `notes`。
- 响应不包含探索任务级 `description`。
- 迁移旧 `description` 到 `goal`。
- `run.yaml` 写入 `goal`。
- 报告读取 `goal`。
- 无目标验证产物时，`goal_validation.status` 为 `pending`。
- 目标验证失败时，任务不应为普通 `completed`。

### 前端

新增或更新测试/检查：

- 表单输入“探索目标”后请求 payload 使用 `goal`。
- 详情页显示 `run.goal`。
- 不再引用 `run.description`。
- 目标验证区块能展示 `pending/passed/partial/failed`。

## 迁移注意事项

- 全仓搜索 `description` 时，不要误删其他业务对象的描述字段。
- 本规范只处理探索任务级字段。
- 若已有前端缓存旧字段，需要清空或容错。
- 如果数据库中已有旧任务，迁移必须保证旧任务“探索目标”不丢失。

